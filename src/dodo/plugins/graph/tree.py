"""Tree formatter for dependency visualization."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.models import TodoItemView


class TreeFormatter:
    """Format todos as dependency tree with proper text wrapping."""

    MAX_WIDTH = 120  # Maximum width even on wide terminals
    MAX_LINES = 5  # Maximum lines per item before truncation
    ID_WIDTH = 10  # "• abc12345 " prefix width

    def __init__(self, max_width: int | None = None):
        # Get terminal width, cap at MAX_WIDTH
        term_width = shutil.get_terminal_size().columns
        self.max_width = min(max_width or term_width, self.MAX_WIDTH)

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

    def _wrap_text(self, text: str, width: int, indent: int = 0) -> list[str]:
        """Wrap text to width, returning list of lines.

        First line uses full width, subsequent lines are indented.
        """
        if width <= 0:
            return [text]

        lines = []
        remaining = text

        # First line
        if len(remaining) <= width:
            return [remaining]

        # Find wrap point (prefer space)
        wrap_at = width
        space_pos = remaining.rfind(" ", 0, width)
        if space_pos > width // 2:  # Only use space if not too early
            wrap_at = space_pos

        lines.append(remaining[:wrap_at].rstrip())
        remaining = remaining[wrap_at:].lstrip()

        # Subsequent lines with indent
        subsequent_width = width - indent
        while remaining:
            if len(remaining) <= subsequent_width:
                lines.append(remaining)
                break

            wrap_at = subsequent_width
            space_pos = remaining.rfind(" ", 0, subsequent_width)
            if space_pos > subsequent_width // 2:
                wrap_at = space_pos

            lines.append(remaining[:wrap_at].rstrip())
            remaining = remaining[wrap_at:].lstrip()

        return lines

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

        def format_item(item, depth: int = 0, has_more_siblings: bool = False) -> str:
            item_id = self._get_id(item)
            is_done = self._get_status(item) == Status.DONE
            text = self._get_text(item)

            # Colorblind-safe: blue for done, dim for pending (lighter than orange)
            icon = "[dodger_blue2]✓[/dodger_blue2]" if is_done else "[dim]•[/dim]"
            id_str = f"[dim]{item_id[:8]}[/dim]"

            # Calculate available width for text
            # Tree indent is roughly 4 chars per level
            tree_indent = depth * 4
            prefix_width = self.ID_WIDTH  # "• abc12345 "
            available = self.max_width - tree_indent - prefix_width

            # Child count indicator
            kids = children.get(item_id, [])
            suffix = f" [dodger_blue2]→{len(kids)}[/dodger_blue2]" if kids and not is_done else ""
            suffix_len = len(f" →{len(kids)}") if kids and not is_done else 0

            # Wrap text
            text_width = max(20, available - suffix_len)
            lines = self._wrap_text(text, text_width, indent=0)

            # Truncate to max lines
            if len(lines) > self.MAX_LINES:
                lines = lines[: self.MAX_LINES - 1]
                lines.append("…")

            # Continuation line prefix: preserve tree branch if node has children
            # "• abc12345 " = 11 chars, but icon is 1 char visually
            cont_indent = "           "  # 11 spaces to align under text
            if kids:
                # Show vertical bar to indicate tree continues
                cont_prefix = f"[dim]│[/dim]{cont_indent[1:]}"
            else:
                cont_prefix = cont_indent

            # Format output
            if is_done:
                # Done items: dimmed and strikethrough
                first_line = f"{icon} {id_str} [dim strike]{lines[0]}[/dim strike]"
                if len(lines) > 1:
                    continuation = "\n".join(
                        f"{cont_prefix}[dim strike]{line}[/dim strike]" for line in lines[1:]
                    )
                    return f"{first_line}\n{continuation}"
                return first_line
            else:
                # Pending items
                first_line = f"{icon} {id_str} {lines[0]}{suffix}"
                if len(lines) > 1:
                    continuation = "\n".join(f"{cont_prefix}{line}" for line in lines[1:])
                    return f"{first_line}\n{continuation}"
                return first_line

        def add_children(tree_node, parent_id: str, depth: int) -> None:
            for child in children.get(parent_id, []):
                child_id = self._get_id(child)
                if child_id in rendered:
                    continue
                rendered.add(child_id)
                child_node = tree_node.add(format_item(child, depth))
                add_children(child_node, child_id, depth + 1)

        # Build forest of trees
        trees = []
        for root in roots:
            item_id = self._get_id(root)
            if item_id in rendered:
                continue
            rendered.add(item_id)

            tree = Tree(format_item(root, depth=0), guide_style="dim")
            add_children(tree, item_id, depth=1)
            trees.append(tree)

        # Return a Group of trees - Rich will render this properly
        return Group(*trees)
