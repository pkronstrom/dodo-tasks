# Backend Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure dodo to use "backend" terminology, make SQLite the core default, add per-project backend config via dodo.json, and require quoted strings for add command.

**Architecture:** Rename adapters → backends throughout. Move SQLite from plugin to core. Add project_config.py for per-project dodo.json. Update CLI to use single quoted text argument and add `dodo backend` command.

**Tech Stack:** Python, typer, sqlite3, JSON config files

---

## Task 1: Rename adapters/ directory to backends/

**Files:**
- Rename: `src/dodo/adapters/` → `src/dodo/backends/`
- Modify: `src/dodo/backends/base.py` (rename TodoAdapter → TodoBackend)
- Modify: `src/dodo/backends/__init__.py`

**Step 1: Rename directory**

```bash
git mv src/dodo/adapters src/dodo/backends
```

**Step 2: Update base.py - rename class**

In `src/dodo/backends/base.py`, change:

```python
@runtime_checkable
class TodoBackend(Protocol):
    """Protocol for todo storage backends."""
```

**Step 3: Update __init__.py**

In `src/dodo/backends/__init__.py`:

```python
"""Todo backends."""

from .base import TodoBackend

__all__ = [
    "TodoBackend",
]
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: rename adapters/ to backends/"
```

---

## Task 2: Move SQLite from plugin to core backends

**Files:**
- Move: `src/dodo/plugins/sqlite/adapter.py` → `src/dodo/backends/sqlite.py`
- Delete: `src/dodo/plugins/sqlite/` (entire directory)
- Modify: `src/dodo/backends/sqlite.py` (rename class)

**Step 1: Move and rename file**

```bash
cp src/dodo/plugins/sqlite/adapter.py src/dodo/backends/sqlite.py
```

**Step 2: Rename class in sqlite.py**

In `src/dodo/backends/sqlite.py`, change class name:

```python
class SqliteBackend:
    """SQLite backend - better for querying/filtering large lists."""
```

**Step 3: Delete plugin directory**

```bash
rm -rf src/dodo/plugins/sqlite
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: move SQLite from plugin to core backends"
```

---

## Task 3: Rename MarkdownAdapter to MarkdownBackend

**Files:**
- Modify: `src/dodo/backends/markdown.py`

**Step 1: Update class name and references**

In `src/dodo/backends/markdown.py`, rename:
- `class MarkdownAdapter` → `class MarkdownBackend`

**Step 2: Commit**

```bash
git add -A && git commit -m "refactor: rename MarkdownAdapter to MarkdownBackend"
```

---

## Task 4: Update core.py for backend terminology

**Files:**
- Modify: `src/dodo/core.py`

**Step 1: Update imports and registry**

Replace all occurrences:
- `_adapter_registry` → `_backend_registry`
- `register_adapter` → `register_backend`
- `extend_adapter` → `extend_backend`
- `adapter` → `backend` (variable names)
- `Adapter` → `Backend` (in strings like "dodo.backends.markdown:MarkdownBackend")

**Step 2: Update _register_builtin_backends function**

```python
def _register_builtin_backends() -> None:
    """Register built-in and bundled plugin backends."""
    _backend_registry["markdown"] = "dodo.backends.markdown:MarkdownBackend"
    _backend_registry["sqlite"] = "dodo.backends.sqlite:SqliteBackend"
    _backend_registry["obsidian"] = "dodo.plugins.obsidian.backend:ObsidianBackend"
```

**Step 3: Update TodoService methods**

Rename methods:
- `_create_adapter` → `_create_backend`
- `_instantiate_adapter` → `_instantiate_backend`

