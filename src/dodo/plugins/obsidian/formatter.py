"""Obsidian-specific formatting for various syntax styles."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from dodo.models import Priority, Status, TodoItem

if TYPE_CHECKING:
    pass

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

# Priority sort order (lower number = higher priority)
PRIORITY_ORDER = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
    Priority.SOMEDAY: 4,
    None: 5,
}

# Reverse mappings for parsing
SYMBOLS_TO_PRIORITY = {v: k for k, v in PRIORITY_SYMBOLS.items() if v}
EMOJI_TO_PRIORITY = {v: k for k, v in PRIORITY_EMOJI.items() if v}


def parse_header(line: str) -> tuple[int, str] | None:
    """Parse a markdown header line.

    Returns (level, text) or None if not a header.
    """
    line = line.strip()
    match = re.match(r'^(#{1,6})\s+(.+)$', line)
    if match:
        level = len(match.group(1))
        text = match.group(2).strip()
        return level, text
    return None


def get_section_key(header_text: str) -> str:
    """Get unique key for a section from its header text.

    Uses full header text (normalized) to avoid collisions.
    "Work Projects" -> "work projects"
    "Work Meetings" -> "work meetings"
    "home" -> "home"
    """
    return header_text.lower().strip()


def get_tag_from_header(header_text: str) -> str:
    """Extract primary tag name from header text.

    Uses first word, lowercased. Used for task-to-section matching.
    "Work Projects" -> "work"
    "home" -> "home"
    """
    first_word = header_text.split()[0] if header_text.split() else header_text
    return first_word.lower()


def format_header(tag: str, level: int = 3) -> str:
    """Format a tag as a markdown header."""
    hashes = "#" * level
    return f"{hashes} {tag}"


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

    INDENT = "    "  # 4 spaces per level

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

    def format_with_children(
        self,
        item: TodoItem,
        children: list[TodoItem],
        depth: int = 0,
    ) -> str:
        """Format a task with its children indented below.

        Args:
            item: The parent task to format
            children: List of child tasks to format below the parent
            depth: Nesting depth (0 = root level, 1 = first indent level, etc.)

        Returns:
            Formatted markdown string with parent and children properly indented
        """
        indent = self.INDENT * depth
        lines = [f"{indent}{self.format_line(item)}"]

        for child in children:
            lines.append(f"{self.INDENT * (depth + 1)}{self.format_line(child)}")

        return "\n".join(lines)

    def parse_line(self, line: str) -> tuple[str, Status, Priority | None, list[str], str | None, datetime | None] | None:
        """Parse a markdown line into (text, status, priority, tags, legacy_id, created_at).

        Returns None if line is not a task.
        The legacy_id is extracted from old format [id] but not used in new format.
        The created_at timestamp is preserved if present in any format.
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

        # Parse timestamp if present - preserve it!
        created_at = None

        # Pattern: YYYY-MM-DD HH:MM at start
        ts_match = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+", rest)
        if ts_match:
            try:
                created_at = datetime.strptime(f"{ts_match.group(1)} {ts_match.group(2)}", "%Y-%m-%d %H:%M")
            except ValueError:
                pass
            rest = rest[len(ts_match.group(0)):].strip()

        # Handle emoji timestamp: 📅 YYYY-MM-DD
        emoji_match = re.match(r"^\U0001f4c5\s*(\d{4}-\d{2}-\d{2})\s*", rest)
        if emoji_match and created_at is None:
            try:
                created_at = datetime.strptime(emoji_match.group(1), "%Y-%m-%d")
            except ValueError:
                pass
            rest = rest[len(emoji_match.group(0)):].strip()

        # Handle dataview timestamp: [created:: YYYY-MM-DD]
        dv_match = re.search(r"\[created::\s*(\d{4}-\d{2}-\d{2})\]", rest)
        if dv_match and created_at is None:
            try:
                created_at = datetime.strptime(dv_match.group(1), "%Y-%m-%d")
            except ValueError:
                pass
            rest = re.sub(r"\[created::\s*[^\]]+\]", "", rest).strip()

        # Handle legacy format with embedded ID: [abc12345] - text
        legacy_id = None
        legacy_match = re.match(r"^\[([a-f0-9]{8})\]\s*-\s*", rest)
        if legacy_match:
            legacy_id = legacy_match.group(1)
            rest = rest[len(legacy_match.group(0)):].strip()

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

        return rest.strip(), status, priority, tags, legacy_id, created_at


@dataclass
class ParsedTask:
    """A parsed task from Obsidian markdown."""

    text: str
    status: Status
    priority: Priority | None
    tags: list[str]
    indent: int = 0  # For dependency tracking
    legacy_id: str | None = None  # ID from old format [id] if present
    created_at: datetime | None = None  # Preserved timestamp


