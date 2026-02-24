"""CLI context utilities for common command setup."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from dodo.config import Config
    from dodo.core import TodoService

console = Console()


def resolve_for_cli(
    config: Config,
    dodo_name: str | None = None,
    global_: bool = False,
) -> tuple[str | None, Path | None]:
    """Resolve dodo for CLI commands. Exits on invalid name.

    Returns (dodo_name, explicit_path) tuple for undo state and service creation.
    """
    from dodo.resolve import InvalidDodoNameError, resolve_dodo

    try:
        result = resolve_dodo(config, dodo_name, global_)
        return result.name, result.path
    except InvalidDodoNameError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def get_service_for_path(config: Config, path: Path) -> TodoService:
    """Create TodoService with explicit storage path."""
    from dodo.core import TodoService

    return TodoService(config, project_id=None, storage_path=path)


def get_service_context(
    global_: bool = False,
    project: str | None = None,
) -> tuple[Config, str | None, TodoService]:
    """Get config, project_id, and service for CLI commands.

    This centralizes the common pattern used by most CLI commands:
        cfg = _get_config()
        dodo_name, storage_path = resolve_dodo(cfg)
        svc = _get_service(cfg, dodo_name)

    Args:
        global_: Force global list (no project)
        project: Explicit project name/ID

    Returns:
        Tuple of (config, project_id, service)

    Raises:
        InvalidDodoNameError: If project name is invalid
    """
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.resolve import resolve_dodo

    cfg = Config.load()

    if global_:
        project_id = None
        storage_path = None
    elif project:
        # resolve_dodo validates the name
        project_id, storage_path = resolve_dodo(cfg, project)
    else:
        # Use resolve_dodo which checks directory mappings first
        project_id, storage_path = resolve_dodo(cfg)

    if storage_path:
        svc = TodoService(cfg, project_id=None, storage_path=storage_path)
    else:
        svc = TodoService(cfg, project_id)
    return cfg, project_id, svc
