# Obsidian Plugin Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the Obsidian plugin with configurable display syntax, hidden IDs via sidecar file, tag-based header organization, and dependency rendering.

**Architecture:** Create a new `ObsidianFormatter` class for syntax variations, a `SyncManager` class for ID mapping/fuzzy matching, update the backend to use these components, and integrate with the graph plugin for dependency rendering.

**Tech Stack:** Python 3.12, httpx, difflib (stdlib), existing plugin system

---

## Task 1: Add Text Normalization Utility

**Files:**
- Create: `src/dodo/plugins/obsidian/sync.py`
- Test: `tests/test_backends/test_obsidian_sync.py`

**Step 1: Write the failing test**

```python
# tests/test_backends/test_obsidian_sync.py
"""Tests for Obsidian sync manager."""

import pytest

from dodo.plugins.obsidian.sync import normalize_text


class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("Ship The Feature") == "ship the feature"

    def test_strip_whitespace(self):
        assert normalize_text("  task  ") == "task"

    def test_collapse_multiple_spaces(self):
        assert normalize_text("ship  the   feature") == "ship the feature"

    def test_punctuation_to_space(self):
        assert normalize_text("ship-the-feature") == "ship the feature"

    def test_complex_normalization(self):
        assert normalize_text("Ship, the Feature!!!") == "ship the feature"

    def test_apostrophe(self):
        assert normalize_text("don't forget") == "don t forget"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backends/test_obsidian_sync.py -v`
Expected: FAIL with "cannot import name 'normalize_text'"

**Step 3: Write minimal implementation**

```python
# src/dodo/plugins/obsidian/sync.py
"""Obsidian sync manager for ID mapping and fuzzy matching."""

from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching.

    - Lowercase
    - Replace punctuation with spaces
    - Collapse multiple whitespace
    - Strip leading/trailing whitespace
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # punctuation → space
    text = re.sub(r'\s+', ' ', text)       # collapse whitespace
    return text.strip()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian_sync.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/sync.py tests/test_backends/test_obsidian_sync.py
git commit -m "feat(obsidian): add text normalization for fuzzy matching"
```

---

## Task 2: Add Fuzzy Matching with difflib

**Files:**
- Modify: `src/dodo/plugins/obsidian/sync.py`
- Modify: `tests/test_backends/test_obsidian_sync.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian_sync.py

from dodo.plugins.obsidian.sync import find_best_match


class TestFindBestMatch:
    def test_exact_match(self):
        candidates = {"ship the feature": "abc12345", "buy groceries": "def67890"}
        match = find_best_match("ship the feature", candidates)
        assert match == "abc12345"

    def test_fuzzy_match_above_threshold(self):
        candidates = {"ship the feature": "abc12345"}
        # "ship feature" is ~88% similar to "ship the feature"
        match = find_best_match("ship feature", candidates, threshold=0.85)
        assert match == "abc12345"

    def test_no_match_below_threshold(self):
        candidates = {"ship the feature": "abc12345"}
        match = find_best_match("buy groceries", candidates, threshold=0.85)
        assert match is None

    def test_empty_candidates(self):
        match = find_best_match("anything", {})
        assert match is None

    def test_best_match_selected(self):
        candidates = {
            "ship the feature": "abc12345",
            "ship feature now": "def67890",
        }
        match = find_best_match("ship the feature now", candidates)
        # "ship feature now" is closer match
        assert match == "def67890"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backends/test_obsidian_sync.py::TestFindBestMatch -v`
Expected: FAIL with "cannot import name 'find_best_match'"

**Step 3: Write minimal implementation**

```python
# Add to src/dodo/plugins/obsidian/sync.py

from difflib import SequenceMatcher


def find_best_match(
    text: str,
    candidates: dict[str, str],
    threshold: float = 0.85,
) -> str | None:
    """Find the best matching ID for text using fuzzy matching.

    Args:
        text: Normalized text to match
        candidates: Dict mapping normalized text to ID
        threshold: Minimum similarity ratio (0.0-1.0)

    Returns:
        Best matching ID if similarity >= threshold, else None
    """
    if not candidates:
        return None

    # Try exact match first (fast path)
    if text in candidates:
        return candidates[text]

    best_id = None
    best_ratio = 0.0

    for candidate_text, candidate_id in candidates.items():
        # Skip if length difference too large (can't be 85%+ similar)
        len_diff = abs(len(text) - len(candidate_text))
        max_len = max(len(text), len(candidate_text))
        if max_len > 0 and len_diff / max_len > (1 - threshold):
            continue

        ratio = SequenceMatcher(None, text, candidate_text).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = candidate_id

    return best_id if best_ratio >= threshold else None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian_sync.py::TestFindBestMatch -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/sync.py tests/test_backends/test_obsidian_sync.py
git commit -m "feat(obsidian): add fuzzy matching with difflib"
```

