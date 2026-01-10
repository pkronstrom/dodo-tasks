"""Plugin CLI commands."""

import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def dispatch(action: str, name: str | None = None) -> None:
    """Dispatch plugin commands."""
    if action == "list":
        list_plugins()
    elif action == "show":
        if not name:
            console.print("[red]Error:[/red] Plugin name required for 'show'")
            console.print("Usage: dodo plugins show <name>")
            sys.exit(1)
        show(name)
    elif action == "run":
        if not name:
            console.print("[red]Error:[/red] Plugin name required for 'run'")
            console.print("Usage: dodo plugins run <name>")
            sys.exit(1)
        run(name)
    else:
        console.print(f"[red]Error:[/red] Unknown action '{action}'")
        console.print("Available actions: list, show, run")
        sys.exit(1)


def _get_plugins():
    """Lazy import and get plugins."""
    from dodo.plugins import get_all_plugins

    return get_all_plugins()


def _get_plugin_locations():
    """Get plugin search locations."""
    from dodo.config import Config

    cfg = Config.load()
    return [
        cfg.config_dir / "plugins",
        Path.cwd() / "plugins",
    ]


def list_plugins() -> None:
    """List installed plugins and their configuration status."""
    plugins = _get_plugins()

    if not plugins:
        locations = _get_plugin_locations()
        console.print("[dim]No plugins found.[/dim]")
        console.print("\n[dim]Searched:[/dim]")
        for loc in locations:
            exists = "[green]exists[/green]" if loc.exists() else "[dim]not found[/dim]"
            console.print(f"  {loc} ({exists})")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Plugin", style="cyan")
    table.add_column("Status")
    table.add_column("Config")

    for plugin in plugins:
        if plugin.is_configured:
            status = "[green]ready[/green]"
        elif plugin.envs:
            missing = [e.name for e in plugin.envs if e.required and not e.is_set]
            status = f"[yellow]missing: {', '.join(missing)}[/yellow]"
        else:
            status = "[green]ready[/green]"

        env_info = ", ".join(e.name for e in plugin.envs) if plugin.envs else "[dim]none[/dim]"
        table.add_row(plugin.name, status, env_info)

    console.print(table)


def run(name: str) -> None:
    """Run a plugin (foreground)."""
    plugins = _get_plugins()

    plugin = next((p for p in plugins if p.name == name), None)
    if not plugin:
        console.print(f"[red]Error:[/red] Plugin not found: {name}")
        console.print("\nAvailable plugins:")
        for p in plugins:
            console.print(f"  - {p.name}")
        sys.exit(1)

    # Check configuration
    missing = [e for e in plugin.envs if e.required and not e.is_set]
    if missing:
        console.print("[red]Error:[/red] Missing required environment variables:")
        for env in missing:
            console.print(f"  {env.name}: {env.description}")
        console.print("\n[dim]Set them in your shell or via 'dodo plugins config'[/dim]")
        sys.exit(1)

    # Run the plugin
    console.print(f"[dim]Running {plugin.name}...[/dim]")
    try:
        result = subprocess.run(
            [str(plugin.script)],
            env=os.environ.copy(),
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def show(name: str) -> None:
    """Show plugin details and configuration."""
    plugins = _get_plugins()

    plugin = next((p for p in plugins if p.name == name), None)
    if not plugin:
        console.print(f"[red]Error:[/red] Plugin not found: {name}")
        sys.exit(1)

    console.print(f"[bold]{plugin.name}[/bold]")
    console.print(f"[dim]Path:[/dim] {plugin.path}")
    console.print(f"[dim]Script:[/dim] {plugin.script}")

    if plugin.envs:
        console.print("\n[bold]Configuration:[/bold]")
        for env in plugin.envs:
            if env.is_set:
                # Mask the value for security
                value = env.current_value or ""
                masked = value[:4] + "..." if len(value) > 8 else "[set]"
                status = f"[green]{masked}[/green]"
            elif env.required:
                status = "[red]missing (required)[/red]"
            elif env.default:
                status = f"[dim]default: {env.default}[/dim]"
            else:
                status = "[dim]not set[/dim]"

            req = " [red]*[/red]" if env.required else ""
            console.print(f"  {env.name}{req}: {status}")
            console.print(f"    [dim]{env.description}[/dim]")
    else:
        console.print("\n[dim]No configuration required.[/dim]")
