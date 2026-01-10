"""Tree formatter for dependency visualization."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.models import TodoItem


class TreeFormatter:
    """Format todos as dependency tree."""

    def format(self, items: list[TodoItem]) -> str:
        """Format items as a dependency tree."""
        from dodo.models import Status

        # Build lookup
        by_id = {item.id: item for item in items}

        # Find roots (no blockers or blockers not in list)
        roots = []
        for item in items:
            blockers = getattr(item, "blocked_by", [])
            if not blockers or not any(b in by_id for b in blockers):
                roots.append(item)

        # Build children map (who does this item block?)
        children: dict[str, list[TodoItem]] = {item.id: [] for item in items}
        for item in items:
            for blocker_id in getattr(item, "blocked_by", []):
                if blocker_id in children:
                    children[blocker_id].append(item)

        # Render tree
        lines: list[str] = []
        rendered: set[str] = set()

        def render(item: TodoItem, prefix: str = "", connector: str = "") -> None:
            if item.id in rendered:
                return
            rendered.add(item.id)

            icon = "✓" if item.status == Status.DONE else "○"
            lines.append(f"{prefix}{connector}{icon} {item.text}")

            kids = children.get(item.id, [])
            for i, child in enumerate(kids):
                is_last = i == len(kids) - 1
                # Determine new prefix for children
                if connector:
                    new_prefix = prefix + ("    " if "└" in connector else "│   ")
                else:
                    new_prefix = prefix
                child_connector = "└── " if is_last else "├── "
                render(child, new_prefix, child_connector)

        for root in roots:
            render(root)

        return "\n".join(lines)
