"""macOS Keychain integration for Claude Code credentials."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from rich.console import Console

console = Console()


class KeychainError(Exception):
    """Keychain access error."""
    pass


def is_macos() -> bool:
    """Check if running on macOS."""
    return os.name == 'posix' and hasattr(os, 'uname') and os.uname().sysname == 'Darwin'


def get_claude_credentials_from_keychain() -> Optional[Dict[str, Any]]:
    """Extract Claude Code credentials from macOS Keychain.
    
    Returns:
        Dictionary with credentials or None if not available
        
    Raises:
        KeychainError: If keychain access fails
    """
    if not is_macos():
        return None
    
    credentials = {}
    
    try:
        console.print("[dim]Requesting access to Claude Code credentials in Keychain...[/dim]")
        
        # Look for Claude Code credentials in keychain
        result = subprocess.run([
            'security', 'find-generic-password', 
            '-s', 'Claude Code-credentials',
            '-w'  # Output just the password
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            credentials['claude_code'] = result.stdout.strip()
            console.print("[green]✓[/green] Found Claude Code credentials in Keychain")
        else:
            console.print("[dim]No Claude Code credentials found in Keychain[/dim]")
        
        return credentials if credentials else None
        
    except subprocess.TimeoutExpired:
        raise KeychainError("Keychain access timed out - user may have denied access")
    except subprocess.SubprocessError as e:
        raise KeychainError(f"Failed to access Keychain: {e}")
    except Exception as e:
        raise KeychainError(f"Unexpected error accessing Keychain: {e}")


def get_claude_session_from_file() -> Optional[str]:
    """Get Claude Code session data from ~/.claude.json file.
    
    Returns:
        JSON content as string or None if not found
    """
    claude_json_path = Path.home() / ".claude.json"
    
    if not claude_json_path.exists():
        return None
    
    try:
        content = claude_json_path.read_text()
        
        # Validate it's proper JSON
        json.loads(content)
        
        console.print("[green]✓[/green] Found Claude Code session file")
        return content
        
    except json.JSONDecodeError:
        console.print("[yellow]⚠[/yellow] ~/.claude.json exists but contains invalid JSON")
        return None
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not read ~/.claude.json: {e}")
        return None


def create_minimal_claude_json(full_data: Dict[str, Any]) -> Optional[str]:
    """Create minimal Claude Code session data for cloud-init.
    
    Args:
        full_data: Full Claude session data from ~/.claude.json
        
    Returns:
        Minimal JSON string for remote instance
    """
    try:
        if "oauthAccount" not in full_data:
            console.print("[yellow]⚠[/yellow] No oauthAccount found in Claude session")
            return None
        
        # Extract only essential OAuth data to avoid cloud-init size limits
        minimal_data = {
            "installMethod": "clwd",
            "autoUpdates": False,
            "firstStartTime": full_data.get("firstStartTime", "2025-01-01T00:00:00.000Z"),
            "oauthAccount": full_data["oauthAccount"],
            "isQualifiedForDataSharing": full_data.get("isQualifiedForDataSharing", False),
            "hasCompletedOnboarding": True,
            "lastOnboardingVersion": full_data.get("lastOnboardingVersion", "1.0.69"),
            "projects": {
                "/app": {
                    "allowedTools": [],
                    "history": [],
                    "mcpContextUris": [],
                    "mcpServers": {},
                    "enabledMcpjsonServers": [],
                    "disabledMcpjsonServers": [],
                    "hasTrustDialogAccepted": False,
                    "projectOnboardingSeenCount": 0,
                    "hasClaudeMdExternalIncludesApproved": False,
                    "hasClaudeMdExternalIncludesWarningShown": False
                }
            }
        }
        
        minimal_json = json.dumps(minimal_data, indent=2)
        console.print(f"[green]✓[/green] Created minimal Claude session data ({len(minimal_json)} chars)")
        
        return minimal_json
        
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Failed to create minimal Claude session: {e}")
        return None


def create_credentials_json(credentials: Dict[str, Any]) -> Optional[str]:
    """Create .credentials.json content from keychain credentials.
    
    Args:
        credentials: Dictionary from get_claude_credentials_from_keychain()
        
    Returns:
        JSON string for .credentials.json file
    """
    if not credentials:
        return None
    
    creds_data = {}
    
    if 'claude_code' in credentials:
        try:
            # Try to parse as JSON if it's structured data
            parsed = json.loads(credentials['claude_code'])
            creds_data.update(parsed)
        except json.JSONDecodeError:
            # If it's not JSON, store as a token
            creds_data['token'] = credentials['claude_code']
    
    return json.dumps(creds_data, indent=2) if creds_data else None


def get_claude_authentication() -> Tuple[Optional[str], Optional[str]]:
    """Get Claude Code authentication data for remote instance.
    
    Returns:
        Tuple of (credentials_json, session_json) - both may be None
    """
    credentials_json = None
    session_json = None
    
    # Try to get credentials from keychain
    try:
        keychain_creds = get_claude_credentials_from_keychain()
        if keychain_creds:
            credentials_json = create_credentials_json(keychain_creds)
    except KeychainError as e:
        console.print(f"[yellow]⚠[/yellow] Keychain error: {e}")
    
    # Try to get session from file (return full content, not minimal)
    session_content = get_claude_session_from_file()
    if session_content:
        # Return the full session content instead of creating minimal version
        session_json = session_content
    
    return credentials_json, session_json


def test_keychain_access() -> bool:
    """Test if Keychain access is available.
    
    Returns:
        True if keychain can be accessed, False otherwise
    """
    if not is_macos():
        return False
    
    try:
        result = subprocess.run([
            'security', 'find-generic-password',
            '-s', 'Claude Code-credentials',
        ], capture_output=True, text=True, timeout=10)
        
        return result.returncode == 0
        
    except Exception:
        return False


def validate_claude_authentication() -> Dict[str, Any]:
    """Validate Claude Code authentication status.
    
    Returns:
        Dictionary with validation results
    """
    result = {
        "keychain_available": False,
        "keychain_credentials": False,
        "session_file": False,
        "session_valid": False,
        "ready_for_deployment": False
    }
    
    if is_macos():
        result["keychain_available"] = test_keychain_access()
        
        try:
            creds = get_claude_credentials_from_keychain()
            result["keychain_credentials"] = bool(creds)
        except KeychainError:
            pass
    
    # Check session file
    claude_json_path = Path.home() / ".claude.json"
    result["session_file"] = claude_json_path.exists()
    
    if result["session_file"]:
        try:
            session_content = claude_json_path.read_text()
            session_data = json.loads(session_content)
            result["session_valid"] = "oauthAccount" in session_data
        except Exception:
            pass
    
    # Ready if we have either credentials or valid session
    result["ready_for_deployment"] = (
        result["keychain_credentials"] or result["session_valid"]
    )
    
    return result