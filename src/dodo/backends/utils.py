"""Shared utilities for todo backends."""

import re
import uuid
from datetime import datetime

from dodo.models import Priority, Status, TodoItem

# Shared pattern for parsing todo lines in markdown format
# Matches: - [ ] 2024-01-15 10:30 [abc12345] - Todo text
# Also matches legacy format without ID: - [ ] 2024-01-15 10:30 - Todo text
# Groups: (checkbox_char, timestamp, optional_id, text_with_metadata)
TODO_LINE_PATTERN = re.compile(
    r"^- \[([ xX])\] (\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2})(?: \[([a-f0-9]{8})\])? - (.+)$"
)

# Standard timestamp format for todo lines
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"

# Patterns for extracting priority and tags from text
PRIORITY_PATTERN = re.compile(r"\s*!(critical|high|normal|low|someday)\b")
TAG_PATTERN = re.compile(r"\s*#([\w-]+)")

PRIORITY_MAP = {
    "critical": Priority.CRITICAL,
    "high": Priority.HIGH,
    "normal": Priority.NORMAL,
    "low": Priority.LOW,
    "someday": Priority.SOMEDAY,
}


def generate_todo_id(text: str, timestamp: datetime) -> str:
    """Generate a unique 8-char hex ID.

    Uses UUID4 for uniqueness. Text and timestamp params kept for API compat.
    """
    return uuid.uuid4().hex[:8]


def format_todo_line(item: TodoItem, timestamp_fmt: str = TIMESTAMP_FORMAT) -> str:
    """Format a TodoItem as a markdown checkbox line with embedded ID."""
    checkbox = "x" if item.status == Status.DONE else " "
    ts = item.created_at.strftime(timestamp_fmt)

    # Build text with priority and tags appended
    text_parts = [item.text]
    if item.priority:
        text_parts.append(f"!{item.priority.value}")
    if item.tags:
        text_parts.extend(f"#{tag}" for tag in item.tags)

    full_text = " ".join(text_parts)
    return f"- [{checkbox}] {ts} [{item.id}] - {full_text}"


def parse_todo_line(line: str) -> TodoItem | None:
    """Parse a markdown todo line into a TodoItem.

    Returns None if line doesn't match expected format.
    Supports both new format with embedded ID and legacy format without.
    Extracts !priority and #tags from the text.
    """
    match = TODO_LINE_PATTERN.match(line.strip())
    if not match:
        return None

    checkbox, ts_str, todo_id, text_with_metadata = match.groups()
    # Handle both - and / date separators, and T separator
    ts_str = ts_str.replace("/", "-").replace("T", " ")
    timestamp = datetime.strptime(ts_str, TIMESTAMP_FORMAT)

    # Use embedded ID if present, otherwise generate new one (legacy format)
    final_id = todo_id if todo_id else generate_todo_id(text_with_metadata, timestamp)

    # Extract priority
    priority = None
    priority_match = PRIORITY_PATTERN.search(text_with_metadata)
    if priority_match:
        priority = PRIORITY_MAP.get(priority_match.group(1))

    # Extract tags
    tags = TAG_PATTERN.findall(text_with_metadata)
    tags = tags if tags else None

    # Clean text by removing priority and tags
    text = text_with_metadata
    text = PRIORITY_PATTERN.sub("", text)
    text = TAG_PATTERN.sub("", text)
    text = text.strip()

    return TodoItem(
        id=final_id,
        text=text,
        status=Status.DONE if checkbox.lower() == "x" else Status.PENDING,
        created_at=timestamp,
        priority=priority,
        tags=tags,
    )
