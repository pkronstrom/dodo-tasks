"""Centralized storage path calculation."""

from pathlib import Path

from dodo.config import Config
from dodo.project import detect_project_root


def get_storage_path(
    config: Config,
    project_id: str | None,
    backend: str,
    worktree_shared: bool = True,
) -> Path:
    """Calculate storage path for a backend.

    Args:
        config: Config instance
        project_id: Project ID or None for global
        backend: Backend name (markdown, sqlite, etc.)
        worktree_shared: Whether to use worktree-shared paths

    Returns:
        Path to storage file
    """
    # File extension by backend
    extensions = {
        "markdown": "dodo.md",
        "sqlite": "dodo.db",
    }
    filename = extensions.get(backend, f"dodo.{backend}")

    # Local storage in project directory
    if config.local_storage and project_id:
        root = detect_project_root(worktree_shared=worktree_shared)
        if root:
            if backend == "sqlite":
                return root / ".dodo" / filename
            return root / filename

    # Centralized storage
    if project_id:
        return config.config_dir / "projects" / project_id / filename

    return config.config_dir / filename
