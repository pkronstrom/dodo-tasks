# Dodo Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up code audit findings across dead code, security issues, error handling, and DRY violations.

**Architecture:** Three-phase approach - Quick Wins first (low-risk, high-impact), then Core Improvements (medium effort), finally Architectural Changes (larger refactors).

**Tech Stack:** Python 3.11+, pytest, typer, httpx, sqlite3

---

## Phase 1: Quick Wins

### Task 1: Remove unused InteractiveList and ListContext

**Files:**
- Modify: `src/dodo/ui/rich_menu.py`

**Step 1: Verify no usages exist**

Run: `rg "InteractiveList|ListContext" src/`
Expected: Only hits in `rich_menu.py` itself (the definition and TODO comment)

**Step 2: Remove the unused classes**

Remove lines 22-195 from `src/dodo/ui/rich_menu.py`:

```python
# TODO: InteractiveList is an unused abstraction...
class InteractiveList(Generic[T]):
    ...

class ListContext(Generic[T]):
    ...
```

Keep only `RichTerminalMenu` class (lines 197-236).

**Step 3: Remove unused imports**

Update imports at top of file - remove `Generic`, `TypeVar`, `Callable`, `Any` if no longer needed:

```python
"""Rich + simple-term-menu implementation."""

import readchar
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from simple_term_menu import TerminalMenu

from dodo.ui.panel_builder import calculate_visible_range, format_scroll_indicator
```

Wait - `RichTerminalMenu` doesn't use those imports. Check if `calculate_visible_range`, `format_scroll_indicator` are used. They're not used by `RichTerminalMenu`. But they're re-exported from `ui/__init__.py` so keep them.

Final imports:
```python
"""Rich + simple-term-menu implementation."""

from rich.console import Console
from simple_term_menu import TerminalMenu
```

**Step 4: Run tests**

Run: `pytest tests/ -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/dodo/ui/rich_menu.py
git commit -m "refactor: remove unused InteractiveList and ListContext classes"
```

---

### Task 2: Add JSON decode guard for config loading

**Files:**
- Modify: `src/dodo/config.py`
- Create: `tests/test_config_errors.py`

**Step 1: Write the failing test**

```python
# tests/test_config_errors.py
"""Tests for config error handling."""

import pytest
from pathlib import Path

from dodo.config import Config, clear_config_cache


def test_corrupted_config_loads_defaults(tmp_path: Path):
    """Corrupted config file should fall back to defaults."""
    clear_config_cache()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text("{ invalid json }")

    cfg = Config.load(config_dir)

    # Should load defaults instead of crashing
    assert cfg.default_adapter == "markdown"
    assert cfg.worktree_shared is True


def test_empty_config_file_loads_defaults(tmp_path: Path):
    """Empty config file should load defaults."""
    clear_config_cache()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text("")

    cfg = Config.load(config_dir)
    assert cfg.default_adapter == "markdown"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_errors.py -v`
Expected: FAIL with `json.JSONDecodeError`

**Step 3: Write minimal implementation**

Modify `src/dodo/config.py` `_load_from_file` method:

```python
def _load_from_file(self) -> None:
    if self._config_file.exists():
        try:
            content = self._config_file.read_text()
            if content.strip():
                self._data = json.loads(content)
        except json.JSONDecodeError:
            # Corrupted config - use defaults, will be fixed on next save
            self._data = {}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_errors.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/config.py tests/test_config_errors.py
git commit -m "fix: gracefully handle corrupted config.json"
```

---

### Task 3: Add JSON decode guard for plugin registry

**Files:**
- Modify: `src/dodo/plugins/__init__.py`
- Modify: `tests/test_config_errors.py`

**Step 1: Write the failing test**

Add to `tests/test_config_errors.py`:

```python
from dodo.plugins import _load_registry, clear_plugin_cache


def test_corrupted_registry_triggers_rescan(tmp_path: Path, monkeypatch):
    """Corrupted plugin registry should trigger rescan."""
    clear_plugin_cache()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    registry_file = config_dir / "plugin_registry.json"
    registry_file.write_text("not valid json {{{")

    # Mock _scan_and_save_to to avoid actual scanning
    def mock_scan(path):
        return {"test-plugin": {"hooks": [], "builtin": True}}

    monkeypatch.setattr("dodo.plugins._scan_and_save_to", mock_scan)

    result = _load_registry(config_dir)

    # Should have rescanned instead of crashing
    assert "test-plugin" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_errors.py::test_corrupted_registry_triggers_rescan -v`
