"""Dodo resolution - find which dodo to use."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.config import Config

# Security: Pattern for valid dodo names (prevents path traversal)
_VALID_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


class InvalidDodoNameError(ValueError):
    """Raised when a dodo name contains invalid characters."""

    pass


def validate_dodo_name(name: str | None) -> str | None:
    """Validate dodo name to prevent path traversal attacks.

    Args:
        name: Dodo name to validate, or None

    Returns:
        The validated name, or None if input was None

    Raises:
        InvalidDodoNameError: If name contains unsafe characters
    """
    if name is None:
        return None
    if not _VALID_NAME_PATTERN.match(name):
        raise InvalidDodoNameError(
            f"Invalid dodo name '{name}'. Names must start with alphanumeric "
            "and contain only letters, numbers, underscores, and hyphens."
        )
    return name


class ResolveSource(Enum):
    """How the dodo was resolved."""

    GLOBAL = "global"  # --global flag
    EXPLICIT = "explicit"  # --dodo flag
    LOCAL = "local"  # .dodo/ in cwd or parents
    MAPPING = "mapping"  # directory mapping in config
    GIT = "git"  # git-based project detection


@dataclass
class ResolvedDodo:
    """Result of dodo resolution.

    Supports tuple unpacking for backward compatibility:
        name, path = resolve_dodo(cfg)

    Or use named fields for clarity:
        result = resolve_dodo(cfg)
        if result.source == ResolveSource.MAPPING:
            print(f"Using mapped dodo: {result.name}")
    """

    name: str | None
    """Name/ID of the dodo, or None for global."""

    path: Path | None
    """Explicit storage path if resolved, or None to use default."""

    source: ResolveSource
    """How the dodo was resolved."""

    def __iter__(self) -> Iterator[str | None | Path | None]:
        """Support tuple unpacking: name, path = result."""
        yield self.name
        yield self.path


def resolve_dodo(
    config: Config,
    dodo_name: str | None = None,
    global_: bool = False,
) -> ResolvedDodo:
    """Resolve which dodo to use.

    Priority:
    1. --global flag: use global dodo
    2. Explicit --dodo name: check local then global
    3. Default .dodo/ in cwd or parents
    4. Directory mapping in config
    5. Git-based project detection (fallback)

    Args:
        config: Dodo configuration
        dodo_name: Explicit dodo name (from --dodo flag)
        global_: Force global dodo (from --global flag)

    Returns:
        ResolvedDodo with name, path, and source.
        Supports tuple unpacking: name, path = resolve_dodo(cfg)

    Raises:
        InvalidDodoNameError: If dodo_name contains invalid characters
    """
    if global_:
        return ResolvedDodo(None, None, ResolveSource.GLOBAL)

    # Validate and resolve explicit dodo name
    if dodo_name:
        validate_dodo_name(dodo_name)
        return _resolve_named_dodo(config, dodo_name)

    # No name: auto-detect dodo
    return _auto_detect_dodo(config)


def _resolve_named_dodo(config: Config, dodo_name: str) -> ResolvedDodo:
    """Resolve a named dodo, checking local first then global."""
    # Check local first (.dodo/<name>/)
    local_path = Path.cwd() / ".dodo" / dodo_name
    if local_path.exists():
        return ResolvedDodo(dodo_name, local_path, ResolveSource.LOCAL)

    # Check parent directories for .dodo/<name>/
    for parent in Path.cwd().parents:
        candidate = parent / ".dodo" / dodo_name
        if candidate.exists():
            return ResolvedDodo(dodo_name, candidate, ResolveSource.LOCAL)
        if parent == Path.home() or parent == Path("/"):
            break

    # Check global (~/.config/dodo/<name>/)
    global_path = config.config_dir / dodo_name
    if global_path.exists():
        return ResolvedDodo(dodo_name, global_path, ResolveSource.EXPLICIT)

    # Not found - return the global path (will error later)
    return ResolvedDodo(dodo_name, global_path, ResolveSource.EXPLICIT)


def _auto_detect_dodo(config: Config) -> ResolvedDodo:
    """Auto-detect which dodo to use based on current directory."""
    cwd = str(Path.cwd())

    # Check directory mappings first (highest priority after explicit flags)
    mapped_dodo = config.get_directory_mapping(cwd)
    if mapped_dodo:
        dodo_path = config.config_dir / mapped_dodo
        if dodo_path.exists():
            return ResolvedDodo(mapped_dodo, dodo_path, ResolveSource.MAPPING)
        else:
            # Warn about invalid mapping
            import sys

            print(
                f"Warning: Directory mapped to '{mapped_dodo}' but dodo not found. "
                f"Run 'dodo unuse' to remove mapping.",
                file=sys.stderr,
            )

    # Check current directory and parents for .dodo/
    result = _find_dodo_in_dir(Path.cwd())
    if result.path:
        return result

    for parent in Path.cwd().parents:
        result = _find_dodo_in_dir(parent)
        if result.path:
            return result
        if parent == Path.home() or parent == Path("/"):
            break

    # Fall back to git-based detection
    from dodo.project import detect_project

    project_id = detect_project(worktree_shared=config.worktree_shared)
    return ResolvedDodo(project_id, None, ResolveSource.GIT)


def _find_dodo_in_dir(base: Path) -> ResolvedDodo:
    """Find a dodo in a directory.

    Only auto-selects the DEFAULT dodo (dodo.json directly in .dodo/).
    Named dodos (.dodo/<name>/) must be explicitly requested with --dodo flag.

    Returns ResolvedDodo (name/path may be None if not found).
    """
    dodo_dir = base / ".dodo"
    if not dodo_dir.exists():
        return ResolvedDodo(None, None, ResolveSource.LOCAL)

    # Only auto-select the default dodo (dodo.json directly in .dodo/)
    if (dodo_dir / "dodo.json").exists():
        return ResolvedDodo("local", dodo_dir, ResolveSource.LOCAL)

    # Named dodos exist but no default - don't auto-select
    # User must explicitly request with --dodo <name>
    return ResolvedDodo(None, None, ResolveSource.LOCAL)
