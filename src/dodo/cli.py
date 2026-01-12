"""CLI commands."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

if TYPE_CHECKING:
    from dodo.config import Config
    from dodo.core import TodoService

app = typer.Typer(
    name="dodo",
    help="Todo router - manage todos across multiple backends.",
    no_args_is_help=False,
)
console = Console()


def _get_config() -> Config:
    """Lazy import and load config."""
    from dodo.config import Config

    return Config.load()


def _get_service(config: Config, project_id: str | None) -> TodoService:
    """Lazy import and create service."""
    from dodo.core import TodoService

    return TodoService(config, project_id)


def _detect_project(worktree_shared: bool = False) -> str | None:
    """Lazy import and detect project."""
    from dodo.project import detect_project

    return detect_project(worktree_shared=worktree_shared)


# --- Plugin command routing ---


def _load_json_file(path) -> dict:
    """Load JSON file directly, return empty dict if missing."""
    from pathlib import Path

    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _get_config_dir():
    """Get config directory path."""
    from pathlib import Path

    return Path.home() / ".config" / "dodo"


def _get_plugin_for_command(argv: list[str]) -> tuple[str, bool] | None:
    """Check if argv matches an enabled plugin's command.

    Returns (plugin_name, is_root_command) or None if no match.
    """
    if len(argv) < 2:
        return None

    config_dir = _get_config_dir()
    registry = _load_json_file(config_dir / "plugin_registry.json")
    config = _load_json_file(config_dir / "config.json")
    enabled = set(filter(None, config.get("enabled_plugins", "").split(",")))

    # Build lookup key from argv
    if argv[1] == "plugins" and len(argv) > 2:
        key = f"plugins/{argv[2]}"
        is_root = False
    else:
        key = argv[1]
        is_root = True

    # Find plugin that owns this command
    for plugin_name, info in registry.items():
        if plugin_name in enabled and key in info.get("commands", []):
            return (plugin_name, is_root)

    return None


def _register_plugin_for_command(plugin_name: str, is_root: bool) -> None:
    """Load plugin and register its commands."""
    from dodo.plugins import import_plugin

    plugin = import_plugin(plugin_name, None)
    cfg = _get_config()

    if is_root and hasattr(plugin, "register_root_commands"):
        plugin.register_root_commands(app, cfg)
    elif hasattr(plugin, "register_commands"):
        from dodo.cli_plugins import plugins_app

        plugin.register_commands(plugins_app, cfg)


def _register_all_plugin_root_commands() -> None:
    """Register all enabled plugins' root commands (for --help display)."""
    from dodo.plugins import import_plugin

    config_dir = _get_config_dir()
    registry = _load_json_file(config_dir / "plugin_registry.json")
    config = _load_json_file(config_dir / "config.json")
    enabled = set(filter(None, config.get("enabled_plugins", "").split(",")))

    cfg = _get_config()
    registered = set()

    for plugin_name, info in registry.items():
        if plugin_name not in enabled:
            continue
        if not info.get("commands"):
            continue
        if plugin_name in registered:
            continue

        plugin = import_plugin(plugin_name, None)
        if hasattr(plugin, "register_root_commands"):
            plugin.register_root_commands(app, cfg)
            registered.add(plugin_name)


# Check if argv matches a plugin command and register it at module load
# For --help, register all plugin commands so they appear in help output
if "--help" in sys.argv or "-h" in sys.argv:
    _register_all_plugin_root_commands()
