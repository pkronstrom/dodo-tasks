"""Rich table formatter."""

from typing import Any

from rich.table import Table

from dodo.models import Status, TodoItem


class TableFormatter:
    """Format todos as a Rich table."""

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
            table.add_column("ID", style="dim", width=8)
        table.add_column("Done", width=6)
        table.add_column("Created", width=len(self._format_datetime(items[0].created_at)))
        table.add_column("Todo")

        for item in items:
            status = "[green]✓[/green]" if item.status == Status.DONE else "[ ]"
            created = self._format_datetime(item.created_at)
            if self.show_id:
                table.add_row(item.id, status, created, item.text)
            else:
                table.add_row(status, created, item.text)

        return table