def sort_tasks(tasks: list[ParsedTask], sort_by: str) -> list[ParsedTask]:
    """Sort tasks while preserving parent-child relationships.

    Only root-level tasks (indent=0) are sorted. Children stay attached
    to their parent in their original relative order.

    Args:
        tasks: List of ParsedTask objects to sort
        sort_by: Sort mode - one of "priority", "content", "tags", "status", "manual"

    Returns:
        Sorted list of tasks (new list, original not modified)
    """
    if sort_by == "manual" or not tasks:
        return tasks

    # Group tasks: each root task with its children
    groups: list[list[ParsedTask]] = []
    current_group: list[ParsedTask] = []

    for task in tasks:
        if task.indent == 0:
            if current_group:
                groups.append(current_group)
            current_group = [task]
        else:
            # Child task - add to current group
            if current_group:
                current_group.append(task)
            else:
                # Orphan child (no parent) - treat as its own group
                groups.append([task])

    if current_group:
        groups.append(current_group)

    # Sort groups by their root task
    def get_sort_key(group: list[ParsedTask]) -> tuple:
        root = group[0]
        if sort_by == "priority":
            return (PRIORITY_ORDER.get(root.priority, 5),)
        elif sort_by == "content":
            return (root.text.lower(),)
        elif sort_by == "tags":
            return (root.tags[0].lower() if root.tags else "zzz",)
        elif sort_by == "status":
            return (0 if root.status == Status.PENDING else 1,)
        return (0,)

    sorted_groups = sorted(groups, key=get_sort_key)

    # Flatten back to list
    return [task for group in sorted_groups for task in group]


@dataclass
class Section:
    """A section (header + tasks) in an Obsidian document."""

    tag: str
    header: str  # Full header line (e.g., "## Work Projects")
    tasks: list[ParsedTask] = field(default_factory=list)
    trailing_content: list[str] = field(default_factory=list)  # Non-task lines after tasks


@dataclass
class ObsidianDocument:
    """Parsed representation of an Obsidian todo file.

    Preserves non-task content (YAML frontmatter, notes, blank lines) for round-trip fidelity.
    """

    preamble: list[str] = field(default_factory=list)  # Content before first section
    sections: dict[str, Section] = field(default_factory=dict)

    @classmethod
    def parse(cls, content: str, formatter: ObsidianFormatter) -> ObsidianDocument:
        """Parse Obsidian markdown content into structured document.

        Preserves all content including non-task lines for round-trip fidelity.
        """
        doc = cls()
        current_section: Section | None = None
        in_preamble = True
        pending_other_lines: list[str] = []

        for line in content.splitlines():
            # Check for header
            header_result = parse_header(line)
            if header_result:
                in_preamble = False
                # Save any pending other lines to previous section
                if current_section is not None:
                    current_section.trailing_content.extend(pending_other_lines)
                pending_other_lines = []

                level, text = header_result
                # Use full normalized text as key to avoid collisions
                key = get_section_key(text)
                tag = get_tag_from_header(text)  # Primary tag for matching
                current_section = Section(tag=tag, header=line.strip())
                doc.sections[key] = current_section
                continue

            # Check for task
            task_result = formatter.parse_line(line)
            if task_result:
                in_preamble = False
                text, status, priority, tags, legacy_id, created_at = task_result
                # Calculate indentation
                indent = len(line) - len(line.lstrip())
                task = ParsedTask(
                    text=text,
                    status=status,
                    priority=priority,
                    tags=tags,
                    indent=indent,
                    legacy_id=legacy_id,
                    created_at=created_at,
                )

                # Append any pending other lines to section first
                if current_section is not None and pending_other_lines:
                    current_section.trailing_content.extend(pending_other_lines)
                    pending_other_lines = []

                if current_section is None:
                    # Create default section for orphan tasks
                    if "_default" not in doc.sections:
                        doc.sections["_default"] = Section(tag="_default", header="")
                    doc.sections["_default"].tasks.append(task)
                else:
                    current_section.tasks.append(task)
                continue

            # Non-task, non-header line - preserve it
            if in_preamble:
                doc.preamble.append(line)
            else:
                pending_other_lines.append(line)

        # Don't forget trailing content after last section
        if current_section is not None and pending_other_lines:
            current_section.trailing_content.extend(pending_other_lines)
        elif pending_other_lines and "_default" in doc.sections:
            doc.sections["_default"].trailing_content.extend(pending_other_lines)

        return doc

    def render(self, formatter: ObsidianFormatter) -> str:
        """Render document back to markdown.

        Preserves preamble, section order, and trailing content for round-trip fidelity.
        """
        lines = []

        # Emit preamble (YAML frontmatter, etc.)
        if self.preamble:
            lines.extend(self.preamble)
            # Add blank line after preamble if it doesn't end with one
            if self.preamble and self.preamble[-1].strip():
                lines.append("")

        for key, section in self.sections.items():
            if section.header:
                lines.append(section.header)

            for task in section.tasks:
                # Create TodoItem for formatting, preserving timestamp
                item = TodoItem(
                    id="",  # ID not shown in output
                    text=task.text,
                    status=task.status,
                    created_at=task.created_at or datetime.now(),
                    priority=task.priority,
                    tags=task.tags,
                )
                indent = " " * task.indent
                lines.append(f"{indent}{formatter.format_line(item)}")

            # Emit trailing content (notes, blank lines)
            if section.trailing_content:
                lines.extend(section.trailing_content)
            elif section.tasks:
                lines.append("")  # Default blank line after tasks

        result = "\n".join(lines)
        # Ensure single trailing newline
        return result.rstrip() + "\n"
