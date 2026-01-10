"""CLI commands for graph/dependency features."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

console = Console()

# Subapp for `dodo dep` commands
dep_app = typer.Typer(
    name="dep",
    help="Manage todo dependencies.",
    no_args_is_help=True,
)


def _get_graph_adapter():
    """Get adapter with graph wrapper (if available)."""
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.project import detect_project

    cfg = Config.load()
    project_id = detect_project()
    svc = TodoService(cfg, project_id)

    adapter = svc._adapter
    if not hasattr(adapter, "get_ready"):
        console.print("[red]Error:[/red] Graph plugin requires SQLite adapter")
        console.print("[dim]Set adapter with: dodo config (then select sqlite)[/dim]")
        raise typer.Exit(1)

    return adapter, project_id


def ready() -> None:
    """List todos with no blocking dependencies (ready to work on)."""
    adapter, project_id = _get_graph_adapter()

    items = adapter.get_ready(project_id)

    if not items:
        console.print("[dim]No ready todos[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Todo")

    for item in items:
        table.add_row(item.id, item.text)

    console.print(f"[green]Ready to work on ({len(items)}):[/green]")
    console.print(table)


def blocked() -> None:
    """List todos that are blocked by other todos."""
    adapter, project_id = _get_graph_adapter()

    items = adapter.get_blocked_todos(project_id)

    if not items:
        console.print("[dim]No blocked todos[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Todo")
    table.add_column("Blocked by", style="yellow")

    for item in items:
        blockers = adapter.get_blockers(item.id)
        blocker_text = ", ".join(blockers[:3])
        if len(blockers) > 3:
            blocker_text += f" (+{len(blockers) - 3} more)"
        table.add_row(item.id, item.text, blocker_text)

    console.print(f"[yellow]Blocked todos ({len(items)}):[/yellow]")
    console.print(table)


@dep_app.command(name="add")
def add_dep(
    blocker: Annotated[str, typer.Argument(help="ID of blocking todo")],
    blocked: Annotated[str, typer.Argument(help="ID of blocked todo")],
) -> None:
    """Add a dependency: <blocker> blocks <blocked>."""
    adapter, _ = _get_graph_adapter()

    # Validate both todos exist
    if not adapter.get(blocker):
        console.print(f"[red]Error:[/red] Todo not found: {blocker}")
        raise typer.Exit(1)
    if not adapter.get(blocked):
        console.print(f"[red]Error:[/red] Todo not found: {blocked}")
        raise typer.Exit(1)

    adapter.add_dependency(blocker, blocked)
    console.print(f"[green]Added:[/green] {blocker} blocks {blocked}")


@dep_app.command(name="rm")
def remove_dep(
    blocker: Annotated[str, typer.Argument(help="ID of blocking todo")],
    blocked: Annotated[str, typer.Argument(help="ID of blocked todo")],
) -> None:
    """Remove a dependency."""
    adapter, _ = _get_graph_adapter()

    adapter.remove_dependency(blocker, blocked)
    console.print(f"[yellow]Removed:[/yellow] {blocker} no longer blocks {blocked}")


@dep_app.command(name="list")
def list_deps() -> None:
    """List all dependencies."""
    adapter, _ = _get_graph_adapter()

    deps = adapter.list_all_dependencies()

    if not deps:
        console.print("[dim]No dependencies[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Blocker", style="cyan")
    table.add_column("Blocks", style="yellow")

    for blocker_id, blocked_id in deps:
        table.add_row(blocker_id, blocked_id)

    console.print(f"[bold]Dependencies ({len(deps)}):[/bold]")
    console.print(table)
