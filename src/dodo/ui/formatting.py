"""Shared formatting utilities for priority and tags display."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.models import Priority

# Shared constants
MAX_DISPLAY_TAGS = 3  # Maximum tags to display in any formatter
MAX_PARSE_TAGS = 5  # Maximum tags to parse/store from input

# Priority indicators (Rich markup)
PRIORITY_INDICATORS: dict[str, str] = {
    "critical": "[red bold]!![/red bold]",
    "high": "[yellow]![/yellow]",
    "normal": "",
    "low": "[dim]↓[/dim]",
    "someday": "[dim]○[/dim]",
}


def format_priority(priority: Priority | None) -> str:
    """Format priority as a Rich markup indicator.

    Args:
        priority: Priority enum value or None

    Returns:
        Rich markup string for the priority indicator
    """
    if not priority:
        return ""
    return PRIORITY_INDICATORS.get(priority.value, "")


def format_tags(tags: list[str] | None, max_tags: int | None = None) -> str:
    """Format tags as dim hashtags.

    Args:
        tags: List of tag strings or None
        max_tags: Override max tags to display (defaults to MAX_DISPLAY_TAGS)

    Returns:
        Rich markup string with formatted tags (space-prefixed if non-empty)
    """
    if not tags:
        return ""
    limit = max_tags if max_tags is not None else MAX_DISPLAY_TAGS
    formatted = " ".join(f"[dim]#{t}[/dim]" for t in tags[:limit])
    return f" {formatted}" if formatted else ""
