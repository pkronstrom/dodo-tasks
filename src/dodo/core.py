"""Core todo service."""

from pathlib import Path
from typing import Any

from dodo.adapters.base import TodoAdapter
from dodo.adapters.markdown import MarkdownAdapter
from dodo.adapters.obsidian import ObsidianAdapter
from dodo.adapters.sqlite import SqliteAdapter
from dodo.config import Config
from dodo.models import Status, TodoItem
from dodo.project import detect_project_root


class TodoService:
    """Main service - routes to appropriate adapter."""

    ADAPTERS: dict[str, type[Any]] = {
        "markdown": MarkdownAdapter,
        "sqlite": SqliteAdapter,
        "obsidian": ObsidianAdapter,
    }

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

    def delete(self, id: str) -> None:
        self._adapter.delete(id)

    def _create_adapter(self) -> TodoAdapter:
        adapter_name = self._config.default_adapter
        adapter_cls = self.ADAPTERS.get(adapter_name)

        if not adapter_cls:
            raise ValueError(f"Unknown adapter: {adapter_name}")

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

        raise ValueError(f"Unhandled adapter: {adapter_name}")

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
