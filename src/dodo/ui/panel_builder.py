"""Shared utilities for building Rich panels with scrolling lists."""


def calculate_visible_range(
    cursor: int,
    total_items: int,
    max_visible: int,
    scroll_offset: int,
) -> tuple[int, int, int]:
    """Calculate visible range for a scrolling list.

    Args:
        cursor: Current cursor position
        total_items: Total number of items
        max_visible: Maximum items that fit on screen
        scroll_offset: Current scroll offset

    Returns:
        Tuple of (new_scroll_offset, visible_start, visible_end)
    """
    if total_items == 0:
        return 0, 0, 0

    # Clamp cursor to valid range first
    cursor = max(0, min(cursor, total_items - 1))

    # Adjust scroll to keep cursor visible
    if cursor < scroll_offset:
        scroll_offset = cursor
    elif cursor >= scroll_offset + max_visible:
        scroll_offset = cursor - max_visible + 1

    scroll_offset = max(0, min(scroll_offset, total_items - 1))
    visible_end = min(scroll_offset + max_visible, total_items)

    return scroll_offset, scroll_offset, visible_end


def format_scroll_indicator(hidden_above: int, hidden_below: int) -> tuple[str | None, str | None]:
    """Format scroll indicators.

    Returns:
        Tuple of (above_indicator, below_indicator) - None if no items hidden
    """
    above = f"[dim]  ↑ {hidden_above} more[/dim]" if hidden_above > 0 else None
    below = f"[dim]  ↓ {hidden_below} more[/dim]" if hidden_below > 0 else None
    return above, below
