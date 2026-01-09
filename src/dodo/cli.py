"""CLI commands."""

import json
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

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
    text: Annotated[str, typer.Argument(help="Todo text")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
):
    """Add a todo item."""
    cfg = Config.load()

    if global_:
        target = "global"
        project_id = None
    else:
        project_id = detect_project()
        target = project_id or "global"

    svc = TodoService(cfg, project_id)
    item = svc.add(text)

    _save_last_action("add", item.id, target)

    dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
    console.print(f"[green]✓[/green] Added to {dest}: {item.text} [dim]({item.id})[/dim]")


@app.command(name="list")
def list_todos(
    project: Annotated[str | None, typer.Option("-p", "--project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    done: Annotated[bool, typer.Option("--done", help="Show completed")] = False,
    all_: Annotated[bool, typer.Option("-a", "--all", help="Show all")] = False,
):
    """List todos."""
    cfg = Config.load()

    if global_:
        project_id = None
    else:
        project_id = project or detect_project()

    svc = TodoService(cfg, project_id)
    status = None if all_ else (Status.DONE if done else Status.PENDING)
    items = svc.list(status=status)
    _print_todos(items)


@app.command()
def done(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
):
    """Mark todo as done."""
    cfg = Config.load()
    project_id = detect_project()
    svc = TodoService(cfg, project_id)

    # Try to find matching ID
    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    completed = svc.complete(item.id)
    console.print(f"[green]✓[/green] Done: {completed.text}")


@app.command()
def rm(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
):
    """Remove a todo."""
    cfg = Config.load()
    project_id = detect_project()
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

    if not cfg.ai_enabled:
        console.print("[yellow]AI not enabled.[/yellow] Set DODO_AI_ENABLED=true")
        raise typer.Exit(1)

    project_id = detect_project()
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
    project_id = detect_project()

    if not project_id:
        console.print("[red]Error:[/red] Not in a git repository")
        raise typer.Exit(1)

    cfg = Config.load()

    if local:
        cfg.set("local_storage", True)

    console.print(f"[green]✓[/green] Initialized project: {project_id}")


@app.command()
def config():
    """Open interactive config editor."""
    from dodo.ui.interactive import interactive_config

    interactive_config()


# Helpers


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


def _print_todos(items: list) -> None:
    """Pretty print todos as table."""
    if not items:
        console.print("[dim]No todos[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Status", width=6)
    table.add_column("Created", width=16)
    table.add_column("Todo")

    for item in items:
        status = "[green]✓[/green]" if item.status == Status.DONE else "[ ]"
        created = item.created_at.strftime("%Y-%m-%d %H:%M")
        table.add_row(item.id, status, created, item.text)

    console.print(table)


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
