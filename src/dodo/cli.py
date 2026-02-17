"""CLI commands."""

from __future__ import annotations

import json
import re
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

# Security: Pattern for valid dodo names (prevents path traversal)
_VALID_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def _validate_dodo_name(name: str | None) -> str | None:
    """Validate dodo name to prevent path traversal attacks.

    Raises typer.BadParameter if name contains unsafe characters.
    """
    if name is None:
        return None
    if not _VALID_NAME_PATTERN.match(name):
        raise typer.BadParameter(
            f"Invalid dodo name '{name}'. Names must start with alphanumeric "
            "and contain only letters, numbers, underscores, and hyphens."
        )
    return name


def _get_config() -> Config:
    """Lazy import and load config."""
    from dodo.config import Config

    return Config.load()


def _get_service(config: Config, project_id: str | None) -> TodoService:
    """Lazy import and create service."""
    from dodo.core import TodoService

    return TodoService(config, project_id)


def _resolve_dodo(
    config: Config,
    dodo_name: str | None = None,
    global_: bool = False,
) -> tuple[str | None, Path | None]:
    """Resolve which dodo to use. Wrapper for shared resolve_dodo.

    Returns tuple for backward compatibility (supports unpacking).
    The underlying resolve_dodo returns ResolvedDodo which supports __iter__.

    Raises typer.Exit(1) if dodo_name is invalid.
    """
    from dodo.resolve import InvalidDodoNameError, resolve_dodo

    try:
        result = resolve_dodo(config, dodo_name, global_)
        return result.name, result.path
    except InvalidDodoNameError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


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
def main(
    ctx: typer.Context,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
):
    """Launch interactive menu if no command given."""
    # Store global options in context for subcommands to access
    ctx.ensure_object(dict)
    ctx.obj["global_"] = global_
    ctx.obj["dodo"] = dodo

    if ctx.invoked_subcommand is None:
        from dodo.ui.interactive import interactive_menu

        interactive_menu(global_=global_, dodo=dodo)


def _get_dodo_from_ctx(
    ctx: typer.Context,
    dodo: str | None,
    global_: bool,
) -> tuple[str | None, bool]:
    """Get dodo and global_ from command args or parent context."""
    # Command-level args take precedence
    if dodo is not None:
        return dodo, global_
    if global_:
        return None, True
    # Fall back to parent context (global options)
    if ctx.obj:
        return ctx.obj.get("dodo"), ctx.obj.get("global_", False)
    return None, False


@app.command()
def add(
    ctx: typer.Context,
    text: Annotated[str, typer.Argument(help="Todo text (use quotes)")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    priority: Annotated[
        str | None,
        typer.Option("-p", "--priority", help="Priority: critical/high/normal/low/someday"),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("-t", "--tag", help="Tag (can repeat, comma-separated)"),
    ] = None,
    # Keep old --tags for backward compatibility
    tags: Annotated[str | None, typer.Option("--tags", help="Comma-separated tags (deprecated, use -t)")] = None,
    due: Annotated[str | None, typer.Option("--due", help="Due date (YYYY-MM-DD)")] = None,
    meta: Annotated[
        list[str] | None,
        typer.Option("--meta", help="Metadata key=value (can repeat)"),
    ] = None,
):
    """Add a todo item."""
    from datetime import datetime

    from dodo.models import Priority

    cfg = _get_config()
    dodo, global_ = _get_dodo_from_ctx(ctx, dodo, global_)
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
        target = dodo_id or "local"
        undo_path = explicit_path
    else:
        svc = _get_service(cfg, dodo_id)
        target = dodo_id or "global"
        undo_path = None

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

    # Parse tags - merge from multiple sources
    parsed_tags = []

    # Handle new -t/--tag flags (list of potentially comma-separated values)
    if tag:
        for t in tag:
            parsed_tags.extend(x.strip() for x in t.split(",") if x.strip())

    # Handle old --tags flag for backward compatibility
    if tags:
        parsed_tags.extend(x.strip() for x in tags.split(",") if x.strip())

    # Deduplicate while preserving order
    seen = set()
    unique_tags = []
    for t in parsed_tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)

    parsed_tags = unique_tags if unique_tags else None

    # Parse due date
    parsed_due = None
    if due:
        try:
            parsed_due = datetime.fromisoformat(due)
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid date '{due}'. Use YYYY-MM-DD format.")
            raise typer.Exit(1)

    # Parse metadata
    parsed_metadata = None
    if meta:
        parsed_metadata = {}
        for m in meta:
            if "=" not in m:
                console.print(f"[red]Error:[/red] Invalid metadata '{m}'. Use key=value format.")
                raise typer.Exit(1)
            k, v = m.split("=", 1)
            parsed_metadata[k.strip()] = v.strip()

    item = svc.add(text, priority=parsed_priority, tags=parsed_tags,
                   due_at=parsed_due, metadata=parsed_metadata)

    _save_last_action("add", item.id, target, undo_path)

    # Format output with priority and tags
    output_text = item.text
    if item.priority:
        output_text += f" !{item.priority.value}"
    if item.tags:
        output_text += " " + " ".join(f"#{t}" for t in item.tags)

    dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
    console.print(f"[green]✓[/green] Added to {dest}: {output_text} [dim]({item.id})[/dim]")


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
    ctx: typer.Context,
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
    dodo, global_ = _get_dodo_from_ctx(ctx, dodo, global_)
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
    ctx: typer.Context,
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
):
    """Mark todo as done."""
    cfg = _get_config()
    dodo, global_ = _get_dodo_from_ctx(ctx, dodo, global_)
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
        undo_path = explicit_path
    else:
        svc = _get_service(cfg, dodo_id)
        undo_path = None

    target = dodo_id or "global"

    # Try to find matching ID
    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    # Save snapshot before modification
    _save_last_action("done", [item], target, undo_path)

    completed = svc.complete(item.id)
    console.print(f"[green]✓[/green] Done: {completed.text}")


