"""Project detection utilities."""

import subprocess
from hashlib import sha1
from pathlib import Path

# Module-level cache
_project_cache: dict[str, str | None] = {}


def clear_project_cache() -> None:
    """Clear the project detection cache. Useful for testing."""
    global _project_cache
    _project_cache.clear()


def detect_project(path: Path | None = None) -> str | None:
    """Detect project ID from current directory.

    Returns: project_id (e.g., 'myapp_d1204e') or None if not in a project.
    """
    path = path or Path.cwd()
    cache_key = str(path.resolve())

    if cache_key in _project_cache:
        return _project_cache[cache_key]

    git_root = _get_git_root(path)
    if not git_root:
        _project_cache[cache_key] = None
        return None

    result = _make_project_id(git_root)
    _project_cache[cache_key] = result
    return result


def detect_project_root(path: Path | None = None, worktree_shared: bool = True) -> Path | None:
    """Get project root path, respecting worktree config."""
    path = path or Path.cwd()

    if worktree_shared:
        return _get_git_common_root(path)
    else:
        return _get_git_root(path)


def _make_project_id(root: Path) -> str:
    """Generate readable project ID: dirname_shorthash."""
    name = root.name
    hash_input = str(root.resolve())
    short_hash = sha1(hash_input.encode()).hexdigest()[:6]
    return f"{name}_{short_hash}"


def _get_git_root(path: Path) -> Path | None:
    """Get git worktree root (or main repo root if not a worktree)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def _get_git_common_root(path: Path) -> Path | None:
    """Get shared git root (same for all worktrees of a repo)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
        git_dir = Path(result.stdout.strip())
        # --git-common-dir may return relative path like ".git"
        if not git_dir.is_absolute():
            git_dir = (path / git_dir).resolve()
        # Parent of .git is repo root
        if git_dir.name == ".git":
            return git_dir.parent
        # For worktrees, it returns /path/to/main/.git
        return git_dir.parent
    except subprocess.CalledProcessError:
        return None