Expected: FAIL with `json.JSONDecodeError`

**Step 3: Write minimal implementation**

Modify `src/dodo/plugins/__init__.py` `_load_registry` function:

```python
def _load_registry(config_dir: Path) -> dict:
    """Load registry from file, with caching. Auto-scan if missing or corrupted."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    path = config_dir / "plugin_registry.json"
    if path.exists():
        try:
            content = path.read_text()
            if content.strip():
                _registry_cache = json.loads(content)
                return _registry_cache
        except json.JSONDecodeError:
            # Corrupted registry - rescan
            pass

    # Auto-scan on first run or if corrupted
    from dodo.cli_plugins import _scan_and_save_to

    _registry_cache = _scan_and_save_to(config_dir)
    return _registry_cache
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_errors.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/__init__.py tests/test_config_errors.py
git commit -m "fix: gracefully handle corrupted plugin_registry.json"
```

---

### Task 4: Add JSON decode guard for last_action file

**Files:**
- Modify: `src/dodo/cli.py`
- Modify: `tests/test_config_errors.py`

**Step 1: Write the failing test**

Add to `tests/test_config_errors.py`:

```python
def test_corrupted_last_action_returns_none(tmp_path: Path, monkeypatch):
    """Corrupted .last_action file should return None."""
    from dodo.cli import _load_last_action, _get_config
    from dodo.config import clear_config_cache

    clear_config_cache()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    last_action_file = config_dir / ".last_action"
    last_action_file.write_text("{broken json")

    # Mock _get_config to return our temp dir
    class MockConfig:
        config_dir = config_dir

    monkeypatch.setattr("dodo.cli._get_config", lambda: MockConfig())

    result = _load_last_action()
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_errors.py::test_corrupted_last_action_returns_none -v`
Expected: FAIL with `json.JSONDecodeError`

**Step 3: Write minimal implementation**

Modify `src/dodo/cli.py` `_load_last_action` function:

```python
def _load_last_action() -> dict | None:
    """Load last action."""
    cfg = _get_config()
    state_file = cfg.config_dir / ".last_action"
    if not state_file.exists():
        return None
    try:
        content = state_file.read_text()
        if content.strip():
            return json.loads(content)
        return None
    except json.JSONDecodeError:
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_errors.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_config_errors.py
git commit -m "fix: gracefully handle corrupted .last_action file"
```

---

### Task 5: Handle missing git binary gracefully

**Files:**
- Modify: `src/dodo/project.py`
- Create: `tests/test_project_errors.py`

**Step 1: Write the failing test**

```python
# tests/test_project_errors.py
"""Tests for project detection error handling."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from dodo.project import detect_project, clear_project_cache


def test_missing_git_returns_none(tmp_path: Path):
    """Missing git binary should return None, not crash."""
    clear_project_cache()

    # Mock subprocess.run to raise FileNotFoundError (git not found)
    def mock_run(*args, **kwargs):
        raise FileNotFoundError("git not found")

    with patch("subprocess.run", mock_run):
        result = detect_project(tmp_path)

    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_errors.py -v`
Expected: FAIL with `FileNotFoundError`

**Step 3: Write minimal implementation**

Modify `src/dodo/project.py` - update both `_get_git_root` and `_get_git_common_root`:

```python
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
    except (subprocess.CalledProcessError, FileNotFoundError):
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
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_project_errors.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/project.py tests/test_project_errors.py
git commit -m "fix: handle missing git binary gracefully"
```

---

### Task 6: Add ambiguity check for partial ID matching

**Files:**
- Modify: `src/dodo/cli.py`
- Create: `tests/test_cli_partial_id.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_partial_id.py
"""Tests for partial ID matching."""

from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest
import typer

from dodo.cli import _find_item_by_partial_id
from dodo.models import Status, TodoItem


def test_ambiguous_partial_id_raises_exit():
    """Ambiguous partial ID should exit with error, not pick first."""
    mock_svc = MagicMock()
    mock_svc.get.return_value = None
    mock_svc.list.return_value = [
        TodoItem(id="abc123", text="First", status=Status.PENDING, created_at=datetime.now()),
        TodoItem(id="abc456", text="Second", status=Status.PENDING, created_at=datetime.now()),
    ]

    with pytest.raises(typer.Exit) as exc_info:
        _find_item_by_partial_id(mock_svc, "abc")

    assert exc_info.value.exit_code == 1


def test_unique_partial_id_returns_item():
    """Unique partial ID should return the matching item."""
    mock_svc = MagicMock()
    mock_svc.get.return_value = None
    item = TodoItem(id="xyz789", text="Only one", status=Status.PENDING, created_at=datetime.now())
    mock_svc.list.return_value = [item]

    result = _find_item_by_partial_id(mock_svc, "xyz")
    assert result == item
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_partial_id.py -v`
Expected: FAIL - currently returns first match without checking ambiguity