Update internal variable names from `adapter` to `backend`.

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: update core.py for backend terminology"
```

---

## Task 5: Update config.py defaults

**Files:**
- Modify: `src/dodo/config.py`

**Step 1: Update DEFAULTS and ConfigMeta**

In ConfigMeta.SETTINGS, change:
```python
"default_backend": "Backend (markdown|sqlite|obsidian)",
```

In Config.DEFAULTS, change:
```python
"default_backend": "sqlite",  # Changed from "markdown"
```

**Step 2: Commit**

```bash
git add -A && git commit -m "refactor: rename default_adapter to default_backend, sqlite as default"
```

---

## Task 6: Update plugins system for backend hooks

**Files:**
- Modify: `src/dodo/plugins/__init__.py`

**Step 1: Update _KNOWN_HOOKS**

```python
_KNOWN_HOOKS = [
    "register_commands",
    "register_config",
    "register_backend",   # was register_adapter
    "extend_backend",     # was extend_adapter
    "extend_formatter",
]
```

**Step 2: Commit**

```bash
git add -A && git commit -m "refactor: rename adapter hooks to backend hooks"
```

---

## Task 7: Update Obsidian plugin

**Files:**
- Rename: `src/dodo/plugins/obsidian/adapter.py` → `src/dodo/plugins/obsidian/backend.py`
- Modify: `src/dodo/plugins/obsidian/__init__.py`
- Modify: `src/dodo/plugins/obsidian/backend.py`

**Step 1: Rename file**

```bash
git mv src/dodo/plugins/obsidian/adapter.py src/dodo/plugins/obsidian/backend.py
```

**Step 2: Update __init__.py**

```python
def register_backend(registry: dict, config) -> None:
    """Register the Obsidian backend with the backend registry."""
    from dodo.plugins.obsidian.backend import ObsidianBackend

    registry["obsidian"] = ObsidianBackend
```

**Step 3: Rename class in backend.py**

Change `class ObsidianAdapter` → `class ObsidianBackend`

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: update Obsidian plugin for backend terminology"
```

---

## Task 8: Update graph plugin references

**Files:**
- Modify: `src/dodo/plugins/graph/wrapper.py`

**Step 1: Search and replace adapter references**

Update any references to "adapter" in the graph plugin to use "backend".

**Step 2: Commit**

```bash
git add -A && git commit -m "refactor: update graph plugin for backend terminology"
```

---

## Task 9: Create project_config.py for per-project dodo.json

**Files:**
- Create: `src/dodo/project_config.py`
- Create: `tests/test_project_config.py`

**Step 1: Write failing test**

Create `tests/test_project_config.py`:

```python
"""Tests for project config (dodo.json)."""

import json
from pathlib import Path

import pytest

from dodo.project_config import ProjectConfig


def test_load_missing_returns_none(tmp_path):
    """Loading non-existent dodo.json returns None."""
    config = ProjectConfig.load(tmp_path / "nonexistent")
    assert config is None


def test_load_existing(tmp_path):
    """Loading existing dodo.json returns ProjectConfig."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "dodo.json").write_text('{"backend": "markdown"}')

    config = ProjectConfig.load(project_dir)
    assert config is not None
    assert config.backend == "markdown"


def test_save_creates_file(tmp_path):
    """Saving creates dodo.json."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = ProjectConfig(backend="sqlite")
    config.save(project_dir)

    assert (project_dir / "dodo.json").exists()
    data = json.loads((project_dir / "dodo.json").read_text())
    assert data["backend"] == "sqlite"


def test_ensure_creates_with_default(tmp_path):
    """ensure() creates config with default backend if missing."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = ProjectConfig.ensure(project_dir, default_backend="sqlite")

    assert config.backend == "sqlite"
    assert (project_dir / "dodo.json").exists()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_project_config.py -v
```

Expected: FAIL with "No module named 'dodo.project_config'"

**Step 3: Write implementation**

Create `src/dodo/project_config.py`:

```python
"""Per-project configuration (dodo.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectConfig:
    """Project-level configuration stored in dodo.json."""

    backend: str

    @classmethod
    def load(cls, project_dir: Path) -> ProjectConfig | None:
        """Load project config from dodo.json.

        Args:
            project_dir: Directory containing dodo.json

        Returns:
            ProjectConfig if file exists, None otherwise
        """
        config_file = project_dir / "dodo.json"
        if not config_file.exists():
            return None

        try:
            data = json.loads(config_file.read_text())
            return cls(backend=data.get("backend", "sqlite"))
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, project_dir: Path) -> None:
        """Save project config to dodo.json."""
        project_dir.mkdir(parents=True, exist_ok=True)
        config_file = project_dir / "dodo.json"
        config_file.write_text(json.dumps({"backend": self.backend}, indent=2))

    @classmethod
    def ensure(cls, project_dir: Path, default_backend: str) -> ProjectConfig:
        """Load or create project config with default.

        Args:
            project_dir: Directory for dodo.json
            default_backend: Backend to use if creating new config

        Returns:
            Existing or newly created ProjectConfig
        """
        config = cls.load(project_dir)
        if config is not None:
            return config

        config = cls(backend=default_backend)
        config.save(project_dir)
        return config
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_project_config.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add project_config.py for per-project dodo.json"
```

