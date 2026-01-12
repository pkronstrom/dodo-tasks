# Audit Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 12 issues identified in the code audit (2 high, 6 medium, 4 low severity).

**Architecture:** Fix ID generation first (critical), then path handling, then file locking, then architectural improvements. Each fix is isolated and testable.

**Tech Stack:** Python, pytest, fcntl (file locking), uuid

---

## Phase 1: Quick Wins

### Task 1: Fix ID Collision Risk

**Files:**
- Modify: `src/dodo/backends/utils.py`
- Modify: `tests/test_backends/test_utils.py`

**Step 1: Write failing test**

Add to `tests/test_backends/test_utils.py`:

```python
def test_generate_todo_id_unique_for_same_text_same_minute():
    """IDs should be unique even for identical text at same timestamp."""
    from datetime import datetime
    from dodo.backends.utils import generate_todo_id

    ts = datetime(2024, 1, 15, 10, 30, 0)
    id1 = generate_todo_id("same text", ts)
    id2 = generate_todo_id("same text", ts)

    # Should be different due to random component
    assert id1 != id2
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_backends/test_utils.py::test_generate_todo_id_unique_for_same_text_same_minute -v
```

Expected: FAIL (ids are equal)

**Step 3: Update generate_todo_id with random salt**

In `src/dodo/backends/utils.py`, change:

```python
import uuid

def generate_todo_id(text: str, timestamp: datetime) -> str:
    """Generate a unique 8-char hex ID.

    Uses UUID4 for uniqueness, ignoring text/timestamp.
    This ensures no collisions and stable IDs on edit.
    """
    return uuid.uuid4().hex[:8]
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_backends/test_utils.py::test_generate_todo_id_unique_for_same_text_same_minute -v
```

**Step 5: Run full test suite**

```bash
uv run pytest -v
```

**Step 6: Commit**

```bash
git add -A && git commit -m "fix: use UUID for todo IDs to prevent collisions"
```

---

### Task 2: Fix Hardcoded Config Dir in CLI

**Files:**
- Modify: `src/dodo/cli.py`

**Step 1: Update _get_config_dir to use Config**

In `src/dodo/cli.py`, change `_get_config_dir`:

```python
def _get_config_dir():
    """Get config directory path from Config."""
    return _get_config().config_dir
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_cli.py -v
```

**Step 3: Commit**

```bash
git add -A && git commit -m "fix: use Config.load() for config dir in CLI"
```

---

### Task 3: Centralize Project Config Path

**Files:**
- Modify: `src/dodo/project_config.py`
- Modify: `src/dodo/core.py`
- Modify: `src/dodo/cli.py`

**Step 1: Add get_project_config_dir helper**

In `src/dodo/project_config.py`, add:

```python
def get_project_config_dir(
    config_dir: Path,
    project_id: str,
    local_storage: bool = False,
    worktree_shared: bool = True,
) -> Path:
    """Get the directory where project config (dodo.json) lives.

    Args:
        config_dir: Global config directory (~/.config/dodo)
        project_id: Project identifier
        local_storage: If True, use project root's .dodo/
        worktree_shared: Worktree sharing setting

    Returns:
        Path to project config directory
    """
    if local_storage:
        from dodo.project import detect_project_root
        root = detect_project_root(worktree_shared=worktree_shared)
        if root:
            return root / ".dodo"

    return config_dir / "projects" / project_id
```

**Step 2: Update core.py to use helper**

In `src/dodo/core.py`, update `_get_project_config_dir`:

```python
def _get_project_config_dir(self) -> Path:
    """Get the directory where project config (dodo.json) lives."""
    from dodo.project_config import get_project_config_dir

    return get_project_config_dir(
        self._config.config_dir,
        self._project_id,
        self._config.local_storage,
        self._config.worktree_shared,
    )
```

**Step 3: Update cli.py backend command**

In `src/dodo/cli.py`, update the `backend` command to use the helper:

```python
@app.command()
def backend(
    name: Annotated[str | None, typer.Argument(help="Backend to set")] = None,
    migrate: Annotated[bool, typer.Option("--migrate", help="Migrate todos from current backend")] = False,
    migrate_from: Annotated[str | None, typer.Option("--migrate-from", help="Source backend for migration")] = None,
):
    """Show or set project backend."""
    from dodo.project_config import ProjectConfig, get_project_config_dir

    cfg = _get_config()
    project_id = _detect_project(worktree_shared=cfg.worktree_shared)

    if not project_id:
        console.print("[red]Error:[/red] Not in a project")
        raise typer.Exit(1)

    # Use centralized path helper
    project_dir = get_project_config_dir(
        cfg.config_dir,
        project_id,
        cfg.local_storage,
        cfg.worktree_shared,
    )

    # ... rest unchanged
```

**Step 4: Run tests**

```bash
uv run pytest -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "refactor: centralize project config path calculation"
```

---

### Task 4: Remove Unused ProjectConfig.ensure

**Files:**
- Modify: `src/dodo/project_config.py`
- Modify: `tests/test_project_config.py`

**Step 1: Remove ensure method**

Delete the `ensure` classmethod from `ProjectConfig` in `src/dodo/project_config.py` (lines 42-59).

**Step 2: Remove test**

Delete `test_ensure_creates_with_default` from `tests/test_project_config.py`.

**Step 3: Run tests**

```bash
uv run pytest tests/test_project_config.py -v
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: remove unused ProjectConfig.ensure method"
```

---

## Phase 2: Core Improvements

### Task 5: Add File Locking to Markdown Backend

**Files:**
- Modify: `src/dodo/backends/markdown.py`
- Create: `tests/test_backends/test_markdown_locking.py`

**Step 1: Write test for concurrent access**

Create `tests/test_backends/test_markdown_locking.py`:

```python
"""Tests for markdown backend file locking."""

import threading
from pathlib import Path

from dodo.backends.markdown import MarkdownBackend


def test_concurrent_adds_no_data_loss(tmp_path):
    """Concurrent adds should not lose data."""
    md_path = tmp_path / "todos.md"
    backend = MarkdownBackend(md_path)

    results = []
    errors = []

    def add_todo(text):
        try:
            item = backend.add(text)
            results.append(item)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=add_todo, args=(f"Task {i}",))
        for i in range(10)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors: {errors}"

    # All 10 should be saved
    items = backend.list()
    assert len(items) == 10
```

**Step 2: Run test (may pass or fail depending on timing)**

```bash
uv run pytest tests/test_backends/test_markdown_locking.py -v
```

**Step 3: Add file locking to markdown backend**

In `src/dodo/backends/markdown.py`, add locking context manager and use it:

```python
import fcntl
from contextlib import contextmanager

@contextmanager
def _file_lock(path: Path):
    """Acquire exclusive lock on file for read-modify-write."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)

    with open(lock_path, "r") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
```

Then wrap `_read_todos` and `_write_todos` calls in locking:

```python
def add(self, text: str, project: str | None = None) -> TodoItem:
    with _file_lock(self._path):
        todos = self._read_todos()
        item = TodoItem(...)
        todos.append(item)
        self._write_todos(todos)
    return item
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_backends/test_markdown_locking.py -v
uv run pytest tests/test_backends/test_markdown.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add file locking to markdown backend"
```

---

### Task 6: Stabilize IDs on Edit for Markdown

**Files:**
- Modify: `src/dodo/backends/markdown.py`
- Modify: `tests/test_backends/test_markdown.py`

**Step 1: Write failing test**

Add to `tests/test_backends/test_markdown.py`:

```python
def test_update_text_keeps_same_id(tmp_path):
    """Updating text should not change the todo ID."""
    md_path = tmp_path / "todos.md"
    backend = MarkdownBackend(md_path)

    item = backend.add("Original text")
    original_id = item.id

    updated = backend.update_text(item.id, "New text")

    assert updated.id == original_id
    assert updated.text == "New text"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_backends/test_markdown.py::test_update_text_keeps_same_id -v
```

**Step 3: Fix update_text to preserve ID**

The issue is that when we re-parse the file, IDs are regenerated from text+timestamp. Since we now use UUID, this is already fixed by Task 1. But we need to store the ID in the file.