@app.command(name="remove")
@app.command()
def rm(
    ctx: typer.Context,
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
):
    """Remove a todo."""
    cfg = _get_config()
    dodo, global_ = _get_dodo_from_ctx(ctx, dodo, global_)
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
        undo_path = explicit_path
    else:
        svc = _get_service(cfg, dodo_id)
        undo_path = None

    target = dodo_id or "global"

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    # Save snapshot before deletion
    _save_last_action("rm", [item], target, undo_path)

    svc.delete(item.id)
    console.print(f"[yellow]✓[/yellow] Removed: {item.text}")


@app.command()
def undo():
    """Undo the last operation."""
    from dodo.models import Priority, Status

    last = _load_last_action()

    if not last:
        console.print("[yellow]Nothing to undo[/yellow]")
        raise typer.Exit(0)

    action = last.get("action")
    target = last.get("target")
    items = last.get("items", [])

    # Handle old format (single id field)
    if "id" in last and not items:
        items = [{"id": last["id"]}]

    if not items:
        console.print("[yellow]Nothing to undo[/yellow]")
        _clear_last_action()
        raise typer.Exit(0)

    cfg = _get_config()

    # Use explicit path if stored (for local dodos), otherwise use target name
    explicit_path_str = last.get("explicit_path")
    if explicit_path_str:
        svc = _get_service_with_path(cfg, Path(explicit_path_str))
        project_id = None
    else:
        project_id = None if target == "global" else target
        svc = _get_service(cfg, project_id)

    restored = 0
    failed = 0

    if action == "add":
        # Undo add: delete the added items
        for item_data in items:
            item_id = item_data.get("id")
            if item_id:
                try:
                    svc.delete(item_id)
                    restored += 1
                except Exception as e:
                    failed += 1
                    console.print(f"[red]Failed to remove {item_id}:[/red] {e}")
        if restored > 0:
            console.print(f"[yellow]↩[/yellow] Undid add: removed {restored} item(s)")
        if failed > 0:
            console.print(f"[red]Failed to undo {failed} item(s)[/red]")

    elif action == "done":
        # Undo done: restore to pending status
        for item_data in items:
            item_id = item_data.get("id")
            if item_id:
                try:
                    # Update status back to pending
                    svc._backend.update(item_id, Status.PENDING)
                    restored += 1
                except Exception as e:
                    failed += 1
                    console.print(f"[red]Failed to restore {item_id}:[/red] {e}")
        if restored > 0:
            console.print(f"[yellow]↩[/yellow] Undid done: restored {restored} item(s) to pending")
        if failed > 0:
            console.print(f"[red]Failed to undo {failed} item(s)[/red]")

    elif action == "rm":
        # Undo rm: re-create the deleted items
        for item_data in items:
            try:
                # Re-create with original data
                priority = None
                if item_data.get("priority"):
                    try:
                        priority = Priority(item_data["priority"])
                    except ValueError:
                        pass

                svc._backend.add(
                    text=item_data.get("text", ""),
                    project=project_id,
                    priority=priority,
                    tags=item_data.get("tags"),
                )
                restored += 1
            except Exception as e:
                failed += 1
                text_preview = item_data.get("text", "")[:30]
                console.print(f"[red]Failed to restore '{text_preview}...':[/red] {e}")
        if restored > 0:
            console.print(f"[yellow]↩[/yellow] Undid rm: restored {restored} item(s)")
        if failed > 0:
            console.print(f"[red]Failed to undo {failed} item(s)[/red]")

    elif action == "edit":
        # Undo edit: restore original values
        for item_data in items:
            item_id = item_data.get("id")
            if item_id:
                try:
                    if "priority" in item_data:
                        priority = None
                        if item_data["priority"]:
                            try:
                                priority = Priority(item_data["priority"])
                            except ValueError:
                                pass
                        svc.update_priority(item_id, priority)
                    if "tags" in item_data:
                        svc.update_tags(item_id, item_data.get("tags"))
                    if "text" in item_data:
                        svc.update_text(item_id, item_data["text"])
                    restored += 1
                except Exception as e:
                    failed += 1
                    console.print(f"[red]Failed to restore {item_id}:[/red] {e}")
        if restored > 0:
            console.print(f"[yellow]↩[/yellow] Undid edit: restored {restored} item(s)")
        if failed > 0:
            console.print(f"[red]Failed to undo {failed} item(s)[/red]")

    else:
        console.print(f"[yellow]Unknown action: {action}[/yellow]")

    # Report if nothing was actually undone
    if restored == 0 and failed == 0:
        console.print("[yellow]Nothing to undo[/yellow]")

    _clear_last_action()


