"""JSON lines formatter."""

import json

from dodo.models import TodoItem


class JsonlFormatter:
    """Format todos as JSON lines (one JSON object per line).

    Uses item.to_dict() to serialize, which includes any plugin-added
    fields like blocked_by.
    """

    NAME = "jsonl"

    def format(self, items: list[TodoItem]) -> str:
        if not items:
            return ""

        lines = []
        for item in items:
            # Both TodoItem and TodoItemView implement to_dict()
            lines.append(json.dumps(item.to_dict()))

        return "\n".join(lines)
