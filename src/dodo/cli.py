"""CLI commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
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


def _resolve_dodo(
    config: Config,
    dodo_name: str | None = None,
    global_: bool = False,
) -> tuple[str | None, Path | None]:
    """Resolve which dodo to use. Wrapper for shared resolve_dodo."""
    from dodo.resolve import resolve_dodo

    return resolve_dodo(config, dodo_name, global_)


def _get_service_with_path(config: Config, path: Path) -> TodoService:
    """Create TodoService with explicit storage path."""
    from dodo.core import TodoService

    return TodoService(config, project_id=None, storage_path=path)


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
    """Get config directory path using shared resolution logic."""
    from dodo.config import get_default_config_dir

    return get_default_config_dir()


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
    text: Annotated[str, typer.Argument(help="Todo text (use quotes)")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    priority: Annotated[
        str | None,
        typer.Option("--priority", "-P", help="Priority: critical/high/normal/low/someday"),
    ] = None,
    tags: Annotated[str | None, typer.Option("--tags", "-t", help="Comma-separated tags")] = None,
):
    """Add a todo item."""
    from dodo.models import Priority

    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
        target = dodo_id or "local"
    else:
        svc = _get_service(cfg, dodo_id)
        target = dodo_id or "global"

    # Parse priority
    parsed_priority = None
    if priority:
        try:
            parsed_priority = Priority(priority.lower())
        except ValueError:
            console.print(
                f"[red]Error:[/red] Invalid priority '{priority}'. Use: critical/high/normal/low/someday"
            )
            raise typer.Exit(1)

    # Parse tags
    parsed_tags = None
    if tags:
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    item = svc.add(text, priority=parsed_priority, tags=parsed_tags)

    _save_last_action("add", item.id, target)

    dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
    console.print(f"[green]✓[/green] Added to {dest}: {item.text} [dim]({item.id})[/dim]")


def _parse_filter(filter_str: str) -> tuple[str, list[str]]:
    """Parse filter string like 'tag:value1,value2' or 'prio:high'.

    Returns (key, [values]) tuple.
    """
    if ":" not in filter_str:
        raise ValueError(f"Invalid filter format: '{filter_str}'. Use key:value (e.g., tag:work)")
    key, value = filter_str.split(":", 1)
    values = [v.strip() for v in value.split(",") if v.strip()]
    return key.lower(), values


@app.command(name="ls")
@app.command(name="list")
def list_todos(
    project: Annotated[str | None, typer.Option("-p", "--project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    done: Annotated[bool, typer.Option("--done", help="Show completed")] = False,
    all_: Annotated[bool, typer.Option("-a", "--all", help="Show all")] = False,
    format_: Annotated[str | None, typer.Option("-f", "--format", help="Output format")] = None,
    sort: Annotated[
        str | None, typer.Option("--sort", "-s", help="Sort by: priority, created, text")
    ] = None,
    filter_: Annotated[
        list[str] | None,
        typer.Option("--filter", "-F", help="Filter: tag:name, prio:level, status:done"),
    ] = None,
):
    """List todos."""
    from dodo.formatters import get_formatter
    from dodo.models import Priority, Status

    cfg = _get_config()

    # Auto-detect dodo (respects --dodo flag, --global flag, or auto-detection)
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    status = None if all_ else (Status.DONE if done else Status.PENDING)
    items = svc.list(status=status)

    # Apply filters
    if filter_:
        for f in filter_:
            try:
                key, values = _parse_filter(f)
            except ValueError as e:
                console.print(f"[red]Error:[/red] {e}")
                raise typer.Exit(1)

            if key in ("prio", "priority"):
                try:
                    target_priorities = [Priority(v.lower()) for v in values]
                    items = [i for i in items if i.priority in target_priorities]
                except ValueError:
                    console.print(f"[red]Error:[/red] Invalid priority in '{f}'")
                    raise typer.Exit(1)
            elif key in ("tag", "tags"):
                # Match any of the specified tags
                items = [i for i in items if i.tags and any(t in i.tags for t in values)]
            elif key == "status":
                try:
                    target_statuses = [Status(v.lower()) for v in values]
                    items = [i for i in items if i.status in target_statuses]
                except ValueError:
                    console.print(f"[red]Error:[/red] Invalid status in '{f}'")
                    raise typer.Exit(1)
            else:
                console.print(f"[red]Error:[/red] Unknown filter key '{key}'")
                raise typer.Exit(1)

    # Apply sorting
    if sort:
        if sort == "priority":
            # Sort by priority (highest first), items without priority go last
            items = sorted(
                items,
                key=lambda x: (x.priority.sort_order if x.priority else 0),
                reverse=True,
            )
        elif sort == "created":
            items = sorted(items, key=lambda x: x.created_at)
        elif sort == "text":
            items = sorted(items, key=lambda x: x.text.lower())

    format_str = format_ or cfg.default_format
    try:
        formatter = get_formatter(format_str)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Allow plugins to extend/wrap the formatter
    from dodo.plugins import apply_hooks

    formatter = apply_hooks("extend_formatter", formatter, cfg)

    output = formatter.format(items)
    console.print(output)


@app.command()
def done(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
):
    """Mark todo as done."""
    cfg = _get_config()
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
):
    """Remove a todo."""
    cfg = _get_config()
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
def new(
    name: Annotated[str | None, typer.Argument(help="Name for the dodo")] = None,
    local: Annotated[bool, typer.Option("--local", help="Create in .dodo/ locally")] = False,
    backend: Annotated[
        str | None, typer.Option("--backend", "-b", help="Backend (sqlite|markdown)")
    ] = None,
):
    """Create a new dodo."""
    from pathlib import Path

    from dodo.project_config import ProjectConfig

    cfg = _get_config()
    backend_name = backend or cfg.default_backend

    # Determine target directory
    if local:
        # Local storage in .dodo/
        base = Path.cwd() / ".dodo"
        if name:
            target_dir = base / name
        else:
            target_dir = base
    else:
        # Centralized in ~/.config/dodo/
        if name:
            target_dir = cfg.config_dir / name
        else:
            target_dir = cfg.config_dir

    # Check if already exists
    config_file = target_dir / "dodo.json"
    db_file = target_dir / "dodo.db"
    md_file = target_dir / "dodo.md"

    if config_file.exists() or db_file.exists() or md_file.exists():
        location = str(target_dir).replace(str(Path.home()), "~")
        console.print(f"[yellow]Dodo already exists in {location}[/yellow]")
        console.print("  Hint: Use [bold]dodo new <name>[/bold] to create a named dodo")
        return

    # Create directory and config
    target_dir.mkdir(parents=True, exist_ok=True)
    project_config = ProjectConfig(backend=backend_name)
    project_config.save(target_dir)

    # Initialize empty backend file
    if backend_name == "sqlite":
        from dodo.backends.sqlite import SqliteBackend

        SqliteBackend(target_dir / "dodo.db")
    elif backend_name == "markdown":
        (target_dir / "dodo.md").write_text("")

    location = str(target_dir).replace(str(Path.home()), "~")
    console.print(f"[green]✓[/green] Created dodo in {location}")


@app.command()
def destroy(
    name: Annotated[str | None, typer.Argument(help="Name of the dodo to destroy")] = None,
    local: Annotated[
        bool, typer.Option("--local", help="Destroy default .dodo/ (no name)")
    ] = False,
):
    """Destroy a dodo and its data."""
    import shutil
    from pathlib import Path

    cfg = _get_config()

    # No name: --local destroys default .dodo/, otherwise error
    if not name:
        if local:
            target_dir = Path.cwd() / ".dodo"
        else:
            console.print(
                "[red]Error:[/red] Specify a dodo name, or use --local for default .dodo/"
            )
            raise typer.Exit(1)
    else:
        # Name provided: auto-detect local vs global (same as --dodo flag)
        # Check local first
        local_path = Path.cwd() / ".dodo" / name
        if local_path.exists():
            target_dir = local_path
        else:
            # Check parent directories
            found = False
            for parent in Path.cwd().parents:
                candidate = parent / ".dodo" / name
                if candidate.exists():
                    target_dir = candidate
                    found = True
                    break
                if parent == Path.home() or parent == Path("/"):
                    break

            if not found:
                # Check global
                global_path = cfg.config_dir / name
                if global_path.exists():
                    target_dir = global_path
                else:
                    console.print(f"[red]Error:[/red] Dodo '{name}' not found")
                    raise typer.Exit(1)

    if not target_dir.exists():
        location = str(target_dir).replace(str(Path.home()), "~")
        console.print(f"[red]Error:[/red] Dodo not found at {location}")
        raise typer.Exit(1)

    # Remove the directory
    shutil.rmtree(target_dir)

    location = str(target_dir).replace(str(Path.home()), "~")
    console.print(f"[green]✓[/green] Destroyed dodo at {location}")


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

    console.print(f"[bold]Dodo:[/bold] {target}")
    console.print(f"[bold]Backend:[/bold] {svc.backend_name}")
    console.print(f"[bold]Storage:[/bold] {svc.storage_path}")
    console.print(f"[bold]Todos:[/bold] {len(items)} total ({pending} pending, {done} done)")


@app.command()
def backend(
    name: Annotated[str | None, typer.Argument(help="Backend to set")] = None,
    migrate: Annotated[
        bool, typer.Option("--migrate", help="Migrate todos from current backend")
    ] = False,
    migrate_from: Annotated[
        str | None, typer.Option("--migrate-from", help="Source backend for migration")
    ] = None,
):
    """Show or set project backend."""
    from dodo.project_config import ProjectConfig, get_project_config_dir

    cfg = _get_config()
    project_id = _detect_project(worktree_shared=cfg.worktree_shared)

    if not project_id:
        console.print("[red]Error:[/red] No dodo found")
        raise typer.Exit(1)

    # Get project config directory (respects local_storage setting)
    project_dir = get_project_config_dir(cfg, project_id, cfg.worktree_shared)
    if not project_dir:
        console.print("[red]Error:[/red] Could not determine project config directory")
        raise typer.Exit(1)

    if name is None:
        # Show current backend
        config = ProjectConfig.load(project_dir)
        current = config.backend if config else cfg.default_backend
        console.print(f"[bold]Backend:[/bold] {current}")
        return

    # Set backend
    if migrate:
        # Get source backend name
        current_config = ProjectConfig.load(project_dir)
        source_backend = migrate_from or (
            current_config.backend if current_config else cfg.default_backend
        )

        if source_backend == name:
            console.print(f"[yellow]Already using {name} backend[/yellow]")
            return

        # Export from source backend
        console.print(f"[dim]Exporting from {source_backend}...[/dim]")
        source_svc = _get_service(cfg, project_id)
        items = source_svc._backend.export_all()

        if not items:
            console.print("[yellow]No todos to migrate[/yellow]")
        else:
            # Save new backend config first so import uses correct backend
            project_dir.mkdir(parents=True, exist_ok=True)
            new_config = ProjectConfig(backend=name)
            new_config.save(project_dir)

            # Import to new backend
            console.print(f"[dim]Importing to {name}...[/dim]")
            dest_svc = _get_service(cfg, project_id)
            imported, skipped = dest_svc._backend.import_all(items)

            console.print(f"[green]✓[/green] Migrated {imported} todos ({skipped} skipped)")
            console.print(f"[green]✓[/green] Backend set to: {name}")
            return

    project_dir.mkdir(parents=True, exist_ok=True)
    config = ProjectConfig(backend=name)
    config.save(project_dir)
    console.print(f"[green]✓[/green] Backend set to: {name}")


def _register_plugins_subapp() -> None:
    """Register the plugins subapp with the main app."""
    from dodo.cli_plugins import plugins_app

    @plugins_app.callback()
    def plugins_callback() -> None:
        """Register plugin commands lazily when plugins subcommand is accessed."""
        _register_plugin_commands()

    app.add_typer(plugins_app, name="plugins")


_register_plugins_subapp()


# Register AI commands subapp
def _register_ai_subapp() -> None:
    """Register the AI commands subapp lazily."""
    from dodo.ai_commands import ai_app

    app.add_typer(ai_app, name="ai")


_register_ai_subapp()


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
        console.print(f"[yellow]Ambiguous dodo '{partial}'. Matches:[/yellow]")
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
