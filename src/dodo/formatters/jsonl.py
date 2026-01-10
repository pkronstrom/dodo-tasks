"""JSON lines formatter."""

import json

from dodo.models import TodoItem


class JsonlFormatter:
    """Format todos as JSON lines (one JSON object per line)."""

    NAME = "jsonl"

    def format(self, items: list[TodoItem]) -> str:
        if not items:
            return ""

        lines = []
        for item in items:
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
