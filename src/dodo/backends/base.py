"""Base backend protocol."""

from typing import Protocol, runtime_checkable

from dodo.models import Status, TodoItem


@runtime_checkable
class TodoBackend(Protocol):
    """Protocol for todo storage backends.

    Implement this to add new backends (sqlite, notion, etc.)
    """

    def add(self, text: str, project: str | None = None) -> TodoItem:
        """Create a new todo item."""
        ...

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        """List todos, optionally filtered."""
        ...

    def get(self, id: str) -> TodoItem | None:
        """Get single todo by ID."""
        ...

    def update(self, id: str, status: Status) -> TodoItem:
        """Update todo status."""
        ...

    def update_text(self, id: str, text: str) -> TodoItem:
        """Update todo text."""
        ...

    def delete(self, id: str) -> None:
        """Delete a todo."""
        ...
