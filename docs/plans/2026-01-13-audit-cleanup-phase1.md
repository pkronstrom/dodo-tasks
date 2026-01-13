# Audit Cleanup Phase 1: Quick Wins Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 5 low-effort, high-impact issues from the 2026-01-13 code audit

**Architecture:** Small targeted fixes to config, plugins, core, and CLI modules. No structural changes.

**Tech Stack:** Python 3.11+, pytest, typer

**Issues Addressed:**
- ST-2: Config dir mismatch between cli.py and config.py
- PO-2: Missing `register_root_commands` from `_KNOWN_HOOKS`
- CS-2: Backend constructor try/except TypeError masks errors
- DRY-1: Repeated config/project/service resolution in CLI
- MOD-2: Storage path display uses wrong backend

---

## Task 1: Unify Config Directory Resolution (ST-2)

**Files:**
- Modify: `src/dodo/config.py:68-70`
- Modify: `src/dodo/cli.py:61-72`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
class TestConfigDefaultDir:
    def test_get_default_dir_returns_path(self):
        """Config.get_default_dir() should return default config directory."""
        from dodo.config import Config

        result = Config.get_default_dir()

        assert isinstance(result, Path)
        assert result == Path.home() / ".config" / "dodo"

    def test_get_default_dir_respects_env_var(self, tmp_path, monkeypatch):
        """Config.get_default_dir() should respect DODO_CONFIG_DIR env var."""
        from dodo.config import Config

        custom_dir = tmp_path / "custom-dodo"
        monkeypatch.setenv("DODO_CONFIG_DIR", str(custom_dir))

        result = Config.get_default_dir()

        assert result == custom_dir
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py::TestConfigDefaultDir -v
```

Expected: FAIL with `AttributeError: type object 'Config' has no attribute 'get_default_dir'`

**Step 3: Implement Config.get_default_dir()**

In `src/dodo/config.py`, add after `clear_config_cache()` function (around line 16):

```python
def get_default_config_dir() -> Path:
    """Get default config directory, respecting DODO_CONFIG_DIR env var.

    This is the single source of truth for config directory resolution.
    """
    config_dir = os.environ.get("DODO_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    return Path.home() / ".config" / "dodo"
```

Then modify `Config.__init__` to use it:

```python
def __init__(self, config_dir: Path | None = None):
    self._config_dir = config_dir or get_default_config_dir()
    self._config_file = self._config_dir / "config.json"
    self._data: dict[str, Any] = {}
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py::TestConfigDefaultDir -v
```

Expected: PASS

**Step 5: Update cli.py to use shared function**

In `src/dodo/cli.py`, replace `_get_config_dir()` function:

```python
def _get_config_dir():
    """Get config directory path using shared resolution logic."""
    from dodo.config import get_default_config_dir

    return get_default_config_dir()
```

**Step 6: Run all config tests**

```bash
pytest tests/test_config.py tests/test_lazy_loading.py -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add src/dodo/config.py src/dodo/cli.py tests/test_config.py
git commit -m "fix(config): unify config dir resolution with get_default_config_dir()

- Add get_default_config_dir() as single source of truth
- Respects DODO_CONFIG_DIR env var consistently
- CLI and Config now use same resolution logic

Fixes ST-2 from audit"
```

---

## Task 2: Add register_root_commands to Known Hooks (PO-2)

**Files:**
- Modify: `src/dodo/plugins/__init__.py:48-54`
- Test: `tests/test_cli_plugins.py`

**Step 1: Write the failing test**

Add to `tests/test_cli_plugins.py`:

```python
def test_register_root_commands_is_known_hook():
    """register_root_commands should be in _KNOWN_HOOKS for proper detection."""
    from dodo.plugins import _KNOWN_HOOKS

    assert "register_root_commands" in _KNOWN_HOOKS
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli_plugins.py::test_register_root_commands_is_known_hook -v
```

Expected: FAIL with `AssertionError`

**Step 3: Add hook to _KNOWN_HOOKS**

In `src/dodo/plugins/__init__.py`, modify `_KNOWN_HOOKS` (around line 48):

```python
# Known hooks that plugins can implement
_KNOWN_HOOKS = [
    "register_commands",
    "register_root_commands",  # Added: for top-level CLI commands
    "register_config",
    "register_backend",
    "extend_backend",
    "extend_formatter",
]
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli_plugins.py::test_register_root_commands_is_known_hook -v
```

Expected: PASS

**Step 5: Run full plugin tests**

```bash
pytest tests/test_cli_plugins.py tests/test_graph_plugin.py -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add src/dodo/plugins/__init__.py tests/test_cli_plugins.py
git commit -m "fix(plugins): add register_root_commands to _KNOWN_HOOKS

Plugin registry scanner now detects root command hooks properly.

Fixes PO-2 from audit"
```

---

## Task 3: Fix Backend Constructor Error Masking (CS-2)

**Files:**
- Modify: `src/dodo/core.py:157-180`
- Test: `tests/test_core.py`

**Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
class TestBackendInstantiation:
    def test_backend_typeerror_not_masked(self, tmp_path, monkeypatch):
        """Real TypeErrors in backend constructors should propagate."""
        from dodo.config import Config, clear_config_cache
        from dodo.core import TodoService, _backend_registry

        clear_config_cache()

        # Create a backend class that raises TypeError in __init__
        class BrokenBackend:
            def __init__(self, path):
                # Simulate a real bug: wrong attribute access
                self.items = path.nonexistent_method()  # TypeError!

        # Register it
        _backend_registry["broken"] = BrokenBackend
        monkeypatch.setenv("DODO_DEFAULT_BACKEND", "broken")

        config = Config.load(tmp_path / "config")

        # Should raise TypeError, not silently fall back
        with pytest.raises(TypeError):
            TodoService(config, project_id=None)

        # Cleanup
        del _backend_registry["broken"]
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_core.py::TestBackendInstantiation::test_backend_typeerror_not_masked -v
```

Expected: FAIL (test expects TypeError but current code catches it)

**Step 3: Implement signature-based constructor detection**

In `src/dodo/core.py`, replace `_instantiate_backend` method (around line 157):

```python
def _instantiate_backend(self, backend_name: str) -> TodoBackend:
    """Create backend instance with appropriate arguments."""
    import inspect

    backend_ref = _backend_registry[backend_name]
    backend_cls = _resolve_backend_class(backend_ref)

    # Different backends need different initialization
    if backend_name == "markdown":
        return backend_cls(self._get_markdown_path())
    elif backend_name == "sqlite":
        return backend_cls(self._get_sqlite_path())
    elif backend_name == "obsidian":
        return backend_cls(
            api_url=self._config.obsidian_api_url,
            api_key=self._config.obsidian_api_key,
            vault_path=self._config.obsidian_vault_path,
        )
    else:
        # For plugin backends, check constructor signature
        sig = inspect.signature(backend_cls.__init__)
        params = list(sig.parameters.keys())

        # Try config+project_id pattern (preferred for plugins)
        if "config" in params and "project_id" in params:
            return backend_cls(config=self._config, project_id=self._project_id)
        elif "config" in params:
            return backend_cls(config=self._config)
        elif "path" in params:
            # Generic path-based backend
            from dodo.storage import get_storage_path
            path = get_storage_path(
                self._config, self._project_id, backend_name, self._config.worktree_shared
            )
            return backend_cls(path=path)
        else:
            # No-args construction
            return backend_cls()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_core.py::TestBackendInstantiation::test_backend_typeerror_not_masked -v
```

Expected: PASS

**Step 5: Run full core tests**

```bash
pytest tests/test_core.py -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add src/dodo/core.py tests/test_core.py
git commit -m "fix(core): use inspect.signature() for backend construction

Replace try/except TypeError with explicit signature inspection.
Real TypeErrors in plugin backends now propagate correctly.

Fixes CS-2 from audit"
```

---

## Task 4: Create Service Context for CLI Commands (DRY-1)

**Files:**
- Create: `src/dodo/cli_context.py`
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_get_service_context_returns_tuple(tmp_path, monkeypatch):
    """get_service_context() should return (config, project_id, service) tuple."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from dodo.config import clear_config_cache
    clear_config_cache()

    from dodo.cli_context import get_service_context

    cfg, project_id, svc = get_service_context()

    assert cfg is not None
    assert svc is not None
    # project_id can be None (global) or string


def test_get_service_context_respects_global_flag(tmp_path, monkeypatch):
    """get_service_context(global_=True) should force global project."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from dodo.config import clear_config_cache
    clear_config_cache()

    from dodo.cli_context import get_service_context

    cfg, project_id, svc = get_service_context(global_=True)

    assert project_id is None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py::test_get_service_context_returns_tuple -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'dodo.cli_context'`

**Step 3: Create cli_context.py**

Create `src/dodo/cli_context.py`:

```python
"""CLI context utilities for common command setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.config import Config
    from dodo.core import TodoService


def get_service_context(
    global_: bool = False,
    project: str | None = None,
) -> tuple["Config", str | None, "TodoService"]:
    """Get config, project_id, and service for CLI commands.

    This centralizes the common pattern used by most CLI commands:
        cfg = _get_config()
        project_id = _detect_project(worktree_shared=cfg.worktree_shared)
        svc = _get_service(cfg, project_id)

    Args:
        global_: Force global list (no project)
        project: Explicit project name/ID

    Returns:
        Tuple of (config, project_id, service)
    """
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.project import detect_project

    cfg = Config.load()

    if global_:
        project_id = None
    elif project:
        project_id = _resolve_project(project, cfg)
    else:
        project_id = detect_project(worktree_shared=cfg.worktree_shared)

    svc = TodoService(cfg, project_id)
    return cfg, project_id, svc


def _resolve_project(partial: str, cfg: "Config") -> str | None:
    """Resolve partial project name to full project ID."""
    if not partial:
        return None

    projects_dir = cfg.config_dir / "projects"

    if not projects_dir.exists():
        return partial  # No projects yet, use as-is

    existing = [p.name for p in projects_dir.iterdir() if p.is_dir()]

    # Exact match
    if partial in existing:
        return partial

    # Partial match (prefix)
    matches = [p for p in existing if p.startswith(partial)]

    if len(matches) == 1:
        return matches[0]

    # No match or ambiguous - use as-is
    return partial
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli.py::test_get_service_context_returns_tuple tests/test_cli.py::test_get_service_context_respects_global_flag -v
```

Expected: PASS

**Step 5: Update one CLI command to use it (add command)**

In `src/dodo/cli.py`, modify the `add` command:

```python
@app.command()
def add(
    text: Annotated[str, typer.Argument(help="Todo text (use quotes)")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
):
    """Add a todo item."""
    from dodo.cli_context import get_service_context

    cfg, project_id, svc = get_service_context(global_=global_)
    target = project_id or "global"

    item = svc.add(text)

    _save_last_action("add", item.id, target)

    dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
    console.print(f"[green]✓[/green] Added to {dest}: {item.text} [dim]({item.id})[/dim]")
```

**Step 6: Run CLI tests**

```bash
pytest tests/test_cli.py -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add src/dodo/cli_context.py src/dodo/cli.py tests/test_cli.py
git commit -m "refactor(cli): add get_service_context() to reduce duplication

Centralizes config/project/service setup used by CLI commands.
Updated 'add' command as proof of concept.

Fixes DRY-1 from audit (partial - one command updated)"
```

---

## Task 5: Fix Storage Path to Use Resolved Backend (MOD-2)

**Files:**
- Modify: `src/dodo/ui/interactive.py:356-360`
- Test: `tests/test_ui/test_interactive_imports.py` (or create if needed)

**Step 1: Write the failing test**

Create or add to `tests/test_ui/test_interactive_imports.py`:

```python
"""Tests for interactive UI utilities."""

from pathlib import Path

import pytest


def test_get_project_storage_path_uses_resolved_backend(tmp_path, monkeypatch):
    """_get_project_storage_path should use project's backend, not default."""
    from dodo.config import Config, clear_config_cache

    clear_config_cache()
    monkeypatch.setenv("HOME", str(tmp_path))

    # Set up config with sqlite as default
    cfg = Config.load()
    cfg.set("default_backend", "sqlite")

    # Create project config with markdown backend
    project_id = "test-project"
    project_dir = cfg.config_dir / "projects" / project_id
    project_dir.mkdir(parents=True)
    (project_dir / "project.json").write_text('{"backend": "markdown"}')

    from dodo.ui.interactive import _get_project_storage_path

    # Should return markdown path, not sqlite
    path = _get_project_storage_path(cfg, project_id, worktree_shared=False)

    assert path.suffix == ".md", f"Expected .md but got {path}"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_ui/test_interactive_imports.py::test_get_project_storage_path_uses_resolved_backend -v
```

Expected: FAIL with `AssertionError: Expected .md but got .db`

**Step 3: Fix _get_project_storage_path to resolve backend**

In `src/dodo/ui/interactive.py`, modify `_get_project_storage_path` (around line 356):

```python
def _get_project_storage_path(
    cfg: Config, project_id: str | None, worktree_shared: bool, backend: str | None = None
) -> Path:
    """Get storage path for a project configuration.

    Args:
        cfg: Config instance
        project_id: Project ID or None for global
        worktree_shared: Whether worktrees share storage
        backend: Explicit backend name, or None to resolve from project config
    """
    from dodo.storage import get_storage_path

    if backend is None:
        # Resolve backend from project config or use default
        from dodo.project_config import ProjectConfig, get_project_config_dir

        if project_id:
            project_dir = get_project_config_dir(cfg, project_id, worktree_shared)
            if project_dir:
                project_cfg = ProjectConfig.load(project_dir)
                if project_cfg:
                    backend = project_cfg.backend

        if backend is None:
            backend = cfg.default_backend

    return get_storage_path(cfg, project_id, backend, worktree_shared)
```

**Step 4: Update callers to not pass backend when they want resolution**

Several callers in interactive.py need updating. The key ones are in `interactive_menu()` and `_interactive_switch()`. Find and update:

```python
# In interactive_menu() around line 44
storage_path = _get_project_storage_path(cfg, project_id, cfg.worktree_shared)

# In _interactive_switch() around line 419, 425, 431, 443
# These already don't pass backend, so they should work
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_ui/test_interactive_imports.py::test_get_project_storage_path_uses_resolved_backend -v
```

Expected: PASS

**Step 6: Run all UI tests**

```bash
pytest tests/test_ui/ -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add src/dodo/ui/interactive.py tests/test_ui/test_interactive_imports.py
git commit -m "fix(ui): storage path now uses project's resolved backend

_get_project_storage_path() resolves backend from project config
instead of always using cfg.default_backend.

Fixes MOD-2 from audit"
```

---

## Final Verification

**Step 1: Run full test suite**

```bash
pytest -v
```

Expected: All PASS

**Step 2: Test common commands manually**

```bash
time dodo list
time dodo add "test item"
time dodo done <id>
dodo rm <id>
```

Verify startup time hasn't regressed.

**Step 3: Create summary commit (optional)**

```bash
git log --oneline -5
```

Review that all 5 tasks have been committed.

---

## Summary

| Task | Issue | Status |
|------|-------|--------|
| 1 | ST-2: Config dir mismatch | |
| 2 | PO-2: Missing hook | |
| 3 | CS-2: TypeError masking | |
| 4 | DRY-1: Service context | |
| 5 | MOD-2: Storage path backend | |

Total estimated time: 30-45 minutes
