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


def _get_graph_backend(
    dodo: str | None = None,
    global_: bool = False,
):
    """Get backend with graph wrapper (if available)."""
    from dodo.backends.base import GraphCapable
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.resolve import resolve_dodo

    cfg = Config.load()
    result = resolve_dodo(cfg, dodo, global_)

    if result.path:
        svc = TodoService(cfg, project_id=None, storage_path=result.path)
    else:
        svc = TodoService(cfg, result.name)

    backend = svc.backend
    if not isinstance(backend, GraphCapable):
        console.print("[red]Error:[/red] Graph plugin requires SQLite backend")
        console.print("[dim]Set backend with: dodo config (then select sqlite)[/dim]")
        raise typer.Exit(1)

    return backend, result.name


def ready(
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
) -> None:
    """List todos with no blocking dependencies (ready to work on)."""
    backend, project_id = _get_graph_backend(dodo, global_)

    items = backend.get_ready(project_id)

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


def blocked(
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
) -> None:
    """List todos that are blocked by other todos."""
    backend, project_id = _get_graph_backend(dodo, global_)

    items = backend.get_blocked_todos(project_id)

    if not items:
        console.print("[dim]No blocked todos[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Todo")
    table.add_column("Blocked by", style="yellow")

    for item in items:
        blockers = backend.get_blockers(item.id)
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
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
) -> None:
    """Add a dependency: <blocker> blocks <blocked>."""
    backend, _ = _get_graph_backend(dodo, global_)

    # Validate both todos exist
    if not backend.get(blocker):
        console.print(f"[red]Error:[/red] Todo not found: {blocker}")
        raise typer.Exit(1)
    if not backend.get(blocked):
        console.print(f"[red]Error:[/red] Todo not found: {blocked}")
        raise typer.Exit(1)

    backend.add_dependency(blocker, blocked)
    console.print(f"[green]Added:[/green] {blocker} blocks {blocked}")


@dep_app.command(name="rm")
def remove_dep(
    blocker: Annotated[str, typer.Argument(help="ID of blocking todo")],
    blocked: Annotated[str, typer.Argument(help="ID of blocked todo")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
) -> None:
    """Remove a dependency."""
    backend, _ = _get_graph_backend(dodo, global_)

    backend.remove_dependency(blocker, blocked)
    console.print(f"[yellow]Removed:[/yellow] {blocker} no longer blocks {blocked}")


@dep_app.command(name="list")
def list_deps(
    tree: Annotated[bool, typer.Option("--tree", "-t", help="Show as tree")] = False,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
) -> None:
    """List all dependencies."""
    backend, project_id = _get_graph_backend(dodo, global_)

    if tree:
        # Get all todos with blocked_by info
        items = backend.list(project=project_id)
        if not items:
            console.print("[dim]No todos[/dim]")
            return

        from dodo.plugins.graph.tree import TreeFormatter

        formatter = TreeFormatter()
        output = formatter.format(items)
        console.print(output)
        return

    deps = backend.list_all_dependencies()

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
