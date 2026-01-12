"""Dodo resolution - find which dodo to use."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.config import Config


def resolve_dodo(
    config: Config,
    dodo_name: str | None = None,
    global_: bool = False,
) -> tuple[str | None, Path | None]:
    """Resolve which dodo to use.

    Priority:
    1. --global flag: use global dodo
    2. Explicit --dodo name: check local then global
    3. Default .dodo/ in cwd or parents
    4. Single named .dodo/<name>/ in cwd or parents
    5. Git-based project detection (fallback)

    Args:
        config: Dodo configuration
        dodo_name: Explicit dodo name (from --dodo flag)
        global_: Force global dodo (from --global flag)

    Returns:
        (dodo_name, explicit_storage_path)
        - dodo_name: Name/ID of the dodo (or None for global)
        - explicit_storage_path: Path to storage dir if explicitly resolved
    """
    if global_:
        return None, None

    # Explicit dodo name provided - auto-detect local vs global
    if dodo_name:
        return _resolve_named_dodo(config, dodo_name)

    # No name: auto-detect dodo
    return _auto_detect_dodo(config)


def _resolve_named_dodo(config: Config, dodo_name: str) -> tuple[str, Path]:
    """Resolve a named dodo, checking local first then global."""
    # Check local first (.dodo/<name>/)
    local_path = Path.cwd() / ".dodo" / dodo_name
    if local_path.exists():
        return dodo_name, local_path

    # Check parent directories for .dodo/<name>/
    for parent in Path.cwd().parents:
        candidate = parent / ".dodo" / dodo_name
        if candidate.exists():
            return dodo_name, candidate
        if parent == Path.home() or parent == Path("/"):
            break

    # Check global (~/.config/dodo/<name>/)
    global_path = config.config_dir / dodo_name
    if global_path.exists():
        return dodo_name, global_path

    # Not found - return the global path (will error later)
    return dodo_name, global_path


def _auto_detect_dodo(config: Config) -> tuple[str | None, Path | None]:
    """Auto-detect which dodo to use based on current directory."""
    # Check current directory and parents for .dodo/
    name, path = _find_dodo_in_dir(Path.cwd())
    if path:
        return name, path

    for parent in Path.cwd().parents:
        name, path = _find_dodo_in_dir(parent)
        if path:
            return name, path
        if parent == Path.home() or parent == Path("/"):
            break

    # Fall back to git-based detection
    from dodo.project import detect_project

    project_id = detect_project(worktree_shared=config.worktree_shared)
    return project_id, None


def _find_dodo_in_dir(base: Path) -> tuple[str | None, Path | None]:
    """Find a dodo in a directory.

    Returns (name, path) or (None, None).
    """
    dodo_dir = base / ".dodo"
    if not dodo_dir.exists():
        return None, None

    # Check for default dodo (dodo.json directly in .dodo/)
    if (dodo_dir / "dodo.json").exists():
        return "local", dodo_dir

    # Check for named dodos (.dodo/<name>/dodo.json)
    try:
        named_dodos = [d for d in dodo_dir.iterdir() if d.is_dir() and (d / "dodo.json").exists()]
    except PermissionError:
        return None, None

    if len(named_dodos) == 1:
        # Single named dodo - auto-select it
        return named_dodos[0].name, named_dodos[0]

    # Multiple or none - don't auto-select
    return None, None
