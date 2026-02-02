"""Obsidian-specific formatting for various syntax styles."""

from __future__ import annotations

import re

from dodo.models import Priority

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
