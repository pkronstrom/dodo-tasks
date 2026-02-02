"""Obsidian-specific formatting for various syntax styles."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from dodo.models import Priority, Status

if TYPE_CHECKING:
    from dodo.models import TodoItem

# Priority symbol mappings
PRIORITY_SYMBOLS = {
    Priority.CRITICAL: "!!!",
    Priority.HIGH: "!!",
    Priority.NORMAL: "!",
    Priority.LOW: "",
    Priority.SOMEDAY: "~",
}

PRIORITY_EMOJI = {
    Priority.CRITICAL: "⏫",
    Priority.HIGH: "🔼",
    Priority.NORMAL: "",
    Priority.LOW: "🔽",
    Priority.SOMEDAY: "⏬",
}

# Reverse mappings for parsing
SYMBOLS_TO_PRIORITY = {v: k for k, v in PRIORITY_SYMBOLS.items() if v}
EMOJI_TO_PRIORITY = {v: k for k, v in PRIORITY_EMOJI.items() if v}


def format_priority(priority: Priority | None, syntax: str) -> str:
    """Format priority according to syntax style.

    Args:
        priority: Priority level or None
        syntax: One of "hidden", "symbols", "emoji", "dataview"

    Returns:
        Formatted priority string (may be empty)
    """
    if priority is None or syntax == "hidden":
        return ""

    if syntax == "symbols":
        return PRIORITY_SYMBOLS.get(priority, "")
    elif syntax == "emoji":
        return PRIORITY_EMOJI.get(priority, "")
    elif syntax == "dataview":
        return f"[priority:: {priority.value}]"

    return ""


def parse_priority(text: str, syntax: str) -> tuple[Priority | None, str]:
    """Parse priority from text and return (priority, clean_text).

    Tries to parse priority in the given syntax style.
    Returns (None, original_text) if no priority found.
    """
    text = text.strip()

    if syntax == "hidden":
        return None, text

    if syntax == "symbols":
        # Check for symbol suffixes (longest first)
        for symbol in ["!!!", "!!", "!", "~"]:
            if text.endswith(symbol):
                priority = SYMBOLS_TO_PRIORITY.get(symbol)
                clean = text[:-len(symbol)].strip()
                return priority, clean
        return None, text

    elif syntax == "emoji":
        for emoji, priority in EMOJI_TO_PRIORITY.items():
            if emoji in text:
                clean = text.replace(emoji, "").strip()
                return priority, clean
        return None, text

    elif syntax == "dataview":
        match = re.search(r'\[priority::\s*(\w+)\]', text)
        if match:
            priority_str = match.group(1)
            try:
                priority = Priority(priority_str)
                clean = re.sub(r'\[priority::\s*\w+\]', '', text).strip()
                return priority, clean
            except ValueError:
                pass
        return None, text

    return None, text


def format_timestamp(ts: datetime | None, syntax: str) -> str:
    """Format timestamp according to syntax style.

    Args:
        ts: Timestamp or None
        syntax: One of "hidden", "plain", "emoji", "dataview"

    Returns:
        Formatted timestamp string (may be empty)
    """
    if ts is None or syntax == "hidden":
        return ""

    if syntax == "plain":
        return ts.strftime("%Y-%m-%d %H:%M")
    elif syntax == "emoji":
        return f"📅 {ts.strftime('%Y-%m-%d')}"
    elif syntax == "dataview":
        return f"[created:: {ts.strftime('%Y-%m-%d')}]"

    return ""


def format_tags(tags: list[str] | None, syntax: str) -> str:
    """Format tags according to syntax style.

    Args:
        tags: List of tag strings or None
        syntax: One of "hidden", "hashtags", "dataview"

    Returns:
        Formatted tags string (may be empty)
    """
    if not tags or syntax == "hidden":
        return ""

    if syntax == "hashtags":
        return " ".join(f"#{tag}" for tag in tags)
    elif syntax == "dataview":
        return f"[tags:: {', '.join(tags)}]"

    return ""


def parse_tags(text: str, syntax: str) -> tuple[list[str], str]:
    """Parse tags from text and return (tags, clean_text).

    Tries to parse tags in the given syntax style.
    Returns ([], original_text) if no tags found.

    Args:
        text: Text potentially containing tags
        syntax: One of "hidden", "hashtags", "dataview"

    Returns:
        Tuple of (list of tag strings, text with tags removed)
    """
    if syntax == "hidden":
        return [], text

    if syntax == "hashtags":
        tags = re.findall(r"#([\w-]+)", text)
        clean = re.sub(r"\s*#[\w-]+", "", text).strip()
        return tags, clean

    elif syntax == "dataview":
        match = re.search(r"\[tags::\s*([^\]]+)\]", text)
        if match:
            tag_str = match.group(1)
            tags = [t.strip() for t in tag_str.split(",")]
            clean = re.sub(r"\[tags::\s*[^\]]+\]", "", text).strip()
            return tags, clean
        return [], text

    return [], text


class ObsidianFormatter:
    """Formats TodoItems for Obsidian with configurable syntax.

    Handles bidirectional conversion between TodoItem and markdown lines.
    """

    def __init__(
        self,
        priority_syntax: str = "symbols",
        timestamp_syntax: str = "hidden",
        tags_syntax: str = "hashtags",
    ):
        self.priority_syntax = priority_syntax
        self.timestamp_syntax = timestamp_syntax
        self.tags_syntax = tags_syntax

    def format_line(self, item: TodoItem) -> str:
        """Format a TodoItem as a markdown checkbox line."""
        checkbox = "[x]" if item.status == Status.DONE else "[ ]"

        parts = [f"- {checkbox}"]

        # Timestamp (if enabled, goes after checkbox)
        ts = format_timestamp(item.created_at, self.timestamp_syntax)
        if ts:
            parts.append(ts)

        # Task text
        parts.append(item.text)

        # Priority (at end)
        prio = format_priority(item.priority, self.priority_syntax)
        if prio:
            parts.append(prio)

        # Tags (at end)
        tags = format_tags(item.tags, self.tags_syntax)
        if tags:
            parts.append(tags)

        return " ".join(parts)

    def parse_line(self, line: str) -> tuple[str, Status, Priority | None, list[str]] | None:
        """Parse a markdown line into (text, status, priority, tags).

        Returns None if line is not a task.
        """
        line = line.strip()

        # Must start with checkbox
        if not line.startswith("- ["):
            return None

        # Extract checkbox state
        if line.startswith("- [x]") or line.startswith("- [X]"):
            status = Status.DONE
            rest = line[5:].strip()
        elif line.startswith("- [ ]"):
            status = Status.PENDING
            rest = line[5:].strip()
        else:
            return None

        # Parse timestamp if present (skip it for now, just remove)
        # Pattern: YYYY-MM-DD HH:MM at start
        ts_match = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+", rest)
        if ts_match:
            rest = rest[len(ts_match.group(0)) :].strip()

        # Also handle emoji timestamp
        if rest.startswith("\U0001f4c5"):
            rest = re.sub(r"^\U0001f4c5\s*\d{4}-\d{2}-\d{2}\s*", "", rest).strip()

        # Also handle dataview timestamp
        rest = re.sub(r"\[created::\s*[^\]]+\]", "", rest).strip()

        # Parse tags (removes from text)
        tags, rest = parse_tags(rest, self.tags_syntax)
        # Also try other formats if no tags found
        if not tags:
            tags, rest = parse_tags(rest, "hashtags")
        if not tags:
            tags, rest = parse_tags(rest, "dataview")

        # Parse priority (removes from text)
        priority, rest = parse_priority(rest, self.priority_syntax)
        # Also try other formats if no priority found
        if priority is None:
            priority, rest = parse_priority(rest, "symbols")
        if priority is None:
            priority, rest = parse_priority(rest, "emoji")
        if priority is None:
            priority, rest = parse_priority(rest, "dataview")

        return rest.strip(), status, priority, tags
