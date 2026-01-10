# Dodo CLI Startup Optimization & Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Optimize dodo CLI startup time by implementing lazy loading for adapters, caching config/git results, and cleaning up DRY violations.

**Architecture:** Move eager imports to lazy imports inside functions that need them. Add simple module-level caching for Config and git detection. Extract shared utilities from duplicate adapter code.

**Tech Stack:** Python 3.11+, pytest for testing

---

## Phase 1: Startup Performance (Critical)

### Task 1: Lazy Load Adapters in core.py

**Files:**
- Modify: `src/dodo/core.py:1-23, 56-74`
- Test: `tests/test_core.py`

**Step 1: Write test for lazy adapter loading**

Create a test that verifies adapters are not imported until needed:

```python
# tests/test_lazy_loading.py
"""Tests for lazy loading behavior."""

import sys


def test_markdown_adapter_not_imported_at_core_import():
    """Verify adapters aren't imported when core module loads."""
    # Remove any cached imports
    modules_to_remove = [
        k for k in sys.modules.keys()
        if k.startswith('dodo.adapters.') and k != 'dodo.adapters.base'
    ]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Also remove core to force reimport
    if 'dodo.core' in sys.modules:
        del sys.modules['dodo.core']

    # Import core
    import dodo.core  # noqa: F401

    # Adapters should NOT be imported yet
    assert 'dodo.adapters.markdown' not in sys.modules
    assert 'dodo.adapters.sqlite' not in sys.modules
    assert 'dodo.adapters.obsidian' not in sys.modules
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_lazy_loading.py -v`
Expected: FAIL - adapters are currently imported eagerly

**Step 3: Modify core.py to lazy load adapters**

Remove the eager adapter imports and move them inside `_create_adapter()`:

```python
"""Core todo service."""

from pathlib import Path
from typing import Any

from dodo.adapters.base import TodoAdapter
from dodo.config import Config
from dodo.models import Status, TodoItem
from dodo.project import detect_project_root


class TodoService:
    """Main service - routes to appropriate adapter."""

    def __init__(self, config: Config, project_id: str | None = None):
        self._config = config
        self._project_id = project_id
        self._adapter = self._create_adapter()

    def add(self, text: str) -> TodoItem:
        return self._adapter.add(text, project=self._project_id)

    def list(self, status: Status | None = None) -> list[TodoItem]:
        return self._adapter.list(project=self._project_id, status=status)

    def get(self, id: str) -> TodoItem | None:
        return self._adapter.get(id)

    def complete(self, id: str) -> TodoItem:
        return self._adapter.update(id, Status.DONE)

    def toggle(self, id: str) -> TodoItem:
        """Toggle status between PENDING and DONE."""
        item = self._adapter.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        new_status = Status.PENDING if item.status == Status.DONE else Status.DONE
        return self._adapter.update(id, new_status)

    def update_text(self, id: str, text: str) -> TodoItem:
        """Update todo text."""
        return self._adapter.update_text(id, text)

    def delete(self, id: str) -> None:
        self._adapter.delete(id)

    def _create_adapter(self) -> TodoAdapter:
        adapter_name = self._config.default_adapter

        if adapter_name == "markdown":
            from dodo.adapters.markdown import MarkdownAdapter
            return MarkdownAdapter(self._get_markdown_path())
        elif adapter_name == "sqlite":
            from dodo.adapters.sqlite import SqliteAdapter
            return SqliteAdapter(self._get_sqlite_path())
        elif adapter_name == "obsidian":
            from dodo.adapters.obsidian import ObsidianAdapter
            return ObsidianAdapter(
                api_url=self._config.obsidian_api_url,
                api_key=self._config.obsidian_api_key,
                vault_path=self._config.obsidian_vault_path,
            )

        raise ValueError(f"Unknown adapter: {adapter_name}")

    def _get_markdown_path(self) -> Path:
        if self._config.local_storage and self._project_id:
            root = detect_project_root(worktree_shared=self._config.worktree_shared)
            if root:
                return root / "dodo.md"

        if self._project_id:
            return self._config.config_dir / "projects" / self._project_id / "todo.md"

        return self._config.config_dir / "todo.md"

    def _get_sqlite_path(self) -> Path:
        if self._project_id:
            return self._config.config_dir / "projects" / self._project_id / "todos.db"
        return self._config.config_dir / "todos.db"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_lazy_loading.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/dodo/core.py tests/test_lazy_loading.py
git commit -m "perf: lazy load adapters in core.py

Only import the adapter that's actually configured,
avoiding expensive httpx import for non-Obsidian users."
```

