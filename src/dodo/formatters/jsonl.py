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
            # to_dict() handles both TodoItem and TodoItemView
            if hasattr(item, "to_dict"):
                obj = item.to_dict()
            else:
                # Fallback for plain items
                obj = {
                    "id": item.id,
                    "text": item.text,
                    "status": item.status.value,
                    "created_at": item.created_at.isoformat(),
                    "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                    "project": item.project,
                }
            lines.append(json.dumps(obj))

        return "\n".join(lines)
