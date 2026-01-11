"""Rich table formatter."""

from typing import Any

from rich.table import Table

from dodo.models import Status, TodoItem


class TableFormatter:
    """Format todos as a Rich table.

    Automatically includes blocked_by column if items have dependencies.
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
        if not items:
            return "[dim]No todos[/dim]"

        # Check if any item has blocked_by
        has_blocked = any(getattr(item, "blocked_by", None) for item in items)

        table = Table(show_header=True, header_style="bold")

        if self.show_id:
            table.add_column("ID", style="dim", width=8)
        table.add_column("Done", width=6)
        table.add_column("Created", width=len(self._format_datetime(items[0].created_at)))
        table.add_column("Todo")
        if has_blocked:
            table.add_column("Blocked by", style="dark_orange")

        for item in items:
            # Colorblind-safe: blue checkmark for done
            status = (
                "[dodger_blue2]✓[/dodger_blue2]"
                if item.status == Status.DONE
                else "[dark_orange]•[/dark_orange]"
            )
            created = self._format_datetime(item.created_at)

            row = []
            if self.show_id:
                row.append(item.id[:8])
            row.extend([status, created, item.text])
            if has_blocked:
                row.append(self._format_blocked(item))

            table.add_row(*row)

        return table
