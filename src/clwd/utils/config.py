"""Configuration management for Clwd projects and settings."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from ..providers import Instance


class ConfigError(Exception):
    """Base exception for configuration-related errors."""
    pass


class ProjectNotFoundError(ConfigError):
    """Raised when a requested project is not found."""
    pass


class ProjectExistsError(ConfigError):
    """Raised when trying to create a project that already exists."""
    pass


class Config:
    """Configuration management for Clwd projects and global settings.
    
    Manages project state in ~/.clwd/projects.json and provides methods
    for CRUD operations on project configurations.
    """
    
    DEFAULT_CONFIG_DIR = "~/.clwd"
    PROJECTS_FILE = "projects.json"
    CONFIG_FILE = "config.json"
    BACKUP_SUFFIX = ".backup"
    
    def __init__(self, config_dir: Optional[str] = None) -> None:
        """Initialize configuration manager.
        
        Args:
            config_dir: Custom configuration directory. Defaults to ~/.clwd
        """
        self.config_dir = Path(config_dir or os.path.expanduser(self.DEFAULT_CONFIG_DIR))
        self.projects_file = self.config_dir / self.PROJECTS_FILE
        self.config_file = self.config_dir / self.CONFIG_FILE
        
        self._ensure_config_dir()
    
    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists with proper permissions."""
        try:
            self.config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as e:
            raise ConfigError(f"Failed to create config directory {self.config_dir}: {e}")
    
    def _load_json_file(self, file_path: Path, default: Any = None) -> Any:
        """Load JSON file with error handling.
        
        Args:
            file_path: Path to JSON file
            default: Default value if file doesn't exist
            
        Returns:
            Parsed JSON data or default value
            
        Raises:
            ConfigError: If file exists but cannot be parsed
        """
        if not file_path.exists():
            return default if default is not None else {}
        
        try:
            content = file_path.read_text()
            return json.loads(content)
        except (OSError, json.JSONDecodeError) as e:
            raise ConfigError(f"Failed to load {file_path}: {e}")
    
    def _save_json_file(self, file_path: Path, data: Any, backup: bool = True) -> None:
        """Save data to JSON file with optional backup.
        
        Args:
            file_path: Path to JSON file
            data: Data to save
            backup: Whether to create backup of existing file
            
        Raises:
            ConfigError: If save operation fails
        """
        try:
            # Create backup if requested and file exists
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + self.BACKUP_SUFFIX)
                shutil.copy2(file_path, backup_path)
            
            # Write to temporary file first for atomic operation
            temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
            
            with temp_path.open('w') as f:
                json.dump(data, f, indent=2, sort_keys=True)
            
            # Atomic move to final location
            temp_path.replace(file_path)
            
        except OSError as e:
            raise ConfigError(f"Failed to save {file_path}: {e}")
    
    def load_projects(self) -> Dict[str, Dict[str, Any]]:
        """Load all projects from state file.
        
        Returns:
            Dictionary mapping project names to project data
            
        Raises:
            ConfigError: If projects file cannot be loaded
        """
        return self._load_json_file(self.projects_file, {})
    
    def save_projects(self, projects: Dict[str, Dict[str, Any]]) -> None:
        """Save projects to state file.
        
        Args:
            projects: Dictionary mapping project names to project data
            
        Raises:
            ConfigError: If save operation fails
        """
        self._save_json_file(self.projects_file, projects)
    
    def add_project(self, name: str, instance: Instance) -> None:
        """Add a new project to configuration.
        
        Args:
            name: Project name (must be unique)
            instance: Instance object with project details
            
        Raises:
            ProjectExistsError: If project already exists
            ConfigError: If save operation fails
        """
        if not name or not name.strip():
            raise ValueError("Project name cannot be empty")
        
        name = name.strip()
        projects = self.load_projects()
        
        if name in projects:
            raise ProjectExistsError(f"Project '{name}' already exists")
        
        # Convert Instance to dict and add metadata
        project_data = asdict(instance)
        project_data.update({
            "project_name": name,
            "added_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat()
        })
        
        projects[name] = project_data
        self.save_projects(projects)
    
    def get_project(self, name: str) -> Optional[Dict[str, Any]]:
        """Get project configuration by name.
        
        Args:
            name: Project name
            
        Returns:
            Project data dictionary or None if not found
        """
        if not name:
            return None
        
        projects = self.load_projects()
        return projects.get(name.strip())
    
    def get_project_instance(self, name: str) -> Optional[Instance]:
        """Get project as Instance object.
        
        Args:
            name: Project name
            
        Returns:
            Instance object or None if not found
        """
        project_data = self.get_project(name)
        if not project_data:
            return None
        
        # Extract Instance fields and create Instance object
        instance_fields = {
            "id": project_data.get("id"),
            "name": project_data.get("name"),
            "ip": project_data.get("ip"),
            "provider": project_data.get("provider"),
            "status": project_data.get("status"),
            "created_at": project_data.get("created_at"),
            "metadata": project_data.get("metadata", {})
        }
        
        return Instance(**instance_fields)
    
    def update_project(self, name: str, updates: Dict[str, Any]) -> None:
        """Update existing project configuration.
        
        Args:
            name: Project name
            updates: Dictionary of updates to apply
            
        Raises:
            ProjectNotFoundError: If project doesn't exist
            ConfigError: If save operation fails
        """
        if not name:
            raise ValueError("Project name cannot be empty")
        
        name = name.strip()
        projects = self.load_projects()
        
        if name not in projects:
            raise ProjectNotFoundError(f"Project '{name}' not found")
        
        # Update project data
        projects[name].update(updates)
        projects[name]["last_accessed"] = datetime.now().isoformat()
        
        self.save_projects(projects)
    
    def update_project_status(self, name: str, status: str) -> None:
        """Update project status.
        
        Args:
            name: Project name
            status: New status value
            
        Raises:
            ProjectNotFoundError: If project doesn't exist
        """
        self.update_project(name, {"status": status})
    
    def remove_project(self, name: str) -> None:
        """Remove project from configuration.
        
        Args:
            name: Project name
            
        Raises:
            ProjectNotFoundError: If project doesn't exist
            ConfigError: If save operation fails
        """
        if not name:
            raise ValueError("Project name cannot be empty")
        
        name = name.strip()
        projects = self.load_projects()
        
        if name not in projects:
            raise ProjectNotFoundError(f"Project '{name}' not found")
        
        del projects[name]
        self.save_projects(projects)
    
    def list_projects(self) -> List[str]:
        """Get list of all project names.
        
        Returns:
            List of project names sorted alphabetically
        """
        projects = self.load_projects()
        return sorted(projects.keys())
    
    def list_project_details(self) -> List[Dict[str, Any]]:
        """Get list of all projects with summary details.
        
        Returns:
            List of project summaries containing name, status, IP, provider
        """
        projects = self.load_projects()
        details = []
        
        for name, data in projects.items():
            details.append({
                "project_name": name,
                "status": data.get("status", "unknown"),
                "ip": data.get("ip", ""),
                "provider": data.get("provider", ""),
                "created_at": data.get("created_at", ""),
                "last_accessed": data.get("last_accessed", "")
            })
        
        # Sort by last accessed (most recent first)
        details.sort(key=lambda x: x.get("last_accessed", ""), reverse=True)
        return details
    
    def project_exists(self, name: str) -> bool:
        """Check if project exists.
        
        Args:
            name: Project name
            
        Returns:
            True if project exists, False otherwise
        """
        return self.get_project(name) is not None
    
    def load_global_config(self) -> Dict[str, Any]:
        """Load global configuration settings.
        
        Returns:
            Global configuration dictionary
        """
        return self._load_json_file(self.config_file, {})
    
    def save_global_config(self, config: Dict[str, Any]) -> None:
        """Save global configuration settings.
        
        Args:
            config: Global configuration dictionary
        """
        self._save_json_file(self.config_file, config)
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a global configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        config = self.load_global_config()
        return config.get(key, default)
    
    def set_config_value(self, key: str, value: Any) -> None:
        """Set a global configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        config = self.load_global_config()
        config[key] = value
        self.save_global_config(config)
    
    def cleanup_backups(self, max_backups: int = 5) -> None:
        """Clean up old backup files.
        
        Args:
            max_backups: Maximum number of backup files to keep
        """
        backup_pattern = f"*{self.BACKUP_SUFFIX}"
        backup_files = list(self.config_dir.glob(backup_pattern))
        
        if len(backup_files) <= max_backups:
            return
        
        # Sort by modification time (oldest first)
        backup_files.sort(key=lambda f: f.stat().st_mtime)
        
        # Remove oldest backups
        for backup_file in backup_files[:-max_backups]:
            try:
                backup_file.unlink()
            except OSError:
                pass  # Ignore errors when cleaning up
    
    def export_projects(self, output_path: str) -> None:
        """Export projects to external file.
        
        Args:
            output_path: Path to export file
            
        Raises:
            ConfigError: If export fails
        """
        projects = self.load_projects()
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "clwd_version": "1.0.0",  # TODO: Get from package
            "projects": projects
        }
        
        try:
            output_file = Path(output_path)
            with output_file.open('w') as f:
                json.dump(export_data, f, indent=2, sort_keys=True)
        except OSError as e:
            raise ConfigError(f"Failed to export projects to {output_path}: {e}")
    
    def import_projects(self, import_path: str, merge: bool = False) -> None:
        """Import projects from external file.
        
        Args:
            import_path: Path to import file
            merge: If True, merge with existing projects. If False, replace all.
            
        Raises:
            ConfigError: If import fails
        """
        try:
            import_file = Path(import_path)
            with import_file.open('r') as f:
                import_data = json.load(f)
            
            imported_projects = import_data.get("projects", {})
            
            if merge:
                existing_projects = self.load_projects()
                existing_projects.update(imported_projects)
                self.save_projects(existing_projects)
            else:
                self.save_projects(imported_projects)
                
        except (OSError, json.JSONDecodeError, KeyError) as e:
            raise ConfigError(f"Failed to import projects from {import_path}: {e}")
    
    def validate_config(self) -> List[str]:
        """Validate configuration files and return any issues found.
        
        Returns:
            List of validation issues (empty if all valid)
        """
        issues = []
        
        # Check config directory permissions
        if not os.access(self.config_dir, os.R_OK | os.W_OK):
            issues.append(f"Config directory not accessible: {self.config_dir}")
        
        # Validate projects file
        try:
            projects = self.load_projects()
            for name, data in projects.items():
                if not isinstance(data, dict):
                    issues.append(f"Invalid project data for '{name}': not a dictionary")
                    continue
                
                required_fields = ["id", "name", "ip", "provider", "status"]
                for field in required_fields:
                    if field not in data:
                        issues.append(f"Project '{name}' missing required field: {field}")
                        
        except ConfigError as e:
            issues.append(f"Projects file validation failed: {e}")
        
        # Validate global config
        try:
            self.load_global_config()
        except ConfigError as e:
            issues.append(f"Global config validation failed: {e}")
        
        return issues