"""SSH operations for connecting to and managing remote instances."""

import asyncio
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from ..providers import ProviderError


class SSHError(Exception):
    """SSH operation failed."""
    pass


class SSHOperations:
    """Handle SSH connections and operations for cloud instances."""
    
    def __init__(self, ip: str, user: str = "root", ssh_key_path: Optional[str] = None):
        """Initialize SSH operations for an instance.
        
        Args:
            ip: Instance IP address
            user: SSH user (default: root)
            ssh_key_path: Path to SSH private key (auto-detected if None)
        """
        self.ip = ip
        self.user = user
        self.ssh_key_path = ssh_key_path or self._find_ssh_key()
        
    def _find_ssh_key(self) -> Optional[str]:
        """Find the SSH private key to use.
        
        Returns:
            Path to SSH private key or None if not found
        """
        key_paths = [
            "~/.ssh/id_ed25519",
            "~/.ssh/id_rsa", 
            "~/.ssh/id_ecdsa"
        ]
        
        for key_path in key_paths:
            expanded_path = Path(key_path).expanduser()
            if expanded_path.exists():
                return str(expanded_path)
        
        return None
    
    def _build_ssh_command(self, command: Optional[str] = None, tty: bool = False) -> list[str]:
        """Build SSH command with proper options.
        
        Args:
            command: Command to execute (None for interactive session)
            tty: Whether to allocate a TTY
            
        Returns:
            SSH command as list of strings
        """
        ssh_cmd = ["ssh"]
        
        # SSH options for automation and security
        ssh_cmd.extend([
            "-o", "StrictHostKeyChecking=no",  # Accept new host keys automatically
            "-o", "UserKnownHostsFile=/dev/null",  # Don't save host keys
            "-o", "LogLevel=ERROR",  # Reduce SSH output noise
            "-o", "ConnectTimeout=10",  # Connection timeout
            "-o", "ServerAliveInterval=60",  # Keep connection alive
            "-o", "ServerAliveCountMax=3",  # Max failed keepalives
        ])
        
        # Add SSH key if available
        if self.ssh_key_path:
            ssh_cmd.extend(["-i", self.ssh_key_path])
        
        # Add TTY allocation if requested
        if tty:
            ssh_cmd.append("-t")
        
        # Add user@host
        ssh_cmd.append(f"{self.user}@{self.ip}")
        
        # Add command if provided
        if command:
            ssh_cmd.append(command)
            
        return ssh_cmd
    
    def test_connection(self, timeout: int = 10) -> bool:
        """Test if SSH connection is working.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            cmd = self._build_ssh_command("echo 'SSH connection test'")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return False
    
    def execute_command(
        self, 
        command: str, 
        timeout: int = 120,
        capture_output: bool = True
    ) -> Tuple[int, str, str]:
        """Execute a command on the remote instance.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            Tuple of (return_code, stdout, stderr)
            
        Raises:
            SSHError: If SSH execution fails
        """
        try:
            # Build SSH command with the raw command (SSH handles the escaping)
            ssh_cmd = self._build_ssh_command(command)
            
            result = subprocess.run(
                ssh_cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout
            )
            
            return result.returncode, result.stdout or "", result.stderr or ""
            
        except subprocess.TimeoutExpired:
            raise SSHError(f"Command timed out after {timeout} seconds")
        except subprocess.SubprocessError as e:
            raise SSHError(f"SSH command execution failed: {e}")
    
    
    def execute_interactive(self, command: Optional[str] = None) -> int:
        """Start an interactive SSH session.
        
        Args:
            command: Optional command to run in the interactive session
        
        Returns:
            Exit code of the SSH session
            
        Raises:
            SSHError: If SSH session fails to start
        """
        try:
            ssh_cmd = self._build_ssh_command(command, tty=True)
            
            # Run SSH with direct stdio for interactive session
            result = subprocess.run(ssh_cmd)
            return result.returncode
            
        except subprocess.SubprocessError as e:
            raise SSHError(f"Failed to start interactive SSH session: {e}")
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            return 130
    
    def copy_file_to_remote(
        self, 
        local_path: str, 
        remote_path: str,
        timeout: int = 60
    ) -> bool:
        """Copy a file to the remote instance using SCP.
        
        Args:
            local_path: Local file path
            remote_path: Remote file path
            timeout: Transfer timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            scp_cmd = ["scp"]
            
            # SCP options matching SSH options
            scp_cmd.extend([
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null", 
                "-o", "LogLevel=ERROR",
                "-o", "ConnectTimeout=10",
            ])
            
            # Add SSH key if available
            if self.ssh_key_path:
                scp_cmd.extend(["-i", self.ssh_key_path])
            
            # Add source and destination
            scp_cmd.extend([
                local_path,
                f"{self.user}@{self.ip}:{remote_path}"
            ])
            
            result = subprocess.run(
                scp_cmd,
                capture_output=True,
                timeout=timeout
            )
            
            return result.returncode == 0
            
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return False
    
    def wait_for_setup_complete(self, timeout: int = 300) -> bool:
        """Wait for instance setup to complete by checking for marker file.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if setup completed, False if timeout
        """
        start_time = asyncio.get_event_loop().time() if hasattr(asyncio, 'get_event_loop') else 0
        
        while True:
            try:
                # Check for setup completion marker
                return_code, stdout, stderr = self.execute_command(
                    "test -f /tmp/clwd-setup-complete",
                    timeout=10
                )
                
                if return_code == 0:
                    return True
                    
                # Check for timeout
                current_time = asyncio.get_event_loop().time() if hasattr(asyncio, 'get_event_loop') else start_time + 1
                if current_time - start_time > timeout:
                    return False
                
                # Wait before retrying
                import time
                time.sleep(5)
                
            except SSHError:
                # SSH not ready yet, continue waiting
                import time
                time.sleep(5)
                continue
    
    def get_instance_info(self) -> Dict[str, Any]:
        """Get basic information about the remote instance.
        
        Returns:
            Dictionary with instance information
        """
        info = {
            "ip": self.ip,
            "user": self.user,
            "ssh_key": self.ssh_key_path,
            "connection_available": False,
            "setup_complete": False,
            "system_info": {}
        }
        
        try:
            # Test connection
            info["connection_available"] = self.test_connection(timeout=5)
            
            if info["connection_available"]:
                # Check setup status
                return_code, _, _ = self.execute_command("test -f /tmp/clwd-setup-complete", timeout=5)
                info["setup_complete"] = (return_code == 0)
                
                # Get basic system info
                try:
                    return_code, stdout, _ = self.execute_command("uname -a && uptime", timeout=10)
                    if return_code == 0:
                        lines = stdout.strip().split('\n')
                        if len(lines) >= 2:
                            info["system_info"]["kernel"] = lines[0]
                            info["system_info"]["uptime"] = lines[1]
                except SSHError:
                    pass  # System info is optional
                    
        except Exception:
            pass  # Connection info is best-effort
            
        return info


class SSHSessionManager:
    """Manage SSH sessions for multiple instances."""
    
    def __init__(self):
        """Initialize session manager."""
        self._sessions: Dict[str, SSHOperations] = {}
    
    def get_session(self, ip: str, user: str = "root") -> SSHOperations:
        """Get or create SSH session for an instance.
        
        Args:
            ip: Instance IP address
            user: SSH user
            
        Returns:
            SSHOperations instance
        """
        session_key = f"{user}@{ip}"
        
        if session_key not in self._sessions:
            self._sessions[session_key] = SSHOperations(ip, user)
        
        return self._sessions[session_key]
    
    def remove_session(self, ip: str, user: str = "root") -> None:
        """Remove SSH session from cache.
        
        Args:
            ip: Instance IP address
            user: SSH user
        """
        session_key = f"{user}@{ip}"
        self._sessions.pop(session_key, None)
    
    def clear_all_sessions(self) -> None:
        """Clear all cached SSH sessions."""
        self._sessions.clear()


# Global session manager instance
ssh_manager = SSHSessionManager()