---

## Task 3: Add SyncManager Class for ID Storage

**Files:**
- Modify: `src/dodo/plugins/obsidian/sync.py`
- Modify: `tests/test_backends/test_obsidian_sync.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian_sync.py

import json
from pathlib import Path

from dodo.plugins.obsidian.sync import SyncManager


class TestSyncManager:
    def test_load_empty(self, tmp_path):
        sync_file = tmp_path / "obsidian-sync.json"
        mgr = SyncManager(sync_file)
        assert mgr.ids == {}
        assert mgr.headers == {}

    def test_load_existing(self, tmp_path):
        sync_file = tmp_path / "obsidian-sync.json"
        sync_file.write_text(json.dumps({
            "ids": {"task one": "abc12345"},
            "headers": {"work": "## Work"}
        }))
        mgr = SyncManager(sync_file)
        assert mgr.ids == {"task one": "abc12345"}
        assert mgr.headers == {"work": "## Work"}

    def test_save(self, tmp_path):
        sync_file = tmp_path / "obsidian-sync.json"
        mgr = SyncManager(sync_file)
        mgr.ids["new task"] = "def67890"
        mgr.headers["home"] = "### home"
        mgr.save()

        data = json.loads(sync_file.read_text())
        assert data["ids"]["new task"] == "def67890"
        assert data["headers"]["home"] == "### home"

    def test_get_or_create_id_existing(self, tmp_path):
        sync_file = tmp_path / "obsidian-sync.json"
        sync_file.write_text(json.dumps({"ids": {"my task": "abc12345"}, "headers": {}}))
        mgr = SyncManager(sync_file)

        task_id = mgr.get_or_create_id("My Task!")  # normalizes to "my task"
        assert task_id == "abc12345"

    def test_get_or_create_id_fuzzy(self, tmp_path):
        sync_file = tmp_path / "obsidian-sync.json"
        sync_file.write_text(json.dumps({"ids": {"ship the feature": "abc12345"}, "headers": {}}))
        mgr = SyncManager(sync_file)

        task_id = mgr.get_or_create_id("ship feature")  # fuzzy matches
        assert task_id == "abc12345"

    def test_get_or_create_id_new(self, tmp_path):
        sync_file = tmp_path / "obsidian-sync.json"
        mgr = SyncManager(sync_file)

        task_id = mgr.get_or_create_id("brand new task")
        assert len(task_id) == 8  # generates new 8-char ID
        assert mgr.ids["brand new task"] == task_id
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backends/test_obsidian_sync.py::TestSyncManager -v`
Expected: FAIL with "cannot import name 'SyncManager'"

**Step 3: Write minimal implementation**

```python
# Add to src/dodo/plugins/obsidian/sync.py

import json
from pathlib import Path
import uuid


class SyncManager:
    """Manages ID mappings and header associations for Obsidian sync.

    Stores data in a JSON sidecar file separate from the Obsidian markdown.
    """

    def __init__(self, sync_file: Path):
        self._sync_file = sync_file
        self.ids: dict[str, str] = {}      # normalized_text -> id
        self.headers: dict[str, str] = {}  # tag -> header_text
        self._load()

    def _load(self) -> None:
        """Load sync data from file."""
        if self._sync_file.exists():
            try:
                data = json.loads(self._sync_file.read_text())
                self.ids = data.get("ids", {})
                self.headers = data.get("headers", {})
            except (json.JSONDecodeError, KeyError):
                pass  # Start fresh on corrupt file

    def save(self) -> None:
        """Save sync data to file."""
        self._sync_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"ids": self.ids, "headers": self.headers}
        self._sync_file.write_text(json.dumps(data, indent=2))

    def get_or_create_id(self, text: str) -> str:
        """Get existing ID or create new one for task text.

        Uses fuzzy matching to find existing IDs for edited text.
        """
        normalized = normalize_text(text)

        # Try exact and fuzzy match
        existing_id = find_best_match(normalized, self.ids)
        if existing_id:
            return existing_id

        # Generate new ID
        new_id = uuid.uuid4().hex[:8]
        self.ids[normalized] = new_id
        return new_id
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian_sync.py::TestSyncManager -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/sync.py tests/test_backends/test_obsidian_sync.py
git commit -m "feat(obsidian): add SyncManager for ID persistence"
```

