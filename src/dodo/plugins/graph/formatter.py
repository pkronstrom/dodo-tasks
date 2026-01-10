"""Graph-aware formatter that shows dependency info."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.models import TodoItem


class GraphFormatter:
    """Wraps a formatter to add blocked_by info to output.

    Only adds info if the adapter supports dependency tracking.
    """

    def __init__(self, formatter):
        self._formatter = formatter

    def format(self, items: list[TodoItem]) -> str:
        """Format items, adding dependency info if available."""
        # For now, just delegate to the base formatter
        # In a full implementation, we'd query the adapter for blockers
        # and add a column to table output or annotations to other formats
        return self._formatter.format(items)
