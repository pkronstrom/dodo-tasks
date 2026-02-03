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
    """Get backend with graph wrapper (if available).

    Returns:
        Tuple of (backend, project_id, config)
        Note: project_id is None for local dodos with explicit paths,
        since tasks in those dodos have project=None.
    """
    from dodo.backends.base import GraphCapable
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.resolve import resolve_dodo

    cfg = Config.load()
    result = resolve_dodo(cfg, dodo, global_)

    if result.path:
        svc = TodoService(cfg, project_id=None, storage_path=result.path)
        # Local dodos with explicit paths store tasks with project=None
        project_id = None
    else:
        svc = TodoService(cfg, result.name)
        project_id = result.name

    backend = svc.backend
    if not isinstance(backend, GraphCapable):
        console.print("[red]Error:[/red] Graph plugin requires SQLite backend")
        console.print("[dim]Set backend with: dodo config (then select sqlite)[/dim]")
        raise typer.Exit(1)

    return backend, project_id, cfg


def _format_items(items, format_: str | None, cfg):
    """Format items using the formatter system."""
    from dodo.formatters import get_formatter
    from dodo.plugins import apply_hooks

    format_str = format_ or cfg.default_format
    try:
        formatter = get_formatter(format_str)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Allow plugins to extend/wrap the formatter
    formatter = apply_hooks("extend_formatter", formatter, cfg)

    return formatter.format(items)


def ready(
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    format_: Annotated[str | None, typer.Option("-f", "--format", help="Output format")] = None,
) -> None:
    """List todos with no blocking dependencies (ready to work on)."""
    backend, project_id, cfg = _get_graph_backend(dodo, global_)

    items = backend.get_ready(project_id)

    if not items:
        console.print("[dim]No ready todos[/dim]")
        return

    output = _format_items(items, format_, cfg)
    console.print(output)


def blocked(
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    format_: Annotated[str | None, typer.Option("-f", "--format", help="Output format")] = None,
) -> None:
    """List todos that are blocked by other todos."""
    backend, project_id, cfg = _get_graph_backend(dodo, global_)

    items = backend.get_blocked_todos(project_id)

    if not items:
        console.print("[dim]No blocked todos[/dim]")
        return

    output = _format_items(items, format_, cfg)
    console.print(output)


@dep_app.command(name="add")
def add_dep(
    blocker: Annotated[str, typer.Argument(help="ID of blocking todo")],
    blocked: Annotated[str, typer.Argument(help="ID of blocked todo")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
) -> None:
    """Add a dependency: <blocker> blocks <blocked>."""
    backend, _, _ = _get_graph_backend(dodo, global_)

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
    backend, _, _ = _get_graph_backend(dodo, global_)

    backend.remove_dependency(blocker, blocked)
    console.print(f"[yellow]Removed:[/yellow] {blocker} no longer blocks {blocked}")


@dep_app.command(name="list")
def list_deps(
    tree: Annotated[bool, typer.Option("--tree", "-t", help="Show as tree")] = False,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
) -> None:
    """List all dependencies."""
    backend, project_id, _ = _get_graph_backend(dodo, global_)

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
