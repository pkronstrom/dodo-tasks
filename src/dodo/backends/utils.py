"""Shared utilities for todo backends."""

import re
from datetime import datetime
from hashlib import sha1

from dodo.models import Status, TodoItem

# Shared pattern for parsing todo lines in markdown format
# Matches: - [ ] 2024-01-15 10:30 - Todo text
# Groups: (checkbox_char, timestamp, text)
TODO_LINE_PATTERN = re.compile(r"^- \[([ xX])\] (\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}) - (.+)$")

# Standard timestamp format for todo lines
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"


def generate_todo_id(text: str, timestamp: datetime) -> str:
    """Generate a consistent 8-char hex ID from text and timestamp.

    Truncates timestamp to minute precision for consistency.
    """
    ts_normalized = timestamp.replace(second=0, microsecond=0)
    content = f"{text}{ts_normalized.isoformat()}"
    return sha1(content.encode()).hexdigest()[:8]


def format_todo_line(item: TodoItem, timestamp_fmt: str = TIMESTAMP_FORMAT) -> str:
    """Format a TodoItem as a markdown checkbox line."""
    checkbox = "x" if item.status == Status.DONE else " "
    ts = item.created_at.strftime(timestamp_fmt)
    return f"- [{checkbox}] {ts} - {item.text}"


def parse_todo_line(line: str) -> TodoItem | None:
    """Parse a markdown todo line into a TodoItem.

    Returns None if line doesn't match expected format.
    """
    match = TODO_LINE_PATTERN.match(line.strip())
    if not match:
        return None

    checkbox, ts_str, text = match.groups()
    # Handle both - and / date separators, and T separator
    ts_str = ts_str.replace("/", "-").replace("T", " ")
    timestamp = datetime.strptime(ts_str, TIMESTAMP_FORMAT)

    return TodoItem(
        id=generate_todo_id(text, timestamp),
        text=text,
        status=Status.DONE if checkbox.lower() == "x" else Status.PENDING,
        created_at=timestamp,
    )
