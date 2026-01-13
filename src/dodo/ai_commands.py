"""AI-assisted todo management commands."""

from typing import Annotated

import typer
from rich.console import Console

ai_app = typer.Typer(
    name="ai",
    help="AI-assisted todo management.",
)

console = Console()


@ai_app.command(name="add")
def ai_add(
    text: Annotated[str | None, typer.Argument(help="Input text")] = None,
):
    """Add todos with AI-inferred priority and tags."""
    console.print("[yellow]AI add not yet implemented[/yellow]")


@ai_app.command(name="prio")
@ai_app.command(name="prioritize")
def ai_prioritize(
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")
    ] = False,
):
    """AI-assisted bulk priority assignment."""
    console.print("[yellow]AI prioritize not yet implemented[/yellow]")


@ai_app.command(name="reword")
def ai_reword(
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")
    ] = False,
):
    """AI-assisted todo rewording for clarity."""
    console.print("[yellow]AI reword not yet implemented[/yellow]")


@ai_app.command(name="tag")
def ai_tag(
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")
    ] = False,
):
    """AI-assisted tag suggestions."""
    console.print("[yellow]AI tag not yet implemented[/yellow]")


@ai_app.command(name="sync")
def ai_sync():
    """Sync all AI suggestions (priority + tags + reword)."""
    console.print("[yellow]AI sync not yet implemented[/yellow]")