@app.command()
def new(
    name: Annotated[str | None, typer.Argument(help="Name for the dodo")] = None,
    local: Annotated[bool, typer.Option("--local", help="Create in .dodo/ locally")] = False,
    backend: Annotated[
        str | None, typer.Option("--backend", "-b", help="Backend (sqlite|markdown|obsidian)")
    ] = None,
    link: Annotated[
        bool, typer.Option("--link", "-l", help="Link current directory to this dodo")
    ] = True,
):
    """Create a new dodo.

    Auto-names from git repo or current directory if no name given.
    With --local, creates at project root (git root if in repo, else current dir).
    """
    from pathlib import Path
    from dodo.project import _get_git_root
    from dodo.project_config import ProjectConfig

    # Validate user-provided name for path safety
    _validate_dodo_name(name)

    cfg = _get_config()
    backend_name = backend or cfg.default_backend
    cwd = Path.cwd()

    # Detect git root
    git_root = _get_git_root(cwd)

    # Auto-name from git repo or directory if not provided
    auto_name = None
    if not name:
        if git_root:
            auto_name = git_root.name
        else:
            auto_name = cwd.name

    # Determine the dodo name (auto-names come from filesystem, already safe)
    dodo_name = name or auto_name

    # Determine base directory for local storage
    project_root = git_root if git_root else cwd

    # Determine target directory
    if local:
        # Local storage at project root
        base = project_root / ".dodo"
        if name:
            target_dir = base / name
        else:
            target_dir = base
    else:
        # Centralized in ~/.config/dodo/
        target_dir = cfg.config_dir / dodo_name

    # Print detection message
    if git_root and not name:
        git_path = str(git_root).replace(str(Path.home()), "~")
        console.print(f"Detected git repo '{git_root.name}' at {git_path}")

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
    if local:
        if name:
            console.print(f"[green]✓[/green] Created local dodo '{name}' at {location}")
        else:
            console.print(f"[green]✓[/green] Created local dodo at {location}")
    else:
        console.print(f"[green]✓[/green] Created dodo '{dodo_name}' at {location}")

    # Link current directory to this dodo via config mapping
    if link and not local and dodo_name:
        cwd_str = str(cwd)
        existing = cfg.get_directory_mapping(cwd_str)
        if existing:
            console.print(f"[dim]  Directory already mapped to '{existing}'[/dim]")
        else:
            cfg.set_directory_mapping(cwd_str, dodo_name)
            console.print(f"[dim]  Mapped {cwd.name} → {dodo_name}[/dim]")


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

    # Validate user-provided name for path safety
    _validate_dodo_name(name)

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
def use(
    name: Annotated[str, typer.Argument(help="Name of the dodo to use")],
):
    """Set current directory to use a specific dodo.

    This stores a mapping so commands from this directory use the specified dodo.
    """
    from pathlib import Path

    cfg = _get_config()
    cwd = str(Path.cwd())

    # Check if the named dodo exists (local or central)
    found = False

    # Check local
    local_path = Path.cwd() / ".dodo" / name
    if local_path.exists():
        found = True

    # Check central
    if not found:
        central_path = cfg.config_dir / name
        if central_path.exists():
            found = True

    if not found:
        console.print(f"[red]Error:[/red] Dodo '{name}' not found")
        console.print(f"  Create it first with: dodo new {name}")
        raise typer.Exit(1)

    # Check if already mapped
    existing = cfg.get_directory_mapping(cwd)
    if existing:
        console.print(f"[yellow]Directory already uses '{existing}'[/yellow]")
        console.print("  Use 'dodo unuse' to remove the mapping first")
        raise typer.Exit(1)

    cfg.set_directory_mapping(cwd, name)
    console.print(f"[green]✓[/green] Now using '{name}' for {Path.cwd().name}")


