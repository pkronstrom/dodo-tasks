"""CLI commands."""

import json
import sys
from typing import Annotated

import typer
from rich.console import Console

from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Status
from dodo.project import detect_project

app = typer.Typer(
    name="dodo",
    help="Todo router - manage todos across multiple backends.",
    no_args_is_help=False,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Launch interactive menu if no command given."""
    if ctx.invoked_subcommand is None:
        from dodo.ui.interactive import interactive_menu

        interactive_menu()


@app.command()
def add(
    text: Annotated[list[str], typer.Argument(help="Todo text")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
):
    """Add a todo item."""
    cfg = Config.load()

    if global_:
        target = "global"
        project_id = None
    else:
        project_id = detect_project(worktree_shared=cfg.worktree_shared)
        target = project_id or "global"

    svc = TodoService(cfg, project_id)
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

    cfg = Config.load()

    if global_:
        project_id = None
    else:
        project_id = _resolve_project(project) or detect_project(
            worktree_shared=cfg.worktree_shared
        )

    svc = TodoService(cfg, project_id)
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
):
    """Mark todo as done."""
    cfg = Config.load()
    project_id = detect_project(worktree_shared=cfg.worktree_shared)
    svc = TodoService(cfg, project_id)

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
    cfg = Config.load()
    project_id = detect_project(worktree_shared=cfg.worktree_shared)
    svc = TodoService(cfg, project_id)

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

    cfg = Config.load()
    project_id = None if last["target"] == "global" else last["target"]
    svc = TodoService(cfg, project_id)

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

    cfg = Config.load()
    project_id = detect_project(worktree_shared=cfg.worktree_shared)
    svc = TodoService(cfg, project_id)

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
    cfg = Config.load()
    project_id = detect_project(worktree_shared=cfg.worktree_shared)

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
    cfg = Config.load()

    if global_:
        project_id = None
    else:
        project_id = detect_project(worktree_shared=cfg.worktree_shared)

    svc = TodoService(cfg, project_id)
    items = svc.list()

    lines = []
    for item in items:
        data = {
            "id": item.id,
            "text": item.text,
            "status": item.status.value,
            "created_at": item.created_at.isoformat(),
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "project": item.project,
        }
        lines.append(json.dumps(data))

    content = "\n".join(lines)

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
    cfg = Config.load()

    if global_:
        project_id = None
        target = "global"
    else:
        project_id = detect_project(worktree_shared=cfg.worktree_shared)
        target = project_id or "global"

    svc = TodoService(cfg, project_id)
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

    app.add_typer(plugins_app, name="plugins")


_register_plugins_subapp()


# Helpers


def _resolve_project(partial: str | None) -> str | None:
    """Resolve partial project name to full project ID."""
    if not partial:
        return None

    cfg = Config.load()
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
    for item in svc.list():
        if item.id.startswith(partial_id):
            return item

    return None


def _save_last_action(action: str, id: str, target: str) -> None:
    """Save last action for undo."""
    cfg = Config.load()
    state_file = cfg.config_dir / ".last_action"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"action": action, "id": id, "target": target}))


def _load_last_action() -> dict | None:
    """Load last action."""
    cfg = Config.load()
    state_file = cfg.config_dir / ".last_action"
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text())


def _clear_last_action() -> None:
    """Clear last action after undo."""
    cfg = Config.load()
    state_file = cfg.config_dir / ".last_action"
    if state_file.exists():
        state_file.unlink()


def _register_plugin_commands() -> None:
    """Allow plugins to register additional CLI commands under 'dodo plugins <name>'."""
    from dodo.cli_plugins import plugins_app
    from dodo.plugins import apply_hooks

    cfg = Config.load()
    apply_hooks("register_commands", plugins_app, cfg)


# Register plugin commands (lazy - only when CLI is actually used)
_register_plugin_commands()
