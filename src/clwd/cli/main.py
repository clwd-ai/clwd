"""Main CLI interface for Clwd."""

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from clwd import __version__
from clwd.utils.config import Config, ProjectNotFoundError, ProjectExistsError
from clwd.utils.ssh import ssh_manager, SSHError
from clwd.utils.keychain import get_claude_authentication, validate_claude_authentication, KeychainError
from clwd.providers.hetzner import HetznerProvider
from clwd.providers import ProviderError


console = Console()


def interactive_project_selection(config: Config, action: str = "select", filter_running: bool = False) -> Optional[str]:
    """Interactive project selection with rich display."""
    try:
        projects = config.load_projects()
        if not projects:
            console.print("[yellow]No projects found.[/yellow]")
            console.print("Create one with: [cyan]clwd init myproject[/cyan]")
            return None
        
        # Filter running projects if requested
        if filter_running:
            # This would require checking actual project status
            # For now, we'll show all projects
            pass
        
        # Create a table for display
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("#", style="dim", width=3)
        table.add_column("Name", style="cyan")
        table.add_column("IP Address", style="green")
        table.add_column("Provider", style="magenta") 
        table.add_column("Created", style="dim")
        
        project_list = []
        for i, (name, project) in enumerate(projects.items(), 1):
            table.add_row(
                str(i),
                name,
                project.get('ip', 'N/A'),
                project.get('provider', 'N/A'),
                project.get('created_at', 'N/A')[:10] if project.get('created_at') else 'N/A'
            )
            project_list.append(name)
        
        console.print(f"\n[bold]Select a project to {action}:[/bold]")
        console.print(table)
        
        # Simple numbered selection (Rich doesn't have built-in arrow key navigation)
        while True:
            try:
                choice = Prompt.ask(
                    "\nEnter project number (or 'q' to quit)",
                    choices=[str(i) for i in range(1, len(project_list) + 1)] + ['q'],
                    show_choices=False
                )
                
                if choice == 'q':
                    return None
                    
                return project_list[int(choice) - 1]
                
            except (ValueError, IndexError):
                console.print("[red]Invalid selection. Try again.[/red]")
                
    except Exception as e:
        console.print(f"[red]Error loading projects: {e}[/red]")
        return None


@click.group()
@click.version_option(version=__version__)
@click.option("--debug/--no-debug", default=False, help="Enable debug mode")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Clwd - Fast cloud deployment CLI for Claude Code.
    
    Deploy Claude Code instances to the cloud with live preview URLs
    and optional security hardening.
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["config"] = Config()
    
    if debug:
        console.print("[dim]Debug mode enabled[/dim]")


