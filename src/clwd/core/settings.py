"""CLI settings and environment variables."""

import os
from pathlib import Path
from typing import Optional


class Settings:
    """Global settings for Clwd CLI."""
    
    def __init__(self) -> None:
        """Initialize settings from environment variables."""
        # Premium service configuration
        self.premium_server_url = os.getenv("CLWD_PREMIUM_SERVER_URL", "https://premium.clwd.com")
        self.premium_token_file = os.path.expanduser(
            os.getenv("CLWD_PREMIUM_TOKEN_FILE", "~/.clwd/premium_token")
        )
        
        # Standard provisioning fallback
        self.hetzner_api_token = os.getenv("HETZNER_API_TOKEN", "")
        
        # Debug mode
        self.debug = os.getenv("CLWD_DEBUG", "false").lower() in ("true", "1", "yes")
        
        # Load .env file if it exists
        self._load_env_file()
    
    def _load_env_file(self) -> None:
        """Load .env file if it exists."""
        env_file = Path.cwd() / ".env"
        if env_file.exists():
            try:
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key and not os.getenv(key):
                                os.environ[key] = value
            except Exception:
                pass  # Silently ignore .env file errors
    
    @property
    def is_premium_configured(self) -> bool:
        """Check if premium service is configured."""
        return bool(self.premium_server_url and self.premium_server_url != "https://premium.clwd.com")
    
    @property
    def has_premium_token(self) -> bool:
        """Check if premium token file exists."""
        return Path(self.premium_token_file).exists()
    
    @property
    def has_hetzner_token(self) -> bool:
        """Check if Hetzner API token is available."""
        return bool(self.hetzner_api_token)


# Global settings instance
settings = Settings()