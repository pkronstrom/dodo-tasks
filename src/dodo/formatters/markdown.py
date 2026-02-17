"""Markdown checkbox formatter."""

from dodo.models import Status, TodoItem


class MarkdownFormatter:
    """Format todos as markdown checkbox list."""

    NAME = "md"

    def format(self, items: list[TodoItem]) -> str:
        if not items:
            return ""

        lines = []
        for item in items:
            checkbox = "[x]" if item.status == Status.DONE else "[ ]"
            line = f"- {checkbox} {item.text}"
            if item.priority:
                line += f" !{item.priority.value}"
            if item.due_at:
                line += f" @{item.due_at.strftime('%Y-%m-%d')}"
            if item.tags:
                line += " " + " ".join(f"#{t}" for t in item.tags)
            lines.append(line)

        return "\n".join(lines)
