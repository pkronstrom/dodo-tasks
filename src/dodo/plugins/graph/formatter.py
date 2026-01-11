"""Graph-aware formatter that shows dependency info."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from rich.table import Table

if TYPE_CHECKING:
    from dodo.models import TodoItem


class GraphFormatter:
    """Wraps a formatter to add blocked_by info to output.

    Extends table, jsonl, and tsv formatters with dependency data.
    Only adds info if items have blocked_by attributes.
    """

    def __init__(self, formatter):
        self._formatter = formatter

    def _get_blocked_str(self, item) -> str:
        """Format blocked_by list as string."""
        blocked = getattr(item, "blocked_by", [])
        if not blocked:
            return ""
        result = ", ".join(b[:8] for b in blocked[:3])
        if len(blocked) > 3:
            result += f" (+{len(blocked) - 3})"
        return result

    def _format_table(self, items: list[TodoItem]) -> Table:
        """Format as Rich table with blocked_by column."""
        from dodo.models import Status

        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Done", width=6)
        table.add_column("Todo")
        table.add_column("Blocked by", style="yellow")

        for item in items:
            status_icon = "[green]✓[/green]" if item.status == Status.DONE else "[ ]"
            table.add_row(
                item.id[:8],
                status_icon,
                item.text,
                self._get_blocked_str(item),
            )

        return table

    def _format_jsonl(self, items: list[TodoItem]) -> str:
        """Format as JSON lines with blocked_by field."""
        if not items:
            return ""

        lines = []
        for item in items:
            blocked = getattr(item, "blocked_by", [])
            obj = {
                "id": item.id,
                "text": item.text,
                "status": item.status.value,
                "created_at": item.created_at.isoformat(),
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "project": item.project,
                "blocked_by": blocked if blocked else None,
            }
            lines.append(json.dumps(obj))

        return "\n".join(lines)

    def _format_tsv(self, items: list[TodoItem]) -> str:
        """Format as TSV with blocked_by column."""
        if not items:
            return ""

        lines = []
        for item in items:
            blocked_str = self._get_blocked_str(item)
            lines.append(f"{item.id}\t{item.status.value}\t{item.text}\t{blocked_str}")

        return "\n".join(lines)

    def format(self, items: list[TodoItem]) -> Any:
        """Format items, adding dependency info if available."""
        # Check if any item has blocked_by
        has_deps = any(getattr(item, "blocked_by", None) for item in items)

        if not has_deps:
            return self._formatter.format(items)

        # Dispatch based on wrapped formatter type
        formatter_name = getattr(self._formatter, "NAME", None)

        if formatter_name == "jsonl":
            return self._format_jsonl(items)
        elif formatter_name == "tsv":
            return self._format_tsv(items)
        else:
            # Default: table format
            return self._format_table(items)
