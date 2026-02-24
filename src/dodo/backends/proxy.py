"""Base proxy class for backend wrappers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from dodo.backends.base import TodoBackend
from dodo.models import Priority, Status, TodoItem


class BackendProxy:
    """Transparent proxy that delegates TodoBackend methods to a wrapped backend."""

    def __init__(self, backend: TodoBackend):
        self._backend = backend

    @property
    def storage_path(self) -> Path | None:
        path = getattr(self._backend, "storage_path", None)
        if path is not None:
            return path
        return getattr(self._backend, "_path", None)

    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        due_at: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> TodoItem:
        return self._backend.add(
            text,
            project=project,
            priority=priority,
            tags=tags,
            due_at=due_at,
            metadata=metadata,
        )

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        return self._backend.list(project=project, status=status)

    def get(self, id: str) -> TodoItem | None:
        return self._backend.get(id)

    def update(self, id: str, status: Status) -> TodoItem:
        return self._backend.update(id, status)

    def update_text(self, id: str, text: str) -> TodoItem:
        return self._backend.update_text(id, text)

    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        return self._backend.update_priority(id, priority)

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        return self._backend.update_tags(id, tags)

    def update_due_at(self, id: str, due_at: datetime | None) -> TodoItem:
        return self._backend.update_due_at(id, due_at)

    def update_metadata(self, id: str, metadata: dict[str, str] | None) -> TodoItem:
        return self._backend.update_metadata(id, metadata)

    def set_metadata_key(self, id: str, key: str, value: str) -> TodoItem:
        return self._backend.set_metadata_key(id, key, value)

    def remove_metadata_key(self, id: str, key: str) -> TodoItem:
        return self._backend.remove_metadata_key(id, key)

    def add_tag(self, id: str, tag: str) -> TodoItem:
        return self._backend.add_tag(id, tag)

    def remove_tag(self, id: str, tag: str) -> TodoItem:
        return self._backend.remove_tag(id, tag)

    def delete(self, id: str) -> None:
        self._backend.delete(id)

    def __getattr__(self, name: str):
        return getattr(self._backend, name)
