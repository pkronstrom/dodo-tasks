"""Tests for shared backend utilities."""

from datetime import datetime

from dodo.backends.utils import (
    TODO_LINE_PATTERN,
    format_todo_line,
    generate_todo_id,
    parse_todo_line,
)
from dodo.models import Status, TodoItem


def test_generate_todo_id_unique_for_same_text_same_minute():
    """IDs should be unique even for identical text at same timestamp."""
    ts = datetime(2024, 1, 15, 10, 30, 0)
    id1 = generate_todo_id("same text", ts)
    id2 = generate_todo_id("same text", ts)

    # Should be different due to random component
    assert id1 != id2


def test_generate_todo_id_8_chars():
    """ID should be 8 hex characters."""
    ts = datetime(2024, 1, 15, 10, 30)
    id_ = generate_todo_id("Test", ts)
    assert len(id_) == 8
    assert all(c in "0123456789abcdef" for c in id_)


def test_todo_line_pattern_matches_pending_with_id():
    """Pattern should match pending todo lines with embedded ID."""
    line = "- [ ] 2024-01-15 10:30 [abc12345] - Buy milk"
    match = TODO_LINE_PATTERN.match(line)
    assert match is not None
    assert match.group(1) == " "
    assert match.group(2) == "2024-01-15 10:30"
    assert match.group(3) == "abc12345"
    assert match.group(4) == "Buy milk"


def test_todo_line_pattern_matches_legacy_format():
    """Pattern should match legacy format without ID."""
    line = "- [ ] 2024-01-15 10:30 - Buy milk"
    match = TODO_LINE_PATTERN.match(line)
    assert match is not None
    assert match.group(1) == " "
    assert match.group(2) == "2024-01-15 10:30"
    assert match.group(3) is None  # No ID in legacy format
    assert match.group(4) == "Buy milk"


def test_todo_line_pattern_matches_done():
    """Pattern should match completed todo lines."""
    line = "- [x] 2024-01-15 10:30 [abc12345] - Buy milk"
    match = TODO_LINE_PATTERN.match(line)
    assert match is not None
    assert match.group(1) == "x"


def test_format_todo_line_pending():
    """Format pending todo as markdown line with embedded ID."""
    item = TodoItem(
        id="abc12345",
        text="Buy milk",
        status=Status.PENDING,
        created_at=datetime(2024, 1, 15, 10, 30),
    )
    line = format_todo_line(item)
    assert line == "- [ ] 2024-01-15 10:30 [abc12345] - Buy milk"


def test_format_todo_line_done():
    """Format completed todo as markdown line with embedded ID."""
    item = TodoItem(
        id="abc12345",
        text="Buy milk",
        status=Status.DONE,
        created_at=datetime(2024, 1, 15, 10, 30),
    )
    line = format_todo_line(item)
    assert line == "- [x] 2024-01-15 10:30 [abc12345] - Buy milk"


def test_parse_todo_line_pending_with_id():
    """Parse pending todo line with embedded ID."""
    line = "- [ ] 2024-01-15 10:30 [abc12345] - Buy milk"
    item = parse_todo_line(line)
    assert item is not None
    assert item.id == "abc12345"
    assert item.text == "Buy milk"
    assert item.status == Status.PENDING


def test_parse_todo_line_legacy_generates_id():
    """Parse legacy format generates new ID."""
    line = "- [ ] 2024-01-15 10:30 - Buy milk"
    item = parse_todo_line(line)
    assert item is not None
    assert len(item.id) == 8
    assert item.text == "Buy milk"
    assert item.status == Status.PENDING


def test_parse_todo_line_done():
    """Parse completed todo line."""
    line = "- [x] 2024-01-15 10:30 [abc12345] - Buy milk"
    item = parse_todo_line(line)
    assert item is not None
    assert item.id == "abc12345"
    assert item.status == Status.DONE


def test_parse_todo_line_invalid():
    """Non-todo lines return None."""
    assert parse_todo_line("# Header") is None
    assert parse_todo_line("Regular text") is None
    assert parse_todo_line("") is None