---

### Task 2: Cache Config.load() Result

**Files:**
- Modify: `src/dodo/config.py:63-69`
- Test: `tests/test_config.py`

**Step 1: Write test for config caching**

```python
# Add to tests/test_config.py (or create if doesn't exist)

def test_config_load_caches_result(tmp_path, monkeypatch):
    """Config.load() should return cached instance on repeated calls."""
    monkeypatch.setenv("HOME", str(tmp_path))

    # Clear any existing cache
    from dodo import config
    config._config_cache = None

    cfg1 = config.Config.load()
    cfg2 = config.Config.load()

    # Should be the same instance
    assert cfg1 is cfg2


def test_config_cache_can_be_cleared(tmp_path, monkeypatch):
    """Config cache can be explicitly cleared."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from dodo import config
    config._config_cache = None

    cfg1 = config.Config.load()
    config.clear_config_cache()
    cfg2 = config.Config.load()

    # Should be different instances after cache clear
    assert cfg1 is not cfg2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_config_load_caches_result -v`
Expected: FAIL - no caching exists yet

**Step 3: Add caching to config.py**

Add a module-level cache and modify `Config.load()`:

```python
"""Configuration system with autodiscoverable toggles."""

import json
import os
from pathlib import Path
from typing import Any

# Module-level cache for singleton pattern
_config_cache: "Config | None" = None


def clear_config_cache() -> None:
    """Clear the config cache. Useful for testing or config reload."""
    global _config_cache
    _config_cache = None


class ConfigMeta:
    """Schema definition - separate from runtime state."""

    TOGGLES: dict[str, str] = {
        "worktree_shared": "Share todos across git worktrees",
        "local_storage": "Store todos in project dir (vs centralized)",
        "timestamps_enabled": "Add timestamps to todo entries",
    }

    SETTINGS: dict[str, str] = {
        "default_adapter": "Backend adapter (markdown|sqlite|obsidian)",
        "default_format": "Output format (table|jsonl|tsv)",
        "editor": "Editor command (empty = use $EDITOR)",
        "ai_command": "AI CLI command template",
        "ai_sys_prompt": "AI system prompt",
        "obsidian_api_url": "Obsidian REST API URL",
        "obsidian_api_key": "Obsidian API key",
        "obsidian_vault_path": "Path within Obsidian vault",
    }


class Config:
    """Runtime configuration with env override support."""

    DEFAULTS: dict[str, Any] = {
        # Toggles
        "worktree_shared": True,
        "local_storage": False,
        "timestamps_enabled": True,
        # Settings
        "default_adapter": "markdown",
        "default_format": "table",
        "editor": "",  # Empty = use $EDITOR or vim
        "ai_command": "claude -p '{{prompt}}' --system-prompt '{{system}}' --json-schema '{{schema}}' --output-format json --model haiku --tools ''",
        "ai_sys_prompt": (
            "Convert user input into a JSON array of todo strings. "
            "NEVER ask questions or add commentary. Output ONLY the JSON array, nothing else. "
            'If input is one task, return ["task"]. If multiple, split into separate items. '
            "Keep each item under 100 chars."
        ),
        "obsidian_api_url": "https://localhost:27124",
        "obsidian_api_key": "",
        "obsidian_vault_path": "dodo/todos.md",
    }

    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir or Path.home() / ".config" / "dodo"
        self._config_file = self._config_dir / "config.json"
        self._data: dict[str, Any] = {}

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @classmethod
    def load(cls, config_dir: Path | None = None) -> "Config":
        """Factory method - explicit loading with caching."""
        global _config_cache

        # Return cached instance if available and no custom dir specified
        if _config_cache is not None and config_dir is None:
            return _config_cache

        config = cls(config_dir)
        config._load_from_file()
        config._apply_env_overrides()

        # Cache if using default directory
        if config_dir is None:
            _config_cache = config

        return config

    def __getattr__(self, name: str) -> Any:
        """Access config values as attributes."""
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._data:
            return self._data[name]
        if name in self.DEFAULTS:
            return self.DEFAULTS[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def get_toggles(self) -> list[tuple[str, str, bool]]:
        """Return (attr, description, enabled) for interactive menu."""
        return [
            (name, desc, bool(getattr(self, name))) for name, desc in ConfigMeta.TOGGLES.items()
        ]

    def set(self, key: str, value: Any) -> None:
        """Set value and persist."""
        self._data[key] = value
        self._save()

    def _load_from_file(self) -> None:
        if self._config_file.exists():
            self._data = json.loads(self._config_file.read_text())

    def _save(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._config_file.write_text(json.dumps(self._data, indent=2))

    def _apply_env_overrides(self) -> None:
        """Apply DODO_* env vars (highest priority)."""
        for key, default in self.DEFAULTS.items():
            env_key = f"DODO_{key.upper()}"
            if env_key in os.environ:
                self._data[key] = self._coerce(os.environ[env_key], type(default))

    @staticmethod
    def _coerce(value: str, target_type: type) -> Any:
        """Coerce string env value to target type."""
        if target_type is bool:
            return value.lower() in ("true", "1", "yes")
        if target_type is int:
            return int(value)
        return value
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (may need to clear cache in test fixtures)

**Step 6: Commit**

```bash
git add src/dodo/config.py tests/test_config.py
git commit -m "perf: cache Config.load() result

