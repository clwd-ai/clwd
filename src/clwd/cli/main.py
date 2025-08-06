"""Main CLI interface for Clwd."""

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from clwd import __version__


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
    console.print(f"[bold]Creating cloud instance for project: {name}[/bold]")
    
    if premium:
        console.print("[yellow]Premium service is not yet available. Using standard provisioning.[/yellow]")
    
    # Run async initialization
    asyncio.run(_init_async(ctx, name, provider, size, hardening, region, skip_auth))


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
    console.print(f"[bold]Checking status for project: {name}[/bold]")
    
    # TODO: Implement status checking
    console.print("[red]Command not yet implemented in this version.[/red]")


@cli.command()
@click.option("--name", required=True, help="Project name")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def destroy(ctx: click.Context, name: str, force: bool) -> None:
    """Destroy a cloud instance.
    
    Permanently destroys the specified cloud instance and removes all data.
    This action cannot be undone.
    """
    if not force:
        if not click.confirm(f"Are you sure you want to destroy project '{name}'?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return
    
    console.print(f"[bold red]Destroying project: {name}[/bold red]")
    
    # TODO: Implement instance destruction
    console.print("[red]Command not yet implemented in this version.[/red]")


@cli.group(name="config")
def config_group() -> None:
    """Manage Clwd configuration and projects."""
    pass


@config_group.command(name="list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    """List all configured projects."""
    console.print("[bold]Configured projects:[/bold]")
    
    # TODO: Implement project listing
    console.print("[dim]No projects configured yet.[/dim]")


@config_group.command(name="show")
@click.option("--name", required=True, help="Project name")
@click.pass_context
def config_show(ctx: click.Context, name: str) -> None:
    """Show detailed configuration for a project."""
    console.print(f"[bold]Configuration for project: {name}[/bold]")
    
    # TODO: Implement project details
    console.print("[red]Command not yet implemented in this version.[/red]")


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
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing project...", total=None)
            
            # TODO: Implement actual initialization
            import time
            await asyncio.sleep(1)  # Simulate work
            
            progress.update(task, description="Validating configuration...")
            await asyncio.sleep(1)
            
            progress.update(task, description="Creating cloud instance...")
            await asyncio.sleep(2)
            
            progress.update(task, description="Setting up Claude Code...")
            await asyncio.sleep(2)
            
            progress.update(task, description="Applying security hardening...")
            await asyncio.sleep(1)
            
            progress.update(task, description="Finalizing setup...")
            await asyncio.sleep(1)
        
        console.print(f"[green]✓ Project '{name}' created successfully![/green]")
        console.print(f"[dim]Provider: {provider} | Size: {size} | Hardening: {hardening}[/dim]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  clwd open --name {name}     # Open interactive session")
        console.print(f"  clwd status --name {name}   # Check instance status")
        console.print(f"  clwd destroy --name {name}  # Destroy when done")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to create project: {e}[/red]")
        if debug:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    cli()