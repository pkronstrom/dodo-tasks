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
        project_id = _detect_project(worktree_shared=cfg.worktree_shared)
        svc = _get_service(cfg, project_id)

    Args:
        global_: Force global list (no project)
        project: Explicit project name/ID

    Returns:
        Tuple of (config, project_id, service)
    """
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.project import detect_project

    cfg = Config.load()

    if global_:
        project_id = None
    elif project:
        project_id = _resolve_project(project, cfg)
    else:
        project_id = detect_project(worktree_shared=cfg.worktree_shared)

    svc = TodoService(cfg, project_id)
    return cfg, project_id, svc


def _resolve_project(partial: str, cfg: Config) -> str | None:
    """Resolve partial project name to full project ID."""
    if not partial:
        return None

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

    # No match or ambiguous - use as-is
    return partial