Avoid repeated file reads and JSON parsing within
a single CLI invocation."
```

---

### Task 3: Cache Git Subprocess Results

**Files:**
- Modify: `src/dodo/project.py:1-19`
- Test: `tests/test_project.py`

**Step 1: Write test for git caching**

```python
# Add to tests/test_project.py

def test_detect_project_caches_result(tmp_path, monkeypatch):
    """detect_project() should cache result for repeated calls."""
    # Create a git repo
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

    monkeypatch.chdir(tmp_path)

    from dodo import project
    project.clear_project_cache()

    # Count subprocess calls
    original_run = subprocess.run
    call_count = [0]

    def counting_run(*args, **kwargs):
        if args and "git" in str(args[0]):
            call_count[0] += 1
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", counting_run)

    result1 = project.detect_project()
    result2 = project.detect_project()

    assert result1 == result2
    assert call_count[0] == 1  # Only one git call, not two
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project.py::test_detect_project_caches_result -v`
Expected: FAIL - currently makes subprocess call every time

**Step 3: Add caching to project.py**

```python
"""Project detection utilities."""

import subprocess
from hashlib import sha1
from pathlib import Path

# Module-level cache
_project_cache: dict[str, str | None] = {}


def clear_project_cache() -> None:
    """Clear the project detection cache. Useful for testing."""
    global _project_cache
    _project_cache.clear()


def detect_project(path: Path | None = None) -> str | None:
    """Detect project ID from current directory.

    Returns: project_id (e.g., 'myapp_d1204e') or None if not in a project.
    """
    path = path or Path.cwd()
    cache_key = str(path.resolve())

    if cache_key in _project_cache:
        return _project_cache[cache_key]

    git_root = _get_git_root(path)
    if not git_root:
        _project_cache[cache_key] = None
        return None

    result = _make_project_id(git_root)
    _project_cache[cache_key] = result
    return result


def detect_project_root(path: Path | None = None, worktree_shared: bool = True) -> Path | None:
    """Get project root path, respecting worktree config."""
    path = path or Path.cwd()

    if worktree_shared:
        return _get_git_common_root(path)
    else:
        return _get_git_root(path)


def _make_project_id(root: Path) -> str:
    """Generate readable project ID: dirname_shorthash."""
    name = root.name
    hash_input = str(root.resolve())
    short_hash = sha1(hash_input.encode()).hexdigest()[:6]
    return f"{name}_{short_hash}"


