"""Plain text formatter."""

from dodo.models import TodoItem


class TxtFormatter:
    """Format todos as plain text lines with priority and tags."""

    NAME = "txt"

    def format(self, items: list[TodoItem]) -> str:
        if not items:
            return ""

        lines = []
        for item in items:
            line = item.text
            if item.priority:
                line += f" !{item.priority.value}"
            if item.tags:
                line += " " + " ".join(f"#{t}" for t in item.tags)
            lines.append(line)

        return "\n".join(lines)
