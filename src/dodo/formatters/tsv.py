"""Tab-separated values formatter."""

from dodo.models import TodoItem


class TsvFormatter:
    """Format todos as tab-separated values.

    Columns: id, status, text, [blocked_by if present]
    """

    NAME = "tsv"

    def format(self, items: list[TodoItem]) -> str:
        if not items:
            return ""

        # Check if any item has blocked_by
        has_blocked = any(getattr(item, "blocked_by", None) for item in items)

        lines = []
        for item in items:
            row = [item.id, item.status.value, item.text]
            if has_blocked:
                blocked = getattr(item, "blocked_by", None) or []
                row.append(", ".join(b[:8] for b in blocked))
            lines.append("\t".join(row))

        return "\n".join(lines)