else:
    _plugin_match = _get_plugin_for_command(sys.argv)
    if _plugin_match:
        _register_plugin_for_command(_plugin_match[0], _plugin_match[1])


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Launch interactive menu if no command given."""
    if ctx.invoked_subcommand is None:
        from dodo.ui.interactive import interactive_menu

        interactive_menu()


@app.command()
def add(
    text: Annotated[list[str], typer.Argument(help="Todo text")],
    project: Annotated[str | None, typer.Option("-p", "--project", help="Target project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
):
    """Add a todo item."""
    cfg = _get_config()

    if global_:
        target = "global"
        project_id = None
    elif project:
        project_id = _resolve_project(project)
        target = project_id or "global"
    else:
        project_id = _detect_project(worktree_shared=cfg.worktree_shared)
        target = project_id or "global"

    svc = _get_service(cfg, project_id)
    item = svc.add(" ".join(text))

    _save_last_action("add", item.id, target)

    dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
    console.print(f"[green]✓[/green] Added to {dest}: {item.text} [dim]({item.id})[/dim]")


@app.command(name="ls")
@app.command(name="list")
def list_todos(
    project: Annotated[str | None, typer.Option("-p", "--project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    done: Annotated[bool, typer.Option("--done", help="Show completed")] = False,
    all_: Annotated[bool, typer.Option("-a", "--all", help="Show all")] = False,
    format_: Annotated[str | None, typer.Option("-f", "--format", help="Output format")] = None,
):
    """List todos."""
    from dodo.formatters import get_formatter
    from dodo.models import Status

    cfg = _get_config()

    if global_:
        project_id = None
    else:
        project_id = _resolve_project(project) or _detect_project(
            worktree_shared=cfg.worktree_shared
        )

    svc = _get_service(cfg, project_id)
    status = None if all_ else (Status.DONE if done else Status.PENDING)
    items = svc.list(status=status)

    format_str = format_ or cfg.default_format
    formatter = get_formatter(format_str)

    # Allow plugins to extend/wrap the formatter
    from dodo.plugins import apply_hooks

    formatter = apply_hooks("extend_formatter", formatter, cfg)

    output = formatter.format(items)
    console.print(output)


@app.command()
def done(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
    project: Annotated[str | None, typer.Option("-p", "--project", help="Target project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
):
    """Mark todo as done."""
    cfg = _get_config()
    if global_:
        project_id = None
    elif project:
        project_id = _resolve_project(project)
    else:
        project_id = _detect_project(worktree_shared=cfg.worktree_shared)
    svc = _get_service(cfg, project_id)

    # Try to find matching ID
    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    completed = svc.complete(item.id)
    console.print(f"[green]✓[/green] Done: {completed.text}")


@app.command(name="remove")
@app.command()
def rm(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
    project: Annotated[str | None, typer.Option("-p", "--project", help="Target project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
):
    """Remove a todo."""
    cfg = _get_config()
    if global_:
        project_id = None
    elif project:
        project_id = _resolve_project(project)
    else:
        project_id = _detect_project(worktree_shared=cfg.worktree_shared)
    svc = _get_service(cfg, project_id)

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    svc.delete(item.id)
    console.print(f"[yellow]✓[/yellow] Removed: {item.text}")


@app.command()
def undo():
    """Undo the last add operation."""
    last = _load_last_action()

    if not last or last.get("action") != "add":
        console.print("[yellow]Nothing to undo[/yellow]")
        raise typer.Exit(0)

    cfg = _get_config()
    project_id = None if last["target"] == "global" else last["target"]
    svc = _get_service(cfg, project_id)

    try:
        item = svc.get(last["id"])
        if not item:
            console.print("[yellow]Todo already removed[/yellow]")
            _clear_last_action()
            raise typer.Exit(0)

        svc.delete(last["id"])
        _clear_last_action()

        dest = (
            f"[cyan]{last['target']}[/cyan]" if last["target"] != "global" else "[dim]global[/dim]"
        )
        console.print(f"[yellow]↩[/yellow] Undid add from {dest}: {item.text}")

    except KeyError:
        console.print("[yellow]Todo already removed[/yellow]")
        _clear_last_action()


@app.command()
def ai(
    text: Annotated[str | None, typer.Argument(help="Input text")] = None,
):
    """AI-assisted todo creation."""
    piped = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()

    if not text and not piped:
        console.print("[red]Error:[/red] Provide text or pipe input")
        raise typer.Exit(1)

    cfg = _get_config()
    project_id = _detect_project(worktree_shared=cfg.worktree_shared)
    svc = _get_service(cfg, project_id)

    from dodo.ai import run_ai

    todo_texts = run_ai(
        user_input=text or "",
        piped_content=piped,
        command=cfg.ai_command,
        system_prompt=cfg.ai_sys_prompt,
    )

    if not todo_texts:
        console.print("[red]Error:[/red] AI returned no todos")
        raise typer.Exit(1)

    target = project_id or "global"
    for todo_text in todo_texts:
        item = svc.add(todo_text)
        dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
        console.print(f"[green]✓[/green] Added to {dest}: {item.text} [dim]({item.id})[/dim]")


@app.command()
def init(
    local: Annotated[bool, typer.Option("--local", help="Store todos in project dir")] = False,
):
    """Initialize dodo for current project."""
    cfg = _get_config()
    project_id = _detect_project(worktree_shared=cfg.worktree_shared)

    if not project_id:
        console.print("[red]Error:[/red] Not in a git repository")
        raise typer.Exit(1)

    if local:
        cfg.set("local_storage", True)

    console.print(f"[green]✓[/green] Initialized project: {project_id}")


@app.command()
def config():
    """Open interactive config editor."""
    from dodo.ui.interactive import interactive_config

    interactive_config()


@app.command()
def export(
    output: Annotated[str | None, typer.Option("-o", "--output", help="Output file")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Global todos")] = False,
):
    """Export todos to jsonl format."""
    from dodo.formatters.jsonl import JsonlFormatter

    cfg = _get_config()

    if global_:
        project_id = None
    else:
        project_id = _detect_project(worktree_shared=cfg.worktree_shared)

    svc = _get_service(cfg, project_id)
    items = svc.list()

    # JsonlFormatter uses to_dict() which includes plugin fields like blocked_by
    formatter = JsonlFormatter()
    content = formatter.format(items)

    if output:
        from pathlib import Path

        Path(output).write_text(content + "\n" if content else "")
        console.print(f"[green]✓[/green] Exported {len(items)} todos to {output}")
    else:
        console.print(content)


@app.command()
def info(
    global_: Annotated[bool, typer.Option("-g", "--global", help="Global info")] = False,
):
    """Show current storage info."""
    from dodo.models import Status

    cfg = _get_config()

    if global_:
        project_id = None
        target = "global"
    else:
        project_id = _detect_project(worktree_shared=cfg.worktree_shared)
        target = project_id or "global"

    svc = _get_service(cfg, project_id)
    items = svc.list()

    pending = sum(1 for i in items if i.status == Status.PENDING)
    done = sum(1 for i in items if i.status == Status.DONE)

    console.print(f"[bold]Project:[/bold] {target}")
    console.print(f"[bold]Adapter:[/bold] {cfg.default_adapter}")
    console.print(f"[bold]Storage:[/bold] {svc.storage_path}")
    console.print(f"[bold]Todos:[/bold] {len(items)} total ({pending} pending, {done} done)")


def _register_plugins_subapp() -> None:
    """Register the plugins subapp with the main app."""
    from dodo.cli_plugins import plugins_app

    @plugins_app.callback()
    def plugins_callback() -> None:
        """Register plugin commands lazily when plugins subcommand is accessed."""
        _register_plugin_commands()

    app.add_typer(plugins_app, name="plugins")


_register_plugins_subapp()


# Helpers


def _resolve_project(partial: str | None) -> str | None:
    """Resolve partial project name to full project ID."""
    if not partial:
        return None

    cfg = _get_config()
    projects_dir = cfg.config_dir / "projects"

    if not projects_dir.exists():
        return partial  # No projects yet, use as-is

    existing = [p.name for p in projects_dir.iterdir() if p.is_dir()]

    # Exact match
    if partial in existing:
        return partial

    # Partial match (prefix)
    matches = [p for p in existing if p.startswith(partial)]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        console.print(f"[yellow]Ambiguous project '{partial}'. Matches:[/yellow]")
        for m in matches:
            console.print(f"  - {m}")
        raise typer.Exit(1)

    # No match - use as-is (new project)
    return partial


def _find_item_by_partial_id(svc: TodoService, partial_id: str):
    """Find item by full or partial ID."""
    # First try exact match
    item = svc.get(partial_id)
    if item:
        return item

    # Try partial match
    matches = [item for item in svc.list() if item.id.startswith(partial_id)]

    if len(matches) == 0:
        return None
    elif len(matches) == 1:
        return matches[0]
    else:
        # Ambiguous - show options and exit
        console.print(f"[yellow]Ambiguous ID '{partial_id}'. Matches:[/yellow]")
        for m in matches:
            console.print(f"  - {m.id}: {m.text[:50]}")
        raise typer.Exit(1)


def _save_last_action(action: str, id: str, target: str) -> None:
    """Save last action for undo."""
    cfg = _get_config()
    state_file = cfg.config_dir / ".last_action"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"action": action, "id": id, "target": target}))


def _load_last_action() -> dict | None:
    """Load last action."""
    cfg = _get_config()
    state_file = cfg.config_dir / ".last_action"
    if not state_file.exists():
        return None
    try:
        content = state_file.read_text()
        if content.strip():
            return json.loads(content)
        return None
    except json.JSONDecodeError:
        return None


def _clear_last_action() -> None:
    """Clear last action after undo."""
    cfg = _get_config()
    state_file = cfg.config_dir / ".last_action"
    if state_file.exists():
        state_file.unlink()


_plugin_commands_registered = False


def _register_plugin_commands() -> None:
    """Allow plugins to register additional CLI commands under 'dodo plugins <name>'.

    Called lazily on first plugin subcommand access to avoid import-time overhead.
    """
    global _plugin_commands_registered
    if _plugin_commands_registered:
        return
    _plugin_commands_registered = True

    from dodo.cli_plugins import plugins_app
    from dodo.plugins import apply_hooks

    cfg = _get_config()
    apply_hooks("register_commands", plugins_app, cfg)
