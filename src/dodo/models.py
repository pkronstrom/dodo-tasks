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


@dataclass
class UndoAction:
    """Represents an undoable action in the UI."""

    kind: str  # "toggle" | "delete" | "edit"
    item: TodoItem
    new_id: str | None = None  # For edit: track new ID after text change