Update markdown format to include ID:
```
- [ ] 2024-01-15 10:30 [abc12345] - Todo text
```

This requires updating `TODO_LINE_PATTERN`, `format_todo_line`, and `parse_todo_line` in utils.py.

**Step 4: Run tests**

```bash
uv run pytest tests/test_backends/test_markdown.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: store ID in markdown format for stable edits"
```

---

### Task 7: Fix Info Command to Show Resolved Backend

**Files:**
- Modify: `src/dodo/cli.py`
- Modify: `src/dodo/core.py`

**Step 1: Add backend_name property to TodoService**

In `src/dodo/core.py`, add:

```python
@property
def backend_name(self) -> str:
    """Get the name of the current backend."""
    return self._backend_name
```

And store it during `_create_backend`:

```python
def _create_backend(self) -> TodoBackend:
    # ...
    backend_name = self._resolve_backend()
    self._backend_name = backend_name
    # ...
```

**Step 2: Update info command**

In `src/dodo/cli.py`, update info:

```python
console.print(f"[bold]Backend:[/bold] {svc.backend_name}")
```

**Step 3: Run tests**

```bash
uv run pytest -v
```

**Step 4: Commit**

```bash
git add -A && git commit -m "fix: info command shows resolved backend"
```

---

### Task 8: Implement Backend Migration

**Files:**
- Modify: `src/dodo/cli.py`
- Create: `tests/test_cli_migration.py`

**Step 1: Write test**

Create `tests/test_cli_migration.py`:

```python
"""Tests for backend migration."""

def test_migrate_copies_todos(tmp_path, monkeypatch):
    """Migration should copy todos from source to target backend."""
    # Setup with sqlite backend, add todos
    # Run: dodo backend markdown --migrate
    # Verify todos exist in markdown file
    pass  # Implement based on CLI testing patterns
```

**Step 2: Implement migration in backend command**

```python
if migrate:
    from dodo.project_config import ProjectConfig

    # Get current backend
    current_config = ProjectConfig.load(project_dir)
    source_backend = current_config.backend if current_config else cfg.default_backend

    if source_backend == name:
        console.print(f"[yellow]Already using {name} backend[/yellow]")
        return

    # Create source and target services
    source_svc = _get_service(cfg, project_id)  # Uses current backend
    source_todos = source_svc.list()

    # Switch backend
    config = ProjectConfig(backend=name)
    config.save(project_dir)

    # Create target service and import
    target_svc = _get_service(cfg, project_id)

    for todo in source_todos:
        target_svc.add(todo.text)

    console.print(f"[green]✓[/green] Migrated {len(source_todos)} todos to {name}")
```

**Step 3: Run tests**

```bash
uv run pytest tests/test_cli_migration.py -v
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: implement backend migration"
```

---

## Phase 3: Architectural Changes

### Task 9: Define GraphCapable Protocol

**Files:**
- Create: `src/dodo/backends/protocols.py`
- Modify: `src/dodo/plugins/graph/__init__.py`
- Modify: `src/dodo/plugins/graph/cli.py`

**Step 1: Create protocols module**

Create `src/dodo/backends/protocols.py`:

```python
"""Extended backend protocols."""

from typing import Protocol, runtime_checkable

from dodo.models import TodoItem


@runtime_checkable
class GraphCapable(Protocol):
    """Protocol for backends that support dependency tracking."""

    def add_dependency(self, todo_id: str, blocked_by_id: str) -> None:
        """Add a dependency between todos."""
        ...

    def remove_dependency(self, todo_id: str, blocked_by_id: str) -> None:
        """Remove a dependency."""
        ...

    def get_dependencies(self, todo_id: str) -> list[str]:
        """Get IDs that block this todo."""
        ...

    def get_ready(self) -> list[TodoItem]:
        """Get todos with no blocking dependencies."""
        ...
```

**Step 2: Update graph plugin to use protocol**

In `src/dodo/plugins/graph/cli.py`:

