"""Tab-separated values formatter."""

from dodo.models import TodoItem


class TsvFormatter:
    """Format todos as tab-separated values."""

    NAME = "tsv"

    def format(self, items: list[TodoItem]) -> str:
        if not items:
            return ""

        lines = []
        for item in items:
            lines.append(f"{item.id}\t{item.status.value}\t{item.text}")

        return "\n".join(lines)