**Step 3: Write minimal implementation**

Modify `src/dodo/cli.py` `_find_item_by_partial_id`:

```python
def _find_item_by_partial_id(svc: TodoService, partial_id: str):
    """Find item by full or partial ID."""
    # First try exact match
    item = svc.get(partial_id)
    if item:
        return item

    # Try partial match
    matches = [item for item in svc.list() if item.id.startswith(partial_id)]

    if len(matches) == 0:
        return None
    elif len(matches) == 1:
        return matches[0]
    else:
        # Ambiguous - show options and exit
        console.print(f"[yellow]Ambiguous ID '{partial_id}'. Matches:[/yellow]")
        for m in matches:
            console.print(f"  - {m.id}: {m.text[:50]}")
        raise typer.Exit(1)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_partial_id.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli_partial_id.py
git commit -m "fix: warn on ambiguous partial ID matches"
```

---

### Task 7: Close httpx.Client in Obsidian adapter

**Files:**
- Modify: `src/dodo/plugins/obsidian/adapter.py`

**Step 1: Verify current behavior**

The `httpx.Client` is created in `__init__` but never closed. This can leak connections.

**Step 2: Add context manager support**

Modify `src/dodo/plugins/obsidian/adapter.py`:

```python
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

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

**Step 3: Run existing tests**

Run: `pytest tests/ -v -k obsidian`
Expected: All pass (or skip if no obsidian tests)

**Step 4: Commit**

```bash
git add src/dodo/plugins/obsidian/adapter.py
git commit -m "fix: add close() method to ObsidianAdapter to prevent connection leaks"
```

---

### Task 8: Reuse JsonlFormatter in export command

**Files:**
- Modify: `src/dodo/cli.py`

**Step 1: Identify the duplication**

In `cli.py` lines 266-278, the export command manually builds JSONL. This duplicates `formatters/jsonl.py`.

**Step 2: Refactor to use JsonlFormatter**

Modify `src/dodo/cli.py` `export` command:

```python
@app.command()
def export(
    output: Annotated[str | None, typer.Option("-o", "--output", help="Output file")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Global todos")] = False,
):
    """Export todos to jsonl format."""
    from dodo.formatters.jsonl import JsonlFormatter

    cfg = _get_config()

    if global_:
        project_id = None
    else:
        project_id = _detect_project(worktree_shared=cfg.worktree_shared)

    svc = _get_service(cfg, project_id)
    items = svc.list()

    formatter = JsonlFormatter()
    content = formatter.format(items)

    if output:
        from pathlib import Path

        Path(output).write_text(content + "\n" if content else "")
        console.print(f"[green]✓[/green] Exported {len(items)} todos to {output}")
    else:
        console.print(content)
```

**Step 3: Run tests**

Run: `pytest tests/ -v`
Expected: All pass

**Step 4: Commit**

```bash
git add src/dodo/cli.py
git commit -m "refactor: reuse JsonlFormatter in export command (DRY)"
```

---

### Task 9: Add dist/ to .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: Check if dist/ is tracked**

Run: `git ls-files dist/`
Expected: Shows files if tracked

**Step 2: Add to .gitignore and remove from tracking**

```bash
echo "dist/" >> .gitignore
git rm -r --cached dist/ 2>/dev/null || true
```

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add dist/ to .gitignore"
```

---

## Phase 2: Core Improvements

### Task 10: Replace raw status strings with Status enum in GraphWrapper

**Files:**
- Modify: `src/dodo/plugins/graph/wrapper.py`

**Step 1: Identify the issue**

Lines 125-127 and 144-146 use raw `'pending'` string instead of `Status.PENDING.value`.

**Step 2: Fix the SQL queries**

Modify `src/dodo/plugins/graph/wrapper.py`:

```python
def get_ready(self, project: str | None = None) -> list[TodoItem]:
    """Get todos with no uncompleted blockers (ready to work on)."""
    from dodo.models import Status

    all_todos = self.list(project=project, status=Status.PENDING)

    # Get all dependencies where blocker is still pending
    with self._connect() as conn:
        rows = conn.execute(
            """
            SELECT d.blocked_id
            FROM dependencies d
            JOIN todos t ON d.blocker_id = t.id
            WHERE t.status = ?
            """,
            (Status.PENDING.value,),
        ).fetchall()
    blocked_ids = {row[0] for row in rows}

    return [t for t in all_todos if t.id not in blocked_ids]

def get_blocked_todos(self, project: str | None = None) -> list[TodoItem]:
    """Get todos that have uncompleted blockers."""
    from dodo.models import Status

    all_todos = self.list(project=project, status=Status.PENDING)

    with self._connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT d.blocked_id
            FROM dependencies d
            JOIN todos t ON d.blocker_id = t.id
            WHERE t.status = ?
            """,
            (Status.PENDING.value,),
        ).fetchall()
    blocked_ids = {row[0] for row in rows}

    return [t for t in all_todos if t.id in blocked_ids]
```

**Step 3: Run tests**

Run: `pytest tests/ -v -k graph`
Expected: All pass

**Step 4: Commit**

```bash
git add src/dodo/plugins/graph/wrapper.py
git commit -m "refactor: use Status.PENDING.value instead of raw string in SQL"
```

---

### Task 11: Fix shell injection vulnerability in ai.py

**Files:**
- Modify: `src/dodo/ai.py`
- Create: `tests/test_ai_security.py`

**Step 1: Write the failing test**

```python
# tests/test_ai_security.py
"""Tests for AI module security."""

from unittest.mock import patch, MagicMock
import subprocess

from dodo.ai import run_ai


def test_ai_command_uses_argument_list():
    """AI command should use argument list, not shell=True."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"tasks": ["test todo"]}'

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        run_ai(
            user_input="test",
            command="echo '{{prompt}}'",
            system_prompt="test system",
        )

        # Should NOT be called with shell=True
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs.get("shell") is not True, "Should not use shell=True"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_security.py -v`
Expected: FAIL - currently uses `shell=True`

**Step 3: Rewrite ai.py to use shlex and argument list**

This is a significant rewrite. The current approach builds a shell command string with template substitution. A safer approach is to use `shlex.split()` after template substitution, or restructure to pass arguments directly.

However, since the command template is user-configurable (`ai_command` in config), we need to preserve flexibility. The safest approach is to use `shlex.split()` on the final command.

Modify `src/dodo/ai.py`:

```python
"""AI-assisted todo formatting."""

import json
import shlex
import subprocess

DEFAULT_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {"tasks": {"type": "array", "items": {"type": "string"}}},
        "required": ["tasks"],
    }
)


def build_command(
    template: str,
    prompt: str,
    system: str,
    schema: str,
) -> list[str]:
    """Build command arguments from template.

    Returns a list of arguments suitable for subprocess.run without shell=True.
    """
    # Substitute placeholders
    cmd_str = (
        template.replace("{{prompt}}", prompt)
        .replace("{{system}}", system)
        .replace("{{schema}}", schema)
    )
    # Parse into argument list (handles quoting properly)
    return shlex.split(cmd_str)


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

    cmd_args = build_command(
        template=command,
        prompt=full_prompt,
        system=system_prompt,
        schema=schema or DEFAULT_SCHEMA,
    )

    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            import sys

            print(f"AI command failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return []

        # Parse JSON output
        output = result.stdout.strip()
        data = json.loads(output)

        # Extract tasks from structured_output (claude --output-format json)
        if isinstance(data, dict) and "structured_output" in data:
            tasks = data["structured_output"].get("tasks", [])
        elif isinstance(data, dict) and "tasks" in data:
            tasks = data["tasks"]
        elif isinstance(data, list):
            tasks = data
        else:
            print(f"Unexpected output format. Raw: {output[:500]}", file=sys.stderr)
            return []

        todos = [str(item) for item in tasks if item]
        if not todos:
            print(f"AI returned empty list. Raw output: {output[:500]}", file=sys.stderr)
        return todos

    except subprocess.TimeoutExpired:
        import sys

        print("AI command timed out", file=sys.stderr)
        return []
    except (json.JSONDecodeError, ValueError) as e:
        import sys

        print(f"Failed to parse AI output: {e}", file=sys.stderr)
        print(f"Raw output: {result.stdout[:500]}", file=sys.stderr)
        return []
```

**Step 4: Update the test to match new signature**

```python
def test_ai_command_uses_argument_list():
    """AI command should use argument list, not shell=True."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"tasks": ["test todo"]}'

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        run_ai(
            user_input="test",
            command="echo '{{prompt}}'",
            system_prompt="test system",
        )

        # Should be called with a list, not a string
        call_args = mock_run.call_args
        assert isinstance(call_args[0][0], list), "Should pass command as list"
        # Should NOT have shell=True
        call_kwargs = call_args.kwargs
        assert "shell" not in call_kwargs or call_kwargs["shell"] is False
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_ai_security.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/dodo/ai.py tests/test_ai_security.py
git commit -m "security: remove shell=True from AI command execution"
```

---

### Task 12: Replace frozen dataclass mutation with TodoItemView

**Files:**
- Modify: `src/dodo/models.py`
- Modify: `src/dodo/plugins/graph/wrapper.py`
- Modify: `src/dodo/plugins/graph/formatter.py`

**Step 1: Add TodoItemView to models**

Add to `src/dodo/models.py`:

```python
@dataclass
class TodoItemView:
    """Mutable view of a TodoItem with optional extension fields.

    Used when plugins need to attach additional data (e.g., blocked_by).
    """

    item: TodoItem
    blocked_by: list[str] | None = None

    # Delegate common properties
    @property
    def id(self) -> str:
        return self.item.id

    @property
    def text(self) -> str:
        return self.item.text

    @property
    def status(self) -> Status:
        return self.item.status

    @property
    def created_at(self):
        return self.item.created_at

    @property
    def completed_at(self):
        return self.item.completed_at

    @property
    def project(self):
        return self.item.project
```

**Step 2: Update GraphWrapper to use TodoItemView**

Modify `src/dodo/plugins/graph/wrapper.py`:

```python
def list(
    self,
    project: str | None = None,
    status: Status | None = None,
) -> list[TodoItem]:
    from dodo.models import TodoItemView

    items = self._adapter.list(project, status)
    # Wrap items with dependency info
    views = []
    for item in items:
        view = TodoItemView(item=item, blocked_by=self.get_blockers(item.id))
        views.append(view)
    return views
```

Note: This changes the return type. We need to update type hints and consumers.

**Step 3: Update GraphFormatter to handle TodoItemView**

The formatter already accesses `.blocked_by` via `getattr()`, so it should work. Verify:

```python
# In src/dodo/plugins/graph/formatter.py
blocked_by = getattr(item, "blocked_by", None)
```

This will work with TodoItemView since it has a `blocked_by` attribute.

**Step 4: Run tests**

Run: `pytest tests/ -v -k graph`
Expected: All pass

**Step 5: Commit**

```bash
git add src/dodo/models.py src/dodo/plugins/graph/wrapper.py
git commit -m "refactor: use TodoItemView instead of mutating frozen TodoItem"
```

---

## Phase 3: Architectural Changes

### Task 13: Centralize storage path calculation

**Files:**
- Create: `src/dodo/storage.py`
- Modify: `src/dodo/core.py`
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Create storage.py module**

```python
# src/dodo/storage.py
"""Centralized storage path calculation."""

from pathlib import Path

from dodo.config import Config
from dodo.project import detect_project_root


def get_storage_path(
    config: Config,
    project_id: str | None,
    adapter: str,
    worktree_shared: bool = True,
) -> Path:
    """Calculate storage path for an adapter.

    Args:
        config: Config instance
        project_id: Project ID or None for global
        adapter: Adapter name (markdown, sqlite, etc.)
        worktree_shared: Whether to use worktree-shared paths

    Returns:
        Path to storage file
    """
    # File extension by adapter
    extensions = {
        "markdown": "dodo.md",
        "sqlite": "dodo.db",
    }
    filename = extensions.get(adapter, f"dodo.{adapter}")

    # Local storage in project directory
    if config.local_storage and project_id:
        root = detect_project_root(worktree_shared=worktree_shared)
        if root:
            if adapter == "sqlite":
                return root / ".dodo" / filename
            return root / filename

    # Centralized storage
    if project_id:
        return config.config_dir / "projects" / project_id / filename

    return config.config_dir / filename
```

**Step 2: Update core.py to use storage.py**

Modify `src/dodo/core.py`:

```python
from dodo.storage import get_storage_path

# In TodoService class, replace _get_markdown_path and _get_sqlite_path:

def _get_markdown_path(self) -> Path:
    return get_storage_path(
        self._config,
        self._project_id,
        "markdown",
        self._config.worktree_shared,
    )

def _get_sqlite_path(self) -> Path:
    return get_storage_path(
        self._config,
        self._project_id,
        "sqlite",
        self._config.worktree_shared,
    )
```

**Step 3: Update interactive.py to use storage.py**

Find usages of storage path calculation in `interactive.py` and replace with `get_storage_path()`.

**Step 4: Run tests**

Run: `pytest tests/ -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/dodo/storage.py src/dodo/core.py src/dodo/ui/interactive.py
git commit -m "refactor: centralize storage path calculation"
```

---

### Task 14: Decouple plugin registry from CLI

**Files:**
- Modify: `src/dodo/plugins/__init__.py`
- Modify: `src/dodo/cli_plugins.py`

**Step 1: Move _scan_and_save_to logic into plugins/__init__.py**

The goal is to remove the circular dependency where `plugins/__init__.py` imports from `cli_plugins.py`.

Move the scanning logic into `plugins/__init__.py`:

```python
# In src/dodo/plugins/__init__.py

def _scan_plugins(config_dir: Path) -> dict:
    """Scan for available plugins and return registry dict."""
    registry = {}

    # Scan built-in plugins
    plugins_dir = Path(__file__).parent
    for plugin_path in plugins_dir.iterdir():
        if not plugin_path.is_dir() or plugin_path.name.startswith("_"):
            continue

        plugin_json = plugin_path / "plugin.json"
        if plugin_json.exists():
            try:
                info = json.loads(plugin_json.read_text())
                info["builtin"] = True
                registry[plugin_path.name] = info
            except json.JSONDecodeError:
                continue
        else:
            # Check for __init__.py with hooks
            init_file = plugin_path / "__init__.py"
            if init_file.exists():
                content = init_file.read_text()
                hooks = []
                for hook in ["register_adapter", "extend_adapter", "extend_formatter", "register_commands", "register_config"]:
                    if f"def {hook}" in content:
                        hooks.append(hook)
                if hooks:
                    registry[plugin_path.name] = {"hooks": hooks, "builtin": True}

    return registry


def _save_registry(config_dir: Path, registry: dict) -> None:
    """Save registry to file."""
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "plugin_registry.json"
    path.write_text(json.dumps(registry, indent=2))


def _scan_and_save(config_dir: Path) -> dict:
    """Scan plugins and save registry."""
    registry = _scan_plugins(config_dir)
    _save_registry(config_dir, registry)
    return registry
```

Then update `_load_registry`:

```python
def _load_registry(config_dir: Path) -> dict:
    """Load registry from file, with caching. Auto-scan if missing or corrupted."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    path = config_dir / "plugin_registry.json"
    if path.exists():
        try:
            content = path.read_text()
            if content.strip():
                _registry_cache = json.loads(content)
                return _registry_cache
        except json.JSONDecodeError:
            pass

    # Auto-scan
    _registry_cache = _scan_and_save(config_dir)
    return _registry_cache
```

**Step 2: Update cli_plugins.py to use the new functions**

```python
# In src/dodo/cli_plugins.py

from dodo.plugins import _scan_and_save, _load_registry

@plugins_app.command()
def scan() -> None:
    """Scan for plugins and update registry."""
    from dodo.config import Config
    cfg = Config.load()

    # Clear cache and rescan
    from dodo.plugins import clear_plugin_cache
    clear_plugin_cache()

    registry = _scan_and_save(cfg.config_dir)
    console.print(f"[green]✓[/green] Found {len(registry)} plugins")
```

**Step 3: Run tests**

Run: `pytest tests/ -v`
Expected: All pass

**Step 4: Commit**

```bash
git add src/dodo/plugins/__init__.py src/dodo/cli_plugins.py
git commit -m "refactor: decouple plugin scanning from CLI module"
```

---

## Verification

After completing all tasks, run full test suite:

```bash
pytest tests/ -v
```

And verify the application works:

```bash
dodo ls
dodo add "Test todo"
dodo done <id>
dodo config
```