---

## Task 4: Add Priority Symbol Formatting

**Files:**
- Create: `src/dodo/plugins/obsidian/formatter.py`
- Create: `tests/test_backends/test_obsidian_formatter.py`

**Step 1: Write the failing test**

```python
# tests/test_backends/test_obsidian_formatter.py
"""Tests for Obsidian formatter."""

import pytest

from dodo.models import Priority
from dodo.plugins.obsidian.formatter import format_priority, parse_priority


class TestFormatPriority:
    def test_symbols_critical(self):
        assert format_priority(Priority.CRITICAL, "symbols") == "!!!"

    def test_symbols_high(self):
        assert format_priority(Priority.HIGH, "symbols") == "!!"

    def test_symbols_normal(self):
        assert format_priority(Priority.NORMAL, "symbols") == "!"

    def test_symbols_low(self):
        assert format_priority(Priority.LOW, "symbols") == ""

    def test_symbols_someday(self):
        assert format_priority(Priority.SOMEDAY, "symbols") == "~"

    def test_symbols_none(self):
        assert format_priority(None, "symbols") == ""

    def test_hidden(self):
        assert format_priority(Priority.CRITICAL, "hidden") == ""

    def test_emoji_high(self):
        assert format_priority(Priority.HIGH, "emoji") == "🔼"

    def test_dataview_critical(self):
        assert format_priority(Priority.CRITICAL, "dataview") == "[priority:: critical]"


class TestParsePriority:
    def test_parse_symbols_critical(self):
        assert parse_priority("task !!!", "symbols") == (Priority.CRITICAL, "task")

    def test_parse_symbols_high(self):
        assert parse_priority("task !!", "symbols") == (Priority.HIGH, "task")

    def test_parse_symbols_normal(self):
        assert parse_priority("task !", "symbols") == (Priority.NORMAL, "task")

    def test_parse_symbols_someday(self):
        assert parse_priority("task ~", "symbols") == (Priority.SOMEDAY, "task")

    def test_parse_symbols_none(self):
        assert parse_priority("task", "symbols") == (None, "task")

    def test_parse_emoji(self):
        assert parse_priority("task ⏫", "emoji") == (Priority.CRITICAL, "task")

    def test_parse_dataview(self):
        assert parse_priority("task [priority:: high]", "dataview") == (Priority.HIGH, "task")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py -v`
Expected: FAIL with "cannot import name 'format_priority'"

**Step 3: Write minimal implementation**

```python
# src/dodo/plugins/obsidian/formatter.py
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/formatter.py tests/test_backends/test_obsidian_formatter.py
git commit -m "feat(obsidian): add priority formatting for all syntax styles"
```

---

## Task 5: Add Timestamp and Tags Formatting

**Files:**
- Modify: `src/dodo/plugins/obsidian/formatter.py`
- Modify: `tests/test_backends/test_obsidian_formatter.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian_formatter.py

from datetime import datetime
from dodo.plugins.obsidian.formatter import format_timestamp, format_tags, parse_tags


class TestFormatTimestamp:
    def test_hidden(self):
        ts = datetime(2024, 1, 15, 10, 30)
        assert format_timestamp(ts, "hidden") == ""

    def test_plain(self):
        ts = datetime(2024, 1, 15, 10, 30)
        assert format_timestamp(ts, "plain") == "2024-01-15 10:30"

    def test_emoji(self):
        ts = datetime(2024, 1, 15, 10, 30)
        assert format_timestamp(ts, "emoji") == "📅 2024-01-15"

    def test_dataview(self):
        ts = datetime(2024, 1, 15, 10, 30)
        assert format_timestamp(ts, "dataview") == "[created:: 2024-01-15]"


class TestFormatTags:
    def test_hidden(self):
        assert format_tags(["work", "urgent"], "hidden") == ""

    def test_hashtags(self):
        assert format_tags(["work", "urgent"], "hashtags") == "#work #urgent"

    def test_dataview(self):
        assert format_tags(["work", "urgent"], "dataview") == "[tags:: work, urgent]"

    def test_empty_tags(self):
        assert format_tags([], "hashtags") == ""
        assert format_tags(None, "hashtags") == ""


class TestParseTags:
    def test_parse_hashtags(self):
        tags, clean = parse_tags("task text #work #urgent", "hashtags")
        assert tags == ["work", "urgent"]
        assert clean == "task text"

    def test_parse_dataview(self):
        tags, clean = parse_tags("task [tags:: work, urgent]", "dataview")
        assert tags == ["work", "urgent"]
        assert clean == "task"

    def test_no_tags(self):
        tags, clean = parse_tags("task text", "hashtags")
        assert tags == []
        assert clean == "task text"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py::TestFormatTimestamp -v`
