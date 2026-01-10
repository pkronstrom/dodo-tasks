"""Base formatter protocol."""

from typing import Any, Protocol, runtime_checkable

from dodo.models import TodoItem


@runtime_checkable
class FormatterProtocol(Protocol):
    """Protocol for output formatters.

    Implement this to add new output formats.
    Returns a Rich-printable object (Table, str, etc.)
    """

    def format(self, items: list[TodoItem]) -> Any:
        """Format todo items for output."""
        ...
