"""Core todo service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dodo.adapters.base import TodoAdapter
from dodo.config import Config
from dodo.models import Status, TodoItem
from dodo.project import detect_project_root

if TYPE_CHECKING:
    pass

# Module-level adapter registry
# Maps adapter name -> adapter class (or string reference for lazy loading)
_adapter_registry: dict[str, type | str] = {}


def _register_builtin_adapters() -> None:
    """Register built-in and bundled plugin adapters.

    Note: Actual imports are lazy - classes are registered as strings
    that resolve to the real class on first use.
    """
    # These are available without explicit plugin enablement
    # Actual class imports happen in _instantiate_adapter for lazy loading
    _adapter_registry["markdown"] = "dodo.adapters.markdown:MarkdownAdapter"
    _adapter_registry["sqlite"] = "dodo.plugins.sqlite.adapter:SqliteAdapter"
    _adapter_registry["obsidian"] = "dodo.plugins.obsidian.adapter:ObsidianAdapter"


def _resolve_adapter_class(adapter_ref: str | type) -> type:
    """Resolve adapter reference to actual class (lazy import)."""
    if isinstance(adapter_ref, type):
        return adapter_ref
    # String format: "module.path:ClassName"
    module_path, class_name = adapter_ref.rsplit(":", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# Register built-in adapters at module load (no actual imports yet)
_register_builtin_adapters()


class TodoService:
    """Main service - routes to appropriate adapter."""

    def __init__(self, config: Config, project_id: str | None = None):
        self._config = config
        self._project_id = project_id
        self._adapter = self._create_adapter()

    def add(self, text: str) -> TodoItem:
        return self._adapter.add(text, project=self._project_id)

    def list(self, status: Status | None = None) -> list[TodoItem]:
        return self._adapter.list(project=self._project_id, status=status)

    def get(self, id: str) -> TodoItem | None:
        return self._adapter.get(id)

    def complete(self, id: str) -> TodoItem:
        return self._adapter.update(id, Status.DONE)

    def toggle(self, id: str) -> TodoItem:
        """Toggle status between PENDING and DONE."""
        item = self._adapter.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        new_status = Status.PENDING if item.status == Status.DONE else Status.DONE
        return self._adapter.update(id, new_status)

    def update_text(self, id: str, text: str) -> TodoItem:
        """Update todo text."""
        return self._adapter.update_text(id, text)

    def delete(self, id: str) -> None:
        self._adapter.delete(id)

    def _create_adapter(self) -> TodoAdapter:
        from dodo.plugins import apply_hooks

        # Let plugins register their adapters
        apply_hooks("register_adapter", _adapter_registry, self._config)

        adapter_name = self._config.default_adapter

        # Check if adapter is in registry
        if adapter_name in _adapter_registry:
            adapter = self._instantiate_adapter(adapter_name)
        else:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        # Allow plugins to extend/wrap the adapter
        return apply_hooks("extend_adapter", adapter, self._config)

    def _instantiate_adapter(self, adapter_name: str) -> TodoAdapter:
        """Create adapter instance with appropriate arguments."""
        adapter_ref = _adapter_registry[adapter_name]
        adapter_cls = _resolve_adapter_class(adapter_ref)

        # Different adapters need different initialization
        if adapter_name == "markdown":
            return adapter_cls(self._get_markdown_path())
        elif adapter_name == "sqlite":
            return adapter_cls(self._get_sqlite_path())
        elif adapter_name == "obsidian":
            return adapter_cls(
                api_url=self._config.obsidian_api_url,
                api_key=self._config.obsidian_api_key,
                vault_path=self._config.obsidian_vault_path,
            )
        else:
            # For unknown plugin adapters, try calling with config
            # Plugins should handle their own initialization
            try:
                return adapter_cls(config=self._config, project_id=self._project_id)
            except TypeError:
                # Fall back to no-args construction
                return adapter_cls()

    def _get_markdown_path(self) -> Path:
        if self._config.local_storage and self._project_id:
            root = detect_project_root(worktree_shared=self._config.worktree_shared)
            if root:
                return root / "dodo.md"

        if self._project_id:
            return self._config.config_dir / "projects" / self._project_id / "todo.md"

        return self._config.config_dir / "todo.md"

    def _get_sqlite_path(self) -> Path:
        if self._project_id:
            return self._config.config_dir / "projects" / self._project_id / "todos.db"
        return self._config.config_dir / "todos.db"