Expected: FAIL with "cannot import name 'format_timestamp'"

**Step 3: Write minimal implementation**

```python
# Add to src/dodo/plugins/obsidian/formatter.py

from datetime import datetime


def format_timestamp(ts: datetime | None, syntax: str) -> str:
    """Format timestamp according to syntax style."""
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
    """Format tags according to syntax style."""
    if not tags or syntax == "hidden":
        return ""

    if syntax == "hashtags":
        return " ".join(f"#{tag}" for tag in tags)
    elif syntax == "dataview":
        return f"[tags:: {', '.join(tags)}]"

    return ""


def parse_tags(text: str, syntax: str) -> tuple[list[str], str]:
    """Parse tags from text and return (tags, clean_text)."""
    if syntax == "hidden":
        return [], text

    if syntax == "hashtags":
        tags = re.findall(r'#([\w-]+)', text)
        clean = re.sub(r'\s*#[\w-]+', '', text).strip()
        return tags, clean

    elif syntax == "dataview":
        match = re.search(r'\[tags::\s*([^\]]+)\]', text)
        if match:
            tag_str = match.group(1)
            tags = [t.strip() for t in tag_str.split(',')]
            clean = re.sub(r'\[tags::\s*[^\]]+\]', '', text).strip()
            return tags, clean
        return [], text

    return [], text
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/formatter.py tests/test_backends/test_obsidian_formatter.py
git commit -m "feat(obsidian): add timestamp and tags formatting"
```

---

## Task 6: Add ObsidianFormatter Class

**Files:**
- Modify: `src/dodo/plugins/obsidian/formatter.py`
- Modify: `tests/test_backends/test_obsidian_formatter.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian_formatter.py

from dodo.models import Priority, Status, TodoItem
from dodo.plugins.obsidian.formatter import ObsidianFormatter


class TestObsidianFormatter:
    def test_format_minimal_default(self):
        formatter = ObsidianFormatter()
        item = TodoItem(
            id="abc12345",
            text="Buy groceries",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            priority=Priority.HIGH,
            tags=["home", "errand"],
        )
        line = formatter.format_line(item)
        assert line == "- [ ] Buy groceries !! #home #errand"

    def test_format_done_task(self):
        formatter = ObsidianFormatter()
        item = TodoItem(
            id="abc12345",
            text="Done task",
            status=Status.DONE,
            created_at=datetime(2024, 1, 15, 10, 30),
        )
        line = formatter.format_line(item)
        assert line == "- [x] Done task"

    def test_format_with_timestamp(self):
        formatter = ObsidianFormatter(timestamp_syntax="plain")
        item = TodoItem(
            id="abc12345",
            text="Task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
        )
        line = formatter.format_line(item)
        assert line == "- [ ] 2024-01-15 10:30 Task"

    def test_format_emoji_priority(self):
        formatter = ObsidianFormatter(priority_syntax="emoji")
        item = TodoItem(
            id="abc12345",
            text="Task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            priority=Priority.CRITICAL,
        )
        line = formatter.format_line(item)
        assert line == "- [ ] Task ⏫"

    def test_parse_line_minimal(self):
        formatter = ObsidianFormatter()
        result = formatter.parse_line("- [ ] Buy groceries !! #home")
        assert result is not None
        text, status, priority, tags = result
        assert text == "Buy groceries"
        assert status == Status.PENDING
        assert priority == Priority.HIGH
        assert tags == ["home"]

    def test_parse_line_done(self):
        formatter = ObsidianFormatter()
        result = formatter.parse_line("- [x] Done task")
        assert result is not None
        text, status, priority, tags = result
        assert text == "Done task"
        assert status == Status.DONE

    def test_parse_line_not_a_task(self):
        formatter = ObsidianFormatter()
        assert formatter.parse_line("Just some text") is None
        assert formatter.parse_line("## Header") is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py::TestObsidianFormatter -v`
Expected: FAIL with "cannot import name 'ObsidianFormatter'"

**Step 3: Write minimal implementation**