@app.command()
def unuse():
    """Remove the dodo mapping for current directory."""
    from pathlib import Path

    cfg = _get_config()
    cwd = str(Path.cwd())

    if cfg.remove_directory_mapping(cwd):
        console.print(f"[green]✓[/green] Removed mapping for {Path.cwd().name}")
    else:
        console.print("[yellow]No mapping exists for this directory[/yellow]")


@app.command()
def config():
    """Open interactive config editor."""
    from dodo.ui.interactive import interactive_config

    interactive_config()


@app.command()
def export(
    ctx: typer.Context,
    output: Annotated[str | None, typer.Option("-o", "--output", help="Output file")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Global todos")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    format_: Annotated[str, typer.Option("-f", "--format", help="Output format: jsonl, csv, tsv, txt, md")] = "jsonl",
):
    """Export todos to various formats."""
    from dodo.formatters import get_formatter

    cfg = _get_config()
    dodo, global_ = _get_dodo_from_ctx(ctx, dodo, global_)
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)
    items = svc.list()

    try:
        formatter = get_formatter(format_)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

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
    dodo_id, explicit_path = _resolve_dodo(cfg, global_=global_)
    target = dodo_id or "global"

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)
    items = svc.list()

    pending = sum(1 for i in items if i.status == Status.PENDING)
    done = sum(1 for i in items if i.status == Status.DONE)

    console.print(f"[bold]Dodo:[/bold] {target}")
    console.print(f"[bold]Backend:[/bold] {svc.backend_name}")
    console.print(f"[bold]Storage:[/bold] {svc.storage_path}")
    console.print(f"[bold]Todos:[/bold] {len(items)} total ({pending} pending, {done} done)")