---

## Task 10: Update storage.py to use project config

**Files:**
- Modify: `src/dodo/storage.py`

**Step 1: Update get_storage_path for local_storage**

When `local_storage=true`, the dodo.json should be in `.dodo/dodo.json` in project root.
Update the storage path logic to account for this.

**Step 2: Commit**

```bash
git add -A && git commit -m "refactor: update storage.py for project config paths"
```

---

## Task 11: Integrate project config into core.py

**Files:**
- Modify: `src/dodo/core.py`

**Step 1: Update _create_backend to check project config**

Add logic to:
1. Determine project config directory (based on local_storage setting)
2. Load or auto-detect backend from project config
3. Create dodo.json on first add if missing

```python
def _create_backend(self) -> TodoBackend:
    from dodo.plugins import apply_hooks
    from dodo.project_config import ProjectConfig

    # Let plugins register their backends
    apply_hooks("register_backend", _backend_registry, self._config)

    # Determine backend: project config > auto-detect > global default
    backend_name = self._resolve_backend()

    if backend_name in _backend_registry:
        backend = self._instantiate_backend(backend_name)
    else:
        raise ValueError(f"Unknown backend: {backend_name}")

    return apply_hooks("extend_backend", backend, self._config)

def _resolve_backend(self) -> str:
    """Resolve which backend to use for this project."""
    from dodo.project_config import ProjectConfig

    if not self._project_id:
        return self._config.default_backend

    # Get project config directory
    project_dir = self._get_project_config_dir()

    # Try loading existing config
    config = ProjectConfig.load(project_dir)
    if config:
        return config.backend

    # Auto-detect from existing files
    detected = self._auto_detect_backend(project_dir)
    if detected:
        return detected

    # Use global default (will create dodo.json on first write)
    return self._config.default_backend
```

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: integrate project config into backend resolution"
```

---

## Task 12: Update CLI add command to require quoted text

**Files:**
- Modify: `src/dodo/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Update add command signature**

Change from:
```python
def add(
    text: Annotated[list[str], typer.Argument(help="Todo text")],
```

To:
```python
def add(
    text: Annotated[str, typer.Argument(help="Todo text (use quotes)")],
```

**Step 2: Update add command body**

Change:
```python
item = svc.add(" ".join(text))
```

To:
```python
item = svc.add(text)
```

**Step 3: Update tests**

Update any tests that use `dodo add word1 word2` to use `dodo add "word1 word2"`.

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: require quoted text for add command"
```

---

## Task 13: Add dodo backend command

**Files:**
- Modify: `src/dodo/cli.py`
- Create: `tests/test_cli_backend.py`

**Step 1: Write failing test**

Create `tests/test_cli_backend.py`:

```python
"""Tests for dodo backend command."""

from typer.testing import CliRunner

from dodo.cli import app

runner = CliRunner()


def test_backend_show_displays_current(tmp_path, monkeypatch):
    """dodo backend shows current project backend."""
    # Setup: create a project with sqlite backend
    monkeypatch.chdir(tmp_path)
    # ... setup git repo and dodo.json

    result = runner.invoke(app, ["backend"])
    assert result.exit_code == 0
    assert "sqlite" in result.stdout