@cli.command()
@click.argument("name", required=False)
@click.option("--name", help="Project name (alternative to positional argument)")
@click.option("--provider", default="hetzner", help="Cloud provider (hetzner)")
@click.option("--size", default="small", help="Instance size (small, medium, large)")
@click.option("--hardening", default="none", help="Security hardening level (none, minimal, full)")
@click.option("--region", help="Cloud provider region")
@click.option("--premium", is_flag=True, help="Use premium service for faster provisioning")
@click.option("--skip-auth", is_flag=True, help="Skip Claude Code authentication transfer")
@click.option("--standard", is_flag=True, help="Force standard provisioning (bypass premium)")
@click.pass_context
def init(
    ctx: click.Context,
    name: Optional[str],
    provider: str,
    size: str,
    hardening: str,
    region: Optional[str],
    premium: bool,
    skip_auth: bool,
    standard: bool,
    **kwargs
) -> None:
    """Initialize a new cloud instance with Claude Code.
    
    Creates a new cloud instance with Claude Code pre-installed and
    authenticated, ready for development with live preview URLs.
    """
    config = ctx.obj["config"]
    debug = ctx.obj.get("debug", False)
    
    # Resolve project name (positional argument takes precedence over --name option)
    project_name = name or kwargs.get('name')
    if not project_name:
        console.print("[red]✗ Project name is required[/red]")
        console.print("Usage: [cyan]clwd init myproject[/cyan] or [cyan]clwd init --name myproject[/cyan]")
        sys.exit(1)
    
    # Check if project already exists
    if config.project_exists(project_name):
        console.print(f"[red]✗ Project '{project_name}' already exists![/red]")
        console.print(f"Use 'clwd status {project_name}' to check its status")
        sys.exit(1)
    
    console.print(f"[bold]Creating cloud instance for project: {project_name}[/bold]")
    
    if premium:
        console.print("[yellow]Premium service is not yet available. Using standard provisioning.[/yellow]")
    
    # Run async initialization
    try:
        asyncio.run(_init_async(ctx, project_name, provider, size, hardening, region, skip_auth))
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Failed to create project: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.option("--name", required=True, help="Project name")
@click.option("--user", default="claude-user", help="SSH user (default: claude-user)")
@click.pass_context
def ssh(ctx: click.Context, name: str, user: str) -> None:
    """Open a plain SSH session to the cloud instance.
    
    Connects to the cloud instance with a standard SSH session for 
    debugging, administration, or direct shell access.
    """
    config = ctx.obj["config"]
    debug = ctx.obj.get("debug", False)
    
    try:
        # Get project from config
        instance = config.get_project_instance(name)
        if not instance:
            console.print(f"[red]✗ Project '{name}' not found[/red]")
            console.print("Use 'clwd config list' to see all projects")
            sys.exit(1)
        
        console.print(f"[bold]Opening SSH session for project: {name}[/bold]")
        console.print(f"[dim]Connecting to {user}@{instance.ip}...[/dim]")
        
        # Get SSH session
        ssh_session = ssh_manager.get_session(instance.ip, user)
        
        # Test connection first
        if not ssh_session.test_connection(timeout=10):
            console.print(f"[red]✗ Cannot connect to {instance.ip}[/red]")
            console.print("[dim]Make sure the instance is running and SSH is available[/dim]")
            sys.exit(1)
        
        # Start plain SSH session
        console.print("[dim]Starting SSH session... (press Ctrl+C or 'exit' to quit)[/dim]\n")
        
        exit_code = ssh_session.execute_interactive()
        
        if exit_code == 0:
            console.print("\n[green]✓ SSH session ended normally[/green]")
        elif exit_code == 130:
            console.print("\n[yellow]SSH session interrupted by user[/yellow]")
        else:
            console.print(f"\n[yellow]SSH session ended with exit code {exit_code}[/yellow]")
            
    except SSHError as e:
        console.print(f"[red]✗ SSH error: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error opening session: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument("name", required=False)
@click.option("--name", help="Project name (alternative to positional argument)")
@click.pass_context
def open(ctx: click.Context, name: Optional[str], **kwargs) -> None:
    """Open an interactive Claude Code session on the cloud instance.
    
    Connects to the cloud instance and starts Claude Code in interactive mode
    in the /app directory, ready for development and conversation.
    """
    config = ctx.obj["config"]
    
    # Resolve project name (positional argument takes precedence over --name option)
    project_name = name or kwargs.get('name')
    if not project_name:
        # Show interactive selection
        project_name = interactive_project_selection(config, "open")
        if not project_name:
            sys.exit(0)  # User cancelled or no projects
    debug = ctx.obj.get("debug", False)
    
    try:
        # Get project from config
        instance = config.get_project_instance(project_name)
        if not instance:
            console.print(f"[red]✗ Project '{project_name}' not found[/red]")
            console.print("Use 'clwd config list' to see all projects")
            sys.exit(1)
        
        console.print(f"[bold]Opening Claude Code interactive session for project: {project_name}[/bold]")
        console.print(f"[dim]Connecting to claude-user@{instance.ip}...[/dim]")
        
        # Get SSH session for claude-user
        ssh_session = ssh_manager.get_session(instance.ip, "claude-user")
        
        # Test connection first
        if not ssh_session.test_connection(timeout=10):
            console.print(f"[red]✗ Cannot connect to {instance.ip}[/red]")
            console.print("[dim]Make sure the instance is running and SSH is available[/dim]")
            sys.exit(1)
        
        # Check if setup is complete (optional warning)
        try:
            return_code, _, _ = ssh_session.execute_command("test -f /tmp/clwd-setup-complete", timeout=5)
            if return_code != 0:
                console.print("[yellow]⚠ Instance setup may not be complete yet[/yellow]")
                console.print("[dim]Some services may still be starting up[/dim]")
        except SSHError:
            pass  # Setup check is optional
        
        # Start Claude Code interactive session
        console.print("[dim]Starting Claude Code session... (press Ctrl+C to exit)[/dim]\n")
        
        # Start Claude Code in the /app directory
        claude_command = "cd /app && claude"
        exit_code = ssh_session.execute_interactive(claude_command)
        
        if exit_code == 0:
            console.print("\n[green]✓ Claude Code session ended normally[/green]")
        elif exit_code == 130:
            console.print("\n[yellow]Claude Code session interrupted by user[/yellow]")
        else:
            console.print(f"\n[yellow]Claude Code session ended with exit code {exit_code}[/yellow]")
        
        # Show helpful next steps
        console.print(f"\n[bold]Next steps:[/bold]")
        console.print(f"  clwd open --name {name}                    # Reconnect to Claude Code")
        console.print(f"  clwd exec --name {name} 'your instruction' # Run headless instruction") 
        console.print(f"[dim]Preview URL: http://{instance.ip}[/dim]")
            
    except SSHError as e:
        console.print(f"[red]✗ SSH error: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error opening session: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.option("--name", required=True, help="Project name")
@click.argument("instruction", required=True)
@click.option("--timeout", default=300, help="Command timeout in seconds (default: 5 minutes)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output from Claude Code")
@click.pass_context
def exec(ctx: click.Context, name: str, instruction: str, timeout: int, verbose: bool) -> None:
    """Execute a Claude Code instruction on the remote instance.
    
    Sends an instruction to Claude Code running on the cloud instance in headless mode.
    Examples:
      clwd exec --name myproject "create a login form with validation"
      clwd exec --name myproject "add error handling to the API routes"
      clwd exec --name myproject "refactor the database connection code"
    """
    config = ctx.obj["config"]
    debug = ctx.obj.get("debug", False)
    
    try:
        # Get project from config
        instance = config.get_project_instance(name)
        if not instance:
            console.print(f"[red]✗ Project '{name}' not found[/red]")
            console.print("Use 'clwd config list' to see all projects")
            sys.exit(1)
        
        console.print(f"[bold]Executing Claude Code instruction on {name}:[/bold] {instruction}")
        console.print(f"[dim]Connecting to claude-user@{instance.ip}...[/dim]")
        
        # Get SSH session for claude-user (not root)
        ssh_session = ssh_manager.get_session(instance.ip, "claude-user")
        
        # Test connection first
        if not ssh_session.test_connection(timeout=10):
            console.print(f"[red]✗ Cannot connect to {instance.ip}[/red]")
            console.print("[dim]Make sure the instance is running and Claude Code is set up[/dim]")
            sys.exit(1)
        
        # Build Claude Code command
        verbose_flag = "--verbose" if verbose else ""
        claude_command = f"cd /app && claude -p --dangerously-skip-permissions {verbose_flag} '{instruction}'"
        
        if debug:
            console.print(f"[dim]Remote command: {claude_command}[/dim]")
        
        console.print("[dim]Running Claude Code in headless mode...[/dim]")
        console.print("[dim]This may take a few minutes for complex instructions[/dim]")
        
        # Execute Claude Code command with longer timeout
        return_code, stdout, stderr = ssh_session.execute_command(
            claude_command, 
            timeout=timeout,
            capture_output=True
        )
        
        # Show output
        if stdout.strip():
            console.print("\n[bold]Claude Code Output:[/bold]")
            console.print(stdout.strip())
        
        if stderr.strip():
            console.print("\n[bold]Error Output:[/bold]")
            console.print(f"[red]{stderr.strip()}[/red]")
        
        # Show result
        if return_code == 0:
            console.print(f"\n[green]✓ Claude Code instruction completed successfully[/green]")
            console.print(f"[dim]Preview changes: http://{instance.ip}[/dim]")
        else:
            console.print(f"\n[red]✗ Claude Code instruction failed (exit code: {return_code})[/red]")
            sys.exit(return_code)
            
    except SSHError as e:
        console.print(f"[red]✗ SSH error: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error executing instruction: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.option("--name", required=True, help="Project name")
@click.pass_context
def status(ctx: click.Context, name: str) -> None:
    """Check the status of a cloud instance.
    
    Displays current status, IP address, and other metadata for the
    specified project instance.
    """
    config = ctx.obj["config"]
    debug = ctx.obj.get("debug", False)
    
    try:
        # Get project from config
        instance = config.get_project_instance(name)
        if not instance:
            console.print(f"[red]✗ Project '{name}' not found[/red]")
            console.print("Use 'clwd config list' to see all projects")
            sys.exit(1)
        
        console.print(f"[bold]Status for project: {name}[/bold]\n")
        
        # Display instance information
        from rich.table import Table
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")
        
        table.add_row("Project Name", name)
        table.add_row("Instance ID", instance.id)
        table.add_row("IP Address", f"[link=http://{instance.ip}]{instance.ip}[/link]")
        table.add_row("Provider", instance.provider)
        table.add_row("Status", f"[{'green' if instance.status == 'running' else 'yellow'}]{instance.status}[/]")
        table.add_row("Created", instance.created_at)
        
        if instance.metadata:
            for key, value in instance.metadata.items():
                table.add_row(key.replace("_", " ").title(), str(value))
        
        console.print(table)
        
        # Additional information
        console.print(f"\n[bold]Preview URL:[/bold] http://{instance.ip}")
        console.print(f"[bold]SSH Command:[/bold] ssh root@{instance.ip}")
        
        # Test SSH connection if requested
        if debug:
            console.print("\n[dim]Testing SSH connection...[/dim]")
            ssh_session = ssh_manager.get_session(instance.ip)
            ssh_info = ssh_session.get_instance_info()
            
            if ssh_info["connection_available"]:
                console.print("[dim]✓ SSH connection available[/dim]")
                if ssh_info["setup_complete"]:
                    console.print("[dim]✓ Instance setup complete[/dim]")
                else:
                    console.print("[dim]⚠ Instance setup may still be in progress[/dim]")
            else:
                console.print("[dim]✗ SSH connection not available[/dim]")
        
        console.print(f"\n[bold]Next steps:[/bold]")
        console.print(f"  clwd open --name {name}      # Open interactive session")
        console.print(f"  clwd exec --name {name} 'ls' # Execute command")
            
    except Exception as e:
        console.print(f"[red]✗ Error checking status: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument("name", required=False)
@click.option("--name", help="Project name (alternative to positional argument)")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def destroy(ctx: click.Context, name: Optional[str], force: bool, **kwargs) -> None:
    """Destroy a cloud instance.
    
    Permanently destroys the specified cloud instance and removes all data.
    This action cannot be undone.
    """
    config = ctx.obj["config"]
    debug = ctx.obj.get("debug", False)
    
    # Resolve project name (positional argument takes precedence over --name option)
    project_name = name or kwargs.get('name')
    if not project_name:
        # Show interactive selection
        project_name = interactive_project_selection(config, "destroy")
        if not project_name:
            sys.exit(0)  # User cancelled or no projects
    
    try:
        # Get project from config
        instance = config.get_project_instance(project_name)
        if not instance:
            console.print(f"[red]✗ Project '{project_name}' not found[/red]")
            sys.exit(1)
        
        # Confirm destruction
        if not force:
            console.print(f"[yellow]About to destroy:[/yellow]")
            console.print(f"  Project: {project_name}")
            console.print(f"  Instance ID: {instance.id}")
            console.print(f"  IP Address: {instance.ip}")
            console.print(f"  Provider: {instance.provider}")
            
            if not click.confirm(f"\nAre you sure you want to destroy project '{project_name}'?"):
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
        
        console.print(f"[bold red]Destroying project: {project_name}[/bold red]")
        
        # Run async destruction
        asyncio.run(_destroy_async(ctx, project_name, instance))
        
    except Exception as e:
        console.print(f"[red]✗ Error destroying project: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


@cli.group(name="config")
def config_group() -> None:
    """Manage Clwd configuration and projects."""
    pass


@config_group.command(name="list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    """List all configured projects."""
    config = ctx.obj["config"]
    
    try:
        project_details = config.list_project_details()
        
        if not project_details:
            console.print("[dim]No projects configured yet.[/dim]")
            console.print("Use 'clwd init --name <project>' to create your first project")
            return
        
        console.print(f"[bold]Configured projects ({len(project_details)}):[/bold]\n")
        
        from rich.table import Table
        
        table = Table()
        table.add_column("Project", style="bold")
        table.add_column("Status")
        table.add_column("IP Address")
        table.add_column("Provider") 
        table.add_column("Created")
        
        for detail in project_details:
            status_color = "green" if detail["status"] == "running" else "yellow"
            table.add_row(
                detail["project_name"],
                f"[{status_color}]{detail['status']}[/]",
                detail["ip"],
                detail["provider"],
                detail["created_at"][:10] if detail["created_at"] else ""
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]✗ Error listing projects: {e}[/red]")
        sys.exit(1)


@config_group.command(name="show")
@click.option("--name", required=True, help="Project name")
@click.pass_context
def config_show(ctx: click.Context, name: str) -> None:
    """Show detailed configuration for a project."""
    config = ctx.obj["config"]
    
    try:
        project_data = config.get_project(name)
        if not project_data:
            console.print(f"[red]✗ Project '{name}' not found[/red]")
            sys.exit(1)
        
        console.print(f"[bold]Configuration for project: {name}[/bold]\n")
        
        from rich.panel import Panel
        import json
        
        # Format the configuration as pretty JSON
        config_json = json.dumps(project_data, indent=2, sort_keys=True)
        
        panel = Panel(
            config_json,
            title="Project Configuration",
            title_align="left",
            border_style="blue"
        )
        
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]✗ Error showing project: {e}[/red]")
        sys.exit(1)


@cli.group(name="premium")
def premium_group() -> None:
    """Manage premium service features."""
    pass


@premium_group.command(name="status")
@click.pass_context
def premium_status(ctx: click.Context) -> None:
    """Check premium service status and subscription."""
    console.print("[bold]Premium service status:[/bold]")
    console.print("[yellow]Premium service is not yet available.[/yellow]")


@premium_group.command(name="login")
@click.pass_context
def premium_login(ctx: click.Context) -> None:
    """Authenticate with premium service."""
    console.print("[bold]Premium service authentication:[/bold]")
    console.print("[yellow]Premium service is not yet available.[/yellow]")


@cli.command()
@click.option("--name", required=True, help="Project name")
@click.pass_context
def auth(ctx: click.Context, name: str) -> None:
    """Authenticate Claude Code on the remote instance.
    
    Opens an interactive session to run 'claude auth login' on the instance.
    Useful when automatic authentication failed or credentials expired.
    """
    config = ctx.obj["config"]
    debug = ctx.obj.get("debug", False)
    
    try:
        # Get project from config
        instance = config.get_project_instance(name)
        if not instance:
            console.print(f"[red]✗ Project '{name}' not found[/red]")
            console.print("Use 'clwd config list' to see all projects")
            sys.exit(1)
        
        console.print(f"[bold]Authenticating Claude Code on '{name}'...[/bold]")
        console.print(f"[dim]This will open an interactive session to run 'claude auth login'[/dim]")
        
        # Get SSH session for claude-user
        ssh_session = ssh_manager.get_session(instance.ip, "claude-user")
        
        # Test connection first
        if not ssh_session.test_connection(timeout=10):
            console.print(f"[red]✗ Cannot connect to {instance.ip}[/red]")
            console.print("[dim]Make sure the instance is running[/dim]")
            sys.exit(1)
        
        # Start auth session
        console.print("[dim]Starting authentication session...[/dim]\n")
        
        auth_command = "cd /app && claude auth login"
        exit_code = ssh_session.execute_interactive(auth_command)
        
        if exit_code == 0:
            console.print("\n[green]✓ Authentication completed[/green]")
            console.print(f"[dim]You can now use: clwd open --name {name}[/dim]")
        else:
            console.print(f"\n[yellow]Authentication session ended with exit code {exit_code}[/yellow]")
            
    except SSHError as e:
        console.print(f"[red]✗ SSH error: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error during authentication: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


async def _init_async(
    ctx: click.Context,
    name: str,
    provider: str,
    size: str,
    hardening: str,
    region: Optional[str],
    skip_auth: bool,
) -> None:
    """Async implementation of init command."""
    debug = ctx.obj.get("debug", False)
    config = ctx.obj["config"]
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing project...", total=None)
        
        try:
            # Initialize provider
            progress.update(task, description="Initializing cloud provider...")
            
            if provider == "hetzner":
                cloud_provider = HetznerProvider(region=region or "nbg1")
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            # Prepare Claude authentication data
            credentials_json = None
            session_json = None  
            claude_json_content = None
            
            if not skip_auth:
                progress.update(task, description="Preparing Claude Code authentication...")
                
                try:
                    credentials_json, session_json = get_claude_authentication()
                    
                    # Follow prototype's fail-fast approach - require keychain credentials
                    if not credentials_json:
                        console.print("[red]✗ No Claude Code credentials found in Keychain![/red]")
                        console.print("[dim]Please authenticate Claude Code locally first:[/dim]")
                        console.print("[dim]  1. Run: claude auth login[/dim]")
                        console.print(f"[dim]  2. Then retry: clwd init --name {name}[/dim]")
                        console.print(f"[dim]  3. Or use: clwd init --name {name} --skip-auth[/dim]")
                        sys.exit(1)
                    
                    # Validate that we have session data too
                    if not session_json:
                        console.print("[red]✗ No Claude Code session file found![/red]")
                        console.print("[dim]Please ensure ~/.claude.json exists (run claude locally first)[/dim]")
                        sys.exit(1)
                    
                    # Skip cloud-init session data - we'll copy everything via SSH after cloud-init
                    console.print("[green]✓[/green] Claude Code authentication prepared for SSH transfer")
                        
                except Exception as e:
                    console.print(f"[red]✗ Could not prepare authentication: {e}[/red]")
                    console.print("[dim]Please ensure Claude Code is authenticated locally[/dim]")
                    sys.exit(1)
            
            # Create cloud instance (no Claude session data in cloud-init)
            progress.update(task, description="Creating cloud instance...")
            instance = await cloud_provider.create_instance(
                name=name,
                size=size,
                hardening_level=hardening,
                claude_json_content=None
            )
            
            # Wait for SSH to be available
            progress.update(task, description="Waiting for instance to be ready...")
            ssh_ready = await cloud_provider.wait_for_ssh(instance.ip, timeout=300)
            
            if not ssh_ready:
                raise ProviderError("Instance created but SSH is not available after 5 minutes")
            
            # Save project to config
            progress.update(task, description="Saving project configuration...")
            config.add_project(name, instance)
            
            # Wait for instance to be fully provisioned
            progress.update(task, description="Waiting for instance to be fully provisioned...")
            ssh_session = ssh_manager.get_session(instance.ip, "root")
            setup_complete = ssh_session.wait_for_setup_complete(timeout=300)

            if not setup_complete:
                raise ProviderError("Instance setup did not complete after 5 minutes")
            
            # Copy Claude Code authentication after setup is complete
            if not skip_auth and credentials_json:
                progress.update(task, description="Copying Claude Code credentials...")
                
                try:
                    # Clear any cached sessions to ensure fresh connection
                    ssh_manager.clear_all_sessions()
                    
                    # Brief delay to ensure SSH daemon is fully ready
                    await asyncio.sleep(3)
                    
                    ssh_session = ssh_manager.get_session(instance.ip, "claude-user")
                    
                    # Test connection first before proceeding
                    if not ssh_session.test_connection(timeout=10):
                        raise Exception("SSH connection test failed")
                    
                    # Create .claude directory
                    ssh_session.execute_command("mkdir -p ~/.claude", timeout=30)
                    
                    # Copy .credentials.json from keychain
                    import tempfile
                    import os
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_creds:
                        temp_creds.write(credentials_json)
                        temp_creds_path = temp_creds.name
                    
                    try:
                        if ssh_session.copy_file_to_remote(temp_creds_path, "~/.claude/.credentials.json"):
                            console.print("[green]✓[/green] Keychain credentials copied")
                        else:
                            console.print("[yellow]⚠[/yellow] Could not copy keychain credentials")
                    finally:
                        os.unlink(temp_creds_path)
                    
                    # Copy full .claude.json content (from session_json)
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_session:
                        temp_session.write(session_json)
                        temp_session_path = temp_session.name
                    
                    try:
                        if ssh_session.copy_file_to_remote(temp_session_path, "~/.claude.json"):
                            console.print("[green]✓[/green] Full Claude session copied")
                        else:
                            console.print("[yellow]⚠[/yellow] Could not copy Claude session file")
                    finally:
                        os.unlink(temp_session_path)
                    
                    # Create settings.json
                    settings_content = """{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "defaultMode": "acceptEdits"
  },
  "theme": "dark",
  "autoUpdates": false
}"""
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_settings:
                        temp_settings.write(settings_content)
                        temp_settings_path = temp_settings.name
                    
                    try:
                        if ssh_session.copy_file_to_remote(temp_settings_path, "~/.claude/settings.json"):
                            console.print("[green]✓[/green] Claude Code settings configured")
                        else:
                            console.print("[yellow]⚠[/yellow] Could not copy settings file")
                    finally:
                        os.unlink(temp_settings_path)
                        
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] Could not copy credentials via SSH: {e}")
                    console.print(f"[dim]You can authenticate manually with: clwd auth --name {name}[/dim]")
            
        except ProviderError as e:
            raise RuntimeError(f"Provider error: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")
    
    # Success message
    console.print(f"[green]✓ Project '{name}' created successfully![/green]")
    console.print(f"[dim]Provider: {provider} | Size: {size} | Hardening: {hardening}[/dim]")
    console.print(f"[dim]IP Address: {instance.ip}[/dim]")
    console.print(f"[dim]Instance ID: {instance.id}[/dim]")
    
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  clwd open --name {name}     # Open interactive session")
    console.print(f"  clwd status --name {name}   # Check instance status") 
    console.print(f"  clwd destroy --name {name}  # Destroy when done")
    
    console.print(f"\n[bold]Preview URL:[/bold] http://{instance.ip}")
    console.print("[dim]Note: It may take a few minutes for services to start[/dim]")


async def _destroy_async(ctx: click.Context, name: str, instance) -> None:
    """Async implementation of destroy command."""
    config = ctx.obj["config"]
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Destroying instance...", total=None)
        
        try:
            # Initialize provider
            progress.update(task, description="Initializing cloud provider...")
            
            if instance.provider == "hetzner":
                # Get region from metadata if available
                region = instance.metadata.get("region", "nbg1")
                cloud_provider = HetznerProvider(region=region)
            else:
                raise ValueError(f"Unsupported provider: {instance.provider}")
            
            # Destroy cloud instance
            progress.update(task, description="Destroying cloud instance...")
            await cloud_provider.destroy_instance(instance.id)
            
            # Remove from config
            progress.update(task, description="Removing project configuration...")
            config.remove_project(name)
            
        except Exception as e:
            raise RuntimeError(f"Failed to destroy instance: {e}")
    
    console.print(f"[green]✓ Project '{name}' destroyed successfully[/green]")


if __name__ == "__main__":
    cli()