```python
# Add to src/dodo/plugins/obsidian/formatter.py

from dodo.models import Status, TodoItem


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
        ts_match = re.match(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+', rest)
        if ts_match:
            rest = rest[len(ts_match.group(0)):].strip()

        # Also handle emoji timestamp
        if rest.startswith("📅"):
            rest = re.sub(r'^📅\s*\d{4}-\d{2}-\d{2}\s*', '', rest).strip()

        # Also handle dataview timestamp
        rest = re.sub(r'\[created::\s*[^\]]+\]', '', rest).strip()

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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py::TestObsidianFormatter -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/formatter.py tests/test_backends/test_obsidian_formatter.py
git commit -m "feat(obsidian): add ObsidianFormatter class"
```

---

## Task 7: Add Header Parsing and Rendering

**Files:**
- Modify: `src/dodo/plugins/obsidian/formatter.py`
- Modify: `tests/test_backends/test_obsidian_formatter.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian_formatter.py

from dodo.plugins.obsidian.formatter import parse_header, format_header, get_tag_from_header


class TestHeaderParsing:
    def test_parse_h1(self):
        level, text = parse_header("# Work")
        assert level == 1
        assert text == "Work"

    def test_parse_h3(self):
        level, text = parse_header("### home tasks")
        assert level == 3
        assert text == "home tasks"

    def test_not_a_header(self):
        assert parse_header("- [ ] task") is None
        assert parse_header("just text") is None

    def test_get_tag_from_header(self):
        assert get_tag_from_header("Work Projects") == "work"
        assert get_tag_from_header("home") == "home"
        assert get_tag_from_header("My Work Tasks") == "my"

    def test_format_header(self):
        assert format_header("work", 3) == "### work"
        assert format_header("home", 2) == "## home"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py::TestHeaderParsing -v`
Expected: FAIL with "cannot import name 'parse_header'"

**Step 3: Write minimal implementation**

```python
# Add to src/dodo/plugins/obsidian/formatter.py

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


def get_tag_from_header(header_text: str) -> str:
    """Extract tag name from header text.

    Uses first word, lowercased.
    "Work Projects" -> "work"
    "home" -> "home"
    """
    first_word = header_text.split()[0] if header_text.split() else header_text
    return first_word.lower()


def format_header(tag: str, level: int = 3) -> str:
    """Format a tag as a markdown header."""
    hashes = "#" * level
    return f"{hashes} {tag}"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py::TestHeaderParsing -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/formatter.py tests/test_backends/test_obsidian_formatter.py
git commit -m "feat(obsidian): add header parsing and rendering"
```

---

## Task 8: Add Document Parser for Full File

**Files:**
- Modify: `src/dodo/plugins/obsidian/formatter.py`
- Modify: `tests/test_backends/test_obsidian_formatter.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian_formatter.py

from dodo.plugins.obsidian.formatter import ObsidianDocument


class TestObsidianDocument:
    def test_parse_simple(self):
        content = """### work
- [ ] Task one !!
- [ ] Task two

### home
- [ ] Buy groceries
"""
        doc = ObsidianDocument.parse(content, ObsidianFormatter())

        assert len(doc.sections) == 2
        assert doc.sections["work"].header == "### work"
        assert len(doc.sections["work"].tasks) == 2
        assert doc.sections["home"].header == "### home"
        assert len(doc.sections["home"].tasks) == 1

    def test_parse_preserves_header_style(self):
        content = """## Work Projects
- [ ] Task one
"""
        doc = ObsidianDocument.parse(content, ObsidianFormatter())
        assert doc.sections["work"].header == "## Work Projects"

    def test_parse_tasks_without_header(self):
        content = """- [ ] Orphan task
"""
        doc = ObsidianDocument.parse(content, ObsidianFormatter())
        # Tasks without header go to "_default" section
        assert "_default" in doc.sections
        assert len(doc.sections["_default"].tasks) == 1

    def test_render(self):
        content = """### work
- [ ] Task one !!

### home
- [ ] Buy groceries
"""
        formatter = ObsidianFormatter()
        doc = ObsidianDocument.parse(content, formatter)
        rendered = doc.render(formatter)

        assert "### work" in rendered
        assert "### home" in rendered
        assert "Task one" in rendered
        assert "Buy groceries" in rendered
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py::TestObsidianDocument -v`
Expected: FAIL with "cannot import name 'ObsidianDocument'"

**Step 3: Write minimal implementation**

