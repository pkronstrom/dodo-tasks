"""Plugin CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

console = Console()

# Typer subapp for plugins
plugins_app = typer.Typer(
    name="plugins",
    help="Manage dodo plugins.",
    no_args_is_help=True,
)

# Built-in plugin locations
BUILTIN_PLUGINS_DIR = Path(__file__).parent / "plugins"
USER_PLUGINS_DIR = Path.home() / ".config" / "dodo" / "plugins"

# Known hooks that plugins can implement
KNOWN_HOOKS = [
    "register_commands",
    "register_config",
    "register_adapter",
    "extend_adapter",
    "extend_formatter",
]


def _get_config_dir() -> Path:
    """Get config directory."""
    from dodo.config import Config

    return Config.load().config_dir


def _load_registry() -> dict:
    """Load plugin registry from JSON file (uses cached version from plugins module)."""
    from dodo.plugins import _load_registry as load_registry_cached

    return load_registry_cached(_get_config_dir())


def _save_registry(registry: dict) -> None:
    """Save plugin registry to JSON file."""
    config_dir = _get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    registry_path = config_dir / "plugin_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2))


def _detect_hooks(plugin_path: Path) -> list[str]:
    """Detect which hooks a plugin implements by inspecting its __init__.py."""
    init_file = plugin_path / "__init__.py"
    if not init_file.exists():
        return []

    hooks = []
    content = init_file.read_text()

    for hook in KNOWN_HOOKS:
        # Check for function definition
        if f"def {hook}(" in content:
            hooks.append(hook)

    return hooks


def _detect_commands(plugin_path: Path) -> list[str]:
    """Detect COMMANDS declaration in plugin __init__.py."""
    import re

    init_file = plugin_path / "__init__.py"
    if not init_file.exists():
        return []

    content = init_file.read_text()
    match = re.search(r"COMMANDS\s*=\s*\[([^\]]*)\]", content)
    if match:
        items = match.group(1)
        return [s.strip().strip("\"'") for s in items.split(",") if s.strip().strip("\"'")]
    return []


def _detect_formatters(plugin_path: Path) -> list[str]:
    """Detect FORMATTERS declaration in plugin __init__.py."""
    import re

    init_file = plugin_path / "__init__.py"
    if not init_file.exists():
        return []

    content = init_file.read_text()
    match = re.search(r"FORMATTERS\s*=\s*\[([^\]]*)\]", content)
    if match:
        items = match.group(1)
        return [s.strip().strip("\"'") for s in items.split(",") if s.strip().strip("\"'")]
    return []


def _scan_plugin_dir(plugins_dir: Path, builtin: bool) -> dict[str, dict]:
    """Scan a directory for Python module plugins."""
    plugins = {}

    if not plugins_dir.exists():
        return plugins

    for entry in plugins_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith((".", "_")):
            continue
        if entry.name == "__pycache__":
            continue

        init_file = entry / "__init__.py"
        if not init_file.exists():
            continue

        # Read manifest if exists
        manifest_file = entry / "plugin.json"
        if manifest_file.exists():
            manifest = json.loads(manifest_file.read_text())
            name = manifest.get("name", entry.name)
            version = manifest.get("version", "0.0.0")
            description = manifest.get("description", "")
        else:
            # Fallback to parsing __init__.py for name
            name = entry.name
            version = "0.0.0"
            description = ""
            content = init_file.read_text()
            for line in content.splitlines():
                if line.strip().startswith("name ="):
                    try:
                        name = line.split("=", 1)[1].strip().strip("'\"")
                    except IndexError:
                        pass
                    break

        hooks = _detect_hooks(entry)
        commands = _detect_commands(entry)
        formatters = _detect_formatters(entry)

        if not hooks and not commands and not formatters:
            continue  # Skip plugins with nothing to offer

        plugin_info: dict = {
            "builtin": builtin,
            "hooks": hooks,
            "commands": commands,
            "formatters": formatters,
            "version": version,
            "description": description,
        }
        if not builtin:
            plugin_info["path"] = str(entry)

        plugins[name] = plugin_info

    return plugins


def _scan_and_save_to(config_dir: Path) -> dict:
    """Scan plugins and save registry to specified config dir."""
    registry: dict = {}

    # Scan built-in plugins
    builtin_plugins = _scan_plugin_dir(BUILTIN_PLUGINS_DIR, builtin=True)
    registry.update(builtin_plugins)

    # Scan user plugins
    user_plugins_dir = config_dir / "plugins"
    user_plugins = _scan_plugin_dir(user_plugins_dir, builtin=False)
    registry.update(user_plugins)

    # Save
    config_dir.mkdir(parents=True, exist_ok=True)
    registry_path = config_dir / "plugin_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2))

    return registry


@plugins_app.command()
def scan() -> None:
    """Scan plugin directories and update the registry."""
    from dodo.plugins import _scan_and_save, clear_plugin_cache

    # Clear cache and rescan
    clear_plugin_cache()
    registry = _scan_and_save(_get_config_dir())

    console.print(f"[green]Scanned[/green] {len(registry)} plugin(s)")
    for name, info in sorted(registry.items()):
        source = "[dim]builtin[/dim]" if info.get("builtin") else "[cyan]user[/cyan]"
        hooks = ", ".join(info.get("hooks", []))
        console.print(f"  {name} ({source}): {hooks}")


@plugins_app.command()
def register(
    path: Annotated[str, typer.Argument(help="Path to plugin directory")],
) -> None:
    """Register a plugin from a specific path."""
    plugin_path = Path(path).resolve()

    if not plugin_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    if not (plugin_path / "__init__.py").exists():
        console.print(f"[red]Error:[/red] No __init__.py found in {path}")
        raise typer.Exit(1)

    hooks = _detect_hooks(plugin_path)
    if not hooks:
        console.print(f"[red]Error:[/red] No hooks found in plugin at {path}")
        raise typer.Exit(1)

    # Get plugin name
    name = plugin_path.name
    init_content = (plugin_path / "__init__.py").read_text()
    for line in init_content.splitlines():
        if line.strip().startswith("name ="):
            try:
                name = line.split("=", 1)[1].strip().strip("'\"")
            except IndexError:
                pass
            break

    registry = _load_registry()
    registry[name] = {
        "builtin": False,
        "path": str(plugin_path),
        "hooks": hooks,
    }
    _save_registry(registry)

    console.print(f"[green]Registered:[/green] {name}")
    console.print(f"  Path: {plugin_path}")
    console.print(f"  Hooks: {', '.join(hooks)}")


@plugins_app.command()
def enable(
    name: Annotated[str, typer.Argument(help="Plugin name to enable")],
) -> None:
    """Enable a plugin."""
    from dodo.config import Config

    registry = _load_registry()
    if name not in registry:
        console.print(f"[red]Error:[/red] Plugin not found: {name}")
        console.print("[dim]Run 'dodo plugins scan' first[/dim]")
        raise typer.Exit(1)

    cfg = Config.load()
    enabled = cfg.enabled_plugins
    enabled.add(name)
    cfg.set("enabled_plugins", ",".join(sorted(enabled)))

    console.print(f"[green]Enabled:[/green] {name}")


@plugins_app.command()
def disable(
    name: Annotated[str, typer.Argument(help="Plugin name to disable")],
) -> None:
    """Disable a plugin."""
    from dodo.config import Config

    cfg = Config.load()
    enabled = cfg.enabled_plugins
    if name not in enabled:
        console.print(f"[yellow]Warning:[/yellow] Plugin not enabled: {name}")
        return

    enabled.discard(name)
    cfg.set("enabled_plugins", ",".join(sorted(enabled)))

    console.print(f"[yellow]Disabled:[/yellow] {name}")


@plugins_app.command(name="list")
def list_plugins() -> None:
    """List all plugins and their status."""
    from dodo.config import Config

    cfg = Config.load()
    registry = _load_registry()
    enabled = cfg.enabled_plugins

    if not registry:
        console.print("[dim]No plugins found.[/dim]")
        console.print("[dim]Run 'dodo plugins scan' to discover plugins[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Plugin", style="cyan")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Hooks")

    for name, info in sorted(registry.items()):
        hooks = info.get("hooks", [])

        if name in enabled:
            status = "[green]enabled[/green]"
        else:
            status = "[dim]disabled[/dim]"

        plugin_type = "[dim]builtin[/dim]" if info.get("builtin") else "user"
        hooks_str = ", ".join(hooks)
        table.add_row(name, status, plugin_type, hooks_str)

    console.print(table)


@plugins_app.command()
def show(
    name: Annotated[str, typer.Argument(help="Plugin name to show")],
) -> None:
    """Show details for a plugin."""
    registry = _load_registry()

    if name not in registry:
        console.print(f"[red]Error:[/red] Plugin not found: {name}")
        console.print("[dim]Run 'dodo plugins scan' first[/dim]")
        raise typer.Exit(1)

    info = registry[name]
    console.print(f"[bold]{name}[/bold]")
    console.print(f"  Builtin: {info.get('builtin', False)}")
    if info.get("path"):
        console.print(f"  Path: {info['path']}")
    console.print(f"  Hooks: {', '.join(info.get('hooks', []))}")
