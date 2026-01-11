"""Tree formatter for dependency visualization."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.models import TodoItemView


class TreeFormatter:
    """Format todos as dependency tree."""

    def __init__(self, max_width: int = 70):
        self.max_width = max_width

    def _get_id(self, item) -> str:
        """Get ID from item or wrapped item."""
        if hasattr(item, "item"):
            return item.item.id
        return item.id

    def _get_text(self, item) -> str:
        """Get text from item or wrapped item."""
        if hasattr(item, "item"):
            return item.item.text
        return item.text

    def _get_status(self, item):
        """Get status from item or wrapped item."""
        if hasattr(item, "item"):
            return item.item.status
        return item.status

    def format(self, items: list[TodoItemView]) -> str:
        """Format items as a dependency tree.

        Returns a Rich-renderable Tree object that will be printed by cli.py.
        """
        from rich.console import Group
        from rich.tree import Tree

        from dodo.models import Status

        # Build lookup by ID
        by_id = {self._get_id(item): item for item in items}

        # Find roots (no blockers or blockers not in list)
        roots = []
        for item in items:
            blockers = getattr(item, "blocked_by", [])
            if not blockers or not any(b in by_id for b in blockers):
                roots.append(item)

        # Build children map (who does this item block?)
        children: dict[str, list] = {self._get_id(item): [] for item in items}
        for item in items:
            for blocker_id in getattr(item, "blocked_by", []):
                if blocker_id in children:
                    children[blocker_id].append(item)

        # Render using rich Tree
        rendered: set[str] = set()

        def truncate(text: str, max_len: int) -> str:
            if len(text) <= max_len:
                return text
            return text[: max_len - 1] + "…"

        def format_item(item) -> str:
            item_id = self._get_id(item)
            is_done = self._get_status(item) == Status.DONE
            # Colorblind-safe: blue for done, orange for pending
            icon = "[dodger_blue2]✓[/dodger_blue2]" if is_done else "[dark_orange]•[/dark_orange]"
            text = truncate(self._get_text(item), self.max_width)

            if is_done:
                return f"{icon} [dim]{item_id[:8]}[/dim] [dim strike]{text}[/dim strike]"

            kids = children.get(item_id, [])
            arrow = f" [orange1]→{len(kids)}[/orange1]" if kids else ""
            return f"{icon} [dim]{item_id[:8]}[/dim] {text}{arrow}"

        def add_children(tree_node, parent_id: str) -> None:
            for child in children.get(parent_id, []):
                child_id = self._get_id(child)
                if child_id in rendered:
                    continue
                rendered.add(child_id)
                child_node = tree_node.add(format_item(child))
                add_children(child_node, child_id)

        # Build forest of trees
        trees = []
        for root in roots:
            item_id = self._get_id(root)
            if item_id in rendered:
                continue
            rendered.add(item_id)

            tree = Tree(format_item(root), guide_style="dim")
            add_children(tree, item_id)
            trees.append(tree)

        # Return a Group of trees - Rich will render this properly
        return Group(*trees)