```python
from dodo.backends.protocols import GraphCapable

def _get_graph_backend(cfg, project_id):
    """Get backend with graph capabilities."""
    svc = _get_service(cfg, project_id)

    if not isinstance(svc._backend, GraphCapable):
        console.print("[red]Error:[/red] Graph features require a GraphCapable backend (sqlite)")
        raise typer.Exit(1)

    return svc._backend
```

**Step 3: Run tests**

```bash
uv run pytest tests/test_graph_plugin.py -v
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: define GraphCapable protocol for graph plugin"
```

---

### Task 10: Add SQLite Connection Reuse

**Files:**
- Modify: `src/dodo/backends/sqlite.py`

**Step 1: Add connection caching**

```python
class SqliteBackend:
    def __init__(self, db_path: Path):
        self._path = db_path
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create connection."""
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path)
            # Pragmas
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA busy_timeout = 5000")
        return self._conn

    def close(self) -> None:
        """Close connection if open."""
        if self._conn:
            self._conn.close()
            self._conn = None
```

**Step 2: Update methods to use _get_conn**

Replace `with self._connect() as conn:` with `conn = self._get_conn()` throughout.

**Step 3: Run tests**

```bash
uv run pytest tests/test_backends/test_sqlite.py -v
```

**Step 4: Commit**

```bash
git add -A && git commit -m "perf: reuse SQLite connection within backend instance"
```

---

### Task 11: Refactor Ntfy Plugin to Use Internal API

**Files:**
- Modify: `src/dodo/plugins/ntfy_inbox/inbox.py`

**Step 1: Replace subprocess with TodoService**

```python
def inbox() -> None:
    """Listen for todos from ntfy.sh and add them automatically."""
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.project import detect_project

    cfg = Config.load()
    project_id = detect_project(worktree_shared=cfg.worktree_shared)
    svc = TodoService(cfg, project_id)

    # ... in message loop:
    item = svc.add(message)
    console.print(f"[green]✓[/green] Added: {item.text}")
```

**Step 2: Run tests**

```bash
uv run pytest -v
```

**Step 3: Commit**

```bash
git add -A && git commit -m "perf: ntfy plugin uses TodoService directly"
```

---

### Task 12: Extract Graph Plugin Command Builder

**Files:**
- Modify: `src/dodo/plugins/graph/__init__.py`

**Step 1: Extract shared setup**

```python
def _setup_commands(app: typer.Typer, cfg: Config) -> None:
    """Shared command setup for graph plugin."""
    from dodo.plugins.graph.cli import dep_app, graph_app

    app.add_typer(dep_app, name="dep")
    app.add_typer(graph_app, name="graph")


def register_commands(app: typer.Typer, cfg: Config) -> None:
    """Register under dodo plugins graph."""
    _setup_commands(app, cfg)


def register_root_commands(app: typer.Typer, cfg: Config) -> None:
    """Register as root commands."""
    _setup_commands(app, cfg)
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_graph_plugin.py -v
```

**Step 3: Commit**

```bash
git add -A && git commit -m "refactor: extract shared command builder in graph plugin"
```

---

## Final Verification

### Task 13: Run Full Test Suite and Cleanup

**Step 1: Run all tests**

```bash
uv run pytest -v
```

**Step 2: Check for any remaining adapter references**

```bash
grep -r "adapter" src/dodo --include="*.py" | grep -v __pycache__ | grep -v backend
```

**Step 3: Commit any final fixes**

```bash
git add -A && git commit -m "fix: final cleanup from audit"
```

---

## Summary

| Task | Description | Severity Fixed |
|------|-------------|----------------|
| 1 | UUID for todo IDs | High |
| 2 | Config dir from Config | Medium |
| 3 | Centralize project config path | Medium |
| 4 | Remove unused ensure | Low |
| 5 | File locking for markdown | High |
| 6 | Stable IDs on edit | Medium |
| 7 | Info shows resolved backend | Low |
| 8 | Implement migration | Low |
| 9 | GraphCapable protocol | Medium |
| 10 | SQLite connection reuse | Medium |
| 11 | Ntfy uses TodoService | Medium |
| 12 | Graph command builder | Low |
| 13 | Final verification | - |
