"""Core todo service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dodo.config import Config
from dodo.models import Status, TodoItem

if TYPE_CHECKING:
    from dodo.backends.base import TodoBackend

# Module-level backend registry
# Maps backend name -> backend class (or string reference for lazy loading)
_backend_registry: dict[str, type | str] = {}


def _register_builtin_backends() -> None:
    """Register built-in and bundled plugin backends.

    Note: Actual imports are lazy - classes are registered as strings
    that resolve to the real class on first use.
    """
    # These are available without explicit plugin enablement
    # Actual class imports happen in _instantiate_backend for lazy loading
    _backend_registry["markdown"] = "dodo.backends.markdown:MarkdownBackend"
    _backend_registry["sqlite"] = "dodo.backends.sqlite:SqliteBackend"
    _backend_registry["obsidian"] = "dodo.plugins.obsidian.backend:ObsidianBackend"


def _resolve_backend_class(backend_ref: str | type) -> type:
    """Resolve backend reference to actual class (lazy import)."""
    if isinstance(backend_ref, type):
        return backend_ref
    # String format: "module.path:ClassName"
    module_path, class_name = backend_ref.rsplit(":", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# Register built-in backends at module load (no actual imports yet)
_register_builtin_backends()


class TodoService:
    """Main service - routes to appropriate backend."""

    def __init__(self, config: Config, project_id: str | None = None):
        self._config = config
        self._project_id = project_id
        self._backend = self._create_backend()

    def add(self, text: str) -> TodoItem:
        return self._backend.add(text, project=self._project_id)

    def list(self, status: Status | None = None) -> list[TodoItem]:
        return self._backend.list(project=self._project_id, status=status)

    def get(self, id: str) -> TodoItem | None:
        return self._backend.get(id)

    def complete(self, id: str) -> TodoItem:
        return self._backend.update(id, Status.DONE)

    def toggle(self, id: str) -> TodoItem:
        """Toggle status between PENDING and DONE."""
        item = self._backend.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        new_status = Status.PENDING if item.status == Status.DONE else Status.DONE
        return self._backend.update(id, new_status)

    def update_text(self, id: str, text: str) -> TodoItem:
        """Update todo text."""
        return self._backend.update_text(id, text)

    def delete(self, id: str) -> None:
        self._backend.delete(id)

    @property
    def storage_path(self) -> str:
        """Get the storage path for current backend."""
        if hasattr(self._backend, "_path"):
            return str(self._backend._path)
        return "N/A"

    def _create_backend(self) -> TodoBackend:
        from dodo.plugins import apply_hooks

        # Let plugins register their backends
        apply_hooks("register_backend", _backend_registry, self._config)

        backend_name = self._resolve_backend()

        # Check if backend is in registry
        if backend_name in _backend_registry:
            backend = self._instantiate_backend(backend_name)
        else:
            raise ValueError(f"Unknown backend: {backend_name}")

        # Allow plugins to extend/wrap the backend
        return apply_hooks("extend_backend", backend, self._config)

    def _resolve_backend(self) -> str:
        """Resolve which backend to use for this project."""
        from dodo.project_config import ProjectConfig, get_project_config_dir

        if not self._project_id:
            return self._config.default_backend

        # Get project config directory
        project_dir = get_project_config_dir(
            self._config, self._project_id, self._config.worktree_shared
        )
        if not project_dir:
            return self._config.default_backend

        # Try loading existing config
        config = ProjectConfig.load(project_dir)
        if config:
            return config.backend

        # Auto-detect from existing files
        detected = self._auto_detect_backend(project_dir)
        if detected:
            return detected

        # Use global default
        return self._config.default_backend

    def _auto_detect_backend(self, project_dir: Path) -> str | None:
        """Auto-detect backend from existing files."""
        # Check for sqlite database
        if (project_dir / "dodo.db").exists():
            return "sqlite"
        # Check for markdown file (could be in project_dir or parent for local_storage)
        if (project_dir / "dodo.md").exists():
            return "markdown"
        if (project_dir.parent / "dodo.md").exists():
            return "markdown"
        return None

    def _instantiate_backend(self, backend_name: str) -> TodoBackend:
        """Create backend instance with appropriate arguments."""
        backend_ref = _backend_registry[backend_name]
        backend_cls = _resolve_backend_class(backend_ref)

        # Different backends need different initialization
        if backend_name == "markdown":
            return backend_cls(self._get_markdown_path())
        elif backend_name == "sqlite":
            return backend_cls(self._get_sqlite_path())
        elif backend_name == "obsidian":
            return backend_cls(
                api_url=self._config.obsidian_api_url,
                api_key=self._config.obsidian_api_key,
                vault_path=self._config.obsidian_vault_path,
            )
        else:
            # For unknown plugin backends, try calling with config
            # Plugins should handle their own initialization
            try:
                return backend_cls(config=self._config, project_id=self._project_id)
            except TypeError:
                # Fall back to no-args construction
                return backend_cls()

    def _get_markdown_path(self) -> Path:
        from dodo.storage import get_storage_path

        return get_storage_path(
            self._config,
            self._project_id,
            "markdown",
            self._config.worktree_shared,
        )

    def _get_sqlite_path(self) -> Path:
        from dodo.storage import get_storage_path

        return get_storage_path(
            self._config,
            self._project_id,
            "sqlite",
            self._config.worktree_shared,
        )