@app.command()
def show():
    """Show detected dodos and current default."""
    from pathlib import Path
    from dodo.models import Status
    from dodo.project import _get_git_root
    from dodo.project_config import ProjectConfig

    cfg = _get_config()
    cwd = Path.cwd()

    # Detect context
    git_root = _get_git_root(cwd)

    console.print("[bold]Context:[/bold]")
    if git_root:
        console.print(f"  Git repo: {git_root.name} ({git_root})")
    console.print(f"  Directory: {cwd}")
    console.print()

    # Find available dodos
    console.print("[bold]Available dodos:[/bold]")

    available = []

    # Check local .dodo/
    local_dodo = cwd / ".dodo"
    if not local_dodo.exists() and git_root:
        local_dodo = git_root / ".dodo"

    if local_dodo.exists():
        # Default local dodo
        if (local_dodo / "dodo.json").exists() or (local_dodo / "dodo.db").exists():
            project_cfg = ProjectConfig.load(local_dodo)
            backend = project_cfg.backend if project_cfg else cfg.default_backend
            available.append(("local", str(local_dodo), "local", backend))
        # Named local dodos
        for subdir in local_dodo.iterdir():
            if subdir.is_dir() and (subdir / "dodo.json").exists():
                project_cfg = ProjectConfig.load(subdir)
                backend = project_cfg.backend if project_cfg else cfg.default_backend
                available.append((subdir.name, str(subdir), "local", backend))

    # Check central dodos
    if cfg.config_dir.exists():
        for item in cfg.config_dir.iterdir():
            if item.is_dir() and item.name not in ("projects", ".last_action"):
                if (item / "dodo.json").exists() or (item / "dodo.db").exists():
                    project_cfg = ProjectConfig.load(item)
                    backend = project_cfg.backend if project_cfg else cfg.default_backend
                    available.append((item.name, str(item), "central", backend))

    # Determine current default
    dodo_id, explicit_path = _resolve_dodo(cfg)
    current = dodo_id or "global"

    if not available:
        console.print("  [dim](none created yet)[/dim]")
        console.print()
        console.print("[bold]Current:[/bold] global (fallback)")
        console.print("[dim]Hint: Run 'dodo new' to create a dodo for this project[/dim]")
        return

    for name, path, location, backend in available:
        marker = "→ " if name == current else "  "
        path_short = path.replace(str(Path.home()), "~")
        hint = "(default)" if name == current else f"(use: dodo -d {name})"
        console.print(f"  {marker}[cyan]{name}[/cyan]  [magenta]{backend}[/magenta]  {path_short}  [dim]{hint}[/dim]")

    console.print()

    # Show stats for current
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    items = svc.list()
    pending = sum(1 for i in items if i.status == Status.PENDING)
    done_count = sum(1 for i in items if i.status == Status.DONE)

    console.print(f"[bold]Current:[/bold] {current} ({pending} pending, {done_count} done)")


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
    dodo_id, explicit_path = _resolve_dodo(cfg)

    if not dodo_id and not explicit_path:
        console.print("[red]Error:[/red] No dodo found")
        raise typer.Exit(1)

    # Get project config directory
    if explicit_path:
        project_dir = explicit_path
    else:
        project_dir = get_project_config_dir(cfg, dodo_id)
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
        source_svc = _get_service(cfg, dodo_id)
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
            dest_svc = _get_service(cfg, dodo_id)
            imported, skipped = dest_svc._backend.import_all(items)

            console.print(f"[green]✓[/green] Migrated {imported} todos ({skipped} skipped)")
            console.print(f"[green]✓[/green] Backend set to: {name}")
            return

    project_dir.mkdir(parents=True, exist_ok=True)
    config = ProjectConfig(backend=name)
    config.save(project_dir)
    console.print(f"[green]✓[/green] Backend set to: {name}")


# --- meta sub-app ---

meta_app = typer.Typer(name="meta", help="Manage todo metadata.")


