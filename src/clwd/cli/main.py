"""Main CLI interface for Clwd."""

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from clwd import __version__
from clwd.utils.config import Config, ProjectNotFoundError, ProjectExistsError
from clwd.providers.hetzner import HetznerProvider
from clwd.providers import ProviderError


console = Console()


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
@click.option("--name", required=True, help="Project name")
@click.option("--provider", default="hetzner", help="Cloud provider (hetzner)")
@click.option("--size", default="small", help="Instance size (small, medium, large)")
@click.option("--hardening", default="none", help="Security hardening level (none, minimal, full)")
@click.option("--region", help="Cloud provider region")
@click.option("--premium", is_flag=True, help="Use premium service for faster provisioning")
@click.option("--skip-auth", is_flag=True, help="Skip Claude Code authentication transfer")
@click.pass_context
def init(
    ctx: click.Context,
    name: str,
    provider: str,
    size: str,
    hardening: str,
    region: Optional[str],
    premium: bool,
    skip_auth: bool,
) -> None:
    """Initialize a new cloud instance with Claude Code.
    
    Creates a new cloud instance with Claude Code pre-installed and
    authenticated, ready for development with live preview URLs.
    """
    config = ctx.obj["config"]
    debug = ctx.obj.get("debug", False)
    
    # Check if project already exists
    if config.project_exists(name):
        console.print(f"[red]✗ Project '{name}' already exists![/red]")
        console.print(f"Use 'clwd status --name {name}' to check its status")
        sys.exit(1)
    
    console.print(f"[bold]Creating cloud instance for project: {name}[/bold]")
    
    if premium:
        console.print("[yellow]Premium service is not yet available. Using standard provisioning.[/yellow]")
    
    # Run async initialization
    try:
        asyncio.run(_init_async(ctx, name, provider, size, hardening, region, skip_auth))
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
@click.pass_context
def open(ctx: click.Context, name: str) -> None:
    """Open an interactive SSH session with the cloud instance.
    
    Connects to the specified project instance and starts an interactive
    SSH session with Claude Code available in the /app directory.
    """
    console.print(f"[bold]Opening interactive session for project: {name}[/bold]")
    
    # TODO: Implement interactive SSH session
    console.print("[red]Command not yet implemented in this version.[/red]")


@cli.command()
@click.option("--name", required=True, help="Project name")
@click.argument("command", required=True)
@click.option("--timeout", default=120, help="Command timeout in seconds")
@click.pass_context
def exec(ctx: click.Context, name: str, command: str, timeout: int) -> None:
    """Execute a command on the cloud instance.
    
    Runs the specified command on the cloud instance and returns the output.
    Useful for running scripts, builds, or other automated tasks.
    """
    console.print(f"[bold]Executing command on {name}:[/bold] {command}")
    
    # TODO: Implement command execution
    console.print("[red]Command not yet implemented in this version.[/red]")


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
        
        # TODO: Get live status from provider
        # For now, just show stored status
        if debug:
            console.print(f"\n[dim]Stored status: {instance.status}[/dim]")
            console.print("[dim]Note: Use provider API to get live status[/dim]")
            
    except Exception as e:
        console.print(f"[red]✗ Error checking status: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.option("--name", required=True, help="Project name")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def destroy(ctx: click.Context, name: str, force: bool) -> None:
    """Destroy a cloud instance.
    
    Permanently destroys the specified cloud instance and removes all data.
    This action cannot be undone.
    """
    config = ctx.obj["config"]
    debug = ctx.obj.get("debug", False)
    
    try:
        # Get project from config
        instance = config.get_project_instance(name)
        if not instance:
            console.print(f"[red]✗ Project '{name}' not found[/red]")
            sys.exit(1)
        
        # Confirm destruction
        if not force:
            console.print(f"[yellow]About to destroy:[/yellow]")
            console.print(f"  Project: {name}")
            console.print(f"  Instance ID: {instance.id}")
            console.print(f"  IP Address: {instance.ip}")
            console.print(f"  Provider: {instance.provider}")
            
            if not click.confirm(f"\n[bold red]Are you sure you want to destroy project '{name}'?[/bold red]"):
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
        
        console.print(f"[bold red]Destroying project: {name}[/bold red]")
        
        # Run async destruction
        asyncio.run(_destroy_async(ctx, name, instance))
        
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
            
            # TODO: Handle Claude authentication (skip for now if skip_auth)
            claude_json_content = None
            if not skip_auth:
                progress.update(task, description="Preparing Claude Code authentication...")
                # TODO: Implement keychain integration
                await asyncio.sleep(1)
            
            # Create cloud instance
            progress.update(task, description="Creating cloud instance...")
            instance = await cloud_provider.create_instance(
                name=name,
                size=size,
                hardening_level=hardening,
                claude_json_content=claude_json_content
            )
            
            # Wait for SSH to be available
            progress.update(task, description="Waiting for instance to be ready...")
            ssh_ready = await cloud_provider.wait_for_ssh(instance.ip, timeout=300)
            
            if not ssh_ready:
                raise ProviderError("Instance created but SSH is not available after 5 minutes")
            
            # Save project to config
            progress.update(task, description="Saving project configuration...")
            config.add_project(name, instance)
            
            # Final setup validation
            progress.update(task, description="Validating setup...")
            await asyncio.sleep(2)  # Allow time for cloud-init to complete
            
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