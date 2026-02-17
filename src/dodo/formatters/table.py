"""Rich table formatter."""

from datetime import datetime
from typing import Any

from rich.table import Table

from dodo.models import Priority, Status, TodoItem


class TableFormatter:
    """Format todos as a Rich table.

    Plugin-specific fields (like blocked_by) are handled by plugin wrappers.
    """

    NAME = "table"

    def __init__(self, datetime_fmt: str = "%m-%d %H:%M", show_id: bool = False):
        self.datetime_fmt = datetime_fmt
        self.show_id = show_id

    def _format_datetime(self, dt) -> str:
        try:
            return dt.strftime(self.datetime_fmt)
        except ValueError:
            return dt.strftime("%m-%d %H:%M")

    def _format_priority(self, priority: Priority | None) -> str:
        from dodo.ui.formatting import format_priority

        return format_priority(priority)

    def _format_tags(self, tags: list[str] | None) -> str:
        from dodo.ui.formatting import MAX_DISPLAY_TAGS

        if not tags:
            return ""
        # Table uses cyan for visibility in dedicated column
        return " ".join(f"[cyan]#{t}[/cyan]" for t in tags[:MAX_DISPLAY_TAGS])

    def _format_due(self, due_at: datetime | None, status: Status) -> str:
        if not due_at:
            return ""
        date_str = due_at.strftime("%Y-%m-%d")
        if status == Status.DONE:
            return f"[dim]{date_str}[/dim]"
        if due_at < datetime.now(tz=due_at.tzinfo):
            return f"[red bold]{date_str}[/red bold]"
        return date_str

    def format(self, items: list[TodoItem]) -> Any:
        if not items:
            return "[dim]No todos[/dim]"

        # Check if any items have priority, tags, or due dates
        has_priority = any(item.priority for item in items)
        has_tags = any(item.tags for item in items)
        has_due = any(item.due_at for item in items)

        table = Table(show_header=True, header_style="bold")

        if self.show_id:
            table.add_column("ID", style="dim")
        table.add_column("Done", width=6)
        if has_priority:
            table.add_column("Pri", width=5)
        table.add_column("Created", width=len(self._format_datetime(items[0].created_at)))
        table.add_column("Todo")
        if has_due:
            table.add_column("Due", width=12)
        if has_tags:
            table.add_column("Tags")

        for item in items:
            # Colorblind-safe: blue checkmark for done
            status = "[blue]✓[/blue]" if item.status == Status.DONE else "[dim]•[/dim]"
            created = self._format_datetime(item.created_at)

            row = []
            if self.show_id:
                row.append(item.id)  # Full ID, not truncated
            row.append(status)
            if has_priority:
                row.append(self._format_priority(item.priority))
            row.append(created)
            row.append(item.text)
            if has_due:
                row.append(self._format_due(item.due_at, item.status))
            if has_tags:
                row.append(self._format_tags(item.tags))

            table.add_row(*row)

        return table