def test_backend_set_changes_backend(tmp_path, monkeypatch):
    """dodo backend <name> sets project backend."""
    # Setup
    monkeypatch.chdir(tmp_path)
    # ... setup git repo

    result = runner.invoke(app, ["backend", "markdown"])
    assert result.exit_code == 0
    assert "markdown" in result.stdout
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli_backend.py -v
```

**Step 3: Implement backend command**

Add to `src/dodo/cli.py`:

```python
@app.command()
def backend(
    name: Annotated[str | None, typer.Argument(help="Backend to set")] = None,
    migrate: Annotated[bool, typer.Option("--migrate", help="Migrate todos from current backend")] = False,
    migrate_from: Annotated[str | None, typer.Option("--migrate-from", help="Source backend for migration")] = None,
):
    """Show or set project backend."""
    from dodo.project_config import ProjectConfig

    cfg = _get_config()
    project_id = _detect_project(worktree_shared=cfg.worktree_shared)

    if not project_id:
        console.print("[red]Error:[/red] Not in a project")
        raise typer.Exit(1)

    # Get project config directory
    project_dir = cfg.config_dir / "projects" / project_id

    if name is None:
        # Show current backend
        config = ProjectConfig.load(project_dir)
        current = config.backend if config else cfg.default_backend
        console.print(f"[bold]Backend:[/bold] {current}")
        return

    # Set backend
    if migrate:
        # TODO: implement migration
        console.print("[yellow]Migration not yet implemented[/yellow]")

    config = ProjectConfig(backend=name)
    config.save(project_dir)
    console.print(f"[green]✓[/green] Backend set to: {name}")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli_backend.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add dodo backend command"
```

---

## Task 14: Update info command for backend terminology

**Files:**
- Modify: `src/dodo/cli.py`

**Step 1: Update info command output**

Change:
```python
console.print(f"[bold]Adapter:[/bold] {cfg.default_adapter}")
```

To:
```python
console.print(f"[bold]Backend:[/bold] {cfg.default_backend}")
```

**Step 2: Commit**

```bash
git add -A && git commit -m "refactor: update info command for backend terminology"
```

---

## Task 15: Rename test directory

**Files:**
- Rename: `tests/test_adapters/` → `tests/test_backends/`
- Update: all test files to use Backend class names

**Step 1: Rename directory**

```bash
git mv tests/test_adapters tests/test_backends
```

**Step 2: Update imports in test files**

In each test file, update imports:
- `from dodo.adapters` → `from dodo.backends`
- `Adapter` → `Backend` in class references

**Step 3: Commit**

```bash
git add -A && git commit -m "refactor: rename test_adapters/ to test_backends/"
```

---

## Task 16: Global search and replace for stragglers

**Files:**
- All `.py` files

**Step 1: Search for remaining adapter references**

```bash
grep -r "adapter" src/dodo --include="*.py" | grep -v __pycache__
grep -r "Adapter" src/dodo --include="*.py" | grep -v __pycache__
```

**Step 2: Fix any remaining references**

Update any found references to use backend terminology.

**Step 3: Run full test suite**

```bash
pytest -v
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: fix remaining adapter references"
```

---

## Task 17: Update interactive UI settings menu

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Add "This Project" section to settings**

Add a section showing:
- Current project's backend
- Storage location
- Option to switch backend

**Step 2: Update any adapter references to backend**

Search for "adapter" in interactive.py and update to "backend".

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: add project backend section to settings UI"
```

---

## Task 18: Final verification and cleanup

**Files:**
- Various

**Step 1: Run full test suite**

```bash
pytest -v
```

**Step 2: Run type checking**

```bash
mypy src/dodo
```

**Step 3: Run linting**

```bash
ruff check src/dodo
```

**Step 4: Manual smoke test**

```bash
dodo backend
dodo add "test task"
dodo list
dodo backend markdown
dodo rm <id>
```

**Step 5: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: address test/lint issues from restructure"
```

---

## Summary

Total tasks: 18
Key changes:
- `adapters/` → `backends/`
- `TodoAdapter` → `TodoBackend`
- `default_adapter` → `default_backend`
- Default backend: `markdown` → `sqlite`
- `plugins/sqlite/` → deleted (moved to core)
- New: `project_config.py` for `dodo.json`
- New: `dodo backend` command
- CLI: `dodo add word1 word2` → `dodo add "word1 word2"`
