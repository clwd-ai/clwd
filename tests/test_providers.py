"""Tests for provider abstractions."""

import pytest
from datetime import datetime

from clwd.providers import (
    Instance,
    Provider,
    ProviderError,
    InstanceNotFoundError,
    QuotaExceededError,
    AuthenticationError,
)


class TestInstance:
    """Test the Instance dataclass."""
    
    def test_instance_creation_success(self):
        """Test successful instance creation."""
        instance = Instance(
            id="test-123",
            name="test-instance",
            ip="192.168.1.100",
            provider="test-provider",
            status="running",
            created_at="2024-01-01T00:00:00Z",
            metadata={"size": "small", "region": "test"}
        )
        
        assert instance.id == "test-123"
        assert instance.name == "test-instance"
        assert instance.ip == "192.168.1.100"
        assert instance.provider == "test-provider"
        assert instance.status == "running"
        assert instance.metadata["size"] == "small"
    
    def test_instance_validation_empty_id(self):
        """Test instance validation fails with empty ID."""
        with pytest.raises(ValueError, match="Instance ID cannot be empty"):
            Instance(
                id="",
                name="test-instance",
                ip="192.168.1.100",
                provider="test-provider",
                status="running",
                created_at="2024-01-01T00:00:00Z",
                metadata={}
            )
    
    def test_instance_validation_empty_name(self):
        """Test instance validation fails with empty name."""
        with pytest.raises(ValueError, match="Instance name cannot be empty"):
            Instance(
                id="test-123",
                name="",
                ip="192.168.1.100",
                provider="test-provider",
                status="running",
                created_at="2024-01-01T00:00:00Z",
                metadata={}
            )
    
    def test_instance_validation_empty_ip(self):
        """Test instance validation fails with empty IP."""
        with pytest.raises(ValueError, match="Instance IP cannot be empty"):
            Instance(
                id="test-123",
                name="test-instance",
                ip="",
                provider="test-provider",
                status="running",
                created_at="2024-01-01T00:00:00Z",
                metadata={}
            )
    
    def test_instance_validation_empty_provider(self):
        """Test instance validation fails with empty provider."""
        with pytest.raises(ValueError, match="Instance provider cannot be empty"):
            Instance(
                id="test-123",
                name="test-instance",
                ip="192.168.1.100",
                provider="",
                status="running",
                created_at="2024-01-01T00:00:00Z",
                metadata={}
            )


class TestProviderErrors:
    """Test provider exception classes."""
    
    def test_provider_error_creation(self):
        """Test ProviderError creation with provider info."""
        error = ProviderError("Test error", provider="test-provider")
        
        assert str(error) == "Test error"
        assert error.provider == "test-provider"
        assert error.timestamp
        # Verify timestamp is recent (within last minute)
        error_time = datetime.fromisoformat(error.timestamp)
        now = datetime.now()
        assert (now - error_time).total_seconds() < 60
    
    def test_provider_error_default_provider(self):
        """Test ProviderError with default provider."""
        error = ProviderError("Test error")
        assert error.provider == "unknown"
    
    def test_instance_not_found_error(self):
        """Test InstanceNotFoundError inheritance."""
        error = InstanceNotFoundError("Instance not found", provider="test")
        assert isinstance(error, ProviderError)
        assert error.provider == "test"
    
    def test_quota_exceeded_error(self):
        """Test QuotaExceededError inheritance."""
        error = QuotaExceededError("Quota exceeded", provider="test")
        assert isinstance(error, ProviderError)
        assert error.provider == "test"
    
    def test_authentication_error(self):
        """Test AuthenticationError inheritance."""
        error = AuthenticationError("Auth failed", provider="test")
        assert isinstance(error, ProviderError)
        assert error.provider == "test"


class MockProvider(Provider):
    """Mock provider implementation for testing."""
    
    async def create_instance(self, name, size="small", hardening_level="none", claude_json_content=None, **kwargs):
        return Instance(
            id="mock-123",
            name=name,
            ip="192.168.1.100",
            provider="mock",
            status="running",
            created_at="2024-01-01T00:00:00Z",
            metadata={"size": size, "hardening": hardening_level}
        )
    
    async def destroy_instance(self, instance_id):
        pass
    
    async def get_instance_status(self, instance_id):
        return "running"
    
    async def wait_for_ssh(self, ip, timeout=300):
        return True
    
    def get_supported_sizes(self):
        return {
            "small": {"cpu": 2, "memory": "4GB", "price": "5.00"},
            "medium": {"cpu": 3, "memory": "8GB", "price": "10.00"},
            "large": {"cpu": 4, "memory": "16GB", "price": "20.00"},
        }
    
    def get_supported_regions(self):
        return {
            "us-east": "US East",
            "us-west": "US West",
            "eu-central": "EU Central",
        }


class TestProvider:
    """Test the abstract Provider class through MockProvider."""
    
    def test_provider_interface(self):
        """Test that MockProvider implements the Provider interface."""
        provider = MockProvider()
        
        # Test supported sizes
        sizes = provider.get_supported_sizes()
        assert "small" in sizes
        assert "medium" in sizes
        assert "large" in sizes
        assert sizes["small"]["cpu"] == 2
        
        # Test supported regions
        regions = provider.get_supported_regions()
        assert "us-east" in regions
        assert "eu-central" in regions
    
    @pytest.mark.asyncio
    async def test_create_instance(self):
        """Test instance creation through provider."""
        provider = MockProvider()
        
        instance = await provider.create_instance(
            name="test-instance",
            size="medium",
            hardening_level="minimal"
        )
        
        assert instance.name == "test-instance"
        assert instance.provider == "mock"
        assert instance.metadata["size"] == "medium"
        assert instance.metadata["hardening"] == "minimal"
    
    @pytest.mark.asyncio
    async def test_instance_status(self):
        """Test instance status check."""
        provider = MockProvider()
        
        status = await provider.get_instance_status("mock-123")
        assert status == "running"
    
    @pytest.mark.asyncio
    async def test_wait_for_ssh(self):
        """Test SSH availability check."""
        provider = MockProvider()
        
        result = await provider.wait_for_ssh("192.168.1.100")
        assert result is True