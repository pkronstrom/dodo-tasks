"""Data models for dodo."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Status(Enum):
    """Todo item status."""

    PENDING = "pending"
    DONE = "done"


class Priority(Enum):
    """Todo priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    SOMEDAY = "someday"

    @property
    def sort_order(self) -> int:
        """Higher number = higher priority for sorting."""
        return {
            Priority.CRITICAL: 5,
            Priority.HIGH: 4,
            Priority.NORMAL: 3,
            Priority.LOW: 2,
            Priority.SOMEDAY: 1,
        }[self]


@dataclass(frozen=True)
class TodoItem:
    """Immutable todo item."""

    id: str
    text: str
    status: Status
    created_at: datetime
    completed_at: datetime | None = None
    project: str | None = None
    priority: Priority | None = None
    tags: list[str] | None = None
    due_at: datetime | None = None
    metadata: dict[str, str] | None = None

    def to_dict(self) -> dict:
        """Serialize to dict for formatters."""
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "project": self.project,
            "priority": self.priority.value if self.priority else None,
            "tags": self.tags,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "metadata": self.metadata,
        }


@dataclass
class TodoItemView:
    """Mutable view of a TodoItem with optional extension fields.

    Used when plugins need to attach additional data (e.g., blocked_by).
    """

    item: TodoItem
    blocked_by: list[str] | None = None

    # Delegate common properties
    @property
    def id(self) -> str:
        return self.item.id

    @property
    def text(self) -> str:
        return self.item.text

    @property
    def status(self) -> Status:
        return self.item.status

    @property
    def created_at(self) -> datetime:
        return self.item.created_at

    @property
    def completed_at(self) -> datetime | None:
        return self.item.completed_at

    @property
    def project(self) -> str | None:
        return self.item.project

    @property
    def priority(self) -> Priority | None:
        return self.item.priority

    @property
    def tags(self) -> list[str] | None:
        return self.item.tags

    @property
    def due_at(self) -> datetime | None:
        return self.item.due_at

    @property
    def metadata(self) -> dict[str, str] | None:
        return self.item.metadata

    def to_dict(self) -> dict:
        """Serialize to dict, including extension fields."""
        d = self.item.to_dict()
        if self.blocked_by is not None:
            d["blocked_by"] = self.blocked_by
        return d


@dataclass
class UndoAction:
    """Represents an undoable action in the UI."""

    kind: str  # "toggle" | "delete" | "edit"
    item: TodoItem
    new_id: str | None = None  # For edit: track new ID after text change
