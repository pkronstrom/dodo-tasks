# Dodo CLI Todo Manager - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a modular CLI todo manager that routes todos to various backends with smart project detection and AI-assisted creation.

**Architecture:** Layered design with Protocol-based adapters, Typer CLI, and Rich UI. Config follows pyafk pattern with autodiscoverable toggles. TodoService orchestrates routing between adapters based on project context.

**Tech Stack:** Python 3.11+, Typer, Rich, simple-term-menu, httpx, SQLite (stdlib)

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/dodo/__init__.py`
- Create: `src/dodo/__main__.py`
- Create: `.env.template`
- Create: `README.md`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "dodo"
version = "0.1.0"
description = "Todo router - manage todos across multiple backends"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }

dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "simple-term-menu>=1.6.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]

[project.scripts]
dodo = "dodo.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

**Step 2: Create directory structure**

Run:
```bash
mkdir -p src/dodo/adapters src/dodo/ui tests
```

**Step 3: Create src/dodo/__init__.py**

```python
"""Dodo - Todo router CLI."""

__version__ = "0.1.0"
```

**Step 4: Create src/dodo/__main__.py**

```python
"""Entry point for python -m dodo."""

from dodo.cli import app

if __name__ == "__main__":
    app()
```

**Step 5: Create .env.template**

```bash
# Dodo Configuration
# Copy to .env and customize

# Backend: markdown | sqlite | obsidian
DODO_DEFAULT_ADAPTER=markdown

# Toggles (true/false)
DODO_AI_ENABLED=false
DODO_WORKTREE_SHARED=true
DODO_LOCAL_STORAGE=false
DODO_TIMESTAMPS_ENABLED=true

# AI Configuration
DODO_AI_COMMAND="llm '{{prompt}}' -s '{{system}}' --schema '{{schema}}'"
DODO_AI_SYS_PROMPT="You are a todo formatter. Return a JSON array of clear, actionable todo items. If one task, return array with one item. If multiple implied, split them. Keep each under 100 chars. Return ONLY valid JSON array."

# Obsidian (if using obsidian adapter)
DODO_OBSIDIAN_API_URL=https://localhost:27124
DODO_OBSIDIAN_API_KEY=
DODO_OBSIDIAN_VAULT_PATH=dodo/todos.md
```

**Step 6: Create minimal README.md**

```markdown
# Dodo

Todo router - manage todos across multiple backends.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Add a todo (smart routing: local project or global)
dodo add "fix the bug"

# Add to global explicitly
dodo add -g "remember to buy milk"

# List todos
dodo list

# Mark done
dodo done <id>

# Interactive menu
dodo
```

## Configuration

Copy `.env.template` to `~/.config/dodo/.env` and customize.

## AI Backends

### llm (default)
```bash
DODO_AI_COMMAND="llm '{{prompt}}' -s '{{system}}' --schema '{{schema}}'"
```

### Claude CLI
```bash
DODO_AI_COMMAND="claude -p '{{prompt}}' --model haiku --json-schema '{{schema}}'"
```

### Gemini CLI (no schema enforcement)
```bash
DODO_AI_COMMAND="gemini '{{prompt}}' --output-format json"
```

### Codex CLI (requires schema file)
```bash
DODO_AI_COMMAND="codex exec '{{prompt}}' --output-schema ~/.config/dodo/schema.json"
```
```

**Step 7: Install in dev mode**

Run:
```bash
pip install -e ".[dev]"
```
Expected: Installs dodo package with dev dependencies

**Step 8: Commit**

```bash
git init
git add .
git commit -m "chore: initial project setup"
```

---

## Task 2: Models

**Files:**
- Create: `src/dodo/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the test**

```python
# tests/test_models.py
"""Tests for data models."""

from datetime import datetime

import pytest

from dodo.models import Status, TodoItem


class TestStatus:
    def test_pending_value(self):
        assert Status.PENDING.value == "pending"

    def test_done_value(self):
        assert Status.DONE.value == "done"


class TestTodoItem:
    def test_create_minimal(self):
        item = TodoItem(
            id="abc123",
            text="Test todo",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 9, 10, 30),
        )
        assert item.id == "abc123"
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert item.completed_at is None
        assert item.project is None

    def test_immutable(self):
        item = TodoItem(
            id="abc123",
            text="Test todo",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 9, 10, 30),
        )
        with pytest.raises(AttributeError):
            item.text = "Changed"  # type: ignore

    def test_with_project(self):
        item = TodoItem(
            id="abc123",
            text="Test todo",
            status=Status.DONE,
            created_at=datetime(2024, 1, 9, 10, 30),
            completed_at=datetime(2024, 1, 9, 11, 0),
            project="myapp_d1204e",
        )
        assert item.project == "myapp_d1204e"
        assert item.completed_at is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'dodo.models'"

**Step 3: Write the implementation**

```python
# src/dodo/models.py
"""Data models for dodo."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Status(Enum):
    """Todo item status."""

    PENDING = "pending"
    DONE = "done"


@dataclass(frozen=True)
class TodoItem:
    """Immutable todo item."""

    id: str
    text: str
    status: Status
    created_at: datetime
    completed_at: datetime | None = None
    project: str | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/dodo/models.py tests/test_models.py
git commit -m "feat: add TodoItem and Status models"
```

---

## Task 3: Config System

**Files:**
- Create: `src/dodo/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the test**

```python
# tests/test_config.py
"""Tests for config system."""

import json
import os
from pathlib import Path

import pytest

from dodo.config import Config, ConfigMeta


class TestConfigMeta:
    def test_toggles_defined(self):
        assert "ai_enabled" in ConfigMeta.TOGGLES
        assert "worktree_shared" in ConfigMeta.TOGGLES

    def test_settings_defined(self):
        assert "default_adapter" in ConfigMeta.SETTINGS


class TestConfigDefaults:
    def test_default_adapter(self):
        config = Config(Path("/tmp/dodo-test-nonexistent"))
        assert config.default_adapter == "markdown"

    def test_default_toggles(self):
        config = Config(Path("/tmp/dodo-test-nonexistent"))
        assert config.ai_enabled is False
        assert config.worktree_shared is True
        assert config.timestamps_enabled is True


class TestConfigLoad:
    def test_load_from_file(self, tmp_path: Path):
        config_dir = tmp_path / "dodo"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"ai_enabled": True, "default_adapter": "sqlite"}))

        config = Config.load(config_dir)

        assert config.ai_enabled is True
        assert config.default_adapter == "sqlite"

    def test_load_nonexistent_uses_defaults(self, tmp_path: Path):
        config = Config.load(tmp_path / "nonexistent")
        assert config.default_adapter == "markdown"