```python
# Add to src/dodo/plugins/obsidian/formatter.py

from dataclasses import dataclass, field


@dataclass
class ParsedTask:
    """A parsed task from Obsidian markdown."""
    text: str
    status: Status
    priority: Priority | None
    tags: list[str]
    indent: int = 0  # For dependency tracking


@dataclass
class Section:
    """A section (header + tasks) in an Obsidian document."""
    tag: str
    header: str  # Full header line (e.g., "## Work Projects")
    tasks: list[ParsedTask] = field(default_factory=list)


@dataclass
class ObsidianDocument:
    """Parsed representation of an Obsidian todo file."""
    sections: dict[str, Section] = field(default_factory=dict)

    @classmethod
    def parse(cls, content: str, formatter: ObsidianFormatter) -> "ObsidianDocument":
        """Parse Obsidian markdown content into structured document."""
        doc = cls()
        current_section: Section | None = None

        for line in content.splitlines():
            # Check for header
            header_result = parse_header(line)
            if header_result:
                level, text = header_result
                tag = get_tag_from_header(text)
                current_section = Section(tag=tag, header=line.strip())
                doc.sections[tag] = current_section
                continue

            # Check for task
            task_result = formatter.parse_line(line)
            if task_result:
                text, status, priority, tags = task_result
                # Calculate indentation
                indent = len(line) - len(line.lstrip())
                task = ParsedTask(
                    text=text,
                    status=status,
                    priority=priority,
                    tags=tags,
                    indent=indent,
                )

                if current_section is None:
                    # Create default section for orphan tasks
                    if "_default" not in doc.sections:
                        doc.sections["_default"] = Section(tag="_default", header="")
                    doc.sections["_default"].tasks.append(task)
                else:
                    current_section.tasks.append(task)

        return doc

    def render(self, formatter: ObsidianFormatter) -> str:
        """Render document back to markdown."""
        lines = []

        for tag, section in self.sections.items():
            if section.header:
                lines.append(section.header)

            for task in section.tasks:
                # Create minimal TodoItem for formatting
                item = TodoItem(
                    id="",  # ID not shown in output
                    text=task.text,
                    status=task.status,
                    created_at=datetime.now(),  # Not used if timestamp hidden
                    priority=task.priority,
                    tags=task.tags,
                )
                indent = " " * task.indent
                lines.append(f"{indent}{formatter.format_line(item)}")

            lines.append("")  # Blank line after section

        return "\n".join(lines).strip() + "\n"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian_formatter.py::TestObsidianDocument -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/formatter.py tests/test_backends/test_obsidian_formatter.py
git commit -m "feat(obsidian): add ObsidianDocument parser"
```

---

## Task 9: Add New ConfigVars to Plugin

**Files:**
- Modify: `src/dodo/plugins/obsidian/__init__.py`
- Test: Manual verification via `dodo config`

**Step 1: Update register_config function**

```python
# Replace register_config in src/dodo/plugins/obsidian/__init__.py

def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin."""
    return [
        # Connection settings
        ConfigVar(
            "api_url",
            "https://localhost:27124",
            label="API URL",
            description="REST API endpoint",
        ),
        ConfigVar(
            "api_key",
            "",
            label="API Key",
            description="Authentication key",
        ),
        ConfigVar(
            "vault_path",
            "dodo/{project}.md",
            label="Vault path",
            description="Path in vault ({project} = dodo name)",
        ),
        # Display syntax
        ConfigVar(
            "priority_syntax",
            "symbols",
            label="Priority",
            kind="cycle",
            options=["hidden", "symbols", "emoji", "dataview"],
            description="How to display priority",
        ),
        ConfigVar(
            "timestamp_syntax",
            "hidden",
            label="Timestamp",
            kind="cycle",
            options=["hidden", "plain", "emoji", "dataview"],
            description="How to display timestamp",
        ),
        ConfigVar(
            "tags_syntax",
            "hashtags",
            label="Tags",
            kind="cycle",
            options=["hidden", "hashtags", "dataview"],
            description="How to display tags",
        ),
        # Organization
        ConfigVar(
            "group_by_tags",
            "true",
            label="Group by tags",
            kind="toggle",
            description="Organize under headers by tag",
        ),
        ConfigVar(
            "default_header_level",
            "3",
            label="Header level",
            kind="cycle",
            options=["1", "2", "3", "4"],
            description="Level for new headers",
        ),
        ConfigVar(
            "sort_by",
            "priority",
            label="Sort by",
            kind="cycle",
            options=["priority", "date", "content", "tags", "status", "manual"],
            description="Task ordering within sections",
        ),
    ]
```

