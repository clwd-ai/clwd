"""Tests for SSH operations."""

import pytest
import subprocess
from unittest.mock import Mock, patch, call
from pathlib import Path

from clwd.utils.ssh import SSHOperations, SSHError, SSHSessionManager


class TestSSHOperations:
    """Test SSH operations functionality."""
    
    def test_init_with_defaults(self):
        """Test SSH operations initialization with defaults."""
        with patch.object(SSHOperations, '_find_ssh_key', return_value='/path/to/key'):
            ssh_ops = SSHOperations("192.168.1.1")
            
            assert ssh_ops.ip == "192.168.1.1"
            assert ssh_ops.user == "root"
            assert ssh_ops.ssh_key_path == "/path/to/key"
    
    def test_init_with_custom_params(self):
        """Test SSH operations initialization with custom parameters."""
        ssh_ops = SSHOperations("10.0.0.1", user="ubuntu", ssh_key_path="/custom/key")
        
        assert ssh_ops.ip == "10.0.0.1"
        assert ssh_ops.user == "ubuntu"
        assert ssh_ops.ssh_key_path == "/custom/key"
    
    def test_find_ssh_key_found(self):
        """Test finding SSH key when it exists."""
        ssh_ops = SSHOperations("192.168.1.1", ssh_key_path="/explicit/key")
        
        with patch('pathlib.Path.expanduser') as mock_expand, \
             patch('pathlib.Path.exists', return_value=True):
            
            mock_expand.return_value = Path("/home/user/.ssh/id_ed25519")
            
            key_path = ssh_ops._find_ssh_key()
            assert key_path == "/home/user/.ssh/id_ed25519"
    
    def test_find_ssh_key_not_found(self):
        """Test finding SSH key when none exist."""
        ssh_ops = SSHOperations("192.168.1.1", ssh_key_path="/explicit/key")
        
        with patch('pathlib.Path.exists', return_value=False):
            key_path = ssh_ops._find_ssh_key()
            assert key_path is None
    
    def test_build_ssh_command_basic(self):
        """Test building basic SSH command."""
        ssh_ops = SSHOperations("192.168.1.1", ssh_key_path="/path/to/key")
        
        cmd = ssh_ops._build_ssh_command()
        
        expected = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=60",
            "-o", "ServerAliveCountMax=3",
            "-i", "/path/to/key",
            "root@192.168.1.1"
        ]
        
        assert cmd == expected
    
    def test_build_ssh_command_with_tty(self):
        """Test building SSH command with TTY."""
        ssh_ops = SSHOperations("192.168.1.1", ssh_key_path=None)
        
        cmd = ssh_ops._build_ssh_command(tty=True)
        
        assert "-t" in cmd
        assert "root@192.168.1.1" in cmd
        assert "-i" not in cmd  # No key specified
    
    def test_build_ssh_command_with_command(self):
        """Test building SSH command with remote command."""
        ssh_ops = SSHOperations("192.168.1.1")
        
        cmd = ssh_ops._build_ssh_command("echo hello")
        
        assert cmd[-1] == "echo hello"
        assert cmd[-2] == "root@192.168.1.1"
    
    @patch('subprocess.run')
    def test_test_connection_success(self, mock_run):
        """Test successful connection test."""
        mock_run.return_value = Mock(returncode=0)
        
        ssh_ops = SSHOperations("192.168.1.1")
        result = ssh_ops.test_connection()
        
        assert result is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_test_connection_failure(self, mock_run):
        """Test failed connection test."""
        mock_run.return_value = Mock(returncode=1)
        
        ssh_ops = SSHOperations("192.168.1.1")
        result = ssh_ops.test_connection()
        
        assert result is False
    
    @patch('subprocess.run')
    def test_test_connection_timeout(self, mock_run):
        """Test connection test with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("ssh", 10)
        
        ssh_ops = SSHOperations("192.168.1.1")
        result = ssh_ops.test_connection()
        
        assert result is False
    
    @patch('subprocess.run')
    def test_execute_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Hello World",
            stderr=""
        )
        
        ssh_ops = SSHOperations("192.168.1.1")
        return_code, stdout, stderr = ssh_ops.execute_command("echo 'Hello World'")
        
        assert return_code == 0
        assert stdout == "Hello World"
        assert stderr == ""
    
    @patch('subprocess.run')
    def test_execute_command_failure(self, mock_run):
        """Test failed command execution."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Command failed"
        )
        
        ssh_ops = SSHOperations("192.168.1.1")
        return_code, stdout, stderr = ssh_ops.execute_command("false")
        
        assert return_code == 1
        assert stdout == ""
        assert stderr == "Command failed"
    
    @patch('subprocess.run')
    def test_execute_command_timeout(self, mock_run):
        """Test command execution timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("ssh", 60)
        
        ssh_ops = SSHOperations("192.168.1.1")
        
        with pytest.raises(SSHError, match="Command timed out"):
            ssh_ops.execute_command("sleep 120", timeout=60)
    
    @patch('subprocess.run')
    def test_execute_interactive_success(self, mock_run):
        """Test successful interactive session."""
        mock_run.return_value = Mock(returncode=0)
        
        ssh_ops = SSHOperations("192.168.1.1")
        exit_code = ssh_ops.execute_interactive()
        
        assert exit_code == 0
        # Verify TTY flag was used
        args = mock_run.call_args[0][0]
        assert "-t" in args
    
    @patch('subprocess.run')
    def test_execute_interactive_keyboard_interrupt(self, mock_run):
        """Test interactive session with keyboard interrupt."""
        mock_run.side_effect = KeyboardInterrupt()
        
        ssh_ops = SSHOperations("192.168.1.1")
        exit_code = ssh_ops.execute_interactive()
        
        assert exit_code == 130
    
    @patch('subprocess.run')
    def test_copy_file_success(self, mock_run):
        """Test successful file copy."""
        mock_run.return_value = Mock(returncode=0)
        
        ssh_ops = SSHOperations("192.168.1.1", ssh_key_path="/path/to/key")
        result = ssh_ops.copy_file_to_remote("/local/file", "/remote/file")
        
        assert result is True
        
        # Verify SCP command was called correctly
        args = mock_run.call_args[0][0]
        assert args[0] == "scp"
        assert "/local/file" in args
        assert "root@192.168.1.1:/remote/file" in args
        assert "-i" in args
        assert "/path/to/key" in args
    
    @patch('subprocess.run')
    def test_copy_file_failure(self, mock_run):
        """Test failed file copy."""
        mock_run.return_value = Mock(returncode=1)
        
        ssh_ops = SSHOperations("192.168.1.1")
        result = ssh_ops.copy_file_to_remote("/local/file", "/remote/file")
        
        assert result is False
    
    def test_get_instance_info_no_connection(self):
        """Test getting instance info when connection fails."""
        ssh_ops = SSHOperations("192.168.1.1")
        
        with patch.object(ssh_ops, 'test_connection', return_value=False):
            info = ssh_ops.get_instance_info()
            
            assert info["ip"] == "192.168.1.1"
            assert info["user"] == "root"
            assert info["connection_available"] is False
            assert info["setup_complete"] is False
    
    def test_get_instance_info_with_connection(self):
        """Test getting instance info with successful connection."""
        ssh_ops = SSHOperations("192.168.1.1")
        
        with patch.object(ssh_ops, 'test_connection', return_value=True), \
             patch.object(ssh_ops, 'execute_command') as mock_exec:
            
            # Mock setup complete check
            mock_exec.side_effect = [
                (0, "", ""),  # setup complete
                (0, "Linux host 5.4.0\nload average: 0.1", "")  # system info
            ]
            
            info = ssh_ops.get_instance_info()
            
            assert info["connection_available"] is True
            assert info["setup_complete"] is True
            assert "kernel" in info["system_info"]
            assert "uptime" in info["system_info"]


class TestSSHSessionManager:
    """Test SSH session manager."""
    
    def test_get_session_creates_new(self):
        """Test getting session creates new instance."""
        manager = SSHSessionManager()
        
        session = manager.get_session("192.168.1.1")
        
        assert isinstance(session, SSHOperations)
        assert session.ip == "192.168.1.1"
        assert session.user == "root"
    
    def test_get_session_reuses_existing(self):
        """Test getting session reuses existing instance."""
        manager = SSHSessionManager()
        
        session1 = manager.get_session("192.168.1.1")
        session2 = manager.get_session("192.168.1.1")
        
        assert session1 is session2
    
    def test_get_session_different_user(self):
        """Test getting session with different user creates new instance."""
        manager = SSHSessionManager()
        
        session1 = manager.get_session("192.168.1.1", "root")
        session2 = manager.get_session("192.168.1.1", "ubuntu")
        
        assert session1 is not session2
        assert session1.user == "root"
        assert session2.user == "ubuntu"
    
    def test_remove_session(self):
        """Test removing session from cache."""
        manager = SSHSessionManager()
        
        session1 = manager.get_session("192.168.1.1")
        manager.remove_session("192.168.1.1")
        session2 = manager.get_session("192.168.1.1")
        
        assert session1 is not session2
    
    def test_clear_all_sessions(self):
        """Test clearing all cached sessions."""
        manager = SSHSessionManager()
        
        session1 = manager.get_session("192.168.1.1")
        session2 = manager.get_session("192.168.1.2")
        
        manager.clear_all_sessions()
        
        session3 = manager.get_session("192.168.1.1")
        session4 = manager.get_session("192.168.1.2")
        
        assert session1 is not session3
        assert session2 is not session4