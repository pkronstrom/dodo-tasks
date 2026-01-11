"""Rich table formatter."""

from typing import Any

from rich.table import Table

from dodo.models import Status, TodoItem


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

    def format(self, items: list[TodoItem]) -> Any:
        if not items:
            return "[dim]No todos[/dim]"

        table = Table(show_header=True, header_style="bold")

        if self.show_id:
            table.add_column("ID", style="dim")
        table.add_column("Done", width=6)
        table.add_column("Created", width=len(self._format_datetime(items[0].created_at)))
        table.add_column("Todo")

        for item in items:
            # Colorblind-safe: blue checkmark for done
            status = "[blue]✓[/blue]" if item.status == Status.DONE else "[dim]•[/dim]"
            created = self._format_datetime(item.created_at)

            row = []
            if self.show_id:
                row.append(item.id)  # Full ID, not truncated
            row.extend([status, created, item.text])

            table.add_row(*row)

        return table
