"""Cloud provider implementations for Clwd."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Instance:
    """Represents a cloud instance with all associated metadata."""
    
    id: str
    name: str
    ip: str
    provider: str
    status: str
    created_at: str
    metadata: Dict[str, Any]
    
    def __post_init__(self) -> None:
        """Validate instance data after initialization."""
        if not self.id:
            raise ValueError("Instance ID cannot be empty")
        if not self.name:
            raise ValueError("Instance name cannot be empty")
        if not self.ip:
            raise ValueError("Instance IP cannot be empty")
        if not self.provider:
            raise ValueError("Instance provider cannot be empty")


class Provider(ABC):
    """Abstract base class for cloud providers.
    
    All cloud provider implementations must inherit from this class
    and implement the required abstract methods.
    """
    
    @abstractmethod
    async def create_instance(
        self,
        name: str,
        size: str = "small",
        hardening_level: str = "none",
        claude_json_content: Optional[str] = None,
        **kwargs: Any
    ) -> Instance:
        """Create a new cloud instance.
        
        Args:
            name: Unique name for the instance
            size: Instance size (small, medium, large)
            hardening_level: Security hardening level (none, minimal, full)
            claude_json_content: Claude Code authentication content
            **kwargs: Provider-specific options
            
        Returns:
            Instance: Created instance object
            
        Raises:
            ProviderError: If instance creation fails
        """
        pass
    
    @abstractmethod
    async def destroy_instance(self, instance_id: str) -> None:
        """Destroy a cloud instance.
        
        Args:
            instance_id: ID of instance to destroy
            
        Raises:
            ProviderError: If instance destruction fails
        """
        pass
    
    @abstractmethod
    async def get_instance_status(self, instance_id: str) -> str:
        """Get current status of a cloud instance.
        
        Args:
            instance_id: ID of instance to check
            
        Returns:
            str: Instance status (creating, running, stopped, destroyed)
            
        Raises:
            ProviderError: If status check fails
        """
        pass
    
    @abstractmethod
    async def wait_for_ssh(self, ip: str, timeout: int = 300) -> bool:
        """Wait for SSH to become available on an instance.
        
        Args:
            ip: IP address to check
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if SSH is available, False if timeout
        """
        pass
    
    @abstractmethod
    def get_supported_sizes(self) -> Dict[str, Dict[str, Any]]:
        """Get supported instance sizes and their specifications.
        
        Returns:
            Dict mapping size names to specifications
        """
        pass
    
    @abstractmethod
    def get_supported_regions(self) -> Dict[str, str]:
        """Get supported regions for this provider.
        
        Returns:
            Dict mapping region codes to region names
        """
        pass


class ProviderError(Exception):
    """Base exception for provider-related errors."""
    
    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(message)
        self.provider = provider
        self.timestamp = datetime.now().isoformat()


class InstanceNotFoundError(ProviderError):
    """Raised when a requested instance is not found."""
    pass


class QuotaExceededError(ProviderError):
    """Raised when provider quota limits are exceeded."""
    pass


class AuthenticationError(ProviderError):
    """Raised when provider authentication fails."""
    pass