class TestConfigEnvOverrides:
    def test_env_overrides_bool(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_AI_ENABLED", "true")
        config = Config.load(tmp_path)
        assert config.ai_enabled is True

    def test_env_overrides_string(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_DEFAULT_ADAPTER", "sqlite")
        config = Config.load(tmp_path)
        assert config.default_adapter == "sqlite"


class TestConfigPersistence:
    def test_set_and_save(self, tmp_path: Path):
        config_dir = tmp_path / "dodo"
        config = Config.load(config_dir)

        config.set("ai_enabled", True)

        # Reload and verify
        config2 = Config.load(config_dir)
        assert config2.ai_enabled is True

    def test_get_toggles(self, tmp_path: Path):
        config = Config.load(tmp_path)
        toggles = config.get_toggles()

        assert len(toggles) > 0
        names = [t[0] for t in toggles]
        assert "ai_enabled" in names

        # Check format: (name, description, value)
        for name, desc, value in toggles:
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(value, bool)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'dodo.config'"

**Step 3: Write the implementation**

```python
# src/dodo/config.py
"""Configuration system with autodiscoverable toggles."""

from pathlib import Path
from typing import Any
import json
import os


class ConfigMeta:
    """Schema definition - separate from runtime state."""

    TOGGLES: dict[str, str] = {
        "ai_enabled": "Enable AI-assisted todo formatting",
        "worktree_shared": "Share todos across git worktrees",
        "local_storage": "Store todos in project dir (vs centralized)",
        "timestamps_enabled": "Add timestamps to todo entries",
    }

    SETTINGS: dict[str, str] = {
        "default_adapter": "Backend adapter (markdown|sqlite|obsidian)",
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
        "ai_enabled": False,
        "worktree_shared": True,
        "local_storage": False,
        "timestamps_enabled": True,
        # Settings
        "default_adapter": "markdown",
        "ai_command": "llm '{{prompt}}' -s '{{system}}' --schema '{{schema}}'",
        "ai_sys_prompt": (
            "You are a todo formatter. Return a JSON array of clear, actionable todo items. "
            "If one task, return array with one item. If multiple implied, split them. "
            "Keep each under 100 chars. Return ONLY valid JSON array."
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
        """Factory method - explicit loading."""
        config = cls(config_dir)
        config._load_from_file()
        config._apply_env_overrides()
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
            (name, desc, bool(getattr(self, name)))
            for name, desc in ConfigMeta.TOGGLES.items()
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

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/dodo/config.py tests/test_config.py
git commit -m "feat: add config system with autodiscoverable toggles"
```

---

## Task 4: Project Detection

**Files:**
- Create: `src/dodo/project.py`
- Create: `tests/test_project.py`

**Step 1: Write the test**

```python
# tests/test_project.py
"""Tests for project detection."""

import subprocess
from pathlib import Path

import pytest

from dodo.project import detect_project, detect_project_root, _make_project_id


class TestMakeProjectId:
    def test_format(self):
        path = Path("/home/user/projects/myapp")
        project_id = _make_project_id(path)

        # Should be dirname_6charhash
        assert project_id.startswith("myapp_")
        assert len(project_id) == len("myapp_") + 6

    def test_deterministic(self):
        path = Path("/home/user/projects/myapp")
        id1 = _make_project_id(path)
        id2 = _make_project_id(path)
        assert id1 == id2

    def test_different_paths_different_ids(self):
        id1 = _make_project_id(Path("/home/user/project1"))
        id2 = _make_project_id(Path("/home/user/project2"))
        assert id1 != id2


class TestDetectProject:
    def test_not_git_repo_returns_none(self, tmp_path: Path):
        result = detect_project(tmp_path)
        assert result is None

    def test_git_repo_returns_id(self, tmp_path: Path):
        # Init a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = detect_project(tmp_path)

        assert result is not None
        assert result.startswith(f"{tmp_path.name}_")

    def test_subdirectory_of_repo(self, tmp_path: Path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        result = detect_project(subdir)

        assert result is not None
        assert result.startswith(f"{tmp_path.name}_")


class TestDetectProjectRoot:
    def test_returns_git_root(self, tmp_path: Path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subdir = tmp_path / "src"
        subdir.mkdir()

        result = detect_project_root(subdir)

        assert result == tmp_path

    def test_not_git_returns_none(self, tmp_path: Path):
        result = detect_project_root(tmp_path)
        assert result is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'dodo.project'"

**Step 3: Write the implementation**

```python
# src/dodo/project.py
"""Project detection utilities."""

from pathlib import Path
from hashlib import sha1
import subprocess


def detect_project(path: Path | None = None) -> str | None:
    """Detect project ID from current directory.

    Returns: project_id (e.g., 'myapp_d1204e') or None if not in a project.
    """
    path = path or Path.cwd()

    git_root = _get_git_root(path)
    if not git_root:
        return None

    return _make_project_id(git_root)


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
        # --git-common-dir returns .git dir, parent is repo root
        if git_dir.name == ".git":
            return git_dir.parent
        # For worktrees, it returns /path/to/main/.git
        return git_dir.parent
    except subprocess.CalledProcessError:
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_project.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/dodo/project.py tests/test_project.py
git commit -m "feat: add project detection with git/worktree support"
```

---

## Task 5: Adapter Base Protocol

**Files:**
- Create: `src/dodo/adapters/__init__.py`
- Create: `src/dodo/adapters/base.py`
- Create: `tests/test_adapters/__init__.py`
- Create: `tests/test_adapters/test_base.py`

**Step 1: Create directory structure**

Run:
```bash
mkdir -p tests/test_adapters
touch src/dodo/adapters/__init__.py tests/test_adapters/__init__.py
```

**Step 2: Write the test**

```python
# tests/test_adapters/test_base.py
"""Tests for adapter base protocol."""

from typing import Protocol, runtime_checkable

from dodo.adapters.base import TodoAdapter
from dodo.models import Status, TodoItem


def test_protocol_is_runtime_checkable():
    """Verify TodoAdapter can be checked with isinstance."""
    assert hasattr(TodoAdapter, "__protocol_attrs__") or isinstance(TodoAdapter, type)


def test_protocol_methods():
    """Verify protocol defines expected methods."""
    # Get protocol methods (excluding dunder)
    methods = [m for m in dir(TodoAdapter) if not m.startswith("_")]

    assert "add" in methods
    assert "list" in methods
    assert "get" in methods
    assert "update" in methods
    assert "delete" in methods
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_adapters/test_base.py -v`
Expected: FAIL

**Step 4: Write the implementation**

```python
# src/dodo/adapters/base.py
"""Base adapter protocol."""

from typing import Protocol, runtime_checkable

from dodo.models import Status, TodoItem


@runtime_checkable
class TodoAdapter(Protocol):
    """Protocol for todo storage backends.

    Implement this to add new backends (sqlite, notion, etc.)
    """

    def add(self, text: str, project: str | None = None) -> TodoItem:
        """Create a new todo item."""
        ...

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        """List todos, optionally filtered."""
        ...

    def get(self, id: str) -> TodoItem | None:
        """Get single todo by ID."""
        ...

    def update(self, id: str, status: Status) -> TodoItem:
        """Update todo status."""
        ...

    def delete(self, id: str) -> None:
        """Delete a todo."""
        ...
```

**Step 5: Update src/dodo/adapters/__init__.py**

```python
# src/dodo/adapters/__init__.py
"""Todo adapters."""

from .base import TodoAdapter

__all__ = ["TodoAdapter"]
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/test_adapters/test_base.py -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add src/dodo/adapters/ tests/test_adapters/
git commit -m "feat: add TodoAdapter protocol"
```

---

## Task 6: Markdown Adapter

**Files:**
- Create: `src/dodo/adapters/markdown.py`
- Create: `tests/test_adapters/test_markdown.py`

**Step 1: Write the test**

```python
# tests/test_adapters/test_markdown.py
"""Tests for markdown adapter."""

from datetime import datetime
from pathlib import Path

import pytest

from dodo.adapters.markdown import MarkdownAdapter, MarkdownFormat
from dodo.models import Status


class TestMarkdownAdapterAdd:
    def test_add_creates_file(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        item = adapter.add("Test todo")

        assert todo_file.exists()
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert len(item.id) == 8

    def test_add_appends_to_file(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        adapter.add("First todo")
        adapter.add("Second todo")

        lines = todo_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestMarkdownAdapterList:
    def test_list_empty_file(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        items = adapter.list()

        assert items == []

    def test_list_all(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        adapter.add("First")
        adapter.add("Second")

        items = adapter.list()

        assert len(items) == 2

    def test_list_filter_by_status(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        item = adapter.add("First")
        adapter.add("Second")
        adapter.update(item.id, Status.DONE)

        pending = adapter.list(status=Status.PENDING)
        done = adapter.list(status=Status.DONE)

        assert len(pending) == 1
        assert len(done) == 1


class TestMarkdownAdapterUpdate:
    def test_update_status(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        item = adapter.add("Test todo")

        updated = adapter.update(item.id, Status.DONE)

        assert updated.status == Status.DONE
        assert "[x]" in todo_file.read_text()

    def test_update_nonexistent_raises(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        with pytest.raises(KeyError):
            adapter.update("nonexistent", Status.DONE)


class TestMarkdownAdapterDelete:
    def test_delete_removes_line(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        item1 = adapter.add("First")
        item2 = adapter.add("Second")

        adapter.delete(item1.id)

        items = adapter.list()
        assert len(items) == 1
        assert items[0].text == "Second"

    def test_delete_nonexistent_raises(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        with pytest.raises(KeyError):
            adapter.delete("nonexistent")


class TestMarkdownAdapterGet:
    def test_get_existing(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        item = adapter.add("Test")

        result = adapter.get(item.id)

        assert result is not None
        assert result.id == item.id

    def test_get_nonexistent(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        result = adapter.get("nonexistent")

        assert result is None


class TestMarkdownFormat:
    def test_custom_timestamp_format(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        fmt = MarkdownFormat(timestamp_fmt="%Y/%m/%d")
        adapter = MarkdownAdapter(todo_file, format=fmt)

        adapter.add("Test")

        content = todo_file.read_text()
        assert "/" in content  # Uses custom format
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters/test_markdown.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/dodo/adapters/markdown.py
"""Markdown file adapter."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from pathlib import Path
import re

from dodo.models import Status, TodoItem


@dataclass
class MarkdownFormat:
    """Format settings - tweak these to change output."""

    timestamp_fmt: str = "%Y-%m-%d %H:%M"
    frontmatter: dict[str, str] | None = None
    section_header: str | None = None


class MarkdownAdapter:
    """Markdown file backend.

    To extend: modify _parse_line/_format_item or subclass.
    """

    LINE_PATTERN = re.compile(
        r"^- \[([ xX])\] (\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}) - (.+)$"
    )

    def __init__(self, file_path: Path, format: MarkdownFormat | None = None):
        self._path = file_path
        self._format = format or MarkdownFormat()

    def add(self, text: str, project: str | None = None) -> TodoItem:
        timestamp = datetime.now()
        item = TodoItem(
            id=self._generate_id(text, timestamp),
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
        match = self.LINE_PATTERN.match(line.strip())
        if not match:
            return None

        checkbox, ts_str, text = match.groups()
        # Handle both - and / date separators
        ts_str = ts_str.replace("/", "-").replace("T", " ")
        timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")

        return TodoItem(
            id=self._generate_id(text, timestamp),
            text=text,
            status=Status.DONE if checkbox.lower() == "x" else Status.PENDING,
            created_at=timestamp,
        )

    def _format_item(self, item: TodoItem) -> str:
        """TodoItem -> line. Modify for different formats."""
        checkbox = "x" if item.status == Status.DONE else " "
        ts = item.created_at.strftime(self._format.timestamp_fmt)
        return f"- [{checkbox}] {ts} - {item.text}"

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

    def _generate_id(self, text: str, timestamp: datetime) -> str:
        content = f"{text}{timestamp.isoformat()}"
        return sha1(content.encode()).hexdigest()[:8]

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

**Step 4: Update adapters __init__.py**

```python
# src/dodo/adapters/__init__.py
"""Todo adapters."""

from .base import TodoAdapter
from .markdown import MarkdownAdapter, MarkdownFormat

__all__ = ["TodoAdapter", "MarkdownAdapter", "MarkdownFormat"]
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_adapters/test_markdown.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/dodo/adapters/ tests/test_adapters/
git commit -m "feat: add markdown adapter"
```

---

## Task 7: SQLite Adapter

**Files:**
- Create: `src/dodo/adapters/sqlite.py`
- Create: `tests/test_adapters/test_sqlite.py`

**Step 1: Write the test**

```python
# tests/test_adapters/test_sqlite.py
"""Tests for SQLite adapter."""

from pathlib import Path

import pytest

from dodo.adapters.sqlite import SqliteAdapter
from dodo.models import Status


class TestSqliteAdapterAdd:
    def test_add_creates_db(self, tmp_path: Path):
        db_file = tmp_path / "todos.db"
        adapter = SqliteAdapter(db_file)

        item = adapter.add("Test todo")

        assert db_file.exists()
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert len(item.id) == 8


class TestSqliteAdapterList:
    def test_list_empty(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        assert adapter.list() == []

    def test_list_filter_by_status(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        item = adapter.add("First")
        adapter.add("Second")
        adapter.update(item.id, Status.DONE)

        assert len(adapter.list(status=Status.PENDING)) == 1
        assert len(adapter.list(status=Status.DONE)) == 1

    def test_list_filter_by_project(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        adapter.add("Proj A todo", project="proj_a")
        adapter.add("Proj B todo", project="proj_b")

        items = adapter.list(project="proj_a")
        assert len(items) == 1
        assert items[0].text == "Proj A todo"


class TestSqliteAdapterUpdate:
    def test_update_status(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        item = adapter.add("Test")

        updated = adapter.update(item.id, Status.DONE)

        assert updated.status == Status.DONE
        assert updated.completed_at is not None

    def test_update_nonexistent_raises(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")

        with pytest.raises(KeyError):
            adapter.update("nonexistent", Status.DONE)


class TestSqliteAdapterDelete:
    def test_delete(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        item = adapter.add("Test")

        adapter.delete(item.id)

        assert adapter.get(item.id) is None

    def test_delete_nonexistent_raises(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")

        with pytest.raises(KeyError):
            adapter.delete("nonexistent")


class TestSqliteAdapterGet:
    def test_get_existing(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        item = adapter.add("Test")

        result = adapter.get(item.id)

        assert result is not None
        assert result.id == item.id

    def test_get_nonexistent(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        assert adapter.get("nonexistent") is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters/test_sqlite.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/dodo/adapters/sqlite.py
"""SQLite adapter."""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from dodo.models import Status, TodoItem


class SqliteAdapter:
    """SQLite backend - better for querying/filtering large lists."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            project TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_project ON todos(project);
        CREATE INDEX IF NOT EXISTS idx_status ON todos(status);
    """

    def __init__(self, db_path: Path):
        self._path = db_path
        self._ensure_schema()

    def add(self, text: str, project: str | None = None) -> TodoItem:
        item = TodoItem(
            id=uuid.uuid4().hex[:8],
            text=text,
            status=Status.PENDING,
            created_at=datetime.now(),
            project=project,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO todos (id, text, status, project, created_at) VALUES (?, ?, ?, ?, ?)",
                (item.id, item.text, item.status.value, item.project, item.created_at.isoformat()),
            )
        return item

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        query = "SELECT id, text, status, project, created_at, completed_at FROM todos WHERE 1=1"
        params: list[str] = []

        if project:
            query += " AND project = ?"
            params.append(project)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_item(row) for row in rows]

    def get(self, id: str) -> TodoItem | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, text, status, project, created_at, completed_at FROM todos WHERE id = ?",
                (id,),
            ).fetchone()
        return self._row_to_item(row) if row else None

    def update(self, id: str, status: Status) -> TodoItem:
        completed_at = datetime.now().isoformat() if status == Status.DONE else None

        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE todos SET status = ?, completed_at = ? WHERE id = ?",
                (status.value, completed_at, id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        return item

    def delete(self, id: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM todos WHERE id = ?", (id,))
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)

    def _row_to_item(self, row: tuple) -> TodoItem:
        id, text, status, project, created_at, completed_at = row
        return TodoItem(
            id=id,
            text=text,
            status=Status(status),
            project=project,
            created_at=datetime.fromisoformat(created_at),
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
        )
```

**Step 4: Update adapters __init__.py**

```python
# src/dodo/adapters/__init__.py
"""Todo adapters."""

from .base import TodoAdapter
from .markdown import MarkdownAdapter, MarkdownFormat
from .sqlite import SqliteAdapter

__all__ = ["TodoAdapter", "MarkdownAdapter", "MarkdownFormat", "SqliteAdapter"]
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_adapters/test_sqlite.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/dodo/adapters/ tests/test_adapters/
git commit -m "feat: add SQLite adapter"
```

---

## Task 8: Obsidian Adapter

**Files:**
- Create: `src/dodo/adapters/obsidian.py`
- Create: `tests/test_adapters/test_obsidian.py`

**Step 1: Write the test (with mocked HTTP)**

```python
# tests/test_adapters/test_obsidian.py
"""Tests for Obsidian adapter."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from dodo.adapters.obsidian import ObsidianAdapter
from dodo.models import Status


@pytest.fixture
def mock_client():
    """Mock httpx client."""
    with patch("dodo.adapters.obsidian.httpx.Client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


class TestObsidianAdapterAdd:
    def test_add_posts_to_api(self, mock_client):
        mock_client.get.return_value = MagicMock(status_code=404)  # File doesn't exist
        mock_client.post.return_value = MagicMock(status_code=200)

        adapter = ObsidianAdapter(api_key="test-key")
        item = adapter.add("Test todo")

        assert item.text == "Test todo"
        assert mock_client.post.called


class TestObsidianAdapterList:
    def test_list_parses_content(self, mock_client):
        content = "- [ ] 2024-01-09 10:30 - First todo\n- [x] 2024-01-09 11:00 - Done todo\n"
        mock_client.get.return_value = MagicMock(status_code=200, text=content)

        adapter = ObsidianAdapter(api_key="test-key")
        items = adapter.list()

        assert len(items) == 2
        assert items[0].text == "First todo"
        assert items[1].status == Status.DONE

    def test_list_empty_file(self, mock_client):
        mock_client.get.return_value = MagicMock(status_code=404)

        adapter = ObsidianAdapter(api_key="test-key")
        items = adapter.list()

        assert items == []


class TestObsidianAdapterUpdate:
    def test_update_puts_modified_content(self, mock_client):
        content = "- [ ] 2024-01-09 10:30 - Test todo\n"
        mock_client.get.return_value = MagicMock(status_code=200, text=content)
        mock_client.put.return_value = MagicMock(status_code=200)

        adapter = ObsidianAdapter(api_key="test-key")
        items = adapter.list()
        updated = adapter.update(items[0].id, Status.DONE)

        assert updated.status == Status.DONE
        assert mock_client.put.called
        # Verify the PUT content contains [x]
        call_kwargs = mock_client.put.call_args
        assert "[x]" in call_kwargs.kwargs.get("content", call_kwargs.args[1] if len(call_kwargs.args) > 1 else "")


class TestObsidianAdapterDelete:
    def test_delete_removes_line(self, mock_client):
        content = "- [ ] 2024-01-09 10:30 - Todo 1\n- [ ] 2024-01-09 11:00 - Todo 2\n"
        mock_client.get.return_value = MagicMock(status_code=200, text=content)
        mock_client.put.return_value = MagicMock(status_code=200)

        adapter = ObsidianAdapter(api_key="test-key")
        items = adapter.list()
        adapter.delete(items[0].id)

        assert mock_client.put.called
        call_kwargs = mock_client.put.call_args
        put_content = call_kwargs.kwargs.get("content", "")
        assert "Todo 1" not in put_content
        assert "Todo 2" in put_content
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters/test_obsidian.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/dodo/adapters/obsidian.py
"""Obsidian Local REST API adapter."""

import re
from datetime import datetime
from hashlib import sha1

import httpx

from dodo.models import Status, TodoItem


class ObsidianAdapter:
    """Obsidian Local REST API backend.

    Requires: obsidian-local-rest-api plugin running.
    Docs: https://github.com/coddingtonbear/obsidian-local-rest-api
    """

    DEFAULT_API_URL = "https://localhost:27124"

    LINE_PATTERN = re.compile(
        r"^- \[([ xX])\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) - (.+)$"
    )

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
            id=self._generate_id(text, timestamp),
            text=text,
            status=Status.PENDING,
            created_at=timestamp,
            project=project,
        )

        line = self._format_item(item)
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
            item = self._parse_line(line)
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

    # Format helpers

    def _generate_id(self, text: str, timestamp: datetime) -> str:
        content = f"{text}{timestamp.isoformat()}"
        return sha1(content.encode()).hexdigest()[:8]

    def _format_item(self, item: TodoItem) -> str:
        checkbox = "x" if item.status == Status.DONE else " "
        ts = item.created_at.strftime("%Y-%m-%d %H:%M")
        return f"- [{checkbox}] {ts} - {item.text}"

    def _parse_line(self, line: str) -> TodoItem | None:
        match = self.LINE_PATTERN.match(line.strip())
        if not match:
            return None
        checkbox, ts_str, text = match.groups()
        timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
        return TodoItem(
            id=self._generate_id(text, timestamp),
            text=text,
            status=Status.DONE if checkbox.lower() == "x" else Status.PENDING,
            created_at=timestamp,
        )

    def _parse_content(self, content: str) -> list[TodoItem]:
        return [item for ln in content.splitlines() if (item := self._parse_line(ln))]

    def _line_matches_id(self, line: str, id: str) -> bool:
        item = self._parse_line(line)
        return item is not None and item.id == id
```

**Step 4: Update adapters __init__.py**

```python
# src/dodo/adapters/__init__.py
"""Todo adapters."""

from .base import TodoAdapter
from .markdown import MarkdownAdapter, MarkdownFormat
from .obsidian import ObsidianAdapter
from .sqlite import SqliteAdapter

__all__ = [
    "TodoAdapter",
    "MarkdownAdapter",
    "MarkdownFormat",
    "SqliteAdapter",
    "ObsidianAdapter",
]
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_adapters/test_obsidian.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/dodo/adapters/ tests/test_adapters/
git commit -m "feat: add Obsidian REST API adapter"
```

---

## Task 9: Core TodoService

**Files:**
- Create: `src/dodo/core.py`
- Create: `tests/test_core.py`

**Step 1: Write the test**

```python
# tests/test_core.py
"""Tests for TodoService."""

from pathlib import Path

import pytest

from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Status


class TestTodoServiceAdd:
    def test_add_to_global(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)

        item = svc.add("Test todo")

        assert item.text == "Test todo"
        assert (tmp_path / "config" / "todo.md").exists()

    def test_add_to_project(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id="myapp_abc123")

        item = svc.add("Project todo")

        assert (tmp_path / "config" / "projects" / "myapp_abc123" / "todo.md").exists()


class TestTodoServiceList:
    def test_list_empty(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)

        items = svc.list()

        assert items == []

    def test_list_with_status_filter(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)
        item = svc.add("Test")
        svc.complete(item.id)
        svc.add("Pending")

        done = svc.list(status=Status.DONE)
        pending = svc.list(status=Status.PENDING)

        assert len(done) == 1
        assert len(pending) == 1


class TestTodoServiceComplete:
    def test_complete(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)
        item = svc.add("Test")

        completed = svc.complete(item.id)

        assert completed.status == Status.DONE


class TestTodoServiceDelete:
    def test_delete(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)
        item = svc.add("Test")

        svc.delete(item.id)

        assert svc.get(item.id) is None


class TestTodoServiceAdapterSelection:
    def test_uses_configured_adapter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_DEFAULT_ADAPTER", "sqlite")
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)

        svc.add("Test")

        # SQLite creates .db file, not .md
        assert (tmp_path / "config" / "todos.db").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/dodo/core.py
"""Core todo service."""

from pathlib import Path
from typing import Any

from dodo.adapters.base import TodoAdapter
from dodo.adapters.markdown import MarkdownAdapter
from dodo.adapters.obsidian import ObsidianAdapter
from dodo.adapters.sqlite import SqliteAdapter
from dodo.config import Config
from dodo.models import Status, TodoItem
from dodo.project import detect_project_root


class TodoService:
    """Main service - routes to appropriate adapter."""

    ADAPTERS: dict[str, type[Any]] = {
        "markdown": MarkdownAdapter,
        "sqlite": SqliteAdapter,
        "obsidian": ObsidianAdapter,
    }

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

    def delete(self, id: str) -> None:
        self._adapter.delete(id)

    def _create_adapter(self) -> TodoAdapter:
        adapter_name = self._config.default_adapter
        adapter_cls = self.ADAPTERS.get(adapter_name)

        if not adapter_cls:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        if adapter_name == "markdown":
            return adapter_cls(self._get_markdown_path())
        elif adapter_name == "sqlite":
            return adapter_cls(self._get_sqlite_path())
        elif adapter_name == "obsidian":
            return adapter_cls(
                api_url=self._config.obsidian_api_url,
                api_key=self._config.obsidian_api_key,
                vault_path=self._config.obsidian_vault_path,
            )

        raise ValueError(f"Unhandled adapter: {adapter_name}")

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

Run: `pytest tests/test_core.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/dodo/core.py tests/test_core.py
git commit -m "feat: add TodoService core"
```

---

## Task 10: AI Module

**Files:**
- Create: `src/dodo/ai.py`
- Create: `tests/test_ai.py`

**Step 1: Write the test**

```python
# tests/test_ai.py
"""Tests for AI module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from dodo.ai import run_ai, build_command


class TestBuildCommand:
    def test_substitutes_prompt(self):
        template = "llm '{{prompt}}' -s '{{system}}'"
        cmd = build_command(template, prompt="test prompt", system="sys", schema="{}")

        assert "test prompt" in cmd
        assert "sys" in cmd

    def test_substitutes_schema(self):
        template = "claude --json-schema '{{schema}}'"
        schema = '{"type": "array"}'
        cmd = build_command(template, prompt="test", system="sys", schema=schema)

        assert schema in cmd


class TestRunAi:
    @patch("dodo.ai.subprocess.run")
    def test_returns_list_from_json(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["Todo one", "Todo two"]',
            stderr="",
        )

        result = run_ai(
            user_input="test",
            command="llm '{{prompt}}'",
            system_prompt="format todos",
        )

        assert result == ["Todo one", "Todo two"]

    @patch("dodo.ai.subprocess.run")
    def test_includes_piped_content_in_prompt(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["From pipe"]',
            stderr="",
        )

        run_ai(
            user_input="what to do",
            piped_content="some piped content",
            command="llm '{{prompt}}'",
            system_prompt="format",
        )

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "piped" in cmd.lower() or "some piped content" in cmd

    @patch("dodo.ai.subprocess.run")
    def test_handles_single_item(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["Single todo"]',
            stderr="",
        )

        result = run_ai(
            user_input="test",
            command="llm '{{prompt}}'",
            system_prompt="format",
        )

        assert result == ["Single todo"]

    @patch("dodo.ai.subprocess.run")
    def test_error_returns_empty(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error",
        )

        result = run_ai(
            user_input="test",
            command="llm '{{prompt}}'",
            system_prompt="format",
        )

        assert result == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/dodo/ai.py
"""AI-assisted todo formatting."""

import json
import subprocess
import shlex

DEFAULT_SCHEMA = json.dumps({
    "type": "array",
    "items": {"type": "string"},
    "minItems": 1,
})


def build_command(
    template: str,
    prompt: str,
    system: str,
    schema: str,
) -> str:
    """Build command string from template."""
    return (
        template
        .replace("{{prompt}}", prompt)
        .replace("{{system}}", system)
        .replace("{{schema}}", schema)
    )


def run_ai(
    user_input: str,
    command: str,
    system_prompt: str,
    piped_content: str | None = None,
    schema: str | None = None,
) -> list[str]:
    """Run AI command and return list of todo items.

    Args:
        user_input: User's text input
        command: Command template with {{prompt}}, {{system}}, {{schema}}
        system_prompt: System prompt for the AI
        piped_content: Optional piped stdin content
        schema: Optional JSON schema (defaults to array of strings)

    Returns:
        List of todo item strings, or empty list on error
    """
    # Build the full prompt
    prompt_parts = []

    if piped_content:
        prompt_parts.append(f"[Piped input]:\n{piped_content}\n\n[User request]:")

    prompt_parts.append(user_input)
    full_prompt = "\n".join(prompt_parts)

    # Escape for shell
    escaped_prompt = full_prompt.replace("'", "'\"'\"'")
    escaped_system = system_prompt.replace("'", "'\"'\"'")

    cmd = build_command(
        template=command,
        prompt=escaped_prompt,
        system=escaped_system,
        schema=schema or DEFAULT_SCHEMA,
    )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return []

        # Parse JSON array from output
        output = result.stdout.strip()

        # Try to extract JSON array if there's surrounding text
        if "[" in output:
            start = output.index("[")
            end = output.rindex("]") + 1
            output = output[start:end]

        items = json.loads(output)

        if isinstance(items, list):
            return [str(item) for item in items if item]

        return []

    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return []
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/dodo/ai.py tests/test_ai.py
git commit -m "feat: add AI module for todo formatting"
```

---

## Task 11: CLI Commands

**Files:**
- Create: `src/dodo/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write the test**

```python
# tests/test_cli.py
"""Tests for CLI commands."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dodo.cli import app

runner = CliRunner()


class TestCliAdd:
    def test_add_creates_todo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / "config"
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        with patch("dodo.cli.Config.load") as mock_load:
            from dodo.config import Config
            mock_load.return_value = Config.load(config_dir)

            result = runner.invoke(app, ["add", "Test todo"])

        assert result.exit_code == 0
        assert "Added" in result.stdout
        assert "Test todo" in result.stdout

    def test_add_global_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / "config"
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("dodo.cli.Config.load") as mock_load:
            from dodo.config import Config
            mock_load.return_value = Config.load(config_dir)

            result = runner.invoke(app, ["add", "-g", "Global todo"])

        assert result.exit_code == 0
        assert "global" in result.stdout.lower()


class TestCliList:
    def test_list_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / "config"

        with patch("dodo.cli.Config.load") as mock_load:
            from dodo.config import Config
            mock_load.return_value = Config.load(config_dir)
            with patch("dodo.cli.detect_project", return_value=None):
                result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No todos" in result.stdout

    def test_list_shows_todos(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / "config"

        with patch("dodo.cli.Config.load") as mock_load:
            from dodo.config import Config
            cfg = Config.load(config_dir)
            mock_load.return_value = cfg

            with patch("dodo.cli.detect_project", return_value=None):
                runner.invoke(app, ["add", "First todo"])
                result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "First todo" in result.stdout


class TestCliDone:
    def test_done_marks_complete(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / "config"

        with patch("dodo.cli.Config.load") as mock_load:
            from dodo.config import Config
            cfg = Config.load(config_dir)
            mock_load.return_value = cfg

            with patch("dodo.cli.detect_project", return_value=None):
                # Add a todo first
                add_result = runner.invoke(app, ["add", "Test todo"])
                # Extract ID from output (format: "Added to global: Test todo (abc123)")
                import re
                match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
                assert match, f"Could not find ID in: {add_result.stdout}"
                todo_id = match.group(1)

                result = runner.invoke(app, ["done", todo_id])

        assert result.exit_code == 0
        assert "Done" in result.stdout


class TestCliUndo:
    def test_undo_removes_last_add(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / "config"

        with patch("dodo.cli.Config.load") as mock_load:
            from dodo.config import Config
            cfg = Config.load(config_dir)
            mock_load.return_value = cfg

            with patch("dodo.cli.detect_project", return_value=None):
                runner.invoke(app, ["add", "To be undone"])
                result = runner.invoke(app, ["undo"])

        assert result.exit_code == 0
        assert "Undid" in result.stdout


class TestCliRm:
    def test_rm_deletes_todo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / "config"

        with patch("dodo.cli.Config.load") as mock_load:
            from dodo.config import Config
            cfg = Config.load(config_dir)
            mock_load.return_value = cfg

            with patch("dodo.cli.detect_project", return_value=None):
                add_result = runner.invoke(app, ["add", "To delete"])
                import re
                match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
                todo_id = match.group(1)

                result = runner.invoke(app, ["rm", todo_id])

        assert result.exit_code == 0
        assert "Removed" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/dodo/cli.py
"""CLI commands."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Status
from dodo.project import detect_project

app = typer.Typer(
    name="dodo",
    help="Todo router - manage todos across multiple backends.",
    no_args_is_help=False,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Launch interactive menu if no command given."""
    if ctx.invoked_subcommand is None:
        from dodo.ui.interactive import interactive_menu
        interactive_menu()


@app.command()
def add(
    text: Annotated[str, typer.Argument(help="Todo text")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
):
    """Add a todo item."""
    cfg = Config.load()

    if global_:
        target = "global"
        project_id = None
    else:
        project_id = detect_project()
        target = project_id or "global"

    svc = TodoService(cfg, project_id)
    item = svc.add(text)

    _save_last_action("add", item.id, target)

    dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
    console.print(f"[green]✓[/green] Added to {dest}: {item.text} [dim]({item.id})[/dim]")


@app.command(name="list")
def list_todos(
    project: Annotated[str | None, typer.Option("-p", "--project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    done: Annotated[bool, typer.Option("--done", help="Show completed")] = False,
    all_: Annotated[bool, typer.Option("-a", "--all", help="Show all")] = False,
):
    """List todos."""
    cfg = Config.load()

    if global_:
        project_id = None
    else:
        project_id = project or detect_project()

    svc = TodoService(cfg, project_id)
    status = None if all_ else (Status.DONE if done else Status.PENDING)
    items = svc.list(status=status)
    _print_todos(items)


@app.command()
def done(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
):
    """Mark todo as done."""
    cfg = Config.load()
    project_id = detect_project()
    svc = TodoService(cfg, project_id)

    # Try to find matching ID
    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    completed = svc.complete(item.id)
    console.print(f"[green]✓[/green] Done: {completed.text}")


@app.command()
def rm(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
):
    """Remove a todo."""
    cfg = Config.load()
    project_id = detect_project()
    svc = TodoService(cfg, project_id)

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    svc.delete(item.id)
    console.print(f"[yellow]✓[/yellow] Removed: {item.text}")


@app.command()
def undo():
    """Undo the last add operation."""
    last = _load_last_action()

    if not last or last.get("action") != "add":
        console.print("[yellow]Nothing to undo[/yellow]")
        raise typer.Exit(0)

    cfg = Config.load()
    project_id = None if last["target"] == "global" else last["target"]
    svc = TodoService(cfg, project_id)

    try:
        item = svc.get(last["id"])
        if not item:
            console.print("[yellow]Todo already removed[/yellow]")
            _clear_last_action()
            raise typer.Exit(0)

        svc.delete(last["id"])
        _clear_last_action()

        dest = f"[cyan]{last['target']}[/cyan]" if last["target"] != "global" else "[dim]global[/dim]"
        console.print(f"[yellow]↩[/yellow] Undid add from {dest}: {item.text}")

    except KeyError:
        console.print("[yellow]Todo already removed[/yellow]")
        _clear_last_action()


@app.command()
def ai(
    text: Annotated[str | None, typer.Argument(help="Input text")] = None,
):
    """AI-assisted todo creation."""
    piped = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()

    if not text and not piped:
        console.print("[red]Error:[/red] Provide text or pipe input")
        raise typer.Exit(1)

    cfg = Config.load()

    if not cfg.ai_enabled:
        console.print("[yellow]AI not enabled.[/yellow] Set DODO_AI_ENABLED=true")
        raise typer.Exit(1)

    project_id = detect_project()
    svc = TodoService(cfg, project_id)

    from dodo.ai import run_ai

    todo_texts = run_ai(
        user_input=text or "",
        piped_content=piped,
        command=cfg.ai_command,
        system_prompt=cfg.ai_sys_prompt,
    )

    if not todo_texts:
        console.print("[red]Error:[/red] AI returned no todos")
        raise typer.Exit(1)

    target = project_id or "global"
    for todo_text in todo_texts:
        item = svc.add(todo_text)
        dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
        console.print(f"[green]✓[/green] Added to {dest}: {item.text} [dim]({item.id})[/dim]")


@app.command()
def init(
    local: Annotated[bool, typer.Option("--local", help="Store todos in project dir")] = False,
):
    """Initialize dodo for current project."""
    project_id = detect_project()

    if not project_id:
        console.print("[red]Error:[/red] Not in a git repository")
        raise typer.Exit(1)

    cfg = Config.load()

    if local:
        cfg.set("local_storage", True)

    console.print(f"[green]✓[/green] Initialized project: {project_id}")


@app.command()
def config():
    """Open interactive config editor."""
    from dodo.ui.interactive import interactive_config
    interactive_config()


# Helpers

def _find_item_by_partial_id(svc: TodoService, partial_id: str):
    """Find item by full or partial ID."""
    # First try exact match
    item = svc.get(partial_id)
    if item:
        return item

    # Try partial match
    for item in svc.list():
        if item.id.startswith(partial_id):
            return item

    return None


def _print_todos(items: list) -> None:
    """Pretty print todos as table."""
    if not items:
        console.print("[dim]No todos[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Status", width=6)
    table.add_column("Created", width=16)
    table.add_column("Todo")

    for item in items:
        status = "[green]✓[/green]" if item.status == Status.DONE else "[ ]"
        created = item.created_at.strftime("%Y-%m-%d %H:%M")
        table.add_row(item.id, status, created, item.text)

    console.print(table)


def _save_last_action(action: str, id: str, target: str) -> None:
    """Save last action for undo."""
    cfg = Config.load()
    state_file = cfg.config_dir / ".last_action"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"action": action, "id": id, "target": target}))


def _load_last_action() -> dict | None:
    """Load last action."""
    cfg = Config.load()
    state_file = cfg.config_dir / ".last_action"
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text())


def _clear_last_action() -> None:
    """Clear last action after undo."""
    cfg = Config.load()
    state_file = cfg.config_dir / ".last_action"
    if state_file.exists():
        state_file.unlink()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat: add CLI commands"
```

---

## Task 12: UI Layer

**Files:**
- Create: `src/dodo/ui/__init__.py`
- Create: `src/dodo/ui/base.py`
- Create: `src/dodo/ui/rich_menu.py`
- Create: `src/dodo/ui/interactive.py`

**Step 1: Create UI module structure**

Run:
```bash
mkdir -p src/dodo/ui
touch src/dodo/ui/__init__.py
```

**Step 2: Create src/dodo/ui/base.py**

```python
# src/dodo/ui/base.py
"""UI protocol for swappable menu implementations."""

from typing import Protocol


class MenuUI(Protocol):
    """Protocol for swappable menu implementations."""

    def select(self, options: list[str], title: str = "") -> int | None:
        """Show selection menu, return index or None if cancelled."""
        ...

    def multi_select(
        self, options: list[str], selected: list[bool], title: str = ""
    ) -> list[int]:
        """Checkboxes, return selected indices."""
        ...

    def confirm(self, message: str) -> bool:
        """Yes/no prompt."""
        ...

    def input(self, prompt: str) -> str | None:
        """Text input, None if cancelled."""
        ...
```

**Step 3: Create src/dodo/ui/rich_menu.py**

```python
# src/dodo/ui/rich_menu.py
"""Rich + simple-term-menu implementation."""

from rich.console import Console
from simple_term_menu import TerminalMenu

from .base import MenuUI


class RichTerminalMenu:
    """Rich + simple-term-menu implementation.

    Swap this out for your rich-live-menu library later.
    """

    def __init__(self):
        self.console = Console()

    def select(self, options: list[str], title: str = "") -> int | None:
        if not options:
            return None
        menu = TerminalMenu(options, title=title or None)
        result = menu.show()
        return result

    def multi_select(
        self, options: list[str], selected: list[bool], title: str = ""
    ) -> list[int]:
        if not options:
            return []
        preselected = [i for i, s in enumerate(selected) if s]
        menu = TerminalMenu(
            options,
            title=title or None,
            multi_select=True,
            preselected_entries=preselected,
            multi_select_select_on_accept=False,
        )
        result = menu.show()
        return list(result) if result else []

    def confirm(self, message: str) -> bool:
        menu = TerminalMenu(["Yes", "No"], title=message)
        return menu.show() == 0

    def input(self, prompt: str) -> str | None:
        try:
            return self.console.input(f"[bold]{prompt}[/bold] ")
        except (KeyboardInterrupt, EOFError):
            return None
```

**Step 4: Create src/dodo/ui/interactive.py**

```python
# src/dodo/ui/interactive.py
"""Interactive menu."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Status
from dodo.project import detect_project

from .rich_menu import RichTerminalMenu

console = Console()


def interactive_menu() -> None:
    """Main interactive menu when running bare 'dodo'."""
    cfg = Config.load()
    project_id = detect_project()
    target = project_id or "global"
    svc = TodoService(cfg, project_id)
    ui = RichTerminalMenu()

    while True:
        items = svc.list()
        pending = sum(1 for i in items if i.status == Status.PENDING)
        done = sum(1 for i in items if i.status == Status.DONE)

        console.clear()
        console.print(
            Panel(
                f"[bold]Project:[/bold] {target}\n"
                f"[bold]Backend:[/bold] {cfg.default_adapter}\n"
                f"[bold]Todos:[/bold] {pending} pending, {done} done",
                title="dodo",
                border_style="blue",
            )
        )

        options = [
            "Add todo",
            "List todos",
            "Complete todo",
            "Delete todo",
            "Config",
            "Switch project",
            "Exit",
        ]

        choice = ui.select(options)

        if choice is None or choice == 6:
            break
        elif choice == 0:
            _interactive_add(svc, ui, target)
        elif choice == 1:
            _interactive_list(svc, ui)
        elif choice == 2:
            _interactive_complete(svc, ui)
        elif choice == 3:
            _interactive_delete(svc, ui)
        elif choice == 4:
            interactive_config(ui)
        elif choice == 5:
            project_id, target = _interactive_switch(ui, cfg)
            svc = TodoService(cfg, project_id)


def _interactive_add(svc: TodoService, ui: RichTerminalMenu, target: str) -> None:
    text = ui.input("Todo:")
    if text:
        item = svc.add(text)
        console.print(f"[green]✓[/green] Added to {target}: {item.text}")
        ui.input("Press Enter to continue...")


def _interactive_list(svc: TodoService, ui: RichTerminalMenu) -> None:
    items = svc.list()
    if not items:
        console.print("[dim]No todos[/dim]")
    else:
        table = Table(show_header=True)
        table.add_column("ID", style="dim", width=8)
        table.add_column("✓", width=3)
        table.add_column("Todo")
        for item in items:
            status = "[green]✓[/green]" if item.status == Status.DONE else " "
            table.add_row(item.id, status, item.text)
        console.print(table)
    ui.input("Press Enter to continue...")


def _interactive_complete(svc: TodoService, ui: RichTerminalMenu) -> None:
    items = [i for i in svc.list() if i.status == Status.PENDING]
    if not items:
        console.print("[dim]No pending todos[/dim]")
        ui.input("Press Enter...")
        return

    options = [f"{i.id[:8]} - {i.text}" for i in items]
    choice = ui.select(options, title="Select todo to complete")

    if choice is not None:
        svc.complete(items[choice].id)
        console.print(f"[green]✓[/green] Done: {items[choice].text}")
        ui.input("Press Enter...")


def _interactive_delete(svc: TodoService, ui: RichTerminalMenu) -> None:
    items = svc.list()
    if not items:
        console.print("[dim]No todos[/dim]")
        ui.input("Press Enter...")
        return

    options = [f"{i.id[:8]} - {i.text}" for i in items]
    choice = ui.select(options, title="Select todo to delete")

    if choice is not None and ui.confirm(f"Delete '{items[choice].text}'?"):
        svc.delete(items[choice].id)
        console.print("[yellow]✓[/yellow] Deleted")
        ui.input("Press Enter...")


def _interactive_switch(ui: RichTerminalMenu, cfg: Config) -> tuple[str | None, str]:
    options = ["Global", "Detect from current dir", "Enter project name"]
    choice = ui.select(options, title="Switch project")

    if choice == 0:
        return None, "global"
    elif choice == 1:
        project_id = detect_project()
        return project_id, project_id or "global"
    elif choice == 2:
        name = ui.input("Project name:")
        return name, name or "global"

    return None, "global"


def interactive_config(ui: RichTerminalMenu | None = None) -> None:
    """Interactive config editor with autodiscovered toggles."""
    ui = ui or RichTerminalMenu()
    cfg = Config.load()

    toggles = cfg.get_toggles()
    options = [f"{'[x]' if enabled else '[ ]'} {desc}" for _, desc, enabled in toggles]

    selected = ui.multi_select(
        options,
        selected=[enabled for _, _, enabled in toggles],
        title="Toggle settings (Space to toggle, Enter to save)",
    )

    for i, (attr, _, was_enabled) in enumerate(toggles):
        now_enabled = i in selected
        if now_enabled != was_enabled:
            cfg.set(attr, now_enabled)

    console.print("[green]✓[/green] Config saved")
```

**Step 5: Update src/dodo/ui/__init__.py**

```python
# src/dodo/ui/__init__.py
"""UI module."""

from .base import MenuUI
from .rich_menu import RichTerminalMenu
from .interactive import interactive_menu, interactive_config

__all__ = ["MenuUI", "RichTerminalMenu", "interactive_menu", "interactive_config"]
```

**Step 6: Run all tests**

Run: `pytest -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add src/dodo/ui/
git commit -m "feat: add interactive UI with Rich menu"
```

---

## Task 13: Final Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
"""Integration tests for full workflow."""

from pathlib import Path
import subprocess

import pytest


class TestFullWorkflow:
    def test_add_list_done_workflow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test complete workflow: add -> list -> done -> list."""
        config_dir = tmp_path / ".config" / "dodo"
        monkeypatch.setenv("HOME", str(tmp_path))

        from dodo.config import Config
        from dodo.core import TodoService
        from dodo.models import Status

        cfg = Config.load(config_dir)
        svc = TodoService(cfg, project_id=None)

        # Add
        item1 = svc.add("First todo")
        item2 = svc.add("Second todo")

        # List pending
        pending = svc.list(status=Status.PENDING)
        assert len(pending) == 2

        # Complete one
        svc.complete(item1.id)

        # Verify status
        pending = svc.list(status=Status.PENDING)
        done = svc.list(status=Status.DONE)
        assert len(pending) == 1
        assert len(done) == 1
        assert done[0].id == item1.id

    def test_project_isolation(self, tmp_path: Path):
        """Test that projects have isolated todos."""
        config_dir = tmp_path / ".config" / "dodo"

        from dodo.config import Config
        from dodo.core import TodoService

        cfg = Config.load(config_dir)

        # Add to project A
        svc_a = TodoService(cfg, project_id="project_a")
        svc_a.add("Project A todo")

        # Add to project B
        svc_b = TodoService(cfg, project_id="project_b")
        svc_b.add("Project B todo")

        # Add to global
        svc_global = TodoService(cfg, project_id=None)
        svc_global.add("Global todo")

        # Verify isolation
        assert len(svc_a.list()) == 1
        assert svc_a.list()[0].text == "Project A todo"

        assert len(svc_b.list()) == 1
        assert svc_b.list()[0].text == "Project B todo"

        assert len(svc_global.list()) == 1
        assert svc_global.list()[0].text == "Global todo"

    def test_adapter_switching(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test switching between adapters."""
        config_dir = tmp_path / ".config" / "dodo"

        from dodo.config import Config
        from dodo.core import TodoService

        # Test with markdown
        cfg = Config.load(config_dir)
        svc = TodoService(cfg, project_id=None)
        svc.add("Markdown todo")
        assert (config_dir / "todo.md").exists()

        # Switch to SQLite
        monkeypatch.setenv("DODO_DEFAULT_ADAPTER", "sqlite")
        cfg2 = Config.load(config_dir)
        svc2 = TodoService(cfg2, project_id=None)
        svc2.add("SQLite todo")
        assert (config_dir / "todos.db").exists()
```

**Step 2: Run integration test**

Run: `pytest tests/test_integration.py -v`
Expected: All tests PASS

**Step 3: Run full test suite**

Run: `pytest -v --cov=dodo`
Expected: All tests PASS with good coverage

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests"
```

---

## Task 14: Final Cleanup

**Step 1: Run linting**

Run: `ruff check src/ tests/ --fix`
Expected: No errors

**Step 2: Run type checking**

Run: `mypy src/dodo/`
Expected: No errors (may need to add type: ignore for some third-party libs)

**Step 3: Final commit**

```bash
git add .
git commit -m "chore: lint and type check cleanup"
```

**Step 4: Tag release**

```bash
git tag v0.1.0
```

---

## Summary

This plan implements the full dodo CLI todo manager with:

- **14 tasks** covering all components
- **TDD approach** - tests written before implementation
- **Frequent commits** - one commit per task
- **Full test coverage** - unit tests + integration tests

Execution time estimate: ~2-3 hours for experienced developer following the plan step-by-step.
