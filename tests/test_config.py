"""Tests for configuration management."""

import json
import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open

from clwd.providers import Instance
from clwd.utils.config import (
    Config,
    ConfigError,
    ProjectNotFoundError,
    ProjectExistsError
)


class TestConfig:
    """Test the Config class."""
    
    def test_init_default_config_dir(self):
        """Test initialization with default config directory."""
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            config = Config()
            
            expected_path = Path("~/.clwd").expanduser()
            assert config.config_dir == expected_path
            mock_mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)
    
    def test_init_custom_config_dir(self):
        """Test initialization with custom config directory."""
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            config = Config("/custom/path")
            
            assert config.config_dir == Path("/custom/path")
            mock_mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)
    
    def test_init_mkdir_failure(self):
        """Test initialization fails when mkdir fails."""
        with patch('pathlib.Path.mkdir', side_effect=OSError("Permission denied")):
            with pytest.raises(ConfigError, match="Failed to create config directory"):
                Config()
    
    def test_load_projects_empty(self):
        """Test loading projects when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            projects = config.load_projects()
            
            assert projects == {}
    
    def test_load_projects_with_data(self):
        """Test loading projects with existing data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            # Create test data
            test_projects = {
                "test-project": {
                    "id": "123",
                    "name": "test-instance",
                    "ip": "192.168.1.1",
                    "provider": "hetzner",
                    "status": "running"
                }
            }
            
            # Write test data
            config.projects_file.write_text(json.dumps(test_projects))
            
            projects = config.load_projects()
            assert projects == test_projects
    
    def test_load_projects_invalid_json(self):
        """Test loading projects with invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            # Write invalid JSON
            config.projects_file.write_text("{ invalid json")
            
            with pytest.raises(ConfigError, match="Failed to load"):
                config.load_projects()
    
    def test_save_projects(self):
        """Test saving projects to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            test_projects = {
                "project1": {"id": "123", "name": "test"}
            }
            
            config.save_projects(test_projects)
            
            # Verify file was created with correct content
            assert config.projects_file.exists()
            saved_data = json.loads(config.projects_file.read_text())
            assert saved_data == test_projects
    
    def test_save_projects_creates_backup(self):
        """Test that saving creates backup of existing file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            # Create initial file
            initial_data = {"old": "data"}
            config.projects_file.write_text(json.dumps(initial_data))
            
            # Save new data
            new_data = {"new": "data"}
            config.save_projects(new_data)
            
            # Check backup was created
            backup_file = config.projects_file.with_suffix(".json.backup")
            assert backup_file.exists()
            
            backup_data = json.loads(backup_file.read_text())
            assert backup_data == initial_data
    
    def test_add_project(self):
        """Test adding a new project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123",
                name="test-instance",
                ip="192.168.1.1",
                provider="hetzner",
                status="running",
                created_at="2024-01-01T00:00:00Z",
                metadata={"size": "small"}
            )
            
            config.add_project("test-project", instance)
            
            # Verify project was added
            projects = config.load_projects()
            assert "test-project" in projects
            
            project_data = projects["test-project"]
            assert project_data["id"] == "123"
            assert project_data["name"] == "test-instance"
            assert project_data["project_name"] == "test-project"
            assert "added_at" in project_data
            assert "last_accessed" in project_data
    
    def test_add_project_empty_name(self):
        """Test adding project with empty name fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            
            with pytest.raises(ValueError, match="Project name cannot be empty"):
                config.add_project("", instance)
    
    def test_add_project_already_exists(self):
        """Test adding project that already exists fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            
            # Add project first time
            config.add_project("test-project", instance)
            
            # Try to add again
            with pytest.raises(ProjectExistsError, match="already exists"):
                config.add_project("test-project", instance)
    
    def test_get_project(self):
        """Test getting project by name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            
            config.add_project("test-project", instance)
            
            project_data = config.get_project("test-project")
            assert project_data is not None
            assert project_data["id"] == "123"
    
    def test_get_project_not_found(self):
        """Test getting non-existent project returns None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            project_data = config.get_project("nonexistent")
            assert project_data is None
    
    def test_get_project_instance(self):
        """Test getting project as Instance object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            original_instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={"size": "small"}
            )
            
            config.add_project("test-project", original_instance)
            
            retrieved_instance = config.get_project_instance("test-project")
            assert retrieved_instance is not None
            assert isinstance(retrieved_instance, Instance)
            assert retrieved_instance.id == "123"
            assert retrieved_instance.name == "test"
            assert retrieved_instance.metadata == {"size": "small"}
    
    def test_get_project_instance_not_found(self):
        """Test getting non-existent project as Instance returns None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = config.get_project_instance("nonexistent")
            assert instance is None
    
    def test_update_project(self):
        """Test updating existing project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="creating", created_at="2024-01-01", metadata={}
            )
            
            config.add_project("test-project", instance)
            
            # Update status
            config.update_project("test-project", {"status": "running"})
            
            project_data = config.get_project("test-project")
            assert project_data["status"] == "running"
            assert "last_accessed" in project_data
    
    def test_update_project_not_found(self):
        """Test updating non-existent project fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            with pytest.raises(ProjectNotFoundError, match="not found"):
                config.update_project("nonexistent", {"status": "running"})
    
    def test_update_project_status(self):
        """Test updating project status specifically."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="creating", created_at="2024-01-01", metadata={}
            )
            
            config.add_project("test-project", instance)
            config.update_project_status("test-project", "running")
            
            project_data = config.get_project("test-project")
            assert project_data["status"] == "running"
    
    def test_remove_project(self):
        """Test removing project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            
            config.add_project("test-project", instance)
            assert config.get_project("test-project") is not None
            
            config.remove_project("test-project")
            assert config.get_project("test-project") is None
    
    def test_remove_project_not_found(self):
        """Test removing non-existent project fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            with pytest.raises(ProjectNotFoundError, match="not found"):
                config.remove_project("nonexistent")
    
    def test_list_projects(self):
        """Test listing all project names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            
            config.add_project("project-b", instance)
            config.add_project("project-a", instance)
            config.add_project("project-c", instance)
            
            projects = config.list_projects()
            assert projects == ["project-a", "project-b", "project-c"]  # Sorted
    
    def test_list_project_details(self):
        """Test listing project details."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="hetzner",
                status="running", created_at="2024-01-01", metadata={}
            )
            
            config.add_project("test-project", instance)
            
            details = config.list_project_details()
            assert len(details) == 1
            
            detail = details[0]
            assert detail["project_name"] == "test-project"
            assert detail["status"] == "running"
            assert detail["ip"] == "1.1.1.1"
            assert detail["provider"] == "hetzner"
    
    def test_project_exists(self):
        """Test checking if project exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            
            assert config.project_exists("test-project") is False
            
            config.add_project("test-project", instance)
            assert config.project_exists("test-project") is True
    
    def test_global_config_operations(self):
        """Test global configuration operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            # Initially empty
            global_config = config.load_global_config()
            assert global_config == {}
            
            # Set some values
            test_config = {
                "default_provider": "hetzner",
                "default_size": "medium",
                "auto_hardening": True
            }
            config.save_global_config(test_config)
            
            # Load back
            loaded_config = config.load_global_config()
            assert loaded_config == test_config
    
    def test_config_value_operations(self):
        """Test individual config value get/set operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            # Get non-existent value with default
            value = config.get_config_value("nonexistent", "default")
            assert value == "default"
            
            # Set value
            config.set_config_value("test_key", "test_value")
            
            # Get value back
            value = config.get_config_value("test_key")
            assert value == "test_value"
    
    def test_export_projects(self):
        """Test exporting projects to external file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            
            config.add_project("test-project", instance)
            
            export_file = Path(temp_dir) / "export.json"
            config.export_projects(str(export_file))
            
            # Verify export file
            assert export_file.exists()
            export_data = json.loads(export_file.read_text())
            
            assert "exported_at" in export_data
            assert "projects" in export_data
            assert "test-project" in export_data["projects"]
    
    def test_import_projects_replace(self):
        """Test importing projects with replace mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            # Add existing project
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            config.add_project("existing-project", instance)
            
            # Create import data
            import_data = {
                "exported_at": "2024-01-01T00:00:00Z",
                "projects": {
                    "imported-project": {
                        "id": "456", "name": "imported", "ip": "2.2.2.2",
                        "provider": "test", "status": "running", 
                        "created_at": "2024-01-01", "metadata": {}
                    }
                }
            }
            
            import_file = Path(temp_dir) / "import.json"
            import_file.write_text(json.dumps(import_data))
            
            # Import with replace (default)
            config.import_projects(str(import_file), merge=False)
            
            # Verify existing project was replaced
            projects = config.list_projects()
            assert "existing-project" not in projects
            assert "imported-project" in projects
    
    def test_import_projects_merge(self):
        """Test importing projects with merge mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            # Add existing project
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            config.add_project("existing-project", instance)
            
            # Create import data
            import_data = {
                "exported_at": "2024-01-01T00:00:00Z",
                "projects": {
                    "imported-project": {
                        "id": "456", "name": "imported", "ip": "2.2.2.2",
                        "provider": "test", "status": "running",
                        "created_at": "2024-01-01", "metadata": {}
                    }
                }
            }
            
            import_file = Path(temp_dir) / "import.json"
            import_file.write_text(json.dumps(import_data))
            
            # Import with merge
            config.import_projects(str(import_file), merge=True)
            
            # Verify both projects exist
            projects = config.list_projects()
            assert "existing-project" in projects
            assert "imported-project" in projects
    
    def test_validate_config_valid(self):
        """Test config validation with valid configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            instance = Instance(
                id="123", name="test", ip="1.1.1.1", provider="test",
                status="running", created_at="2024-01-01", metadata={}
            )
            config.add_project("test-project", instance)
            
            issues = config.validate_config()
            assert issues == []
    
    def test_validate_config_missing_fields(self):
        """Test config validation with missing required fields."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(temp_dir)
            
            # Create invalid project data (missing required fields)
            invalid_projects = {
                "invalid-project": {
                    "id": "123"
                    # Missing name, ip, provider, status
                }
            }
            config.save_projects(invalid_projects)
            
            issues = config.validate_config()
            assert len(issues) > 0
            assert any("missing required field" in issue for issue in issues)