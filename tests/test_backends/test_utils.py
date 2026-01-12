"""Tests for shared backend utilities."""

from datetime import datetime

from dodo.backends.utils import (
    TODO_LINE_PATTERN,
    format_todo_line,
    generate_todo_id,
    parse_todo_line,
)
from dodo.models import Status, TodoItem


def test_generate_todo_id_consistent():
    """Same text and timestamp should generate same ID."""
    ts = datetime(2024, 1, 15, 10, 30, 0)
    id1 = generate_todo_id("Buy milk", ts)
    id2 = generate_todo_id("Buy milk", ts)
    assert id1 == id2


def test_generate_todo_id_ignores_seconds():
    """ID should be consistent regardless of seconds."""
    ts1 = datetime(2024, 1, 15, 10, 30, 0)
    ts2 = datetime(2024, 1, 15, 10, 30, 45)
    assert generate_todo_id("Buy milk", ts1) == generate_todo_id("Buy milk", ts2)


def test_generate_todo_id_8_chars():
    """ID should be 8 hex characters."""
    ts = datetime(2024, 1, 15, 10, 30)
    id_ = generate_todo_id("Test", ts)
    assert len(id_) == 8
    assert all(c in "0123456789abcdef" for c in id_)


def test_todo_line_pattern_matches_pending():
    """Pattern should match pending todo lines."""
    line = "- [ ] 2024-01-15 10:30 - Buy milk"
    match = TODO_LINE_PATTERN.match(line)
    assert match is not None
    assert match.group(1) == " "
    assert match.group(2) == "2024-01-15 10:30"
    assert match.group(3) == "Buy milk"


def test_todo_line_pattern_matches_done():
    """Pattern should match completed todo lines."""
    line = "- [x] 2024-01-15 10:30 - Buy milk"
    match = TODO_LINE_PATTERN.match(line)
    assert match is not None
    assert match.group(1) == "x"


def test_format_todo_line_pending():
    """Format pending todo as markdown line."""
    item = TodoItem(
        id="abc12345",
        text="Buy milk",
        status=Status.PENDING,
        created_at=datetime(2024, 1, 15, 10, 30),
    )
    line = format_todo_line(item)
    assert line == "- [ ] 2024-01-15 10:30 - Buy milk"


def test_format_todo_line_done():
    """Format completed todo as markdown line."""
    item = TodoItem(
        id="abc12345",
        text="Buy milk",
        status=Status.DONE,
        created_at=datetime(2024, 1, 15, 10, 30),
    )
    line = format_todo_line(item)
    assert line == "- [x] 2024-01-15 10:30 - Buy milk"


def test_parse_todo_line_pending():
    """Parse pending todo line."""
    line = "- [ ] 2024-01-15 10:30 - Buy milk"
    item = parse_todo_line(line)
    assert item is not None
    assert item.text == "Buy milk"
    assert item.status == Status.PENDING


def test_parse_todo_line_done():
    """Parse completed todo line."""
    line = "- [x] 2024-01-15 10:30 - Buy milk"
    item = parse_todo_line(line)
    assert item is not None
    assert item.status == Status.DONE


def test_parse_todo_line_invalid():
    """Non-todo lines return None."""
    assert parse_todo_line("# Header") is None
    assert parse_todo_line("Regular text") is None
    assert parse_todo_line("") is None