@meta_app.command(name="show")
def meta_show(
    id: Annotated[str, typer.Argument(help="Todo ID")],
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """Show metadata for a todo."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    if not item.metadata:
        console.print("[dim]No metadata[/dim]")
        return

    for k, v in item.metadata.items():
        console.print(f"  [cyan]{k}[/cyan] = {v}")


@meta_app.command(name="set")
def meta_set(
    id: Annotated[str, typer.Argument(help="Todo ID")],
    key: Annotated[str, typer.Argument(help="Metadata key")],
    value: Annotated[str, typer.Argument(help="Metadata value")],
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """Set a metadata key on a todo."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    try:
        updated = svc.set_metadata_key(item.id, key, value)
    except NotImplementedError:
        console.print("[red]Error:[/red] This backend does not support metadata operations.")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Set {key}={value} on {updated.text}")


@meta_app.command(name="rm")
def meta_rm(
    id: Annotated[str, typer.Argument(help="Todo ID")],
    key: Annotated[str, typer.Argument(help="Metadata key to remove")],
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """Remove a metadata key from a todo."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    try:
        updated = svc.remove_metadata_key(item.id, key)
    except NotImplementedError:
        console.print("[red]Error:[/red] This backend does not support metadata operations.")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Removed {key} from {updated.text}")


@meta_app.command(name="ls")
def meta_ls(
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """List todos with metadata."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    items = [i for i in svc.list() if i.metadata]
    if not items:
        console.print("[dim]No todos with metadata[/dim]")
        return

    for item in items:
        meta_str = " ".join(f"[cyan]{k}[/cyan]={v}" for k, v in item.metadata.items())
        console.print(f"  {item.text} [dim]({item.id})[/dim]  {meta_str}")


app.add_typer(meta_app, name="meta")


# --- tag sub-app ---

tag_app = typer.Typer(name="tag", help="Manage todo tags.")


@tag_app.command(name="add")
def tag_add(
    id: Annotated[str, typer.Argument(help="Todo ID")],
    tag: Annotated[str, typer.Argument(help="Tag to add")],
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """Add a tag to a todo."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    try:
        updated = svc.add_tag(item.id, tag)
    except NotImplementedError:
        console.print("[red]Error:[/red] This backend does not support tag operations.")
        raise typer.Exit(1)
    tags_str = " ".join(f"#{t}" for t in (updated.tags or []))
    console.print(f"[green]✓[/green] Added #{tag}: {updated.text} {tags_str}")


@tag_app.command(name="rm")
def tag_rm(
    id: Annotated[str, typer.Argument(help="Todo ID")],
    tag: Annotated[str, typer.Argument(help="Tag to remove")],
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """Remove a tag from a todo."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    try:
        updated = svc.remove_tag(item.id, tag)
    except NotImplementedError:
        console.print("[red]Error:[/red] This backend does not support tag operations.")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Removed #{tag} from {updated.text}")


app.add_typer(tag_app, name="tag")


# --- mcp command ---


@app.command(hidden=True)
def mcp():
    """Run as stdio MCP server for AI agent integration.

    Add to Claude Code:  claude mcp add dodo -- dodo mcp
    """
    try:
        from dodo.plugins.server.mcp_server import run_stdio
    except ImportError:
        console.print("[red]Error:[/red] MCP requires: pip install dodo-tasks[server]")
        raise typer.Exit(1)
    cfg = _get_config()
    run_stdio(cfg)


# --- due command ---

@app.command()
def due(
    id: Annotated[str, typer.Argument(help="Todo ID")],
    date: Annotated[str, typer.Argument(help="Due date (YYYY-MM-DD) or 'none' to clear")],
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """Set or clear a todo's due date."""
    from datetime import datetime

    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    try:
        if date.lower() == "none":
            updated = svc.update_due_at(item.id, None)
            console.print(f"[green]✓[/green] Cleared due date for {updated.text}")
        else:
            try:
                parsed = datetime.fromisoformat(date)
            except ValueError:
                console.print(
                    f"[red]Error:[/red] Invalid date '{date}'. Use YYYY-MM-DD format."
                )
                raise typer.Exit(1)
            updated = svc.update_due_at(item.id, parsed)
            console.print(f"[green]✓[/green] Due {date}: {updated.text}")
    except NotImplementedError:
        console.print("[red]Error:[/red] This backend does not support due dates.")
        raise typer.Exit(1)


_plugin_commands_registered = False


def _register_plugin_commands() -> None:
    """Allow plugins to register additional CLI commands under 'dodo plugins <name>'.

    Called when 'plugins' subcommand is detected to ensure commands are registered
    before Typer validates subcommands.
    """
    global _plugin_commands_registered
    if _plugin_commands_registered:
        return
    _plugin_commands_registered = True

    from dodo.cli_plugins import plugins_app
    from dodo.plugins import apply_hooks

    cfg = _get_config()
    apply_hooks("register_commands", plugins_app, cfg)


def _register_plugins_subapp() -> None:
    """Register the plugins subapp with the main app."""
    from dodo.cli_plugins import plugins_app

    # Register plugin commands eagerly when 'plugins' subcommand is likely
    # This is needed because Typer validates subcommands before callbacks run
    if len(sys.argv) > 2 and sys.argv[1] == "plugins":
        _register_plugin_commands()

    app.add_typer(plugins_app, name="plugins")


_register_plugins_subapp()

# Register bulk subcommand
from dodo.cli_bulk import bulk_app
app.add_typer(bulk_app, name="bulk")


# Helpers


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


def _save_last_action(action: str, id_or_items, target: str, explicit_path: Path | None = None) -> None:
    """Save last action for undo. Delegates to shared undo module."""
    from dodo.undo import save_undo_state

    cfg = _get_config()
    save_undo_state(cfg, action, id_or_items, target, explicit_path)


def _load_last_action() -> dict | None:
    """Load last action. Delegates to shared undo module."""
    from dodo.undo import load_undo_state

    cfg = _get_config()
    return load_undo_state(cfg)


def _clear_last_action() -> None:
    """Clear last action after undo. Delegates to shared undo module."""
    from dodo.undo import clear_undo_state

    cfg = _get_config()
    clear_undo_state(cfg)