def _get_git_root(path: Path) -> Path | None:
    """Get git worktree root (or main repo root if not a worktree)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def _get_git_common_root(path: Path) -> Path | None:
    """Get shared git root (same for all worktrees of a repo)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
        git_dir = Path(result.stdout.strip())
        # --git-common-dir may return relative path like ".git"
        if not git_dir.is_absolute():
            git_dir = (path / git_dir).resolve()
        # Parent of .git is repo root
        if git_dir.name == ".git":
            return git_dir.parent
        # For worktrees, it returns /path/to/main/.git
        return git_dir.parent
    except subprocess.CalledProcessError:
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_project.py::test_detect_project_caches_result -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/dodo/project.py tests/test_project.py
git commit -m "perf: cache git subprocess results in detect_project()

Avoid spawning subprocess on every command when
project ID won't change during CLI invocation."
```

---

### Task 4: Remove Unused Import in Formatters

**Files:**
- Modify: `src/dodo/formatters/__init__.py:4`

**Step 1: Verify the import is unused**

Run: `grep -n "Any" src/dodo/formatters/__init__.py`
Expected: Only line 4 shows `from typing import Any`

**Step 2: Remove unused import**

Edit `src/dodo/formatters/__init__.py` to remove line 4:

```python
"""Output formatters for dodo list command."""

from dodo.models import TodoItem

from .base import FormatterProtocol
from .jsonl import JsonlFormatter
from .table import TableFormatter
from .tsv import TsvFormatter

FORMATTERS: dict[str, type] = {
    "table": TableFormatter,
    "jsonl": JsonlFormatter,
    "tsv": TsvFormatter,
}

DEFAULT_DATETIME_FMT = "%m-%d %H:%M"


def get_formatter(format_str: str) -> FormatterProtocol:
    """Parse format string and return configured formatter.

    Format string syntax: <name>:<datetime_fmt>:<options>

    Examples:
        "table"           -> TableFormatter()
        "table:%Y-%m-%d"  -> TableFormatter(datetime_fmt="%Y-%m-%d")
        "table::id"       -> TableFormatter(show_id=True)
        "table:%m-%d:id"  -> TableFormatter(datetime_fmt="%m-%d", show_id=True)
        "jsonl"           -> JsonlFormatter()
        "tsv"             -> TsvFormatter()
    """
    parts = format_str.split(":")
    name = parts[0]

    if name not in FORMATTERS:
        raise ValueError(f"Unknown format: {name}. Available: {', '.join(FORMATTERS.keys())}")

    cls = FORMATTERS[name]

    if name == "table":
        datetime_fmt = parts[1] if len(parts) > 1 and parts[1] else DEFAULT_DATETIME_FMT
        show_id = len(parts) > 2 and parts[2] == "id"
        return cls(datetime_fmt=datetime_fmt, show_id=show_id)

    return cls()


__all__ = [
    "FormatterProtocol",
    "TableFormatter",
    "JsonlFormatter",
    "TsvFormatter",
    "FORMATTERS",
    "get_formatter",
]
```

**Step 3: Run linter to verify**

Run: `ruff check src/dodo/formatters/__init__.py`
Expected: No errors

**Step 4: Run tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/dodo/formatters/__init__.py
git commit -m "chore: remove unused Any import from formatters"
```

---

## Phase 2: DRY Improvements

### Task 5: Extract Shared Adapter Utilities

**Files:**
- Create: `src/dodo/adapters/utils.py`
- Modify: `src/dodo/adapters/markdown.py`
- Modify: `src/dodo/adapters/obsidian.py`
- Test: `tests/test_adapters/test_utils.py`

**Step 1: Create test for shared utilities**

```python
# tests/test_adapters/test_utils.py
"""Tests for shared adapter utilities."""

import re
from datetime import datetime

from dodo.adapters.utils import generate_todo_id, TODO_LINE_PATTERN, format_todo_line
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters/test_utils.py -v`
Expected: FAIL - module doesn't exist

**Step 3: Create shared utilities module**

