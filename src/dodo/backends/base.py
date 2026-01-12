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


@runtime_checkable
class GraphCapable(Protocol):
    """Protocol for backends that support dependency graph features.

    Used by the graph plugin to check if a backend can track dependencies.
    Implemented by GraphWrapper which wraps SQLite backends.
    """

    def add_dependency(self, blocker_id: str, blocked_id: str) -> None:
        """Add a dependency: blocker blocks blocked."""
        ...

    def remove_dependency(self, blocker_id: str, blocked_id: str) -> None:
        """Remove a dependency."""
        ...

    def get_blockers(self, todo_id: str) -> list[str]:
        """Get IDs of todos blocking this one."""
        ...

    def get_ready(self, project: str | None = None) -> list[TodoItem]:
        """Get todos with no blocking dependencies."""
        ...

    def get_blocked_todos(self, project: str | None = None) -> list[TodoItem]:
        """Get todos that are blocked by others."""
        ...

    def list_all_dependencies(self) -> list[tuple[str, str]]:
        """Get all (blocker_id, blocked_id) pairs."""
        ...
