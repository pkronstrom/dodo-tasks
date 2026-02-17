"""Public Python API for dodo programmatic access.

Usage:
    from dodo.api import Dodo

    d = Dodo.named("work")
    d.add("Fix bug", priority="high")
    items = d.list()
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Priority, Status

if TYPE_CHECKING:
    from dodo.models import TodoItem

_UNSET = object()


def _to_priority(value: str | None) -> Priority | None:
    if value is None:
        return None
    try:
        return Priority(value.lower())
    except ValueError:
        valid = ", ".join(p.value for p in Priority)
        raise ValueError(f"Invalid priority: {value!r}. Valid: {valid}")


def _to_status(value: str | None) -> Status | None:
    if value is None:
        return None
    try:
        return Status(value.lower())
    except ValueError:
        valid = ", ".join(s.value for s in Status)
        raise ValueError(f"Invalid status: {value!r}. Valid: {valid}")


def _to_due(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class Dodo:
    """Public API for dodo programmatic access."""

    def __init__(self, service: TodoService) -> None:
        self._svc = service

    @classmethod
    def named(cls, name: str) -> Dodo:
        """Open a named dodo from ~/.config/dodo/<name>/."""
        config = Config.load()
        return cls(TodoService(config, project_id=name))

    @classmethod
    def local(cls, path: str | Path) -> Dodo:
        """Open a local .dodo/ at the given path."""
        config = Config.load()
        dodo_dir = Path(path) / ".dodo"
        return cls(TodoService(config, storage_path=dodo_dir))

    @classmethod
    def auto(cls) -> Dodo:
        """Auto-detect dodo from cwd (same as CLI)."""
        from dodo.resolve import resolve_dodo

        config = Config.load()
        name, path = resolve_dodo(config)
        return cls(TodoService(config, project_id=name, storage_path=path))

    def add(
        self,
        text: str,
        *,
        priority: str | None = None,
        tags: list[str] | None = None,
        due: str | datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> TodoItem:
        """Add a todo item."""
        return self._svc.add(
            text,
            priority=_to_priority(priority),
            tags=tags,
            due_at=_to_due(due),
            metadata=metadata,
        )

    def list(self, *, status: str | None = None) -> list[TodoItem]:
        """List todo items, optionally filtered by status."""
        return self._svc.list(status=_to_status(status))

    def get(self, id: str) -> TodoItem | None:
        """Get a todo item by ID, or None if not found."""
        return self._svc.get(id)

    def complete(self, id: str) -> TodoItem:
        """Mark a todo as done. Raises KeyError if not found."""
        self._ensure_exists(id)
        return self._svc.complete(id)

    def delete(self, id: str) -> None:
        """Delete a todo item. Raises KeyError if not found."""
        self._ensure_exists(id)
        self._svc.delete(id)

    def update(
        self,
        id: str,
        *,
        text: object = _UNSET,
        priority: object = _UNSET,
        due: object = _UNSET,
        tags: object = _UNSET,
        metadata: object = _UNSET,
    ) -> TodoItem:
        """Update a todo item. Only provided fields are changed.

        Pass None to clear a field. Omit to leave unchanged.
        """
        self._ensure_exists(id)
        item = None
        if text is not _UNSET:
            item = self._svc.update_text(id, text)
        if priority is not _UNSET:
            item = self._svc.update_priority(id, _to_priority(priority))
        if due is not _UNSET:
            item = self._svc.update_due_at(id, _to_due(due))
        if tags is not _UNSET:
            item = self._svc.update_tags(id, tags)
        if metadata is not _UNSET:
            item = self._svc.update_metadata(id, metadata)
        if item is None:
            raise ValueError("No fields to update")
        return item

    def add_tag(self, id: str, tag: str) -> TodoItem:
        """Add a tag to a todo item."""
        self._ensure_exists(id)
        return self._svc.add_tag(id, tag)

    def remove_tag(self, id: str, tag: str) -> TodoItem:
        """Remove a tag from a todo item."""
        self._ensure_exists(id)
        return self._svc.remove_tag(id, tag)

    def set_meta(self, id: str, key: str, value: str) -> TodoItem:
        """Set a metadata key on a todo item."""
        self._ensure_exists(id)
        return self._svc.set_metadata_key(id, key, value)

    def remove_meta(self, id: str, key: str) -> TodoItem:
        """Remove a metadata key from a todo item."""
        self._ensure_exists(id)
        return self._svc.remove_metadata_key(id, key)

    def _ensure_exists(self, id: str) -> None:
        if self._svc.get(id) is None:
            raise KeyError(f"Todo not found: {id}")