```python
# src/dodo/adapters/utils.py
"""Shared utilities for todo adapters."""

import re
from datetime import datetime
from hashlib import sha1

from dodo.models import Status, TodoItem

# Shared pattern for parsing todo lines in markdown format
# Matches: - [ ] 2024-01-15 10:30 - Todo text
# Groups: (checkbox_char, timestamp, text)
TODO_LINE_PATTERN = re.compile(
    r"^- \[([ xX])\] (\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}) - (.+)$"
)

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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_adapters/test_utils.py -v`
Expected: PASS

**Step 5: Commit utilities module**

```bash
git add src/dodo/adapters/utils.py tests/test_adapters/test_utils.py
git commit -m "refactor: extract shared adapter utilities

DRY: ID generation, line pattern, and formatting
now shared between markdown and obsidian adapters."
```

---

### Task 6: Update Markdown Adapter to Use Shared Utils

**Files:**
- Modify: `src/dodo/adapters/markdown.py`
- Test: `tests/test_adapters/test_markdown.py`

**Step 1: Run existing tests to establish baseline**

Run: `pytest tests/test_adapters/test_markdown.py -v`
Expected: All PASS (baseline)

**Step 2: Update markdown adapter to use shared utilities**

```python
"""Markdown file adapter."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dodo.adapters.utils import (
    generate_todo_id,
    format_todo_line,
    parse_todo_line,
    TIMESTAMP_FORMAT,
)
from dodo.models import Status, TodoItem


@dataclass
class MarkdownFormat:
    """Format settings - tweak these to change output."""

    timestamp_fmt: str = TIMESTAMP_FORMAT
    frontmatter: dict[str, str] | None = None
    section_header: str | None = None


class MarkdownAdapter:
    """Markdown file backend.

    To extend: modify _parse_line/_format_item or subclass.
    """

    def __init__(self, file_path: Path, format: MarkdownFormat | None = None):
        self._path = file_path
        self._format = format or MarkdownFormat()

    def add(self, text: str, project: str | None = None) -> TodoItem:
        timestamp = datetime.now()
        item = TodoItem(
            id=generate_todo_id(text, timestamp),
            text=text,
            status=Status.PENDING,
            created_at=timestamp,
            project=project,
        )
        self._append_item(item)
        return item

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        items = self._read_items()
        if status:
            items = [i for i in items if i.status == status]
        return items

    def get(self, id: str) -> TodoItem | None:
        return next((i for i in self._read_items() if i.id == id), None)

    def update(self, id: str, status: Status) -> TodoItem:
        lines, items = self._read_lines_with_items()
        updated_item = None

        for idx, (line, item) in enumerate(zip(lines, items)):
            if item and item.id == id:
                updated_item = TodoItem(
                    id=item.id,
                    text=item.text,
                    status=status,
                    created_at=item.created_at,
                    completed_at=datetime.now() if status == Status.DONE else None,
                    project=item.project,
                )
                lines[idx] = self._format_item(updated_item)
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_lines(lines)
        return updated_item

    def update_text(self, id: str, text: str) -> TodoItem:
        lines, items = self._read_lines_with_items()
        updated_item = None

        for idx, (line, item) in enumerate(zip(lines, items)):
            if item and item.id == id:
                updated_item = TodoItem(
                    id=generate_todo_id(text, item.created_at),
                    text=text,
                    status=item.status,
                    created_at=item.created_at,
                    completed_at=item.completed_at,
                    project=item.project,
                )
                lines[idx] = self._format_item(updated_item)
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_lines(lines)
        return updated_item

    def delete(self, id: str) -> None:
        lines, items = self._read_lines_with_items()
        original_len = len(lines)
        new_lines = [ln for ln, item in zip(lines, items) if not item or item.id != id]

        if len(new_lines) == original_len:
            raise KeyError(f"Todo not found: {id}")

        self._write_lines(new_lines)

    # Extension points

    def _parse_line(self, line: str) -> TodoItem | None:
        """Parse line -> TodoItem. Modify for different formats."""
        return parse_todo_line(line)

    def _format_item(self, item: TodoItem) -> str:
        """TodoItem -> line. Modify for different formats."""
        return format_todo_line(item, self._format.timestamp_fmt)

    def _render_file(self, lines: list[str]) -> str:
        """Full file content. Modify to add frontmatter/sections."""
        parts: list[str] = []

        if self._format.frontmatter:
            parts.append("---")
            for k, v in self._format.frontmatter.items():
                parts.append(f"{k}: {v}")
            parts.append("---")
            parts.append("")

        if self._format.section_header:
            parts.append(self._format.section_header)
            parts.append("")

        parts.extend(lines)
        return "\n".join(parts) + "\n" if parts else ""

    # Private helpers

    def _read_items(self) -> list[TodoItem]:
        if not self._path.exists():
            return []
        content = self._path.read_text()
        return [item for ln in content.splitlines() if (item := self._parse_line(ln))]

    def _read_lines_with_items(self) -> tuple[list[str], list[TodoItem | None]]:
        """Read lines paired with parsed items (None for non-todo lines)."""
        if not self._path.exists():
            return [], []
        lines = self._path.read_text().splitlines()
        items = [self._parse_line(ln) for ln in lines]
        return lines, items

    def _write_lines(self, lines: list[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Keep all lines (including non-todo lines like headers)
        self._path.write_text("\n".join(lines) + "\n" if lines else "")

    def _append_item(self, item: TodoItem) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if not self._path.exists():
            content = self._render_file([self._format_item(item)])
            self._path.write_text(content)
        else:
            with self._path.open("a") as f:
                f.write(self._format_item(item) + "\n")
```

