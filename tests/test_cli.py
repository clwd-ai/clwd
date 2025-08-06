"""Tests for CLI interface."""

import pytest
from click.testing import CliRunner

from clwd.cli.main import cli


class TestCLI:
    """Test the main CLI interface."""
    
    def test_cli_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "Clwd - Fast cloud deployment CLI for Claude Code" in result.output
        assert "init" in result.output
        assert "open" in result.output
        assert "exec" in result.output
        assert "status" in result.output
        assert "destroy" in result.output
    
    def test_cli_version(self):
        """Test CLI version output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        
        assert result.exit_code == 0
        assert "1.0.0" in result.output
    
    def test_init_command_help(self):
        """Test init command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])
        
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--provider" in result.output
        assert "--size" in result.output
        assert "--hardening" in result.output
        assert "--premium" in result.output
    
    def test_init_command_missing_name(self):
        """Test init command fails without name."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init"])
        
        assert result.exit_code != 0
        assert "Missing option '--name'" in result.output
    
    def test_init_command_with_premium_flag(self):
        """Test init command with premium flag shows warning."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--name", "test-project", "--premium"])
        
        assert "Premium service is not yet available" in result.output
        assert "test-project" in result.output
    
    def test_open_command_help(self):
        """Test open command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["open", "--help"])
        
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "interactive SSH session" in result.output
    
    def test_exec_command_help(self):
        """Test exec command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["exec", "--help"])
        
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--timeout" in result.output
        assert "COMMAND" in result.output
    
    def test_status_command_not_implemented(self):
        """Test status command shows not implemented message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--name", "test"])
        
        assert "not yet implemented" in result.output
    
    def test_destroy_command_with_force(self):
        """Test destroy command with force flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["destroy", "--name", "test", "--force"])
        
        assert "Destroying project: test" in result.output
        assert "not yet implemented" in result.output
    
    def test_destroy_command_without_force_cancelled(self):
        """Test destroy command without force gets cancelled."""
        runner = CliRunner()
        result = runner.invoke(cli, ["destroy", "--name", "test"], input="n\n")
        
        assert "Operation cancelled" in result.output
    
    def test_config_list_command(self):
        """Test config list command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "list"])
        
        assert result.exit_code == 0
        assert "Configured projects" in result.output
        assert "No projects configured yet" in result.output
    
    def test_config_show_command(self):
        """Test config show command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show", "--name", "test"])
        
        assert "Configuration for project: test" in result.output
        assert "not yet implemented" in result.output
    
    def test_premium_status_command(self):
        """Test premium status command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["premium", "status"])
        
        assert result.exit_code == 0
        assert "Premium service status" in result.output
        assert "not yet available" in result.output
    
    def test_premium_login_command(self):
        """Test premium login command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["premium", "login"])
        
        assert result.exit_code == 0
        assert "Premium service authentication" in result.output
        assert "not yet available" in result.output
    
    def test_debug_flag(self):
        """Test debug flag is passed through context."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--debug", "config", "list"])
        
        assert result.exit_code == 0
        assert "Debug mode enabled" in result.output