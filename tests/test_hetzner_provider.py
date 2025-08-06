"""Tests for Hetzner Cloud provider."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from hcloud import APIException

from clwd.providers.hetzner import HetznerProvider
from clwd.providers import (
    Instance,
    ProviderError,
    InstanceNotFoundError,
    AuthenticationError,
    QuotaExceededError
)


class TestHetznerProvider:
    """Test the HetznerProvider class."""
    
    def test_init_with_token(self):
        """Test initialization with API token."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            
            provider = HetznerProvider(api_token="test-token")
            
            assert provider.api_token == "test-token"
            assert provider.region == "nbg1"
            mock_client.assert_called_once_with(token="test-token")
    
    def test_init_with_env_token(self):
        """Test initialization with environment variable token."""
        with patch.dict(os.environ, {'HETZNER_API_TOKEN': 'env-token'}):
            with patch('clwd.providers.hetzner.Client') as mock_client:
                mock_client.return_value.server_types.get_all.return_value = []
                
                provider = HetznerProvider()
                
                assert provider.api_token == "env-token"
    
    def test_init_without_token(self):
        """Test initialization fails without token."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthenticationError, match="API token not provided"):
                HetznerProvider()
    
    def test_init_with_invalid_region(self):
        """Test initialization fails with invalid region."""
        with pytest.raises(ValueError, match="Unsupported region"):
            HetznerProvider(api_token="test-token", region="invalid")
    
    def test_init_with_api_error(self):
        """Test initialization fails with API error."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.side_effect = APIException(
                "Authentication failed", Mock()
            )
            
            with pytest.raises(AuthenticationError, match="Failed to authenticate"):
                HetznerProvider(api_token="invalid-token")
    
    def test_get_local_ssh_key_ed25519(self):
        """Test finding ed25519 SSH key."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        with patch('pathlib.Path.expanduser') as mock_expand:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = "ssh-ed25519 AAAAC3... test@example.com"
            mock_expand.return_value = mock_path
            
            key = provider._get_local_ssh_key()
            
            assert key == "ssh-ed25519 AAAAC3... test@example.com"
    
    def test_get_local_ssh_key_not_found(self):
        """Test error when no SSH key is found."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        with patch('pathlib.Path.expanduser') as mock_expand:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_expand.return_value = mock_path
            
            with pytest.raises(ValueError, match="No SSH key found"):
                provider._get_local_ssh_key()
    
    def test_ensure_ssh_key_uploaded_existing(self):
        """Test using existing SSH key."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        # Mock existing SSH key
        mock_key = Mock()
        mock_key.public_key = "ssh-ed25519 AAAAC3... test@example.com"
        mock_client.return_value.ssh_keys.get_all.return_value = [mock_key]
        
        with patch.object(provider, '_get_local_ssh_key') as mock_get_key:
            mock_get_key.return_value = "ssh-ed25519 AAAAC3... test@example.com"
            
            result = provider._ensure_ssh_key_uploaded()
            
            assert result == mock_key
            mock_client.return_value.ssh_keys.create.assert_not_called()
    
    def test_ensure_ssh_key_uploaded_new(self):
        """Test uploading new SSH key."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        # Mock no existing keys
        mock_client.return_value.ssh_keys.get_all.return_value = []
        
        # Mock created key
        mock_new_key = Mock()
        mock_client.return_value.ssh_keys.create.return_value = mock_new_key
        
        with patch.object(provider, '_get_local_ssh_key') as mock_get_key:
            mock_get_key.return_value = "ssh-ed25519 AAAAC3... test@example.com"
            
            result = provider._ensure_ssh_key_uploaded()
            
            assert result == mock_new_key
            mock_client.return_value.ssh_keys.create.assert_called_once()
    
    def test_generate_cloud_init_script(self):
        """Test cloud-init script generation."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        script = provider._generate_cloud_init_script(
            "test-project",
            hardening_level="minimal",
            claude_json_content='{"key": "value"}'
        )
        
        # Should be base64 encoded
        import base64
        decoded = base64.b64decode(script).decode('utf-8')
        
        assert "#!/bin/bash" in decoded
        assert "apt-get update" in decoded
        assert "npm install -g @anthropic-ai/claude-code" in decoded
        assert '{"key": "value"}' in decoded
        assert "ufw --force enable" in decoded  # minimal hardening
    
    def test_get_supported_sizes(self):
        """Test getting supported instance sizes."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        sizes = provider.get_supported_sizes()
        
        assert "small" in sizes
        assert "medium" in sizes
        assert "large" in sizes
        assert sizes["small"]["server_type"] == "cpx11"
        assert sizes["medium"]["cpu"] == 3
        assert "€" in sizes["large"]["price_monthly"]
    
    def test_get_supported_regions(self):
        """Test getting supported regions."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        regions = provider.get_supported_regions()
        
        assert "nbg1" in regions
        assert "fsn1" in regions
        assert "hel1" in regions
        assert regions["nbg1"] == "Nuremberg DC Park 1"
    
    @pytest.mark.asyncio
    async def test_create_instance_success(self):
        """Test successful instance creation."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        # Mock dependencies
        mock_ssh_key = Mock()
        mock_server_type = Mock()
        mock_image = Mock()
        mock_server = Mock()
        mock_server.id = 12345
        mock_server.name = "clwd-test-1234567890"
        mock_server.public_net.ipv4.ip = "192.168.1.100"
        mock_server.status = "running"
        mock_server.datacenter.name = "nbg1-dc3"
        
        mock_response = Mock()
        mock_response.server = mock_server
        
        with patch.object(provider, '_ensure_ssh_key_uploaded', return_value=mock_ssh_key):
            mock_client.return_value.server_types.get_by_name.return_value = mock_server_type
            mock_client.return_value.images.get_by_name.return_value = mock_image
            mock_client.return_value.servers.create.return_value = mock_response
            
            instance = await provider.create_instance(
                name="test-project",
                size="medium",
                hardening_level="minimal"
            )
        
        assert isinstance(instance, Instance)
        assert instance.id == "12345"
        assert instance.name == "clwd-test-1234567890"
        assert instance.ip == "192.168.1.100"
        assert instance.provider == "hetzner"
        assert instance.metadata["server_type"] == "cpx21"
        assert instance.metadata["hardening_level"] == "minimal"
    
    @pytest.mark.asyncio
    async def test_create_instance_invalid_size(self):
        """Test instance creation with invalid size."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        with pytest.raises(ValueError, match="Unsupported size"):
            await provider.create_instance("test", size="invalid")
    
    @pytest.mark.asyncio
    async def test_create_instance_quota_exceeded(self):
        """Test instance creation when quota is exceeded."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        mock_ssh_key = Mock()
        mock_server_type = Mock()
        mock_image = Mock()
        
        with patch.object(provider, '_ensure_ssh_key_uploaded', return_value=mock_ssh_key):
            mock_client.return_value.server_types.get_by_name.return_value = mock_server_type
            mock_client.return_value.images.get_by_name.return_value = mock_image
            mock_client.return_value.servers.create.side_effect = APIException(
                "quota exceeded", Mock()
            )
            
            with pytest.raises(QuotaExceededError, match="quota exceeded"):
                await provider.create_instance("test")
    
    @pytest.mark.asyncio
    async def test_destroy_instance_success(self):
        """Test successful instance destruction."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        mock_server = Mock()
        mock_client.return_value.servers.get_by_id.return_value = mock_server
        
        await provider.destroy_instance("12345")
        
        mock_server.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_destroy_instance_not_found(self):
        """Test destroying non-existent instance."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        mock_client.return_value.servers.get_by_id.return_value = None
        
        with pytest.raises(InstanceNotFoundError):
            await provider.destroy_instance("12345")
    
    @pytest.mark.asyncio
    async def test_get_instance_status_success(self):
        """Test getting instance status."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        mock_server = Mock()
        mock_server.status = "running"
        mock_client.return_value.servers.get_by_id.return_value = mock_server
        
        status = await provider.get_instance_status("12345")
        
        assert status == "running"
    
    @pytest.mark.asyncio
    async def test_get_instance_status_not_found(self):
        """Test getting status of non-existent instance."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        mock_client.return_value.servers.get_by_id.return_value = None
        
        with pytest.raises(InstanceNotFoundError):
            await provider.get_instance_status("12345")
    
    @pytest.mark.asyncio
    async def test_wait_for_ssh_success(self):
        """Test waiting for SSH successfully."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 0  # Success
            mock_socket.return_value = mock_sock
            
            result = await provider.wait_for_ssh("192.168.1.100", timeout=10)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_wait_for_ssh_timeout(self):
        """Test SSH wait timeout."""
        with patch('clwd.providers.hetzner.Client') as mock_client:
            mock_client.return_value.server_types.get_all.return_value = []
            provider = HetznerProvider(api_token="test-token")
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 1  # Connection refused
            mock_socket.return_value = mock_sock
            
            result = await provider.wait_for_ssh("192.168.1.100", timeout=0.1)
            
            assert result is False