**Step 3: Run tests to verify refactor didn't break anything**

Run: `pytest tests/test_adapters/test_markdown.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/dodo/adapters/markdown.py
git commit -m "refactor: use shared utils in markdown adapter"
```

---

### Task 7: Update Obsidian Adapter to Use Shared Utils

**Files:**
- Modify: `src/dodo/adapters/obsidian.py`
- Test: `tests/test_adapters/test_obsidian.py`

**Step 1: Run existing tests to establish baseline**

Run: `pytest tests/test_adapters/test_obsidian.py -v`
Expected: All PASS (or skip if no tests exist)

**Step 2: Update obsidian adapter to use shared utilities**

```python
"""Obsidian Local REST API adapter."""

from datetime import datetime

import httpx

from dodo.adapters.utils import (
    generate_todo_id,
    format_todo_line,
    parse_todo_line,
)
from dodo.models import Status, TodoItem


class ObsidianAdapter:
    """Obsidian Local REST API backend.

    Requires: obsidian-local-rest-api plugin running.
    Docs: https://github.com/coddingtonbear/obsidian-local-rest-api
    """

    DEFAULT_API_URL = "https://localhost:27124"

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str = "",
        vault_path: str = "dodo/todos.md",
    ):
        self._api_url = (api_url or self.DEFAULT_API_URL).rstrip("/")
        self._api_key = api_key
        self._vault_path = vault_path
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            verify=False,  # Local self-signed cert
            timeout=10.0,
        )

    def add(self, text: str, project: str | None = None) -> TodoItem:
        timestamp = datetime.now()
        item = TodoItem(
            id=generate_todo_id(text, timestamp),
            text=text,
            status=Status.PENDING,
            created_at=timestamp,
            project=project,
        )

        line = format_todo_line(item)
        self._append_to_note(line)
        return item

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        content = self._read_note()
        items = self._parse_content(content)

        if status:
            items = [i for i in items if i.status == status]
        return items

    def get(self, id: str) -> TodoItem | None:
        return next((i for i in self.list() if i.id == id), None)

    def update(self, id: str, status: Status) -> TodoItem:
        content = self._read_note()
        lines = content.splitlines()
        updated_item = None

        for idx, line in enumerate(lines):
            item = parse_todo_line(line)
            if item and item.id == id:
                updated_item = TodoItem(
                    id=item.id,
                    text=item.text,
                    status=status,
                    created_at=item.created_at,
                    completed_at=datetime.now() if status == Status.DONE else None,
                    project=item.project,
                )
                lines[idx] = format_todo_line(updated_item)
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_note("\n".join(lines))
        return updated_item

    def update_text(self, id: str, text: str) -> TodoItem:
        content = self._read_note()
        lines = content.splitlines()
        updated_item = None

        for idx, line in enumerate(lines):
            item = parse_todo_line(line)
            if item and item.id == id:
                updated_item = TodoItem(
                    id=generate_todo_id(text, item.created_at),
                    text=text,
                    status=item.status,
                    created_at=item.created_at,
                    completed_at=item.completed_at,
                    project=item.project,
                )
                lines[idx] = format_todo_line(updated_item)
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_note("\n".join(lines))
        return updated_item

    def delete(self, id: str) -> None:
        content = self._read_note()
        lines = content.splitlines()
        new_lines = [ln for ln in lines if not self._line_matches_id(ln, id)]

        if len(new_lines) == len(lines):
            raise KeyError(f"Todo not found: {id}")

        self._write_note("\n".join(new_lines))

    # REST API calls

    def _read_note(self) -> str:
        """GET /vault/{path}"""
        try:
            resp = self._client.get(f"{self._api_url}/vault/{self._vault_path}")
            if resp.status_code == 404:
                return ""
            resp.raise_for_status()
            return resp.text
        except httpx.RequestError as e:
            raise ConnectionError(f"Obsidian API error: {e}") from e

    def _write_note(self, content: str) -> None:
        """PUT /vault/{path}"""
        resp = self._client.put(
            f"{self._api_url}/vault/{self._vault_path}",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()

    def _append_to_note(self, line: str) -> None:
        """POST /vault/{path} with append."""
        resp = self._client.post(
            f"{self._api_url}/vault/{self._vault_path}",
            content=line + "\n",
            headers={
                "Content-Type": "text/markdown",
                "X-Append": "true",
            },
        )
        resp.raise_for_status()

    # Helpers

    def _parse_content(self, content: str) -> list[TodoItem]:
        return [item for ln in content.splitlines() if (item := parse_todo_line(ln))]

    def _line_matches_id(self, line: str, id: str) -> bool:
        item = parse_todo_line(line)
        return item is not None and item.id == id
```

