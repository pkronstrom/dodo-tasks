"""CLI context utilities for common command setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.config import Config
    from dodo.core import TodoService


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