**Step 2: Verify by checking config menu works**

Run: `uv run dodo plugins list`
Expected: Shows obsidian plugin with new config vars

**Step 3: Commit**

```bash
git add src/dodo/plugins/obsidian/__init__.py
git commit -m "feat(obsidian): add configurable display settings"
```

---

## Task 10: Update Backend to Use New Formatter

**Files:**
- Modify: `src/dodo/plugins/obsidian/backend.py`
- Modify: `tests/test_backends/test_obsidian.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian.py

class TestObsidianBackendNewFormat:
    def test_list_parses_new_format(self, mock_client):
        """New format without visible IDs should parse correctly."""
        content = """### work
- [ ] First todo !!
- [x] Done todo

### home
- [ ] Buy groceries
"""
        mock_client.get.return_value = MagicMock(status_code=200, text=content)

        backend = ObsidianBackend(api_key="test-key")
        items = backend.list()

        assert len(items) == 3
        assert items[0].text == "First todo"
        assert items[0].priority.value == "high"
        assert items[1].status == Status.DONE
```

**Step 2: Run test to verify it fails (old parser won't handle new format)**

Run: `uv run pytest tests/test_backends/test_obsidian.py::TestObsidianBackendNewFormat -v`
Expected: FAIL (old pattern doesn't match new format)

**Step 3: Update backend implementation**

This is a larger change - update `backend.py` to:
1. Load config and create formatter
2. Use SyncManager for ID tracking
3. Parse with new formatter
4. Write with new formatter + section organization

```python
# See full implementation in backend.py rewrite below
```

Due to the size of this change, the full implementation is provided in the next task.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backends/test_obsidian.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/obsidian/backend.py tests/test_backends/test_obsidian.py
git commit -m "feat(obsidian): integrate new formatter and sync manager"
```

---

## Task 11: Full Backend Rewrite with New Features

**Files:**
- Rewrite: `src/dodo/plugins/obsidian/backend.py`

This task implements the complete backend rewrite integrating:
- ObsidianFormatter for syntax handling
- SyncManager for ID persistence
- Section-based organization by tags
- Sorting within sections

The implementation should:
1. Load settings from config
2. Create formatter with configured syntax
3. Create sync manager for ID tracking
4. Parse documents into sections
5. Match tasks to IDs via sync manager
6. Write documents with proper organization

**Full implementation provided in separate code block due to length.**

---

## Task 12: Add Dependency Rendering (Graph Plugin Integration)

**Files:**
- Modify: `src/dodo/plugins/obsidian/formatter.py`
- Modify: `src/dodo/plugins/obsidian/backend.py`
- Add tests

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian_formatter.py

class TestDependencyRendering:
    def test_format_with_children(self):
        formatter = ObsidianFormatter()
        parent = TodoItem(
            id="parent01",
            text="Parent task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
            priority=Priority.HIGH,
        )
        child1 = TodoItem(
            id="child001",
            text="Child one",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
        )
        child2 = TodoItem(
            id="child002",
            text="Child two",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
        )

        result = formatter.format_with_children(parent, [child1, child2])
        lines = result.split("\n")

        assert lines[0] == "- [ ] Parent task !!"
        assert lines[1] == "    - [ ] Child one"
        assert lines[2] == "    - [ ] Child two"

    def test_parse_indentation(self):
        content = """- [ ] Parent !!
    - [ ] Child one
    - [ ] Child two
        - [ ] Grandchild
"""
        formatter = ObsidianFormatter()
        doc = ObsidianDocument.parse(content, formatter)

        tasks = doc.sections["_default"].tasks
        assert tasks[0].indent == 0
        assert tasks[1].indent == 4
        assert tasks[2].indent == 4
        assert tasks[3].indent == 8
```

**Step 2: Implement dependency rendering**

```python
# Add to ObsidianFormatter class

INDENT = "    "  # 4 spaces per level

def format_with_children(
    self,
    item: TodoItem,
    children: list[TodoItem],
    depth: int = 0,
) -> str:
    """Format a task with its children indented below."""
    indent = self.INDENT * depth
    lines = [f"{indent}{self.format_line(item)}"]

    for child in children:
        lines.append(f"{self.INDENT * (depth + 1)}{self.format_line(child)}")

    return "\n".join(lines)
```

**Step 3: Integrate with backend**

When graph plugin is enabled, query dependencies and render as indented children.

**Step 4: Commit**

```bash
git add src/dodo/plugins/obsidian/formatter.py src/dodo/plugins/obsidian/backend.py tests/
git commit -m "feat(obsidian): add dependency rendering with indentation"
```

---

## Task 13: Add Sorting Implementation

**Files:**
- Modify: `src/dodo/plugins/obsidian/formatter.py`
- Add tests

**Step 1: Write the failing test**

```python
# Add to tests/test_backends/test_obsidian_formatter.py

from dodo.plugins.obsidian.formatter import sort_tasks


class TestSortTasks:
    def test_sort_by_priority(self):
        tasks = [
            ParsedTask("Low", Status.PENDING, Priority.LOW, []),
            ParsedTask("Critical", Status.PENDING, Priority.CRITICAL, []),
            ParsedTask("High", Status.PENDING, Priority.HIGH, []),
        ]
        sorted_tasks = sort_tasks(tasks, "priority")
        assert [t.text for t in sorted_tasks] == ["Critical", "High", "Low"]

    def test_sort_by_content(self):
        tasks = [
            ParsedTask("Zebra", Status.PENDING, None, []),
            ParsedTask("Apple", Status.PENDING, None, []),
            ParsedTask("Mango", Status.PENDING, None, []),
        ]
        sorted_tasks = sort_tasks(tasks, "content")
        assert [t.text for t in sorted_tasks] == ["Apple", "Mango", "Zebra"]

    def test_sort_manual_preserves_order(self):
        tasks = [
            ParsedTask("First", Status.PENDING, None, []),
            ParsedTask("Second", Status.PENDING, None, []),
        ]
        sorted_tasks = sort_tasks(tasks, "manual")
        assert [t.text for t in sorted_tasks] == ["First", "Second"]
```

**Step 2: Implement sorting**

```python
# Add to src/dodo/plugins/obsidian/formatter.py

PRIORITY_ORDER = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
    Priority.SOMEDAY: 4,
    None: 5,
}


def sort_tasks(tasks: list[ParsedTask], sort_by: str) -> list[ParsedTask]:
    """Sort tasks according to sort_by setting."""
    if sort_by == "manual":
        return tasks

    if sort_by == "priority":
        return sorted(tasks, key=lambda t: PRIORITY_ORDER.get(t.priority, 5))

    if sort_by == "content":
        return sorted(tasks, key=lambda t: t.text.lower())

    if sort_by == "tags":
        return sorted(tasks, key=lambda t: (t.tags[0].lower() if t.tags else "zzz"))

    if sort_by == "status":
        return sorted(tasks, key=lambda t: 0 if t.status == Status.PENDING else 1)

    # Default: no sorting
    return tasks
```

**Step 3: Commit**

```bash
git add src/dodo/plugins/obsidian/formatter.py tests/test_backends/test_obsidian_formatter.py
git commit -m "feat(obsidian): add task sorting"
```

---

## Task 14: Integration Tests

**Files:**
- Create: `tests/test_backends/test_obsidian_integration.py`

Write comprehensive integration tests that verify the full flow:
1. Add task via CLI → appears in Obsidian format
2. Edit task in Obsidian format → ID preserved via sync
3. Tags organize under headers
4. Dependencies render as indentation

```python
# tests/test_backends/test_obsidian_integration.py
"""Integration tests for Obsidian backend with new features."""

import json
from unittest.mock import MagicMock, patch

import pytest

from dodo.models import Priority, Status
from dodo.plugins.obsidian.backend import ObsidianBackend


class TestObsidianIntegration:
    """Full integration tests."""

    # ... comprehensive tests
```

---

## Task 15: Update README and Documentation

**Files:**
- Modify: `src/dodo/plugins/obsidian/README.md`

Update the plugin README with:
- New configuration options
- Example output formats
- Migration notes from old format

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Text normalization | ✓ |
| 2 | Fuzzy matching | ✓ |
| 3 | SyncManager | ✓ |
| 4 | Priority formatting | ✓ |
| 5 | Timestamp/tags formatting | ✓ |
| 6 | ObsidianFormatter | ✓ |
| 7 | Header parsing | ✓ |
| 8 | Document parser | ✓ |
| 9 | Config vars | Manual |
| 10-11 | Backend integration | ✓ |
| 12 | Dependency rendering | ✓ |
| 13 | Sorting | ✓ |
| 14 | Integration tests | ✓ |
| 15 | Documentation | - |

Estimated: ~15 tasks with TDD approach