**Step 3: Run tests to verify refactor didn't break anything**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/dodo/adapters/obsidian.py
git commit -m "refactor: use shared utils in obsidian adapter"
```

---

### Task 8: Clear Test Caches in Fixtures

**Files:**
- Modify: `tests/conftest.py` (create if doesn't exist)

**Step 1: Create/update conftest.py with cache-clearing fixture**

```python
# tests/conftest.py
"""Pytest fixtures for dodo tests."""

import pytest


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear module-level caches before each test."""
    from dodo import config, project

    config.clear_config_cache()
    project.clear_project_cache()

    yield

    # Also clear after test
    config.clear_config_cache()
    project.clear_project_cache()
```

**Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add fixture to clear module caches between tests"
```

---

## Phase 3: Final Verification

### Task 9: Measure Startup Time Improvement

**Step 1: Measure import time**

Run:
```bash
python -X importtime -c "from dodo.cli import app" 2>&1 | sort -t: -k2 -n | tail -20
```

Document the results - httpx should no longer appear in top imports for markdown users.

**Step 2: Time a simple command**

Run:
```bash
time dodo ls 2>/dev/null
```

Compare with baseline (if you measured before starting).

**Step 3: Run full test suite one final time**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

**Step 4: Final commit with summary**

```bash
git add -A
git commit -m "chore: cleanup complete - startup optimization and DRY improvements

Summary:
- Lazy load adapters (httpx only loaded for Obsidian users)
- Cache Config.load() and detect_project() results
- Extract shared adapter utilities (ID gen, line parsing)
- Remove unused imports

Startup time should be significantly improved for markdown users."
```

---

## Execution Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Lazy load adapters | core.py, test_lazy_loading.py |
| 2 | Cache Config.load() | config.py, test_config.py |
| 3 | Cache git subprocess | project.py, test_project.py |
| 4 | Remove unused import | formatters/__init__.py |
| 5 | Create shared utils | adapters/utils.py, test_utils.py |
| 6 | Update markdown adapter | adapters/markdown.py |
| 7 | Update obsidian adapter | adapters/obsidian.py |
| 8 | Test cache clearing | conftest.py |
| 9 | Final verification | (no changes) |

**Total: 9 tasks, ~15 commits**
