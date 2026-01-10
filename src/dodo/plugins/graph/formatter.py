"""Graph-aware formatter that shows dependency info."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.table import Table

if TYPE_CHECKING:
    from dodo.models import TodoItem


class GraphFormatter:
    """Wraps a formatter to add blocked_by info to output.

    Only adds info if the adapter supports dependency tracking.
    """

    def __init__(self, formatter):
        self._formatter = formatter

    def format(self, items: list[TodoItem]) -> Any:
        """Format items, adding dependency info if available."""
        # Check if any item has blocked_by
        has_deps = any(getattr(item, "blocked_by", None) for item in items)

        if not has_deps:
            return self._formatter.format(items)

        # Build table with blocked_by column
        from dodo.models import Status

        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Done", width=6)
        table.add_column("Todo")
        table.add_column("Blocked by", style="yellow")

        for item in items:
            status_icon = "[green]✓[/green]" if item.status == Status.DONE else "[ ]"
            blocked = getattr(item, "blocked_by", [])
            blocked_str = ", ".join(b[:8] for b in blocked[:3])
            if len(blocked) > 3:
                blocked_str += f" (+{len(blocked) - 3})"
            table.add_row(item.id[:8], status_icon, item.text, blocked_str)

        return table
