"""Tests for panel builder utilities."""

from dodo.ui.panel_builder import calculate_visible_range, format_scroll_indicator


def test_calculate_visible_range_no_scroll():
    """No scroll needed when items fit."""
    offset, start, end = calculate_visible_range(
        cursor=2, total_items=5, max_visible=10, scroll_offset=0
    )
    assert start == 0
    assert end == 5


def test_calculate_visible_range_scroll_down():
    """Scroll down when cursor exceeds visible area."""
    offset, start, end = calculate_visible_range(
        cursor=15, total_items=20, max_visible=10, scroll_offset=0
    )
    assert start == 6  # Scrolled to show cursor
    assert end == 16


def test_format_scroll_indicator_above():
    """Show count of items above."""
    above, below = format_scroll_indicator(hidden_above=5, hidden_below=0)
    assert "↑ 5 more" in above
    assert below is None


def test_format_scroll_indicator_below():
    """Show count of items below."""
    above, below = format_scroll_indicator(hidden_above=0, hidden_below=3)
    assert above is None
    assert "↓ 3 more" in below
