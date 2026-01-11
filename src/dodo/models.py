"""Data models for dodo."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Status(Enum):
    """Todo item status."""

    PENDING = "pending"
    DONE = "done"


@dataclass(frozen=True)
class TodoItem:
    """Immutable todo item."""

    id: str
    text: str
    status: Status
    created_at: datetime
    completed_at: datetime | None = None
    project: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dict for formatters."""
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "project": self.project,
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
