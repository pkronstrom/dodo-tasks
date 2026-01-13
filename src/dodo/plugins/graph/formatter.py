"""Graph-aware formatter that shows dependency info."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dodo.models import TodoItem


class GraphFormatter:
    """Wraps a formatter to add blocked_by info to output.

    Only adds info if items have blocked_by attributes.
    Keeps plugin-specific logic out of core formatters.
    """

    def __init__(self, formatter):
        self._formatter = formatter

    def _format_blocked(self, item) -> str:
        """Format blocked_by list as string."""
        blocked = getattr(item, "blocked_by", None) or []
        if not blocked:
            return ""
        result = ", ".join(b[:8] for b in blocked[:3])
        if len(blocked) > 3:
            result += f" (+{len(blocked) - 3})"
        return result

    def format(self, items: list[TodoItem]) -> Any:
        """Format items, adding dependency info if available."""
        # Check if any item has blocked_by
        has_deps = any(getattr(item, "blocked_by", None) for item in items)

        if not has_deps:
            return self._formatter.format(items)

        # For table formatter, build custom table with blocked_by column
        formatter_name = getattr(self._formatter, "NAME", None)

        if formatter_name == "table":
            return self._format_table(items)
        elif formatter_name == "tsv":
            return self._format_tsv(items)
        elif formatter_name == "csv":
            return self._format_csv(items)
        else:
            # For other formatters (jsonl uses to_dict which includes blocked_by)
            return self._formatter.format(items)

    def _format_table(self, items: list[TodoItem]) -> Any:
        """Format as Rich table with blocked_by column."""
        from rich.table import Table

        from dodo.models import Status

        table = Table(show_header=True, header_style="bold")

        # Mirror the wrapped formatter's settings
        show_id = getattr(self._formatter, "show_id", False)
        datetime_fmt = getattr(self._formatter, "datetime_fmt", "%m-%d %H:%M")

        if show_id:
            table.add_column("ID", style="dim", width=8)
        table.add_column("Done", width=6)
        table.add_column("Created", width=12)
        table.add_column("Todo")
        table.add_column("Blocked by", style="dark_orange")

        for item in items:
            status = "[blue]✓[/blue]" if item.status == Status.DONE else "[dim]•[/dim]"
            try:
                created = item.created_at.strftime(datetime_fmt)
            except ValueError:
                created = item.created_at.strftime("%m-%d %H:%M")

            row = []
            if show_id:
                row.append(item.id[:8])
            row.extend([status, created, item.text, self._format_blocked(item)])

            table.add_row(*row)

        return table

    def _format_tsv(self, items: list[TodoItem]) -> str:
        """Format as TSV with blocked_by column."""
        lines = ["id\tstatus\ttext\tblocked_by"]
        for item in items:
            blocked = getattr(item, "blocked_by", None) or []
            blocked_str = ", ".join(b[:8] for b in blocked)
            lines.append(f"{item.id}\t{item.status.value}\t{item.text}\t{blocked_str}")
        return "\n".join(lines)

    def _format_csv(self, items: list[TodoItem]) -> str:
        """Format as CSV with blocked_by column."""
        lines = ["id,status,text,blocked_by"]
        for item in items:
            blocked = getattr(item, "blocked_by", None) or []
            blocked_str = ", ".join(b[:8] for b in blocked)
            # Escape text and blocked_by fields
            text = item.text.replace('"', '""')
            if "," in text or '"' in text or "\n" in text:
                text = f'"{text}"'
            if "," in blocked_str:
                blocked_str = f'"{blocked_str}"'
            lines.append(f"{item.id},{item.status.value},{text},{blocked_str}")
        return "\n".join(lines)
