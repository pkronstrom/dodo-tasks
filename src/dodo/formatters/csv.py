"""CSV formatter with headers."""

from dodo.models import TodoItem


class CsvFormatter:
    """Format todos as comma-separated values with headers.

    Columns: id, status, text
    """

    NAME = "csv"

    def format(self, items: list[TodoItem]) -> str:
        lines = ["id,status,text"]

        for item in items:
            # Escape text field (double quotes, commas)
            text = item.text.replace('"', '""')
            if "," in text or '"' in text or "\n" in text:
                text = f'"{text}"'
            lines.append(f"{item.id},{item.status.value},{text}")

        return "\n".join(lines)
