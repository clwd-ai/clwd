"""Hetzner Cloud provider implementation using hcloud SDK."""

import asyncio
import base64
import os
import socket
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from hcloud import Client, APIException
from hcloud.server_types import ServerType
from hcloud.ssh_keys import SSHKey
from hcloud.servers import Server

from . import (
    Provider, 
    Instance, 
    ProviderError, 
    InstanceNotFoundError, 
    AuthenticationError,
    QuotaExceededError
)


class HetznerProvider(Provider):
    """Hetzner Cloud provider implementation using the official hcloud SDK.
    
    This provider handles server creation, management, and destruction on
    Hetzner Cloud infrastructure with full support for cloud-init scripts
    and SSH key management.
    """
    
    # Server type mapping for different sizes
    SIZE_MAP = {
        "small": "cpx11",   # 2 vCPU, 4GB RAM - €4.51/month
        "medium": "cpx21",  # 3 vCPU, 8GB RAM - €9.07/month  
        "large": "cpx31",   # 4 vCPU, 16GB RAM - €17.86/month
    }
    
    # Supported regions
    REGIONS = {
        "nbg1": "Nuremberg DC Park 1",
        "fsn1": "Falkenstein DC Park 1", 
        "hel1": "Helsinki DC Park 1",
        "ash": "Ashburn, VA",
        "hil": "Hillsboro, OR",
    }
    
    def __init__(self, api_token: Optional[str] = None, region: str = "nbg1") -> None:
        """Initialize Hetzner provider.
        
        Args:
            api_token: Hetzner API token. If None, uses HETZNER_API_TOKEN env var
            region: Hetzner region code (default: nbg1)
            
        Raises:
            AuthenticationError: If API token is missing or invalid
        """
        self.api_token = api_token or os.getenv("HETZNER_API_TOKEN")
        if not self.api_token:
            raise AuthenticationError(
                "Hetzner API token not provided. Set HETZNER_API_TOKEN environment variable.",
                provider="hetzner"
            )
        
        self.region = region
        if region not in self.REGIONS:
            raise ValueError(f"Unsupported region: {region}. Supported: {list(self.REGIONS.keys())}")
        
        try:
            self.client = Client(token=self.api_token)
            # Test the connection
            self.client.server_types.get_all()
        except APIException as e:
            raise AuthenticationError(
                f"Failed to authenticate with Hetzner API: {e}",
                provider="hetzner"
            )
    
    def _get_local_ssh_key(self) -> str:
        """Find and read local SSH public key.
        
        Returns:
            SSH public key content
            
        Raises:
            ValueError: If no SSH key is found
        """
        ssh_key_paths = [
            "~/.ssh/id_ed25519.pub",
            "~/.ssh/id_rsa.pub", 
            "~/.ssh/id_ecdsa.pub"
        ]
        
        for key_path in ssh_key_paths:
            expanded_path = Path(key_path).expanduser()
            if expanded_path.exists():
                return expanded_path.read_text().strip()
        
        raise ValueError(
            "No SSH key found. Please generate one with: ssh-keygen -t ed25519"
        )
    
    def _ensure_ssh_key_uploaded(self) -> SSHKey:
        """Ensure local SSH key is uploaded to Hetzner Cloud.
        
        Returns:
            SSHKey object from Hetzner Cloud
            
        Raises:
            ProviderError: If SSH key upload fails
        """
        try:
            local_key_content = self._get_local_ssh_key()
            
            # Check if key already exists
            existing_keys = self.client.ssh_keys.get_all()
            for key in existing_keys:
                if key.public_key.strip() == local_key_content.strip():
                    return key
            
            # Upload new key
            ssh_key = self.client.ssh_keys.create(
                name=f"clwd-{int(time.time())}",
                public_key=local_key_content,
                labels={"managed-by": "clwd"}
            )
            
            return ssh_key
            
        except APIException as e:
            raise ProviderError(
                f"Failed to upload SSH key to Hetzner: {e}",
                provider="hetzner"
            )
    
    def _generate_cloud_init_script(
        self, 
        name: str, 
        hardening_level: str = "none",
        claude_json_content: Optional[str] = None
    ) -> str:
        """Generate cloud-init script for server setup.
        
        Args:
            name: Project name
            hardening_level: Security hardening level (none, minimal, full)
            claude_json_content: Claude Code authentication content
            
        Returns:
            Base64-encoded cloud-init script
        """
        script_parts = [
            self._get_base_setup_script(),
            self._get_nodejs_setup_script(),
            self._get_claude_setup_script(claude_json_content),
            self._get_nginx_setup_script(),
            self._get_hardening_script(hardening_level),
            self._get_completion_script()
        ]
        
        script = "\n".join(script_parts)
        return base64.b64encode(script.encode('utf-8')).decode('ascii')
    
    def _get_base_setup_script(self) -> str:
        """Get base system setup script."""
        return """#!/bin/bash
set -e

# Update system and install base packages
apt-get update
apt-get install -y curl wget gnupg2 software-properties-common nginx ufw

# Create working directory
mkdir -p /app
cd /app"""
    
    def _get_nodejs_setup_script(self) -> str:
        """Get Node.js installation script."""
        return """
# Install Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code"""
    
    def _get_claude_setup_script(self, claude_json_content: Optional[str]) -> str:
        """Get Claude Code authentication setup script."""
        if not claude_json_content:
            return "# No Claude authentication provided"
        
        return f"""
# Set up Claude Code authentication
mkdir -p /root/.claude
cat > /root/.claude.json << 'EOF'
{claude_json_content}
EOF
chmod 600 /root/.claude.json"""
    
    def _get_nginx_setup_script(self) -> str:
        """Get Nginx configuration script."""
        return """
# Configure Nginx for preview
cat > /etc/nginx/sites-available/default << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    root /app;
    index index.html;
    server_name _;
    
    location / {
        try_files $uri $uri/ @proxy;
    }
    
    location @proxy {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# Create landing page
cat > /app/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Claude Code Instance</title>
    <style>
        body { 
            font-family: system-ui; 
            text-align: center; 
            padding: 2rem;
            background: #0a0a0a;
            color: #e8e8e8;
        }
        .status { 
            color: #10b981; 
            font-size: 1.5rem; 
            margin-bottom: 1rem;
        }
        .info { color: #888; }
    </style>
</head>
<body>
    <div class="status">✓ Claude Code Instance Ready</div>
    <div class="info">SSH in to start developing with Claude Code</div>
    <div class="info">Working directory: /app</div>
</body>
</html>
EOF

systemctl restart nginx"""
    
    def _get_hardening_script(self, hardening_level: str) -> str:
        """Get security hardening script based on level."""
        if hardening_level == "none":
            return "# No security hardening applied"
        elif hardening_level == "minimal":
            return """
# Minimal security hardening
ufw --force enable
ufw allow ssh
ufw allow http
ufw allow https

# Basic SSH hardening
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd"""
        elif hardening_level == "full":
            return """
# Full security hardening
ufw --force enable
ufw allow ssh
ufw allow http  
ufw allow https

# SSH hardening
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config

# Install fail2ban
apt-get install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban

systemctl restart sshd"""
        else:
            return "# Unknown hardening level"
    
    def _get_completion_script(self) -> str:
        """Get setup completion marker script."""
        return """
# Mark setup as complete
touch /tmp/clwd-setup-complete
echo "Setup completed at $(date)" > /var/log/clwd-setup.log"""
    
    async def create_instance(
        self,
        name: str,
        size: str = "small",
        hardening_level: str = "none", 
        claude_json_content: Optional[str] = None,
        **kwargs: Any
    ) -> Instance:
        """Create a new Hetzner Cloud instance.
        
        Args:
            name: Instance name
            size: Instance size (small, medium, large)
            hardening_level: Security level (none, minimal, full)
            claude_json_content: Claude authentication data
            **kwargs: Additional provider-specific options
            
        Returns:
            Created Instance object
            
        Raises:
            ProviderError: If instance creation fails
            QuotaExceededError: If account quota is exceeded
        """
        try:
            # Validate size
            server_type_name = self.SIZE_MAP.get(size)
            if not server_type_name:
                raise ValueError(f"Unsupported size: {size}. Supported: {list(self.SIZE_MAP.keys())}")
            
            # Ensure SSH key is uploaded
            ssh_key = self._ensure_ssh_key_uploaded()
            
            # Get server type and image
            server_type = self.client.server_types.get_by_name(server_type_name)
            if not server_type:
                raise ProviderError(f"Server type not found: {server_type_name}", provider="hetzner")
                
            image = self.client.images.get_by_name("ubuntu-24.04")
            if not image:
                raise ProviderError("Ubuntu 24.04 image not found", provider="hetzner")
            
            # Generate cloud-init script
            user_data = self._generate_cloud_init_script(name, hardening_level, claude_json_content)
            
            # Create server
            server_name = f"clwd-{name}-{int(time.time())}"
            response = self.client.servers.create(
                name=server_name,
                server_type=server_type,
                image=image,
                ssh_keys=[ssh_key],
                user_data=user_data,
                location=self.region,
                labels={
                    "project": name,
                    "managed-by": "clwd",
                    "hardening": hardening_level
                }
            )
            
            server = response.server
            
            return Instance(
                id=str(server.id),
                name=server.name,
                ip=server.public_net.ipv4.ip,
                provider="hetzner",
                status=server.status,
                created_at=datetime.now().isoformat(),
                metadata={
                    "server_type": server_type_name,
                    "region": self.region,
                    "hardening_level": hardening_level,
                    "datacenter": server.datacenter.name if server.datacenter else None
                }
            )
            
        except APIException as e:
            if "quota" in str(e).lower():
                raise QuotaExceededError(f"Hetzner quota exceeded: {e}", provider="hetzner")
            else:
                raise ProviderError(f"Failed to create Hetzner instance: {e}", provider="hetzner")
    
    async def destroy_instance(self, instance_id: str) -> None:
        """Destroy a Hetzner Cloud instance.
        
        Args:
            instance_id: ID of instance to destroy
            
        Raises:
            InstanceNotFoundError: If instance is not found
            ProviderError: If destruction fails
        """
        try:
            server = self.client.servers.get_by_id(int(instance_id))
            if not server:
                raise InstanceNotFoundError(
                    f"Instance not found: {instance_id}", 
                    provider="hetzner"
                )
            
            server.delete()
            
        except APIException as e:
            raise ProviderError(f"Failed to destroy instance: {e}", provider="hetzner")
        except ValueError:
            raise InstanceNotFoundError(
                f"Invalid instance ID: {instance_id}",
                provider="hetzner"
            )
    
    async def get_instance_status(self, instance_id: str) -> str:
        """Get current status of a Hetzner Cloud instance.
        
        Args:
            instance_id: ID of instance to check
            
        Returns:
            Instance status string
            
        Raises:
            InstanceNotFoundError: If instance is not found
            ProviderError: If status check fails
        """
        try:
            server = self.client.servers.get_by_id(int(instance_id))
            if not server:
                raise InstanceNotFoundError(
                    f"Instance not found: {instance_id}",
                    provider="hetzner"
                )
            
            return server.status
            
        except APIException as e:
            raise ProviderError(f"Failed to get instance status: {e}", provider="hetzner")
        except ValueError:
            raise InstanceNotFoundError(
                f"Invalid instance ID: {instance_id}",
                provider="hetzner"
            )
    
    async def wait_for_ssh(self, ip: str, timeout: int = 300) -> bool:
        """Wait for SSH to become available on an instance.
        
        Args:
            ip: IP address to check
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if SSH is available, False if timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((ip, 22))
                sock.close()
                
                if result == 0:
                    # Give SSH daemon a moment to fully initialize
                    await asyncio.sleep(5)
                    return True
                    
            except Exception:
                pass
            
            await asyncio.sleep(2)
        
        return False
    
    def get_supported_sizes(self) -> Dict[str, Dict[str, Any]]:
        """Get supported instance sizes and their specifications.
        
        Returns:
            Dict mapping size names to specifications
        """
        return {
            "small": {
                "server_type": "cpx11",
                "cpu": 2,
                "memory": "4GB", 
                "disk": "40GB SSD",
                "price_monthly": "€4.51"
            },
            "medium": {
                "server_type": "cpx21", 
                "cpu": 3,
                "memory": "8GB",
                "disk": "80GB SSD", 
                "price_monthly": "€9.07"
            },
            "large": {
                "server_type": "cpx31",
                "cpu": 4, 
                "memory": "16GB",
                "disk": "160GB SSD",
                "price_monthly": "€17.86"
            }
        }
    
    def get_supported_regions(self) -> Dict[str, str]:
        """Get supported regions for Hetzner Cloud.
        
        Returns:
            Dict mapping region codes to region names
        """
        return self.REGIONS.copy()