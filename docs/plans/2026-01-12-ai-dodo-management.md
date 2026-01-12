# AI-Friendly Dodo Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable AI agents to create/destroy ephemeral dodos for parallel task tracking with dependencies.

**Architecture:** Add `dodo new`/`dodo destroy` commands, update resolution to check local `.dodo/` first, rename "project" to "dodo" terminology throughout.

**Tech Stack:** Python 3.11+, Typer CLI, SQLite/Markdown backends

---

## Task 1: Add `dodo new` Command (Core)

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test for basic `dodo new`**

Add to `tests/test_cli.py`:

```python
class TestCliNew:
    def test_new_creates_default_dodo(self, cli_env):
        """dodo new creates default dodo in ~/.config/dodo/"""
        result = runner.invoke(app, ["new"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Created dodo" in result.stdout
        # Check file was created
        config_dir = cli_env
        assert (config_dir / "dodo.db").exists() or (config_dir / "dodo.md").exists()

    def test_new_creates_named_dodo(self, cli_env):
        """dodo new <name> creates named dodo in ~/.config/dodo/<name>/"""
        result = runner.invoke(app, ["new", "my-session"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "my-session" in result.stdout
        config_dir = cli_env
        assert (config_dir / "my-session").is_dir()

    def test_new_local_creates_in_cwd(self, cli_env, tmp_path, monkeypatch):
        """dodo new --local creates .dodo/ in current directory"""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["new", "--local"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert ".dodo" in result.stdout
        assert (tmp_path / ".dodo").is_dir()

    def test_new_named_local_creates_subdir(self, cli_env, tmp_path, monkeypatch):
        """dodo new <name> --local creates .dodo/<name>/"""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["new", "agent-123", "--local"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert (tmp_path / ".dodo" / "agent-123").is_dir()

    def test_new_with_backend(self, cli_env):
        """dodo new --backend sqlite uses specified backend"""
        result = runner.invoke(app, ["new", "test-proj", "--backend", "sqlite"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        config_dir = cli_env
        assert (config_dir / "test-proj" / "dodo.db").exists()

    def test_new_idempotent_shows_hint(self, cli_env):
        """dodo new when dodo exists shows hint to use name"""
        runner.invoke(app, ["new"])
        result = runner.invoke(app, ["new"])

        assert result.exit_code == 0
        assert "already exists" in result.stdout.lower()
        assert "dodo new <name>" in result.stdout
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestCliNew -v`
Expected: FAIL with "no such command 'new'"

**Step 3: Implement `dodo new` command**

Add to `src/dodo/cli.py` after the `init` command (~line 347):

```python
@app.command()
def new(
    name: Annotated[str | None, typer.Argument(help="Name for the dodo")] = None,
    local: Annotated[bool, typer.Option("--local", help="Create in .dodo/ locally")] = False,
    backend: Annotated[str | None, typer.Option("--backend", "-b", help="Backend (sqlite|markdown)")] = None,
):
    """Create a new dodo."""
    from dodo.project_config import ProjectConfig

    cfg = _get_config()
    backend_name = backend or cfg.default_backend

    # Determine target directory
    if local or name:
        # Local storage in .dodo/
        base = Path.cwd() / ".dodo"
        if name:
            target_dir = base / name
        else:
            target_dir = base
    else:
        # Centralized in ~/.config/dodo/
        if name:
            target_dir = cfg.config_dir / name
        else:
            target_dir = cfg.config_dir

    # Check if already exists
    config_file = target_dir / "dodo.json"
    db_file = target_dir / "dodo.db"
    md_file = target_dir / "dodo.md"

    if config_file.exists() or db_file.exists() or md_file.exists():
        location = str(target_dir).replace(str(Path.home()), "~")
        console.print(f"[yellow]Dodo already exists in {location}[/yellow]")
        console.print("  Hint: Use [bold]dodo new <name>[/bold] to create a named dodo")
        return

    # Create directory and config
    target_dir.mkdir(parents=True, exist_ok=True)
    project_config = ProjectConfig(backend=backend_name)
    project_config.save(target_dir)

    # Initialize empty backend file
    if backend_name == "sqlite":
        from dodo.backends.sqlite import SqliteBackend
        SqliteBackend(target_dir / "dodo.db")
    elif backend_name == "markdown":
        (target_dir / "dodo.md").write_text("")

    location = str(target_dir).replace(str(Path.home()), "~")
    console.print(f"[green]✓[/green] Created dodo in {location}")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py::TestCliNew -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat: add dodo new command for creating dodos"
```

---

## Task 2: Add `dodo destroy` Command

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test for `dodo destroy`**

Add to `tests/test_cli.py`:

```python
class TestCliDestroy:
    def test_destroy_removes_named_dodo(self, cli_env):
        """dodo destroy <name> removes the dodo"""
        # Create first
        runner.invoke(app, ["new", "temp-session"])
        config_dir = cli_env
        assert (config_dir / "temp-session").exists()

        # Destroy
        result = runner.invoke(app, ["destroy", "temp-session"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Removed" in result.stdout or "Destroyed" in result.stdout
        assert not (config_dir / "temp-session").exists()

    def test_destroy_local_removes_local_dodo(self, cli_env, tmp_path, monkeypatch):
        """dodo destroy <name> --local removes .dodo/<name>/"""
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["new", "agent-456", "--local"])
        assert (tmp_path / ".dodo" / "agent-456").exists()

        result = runner.invoke(app, ["destroy", "agent-456", "--local"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert not (tmp_path / ".dodo" / "agent-456").exists()

    def test_destroy_nonexistent_errors(self, cli_env):
        """dodo destroy <name> errors if dodo doesn't exist"""
        result = runner.invoke(app, ["destroy", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_destroy_default_local(self, cli_env, tmp_path, monkeypatch):
        """dodo destroy --local removes default .dodo/"""
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["new", "--local"])
        assert (tmp_path / ".dodo").exists()

        result = runner.invoke(app, ["destroy", "--local"])

        assert result.exit_code == 0
        assert not (tmp_path / ".dodo").exists()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestCliDestroy -v`
Expected: FAIL with "no such command 'destroy'"

**Step 3: Implement `dodo destroy` command**

Add to `src/dodo/cli.py` after the `new` command:

```python
@app.command()
def destroy(
    name: Annotated[str | None, typer.Argument(help="Name of the dodo to destroy")] = None,
    local: Annotated[bool, typer.Option("--local", help="Destroy from .dodo/ locally")] = False,
):
    """Destroy a dodo and its data."""
    import shutil

    cfg = _get_config()

    # Determine target directory
    if local:
        base = Path.cwd() / ".dodo"
        if name:
            target_dir = base / name
        else:
            target_dir = base
    else:
        if name:
            target_dir = cfg.config_dir / name
        else:
            console.print("[red]Error:[/red] Specify a name or use --local")
            raise typer.Exit(1)

    if not target_dir.exists():
        location = str(target_dir).replace(str(Path.home()), "~")
        console.print(f"[red]Error:[/red] Dodo not found at {location}")
        raise typer.Exit(1)

    # Remove the directory
    shutil.rmtree(target_dir)

    location = str(target_dir).replace(str(Path.home()), "~")
    console.print(f"[green]✓[/green] Destroyed dodo at {location}")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py::TestCliDestroy -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat: add dodo destroy command"
```

---

## Task 3: Add `--dodo` Flag to Commands

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test for `--dodo` flag**

Add to `tests/test_cli.py`:

```python
class TestCliDodoFlag:
    def test_add_with_dodo_flag(self, cli_env):
        """dodo add --dodo <name> adds to specific dodo"""
        runner.invoke(app, ["new", "my-tasks"])
        result = runner.invoke(app, ["add", "Test task", "--dodo", "my-tasks"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Test task" in result.stdout

    def test_list_with_dodo_flag(self, cli_env):
        """dodo list --dodo <name> lists from specific dodo"""
        runner.invoke(app, ["new", "my-tasks"])
        runner.invoke(app, ["add", "Task in my-tasks", "--dodo", "my-tasks"])

        result = runner.invoke(app, ["list", "--dodo", "my-tasks"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Task in my-tasks" in result.stdout

    def test_dodo_flag_local(self, cli_env, tmp_path, monkeypatch):
        """dodo add --dodo <name> --local uses local .dodo/<name>/"""
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["new", "local-tasks", "--local"])
        result = runner.invoke(app, ["add", "Local task", "--dodo", "local-tasks", "--local"])

        assert result.exit_code == 0, f"Failed: {result.output}"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestCliDodoFlag -v`
Expected: FAIL

**Step 3: Add `--dodo` flag and resolution helper**

Add helper function in `src/dodo/cli.py` (after `_detect_project`):

```python
def _resolve_dodo(
    config: Config,
    dodo_name: str | None = None,
    local: bool = False,
    global_: bool = False,
) -> tuple[str | None, Path | None]:
    """Resolve which dodo to use.

    Returns:
        (dodo_id, explicit_path) - explicit_path is set for named dodos
    """
    if global_:
        return None, None

    # Explicit dodo name provided
    if dodo_name:
        if local:
            path = Path.cwd() / ".dodo" / dodo_name
        else:
            path = config.config_dir / dodo_name
        return dodo_name, path

    # Auto-detect: local first, then git-based
    local_dodo = Path.cwd() / ".dodo"
    if local_dodo.exists() and (local_dodo / "dodo.json").exists():
        return "local", local_dodo

    # Check parent directories for .dodo
    for parent in Path.cwd().parents:
        candidate = parent / ".dodo"
        if candidate.exists() and (candidate / "dodo.json").exists():
            return "local", candidate
        # Stop at filesystem root or home
        if parent == Path.home() or parent == Path("/"):
            break

    # Fall back to git-based detection
    project_id = _detect_project(worktree_shared=config.worktree_shared)
    return project_id, None
```

Update `add` command to accept `--dodo` flag (modify existing):

```python
@app.command()
def add(
    text: Annotated[str, typer.Argument(help="Todo text")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Add to global todos")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    local: Annotated[bool, typer.Option("--local", help="Use local .dodo/")] = False,
    # ... keep existing options
):
    """Add a new todo."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, local, global_)

    # If explicit path, temporarily override config for service
    if explicit_path:
        # Create service pointing to explicit path
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)
    # ... rest of command
```

**Note:** This requires creating `_get_service_with_path` helper or updating `TodoService` to accept explicit paths. This is a larger change that affects `core.py`.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py::TestCliDodoFlag -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat: add --dodo flag for targeting specific dodos"
```

---

## Task 4: Update Resolution Logic in Core

**Files:**
- Modify: `src/dodo/core.py`
- Modify: `src/dodo/storage.py`
- Test: `tests/test_core.py`

**Step 1: Write failing test for explicit path support**

Add to `tests/test_core.py`:

```python
class TestTodoServiceExplicitPath:
    def test_service_with_explicit_path(self, tmp_path):
        """TodoService can use an explicit storage path."""
        from dodo.config import Config
        from dodo.core import TodoService

        dodo_path = tmp_path / "my-dodo"
        dodo_path.mkdir()

        config = Config(config_dir=tmp_path / ".config" / "dodo")
        svc = TodoService(config, project_id=None, storage_path=dodo_path)

        item = svc.add("Test task")
        assert item.text == "Test task"
        assert (dodo_path / "dodo.db").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core.py::TestTodoServiceExplicitPath -v`
Expected: FAIL

**Step 3: Update TodoService to accept explicit storage path**

Modify `src/dodo/core.py` `TodoService.__init__`:

```python
class TodoService:
    """Main service - routes to appropriate backend."""

    def __init__(
        self,
        config: Config,
        project_id: str | None = None,
        storage_path: Path | None = None,
    ):
        self._config = config
        self._project_id = project_id
        self._storage_path = storage_path  # Explicit override
        self._backend_name: str = ""
        self._backend = self._create_backend()
```

Update `_get_sqlite_path` and `_get_markdown_path` to respect explicit path:

```python
def _get_sqlite_path(self) -> Path:
    if self._storage_path:
        return self._storage_path / "dodo.db"
    from dodo.storage import get_storage_path
    return get_storage_path(
        self._config,
        self._project_id,
        "sqlite",
        self._config.worktree_shared,
    )

def _get_markdown_path(self) -> Path:
    if self._storage_path:
        return self._storage_path / "dodo.md"
    from dodo.storage import get_storage_path
    return get_storage_path(
        self._config,
        self._project_id,
        "markdown",
        self._config.worktree_shared,
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_core.py::TestTodoServiceExplicitPath -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/core.py tests/test_core.py
git commit -m "feat: TodoService supports explicit storage path"
```

---

## Task 5: Remove `local_storage` Config Setting

**Files:**
- Modify: `src/dodo/config.py`
- Modify: `src/dodo/storage.py`
- Modify: `src/dodo/project_config.py`
- Test: `tests/test_config.py`

**Step 1: Write test verifying local_storage is removed**

Add to `tests/test_config.py`:

```python
def test_local_storage_not_in_toggles():
    """local_storage should be removed from config toggles."""
    from dodo.config import ConfigMeta

    assert "local_storage" not in ConfigMeta.TOGGLES
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_local_storage_not_in_toggles -v`
Expected: FAIL

**Step 3: Remove local_storage from config**

In `src/dodo/config.py`:

1. Remove from `ConfigMeta.TOGGLES`:
```python
TOGGLES: dict[str, str] = {
    "worktree_shared": "Share todos across git worktrees",
    "timestamps_enabled": "Add timestamps to todo entries",
    # "local_storage" removed
}
```

2. Remove from `Config.DEFAULTS`:
```python
DEFAULTS: dict[str, Any] = {
    # Toggles
    "worktree_shared": True,
    "timestamps_enabled": True,
    # "local_storage" removed
    # ... rest
}
```

Update `src/dodo/storage.py` to remove `local_storage` check:

```python
def get_storage_path(
    config: Config,
    project_id: str | None,
    backend: str,
    worktree_shared: bool = True,
) -> Path:
    """Calculate storage path for a backend."""
    extensions = {
        "markdown": "dodo.md",
        "sqlite": "dodo.db",
    }
    filename = extensions.get(backend, f"dodo.{backend}")

    # Centralized storage only now
    if project_id:
        return config.config_dir / "projects" / project_id / filename

    return config.config_dir / filename
```

Update `src/dodo/project_config.py` to remove `local_storage` check.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_local_storage_not_in_toggles -v`
Expected: PASS

**Step 5: Run full test suite to check for regressions**

Run: `uv run pytest -x`
Expected: Some tests may fail due to local_storage references - fix them.

**Step 6: Commit**

```bash
git add src/dodo/config.py src/dodo/storage.py src/dodo/project_config.py tests/
git commit -m "refactor: remove local_storage config setting"
```

---

## Task 6: Deprecate `dodo init` (Keep as Alias)

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write test for init deprecation warning**

Add to `tests/test_cli.py`:

```python
class TestCliInitDeprecation:
    def test_init_shows_deprecation_warning(self, cli_env, tmp_path, monkeypatch):
        """dodo init shows deprecation warning pointing to dodo new"""
        # Create a fake git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        with patch("dodo.project.detect_project", return_value="test_abc123"):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "deprecated" in result.stdout.lower() or "dodo new" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::TestCliInitDeprecation -v`
Expected: FAIL (no deprecation warning yet)

**Step 3: Update init command to show deprecation**

Modify `init` command in `src/dodo/cli.py`:

```python
@app.command(hidden=True)  # Hide from help
def init(
    local: Annotated[bool, typer.Option("--local", help="Store todos in project dir")] = False,
):
    """Initialize dodo for current project. (Deprecated: use 'dodo new')"""
    console.print("[yellow]Note:[/yellow] 'dodo init' is deprecated. Use 'dodo new' instead.")

    cfg = _get_config()
    project_id = _detect_project(worktree_shared=cfg.worktree_shared)

    if not project_id:
        console.print("[red]Error:[/red] Not in a git repository")
        console.print("  Use [bold]dodo new[/bold] to create a dodo anywhere.")
        raise typer.Exit(1)

    # Equivalent to: dodo new --local (for git projects)
    if local:
        target_dir = Path.cwd() / ".dodo"
    else:
        target_dir = cfg.config_dir / "projects" / project_id

    from dodo.project_config import ProjectConfig

    if not (target_dir / "dodo.json").exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        project_config = ProjectConfig(backend=cfg.default_backend)
        project_config.save(target_dir)

    console.print(f"[green]✓[/green] Initialized dodo: {project_id}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::TestCliInitDeprecation -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "deprecate: dodo init in favor of dodo new"
```

---

## Task 7: Rename "Project" to "Dodo" in UI Text

**Files:**
- Modify: `src/dodo/cli.py` (output messages)
- Modify: `src/dodo/ui/interactive.py` (menu labels)

**Step 1: Search and list all "project" references in user-facing text**

```bash
grep -rn -i "project" src/dodo/cli.py src/dodo/ui/interactive.py | grep -v "project_id\|project_config\|project_dir"
```

**Step 2: Update CLI output messages**

In `src/dodo/cli.py`, replace user-facing "project" with "dodo":
- "Not in a project" → "No dodo found"
- "Project:" → "Dodo:"
- etc.

**Step 3: Update interactive menu**

In `src/dodo/ui/interactive.py`:
- "Projects" menu item → "Dodos"
- "Switch Projects" → Remove (auto-detect only)
- Add "New dodo" menu option

**Step 4: Run full test suite**

Run: `uv run pytest`
Expected: PASS (update any tests checking for "project" in output)

**Step 5: Commit**

```bash
git add src/dodo/cli.py src/dodo/ui/interactive.py tests/
git commit -m "refactor: rename 'project' to 'dodo' in user-facing text"
```

---

## Task 8: Update Interactive Menu Structure

**Files:**
- Modify: `src/dodo/ui/interactive.py`
- Test: Manual testing required

**Step 1: Remove "Switch Projects" stateful menu**

Find and remove the Projects switching logic that maintains state.

**Step 2: Add "New dodo" menu option**

Add a menu item that offers:
- Create in ~/.config/dodo/ (default)
- Create locally in .dodo/
- Create for this git repo

**Step 3: Update "Dodos" menu to be read-only list**

Show detected dodos with stats, no switching.

**Step 4: Test interactively**

Run: `dodo config` and verify menu structure

**Step 5: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "refactor: update interactive menu for new dodo model"
```

---

## Task 9: Final Integration Test

**Files:**
- Test: `tests/test_integration.py`

**Step 1: Write end-to-end test for AI workflow**

```python
class TestAIDodoWorkflow:
    def test_ai_ephemeral_dodo_workflow(self, cli_env, tmp_path, monkeypatch):
        """Full AI workflow: create, add tasks with deps, list, destroy"""
        monkeypatch.chdir(tmp_path)

        # Create ephemeral dodo
        result = runner.invoke(app, ["new", "agent-session-123", "--local", "--backend", "sqlite"])
        assert result.exit_code == 0

        # Add tasks with dependencies
        runner.invoke(app, ["add", "Fetch data", "--dodo", "agent-session-123", "--local"])
        runner.invoke(app, ["add", "Process data", "--after", "1", "--dodo", "agent-session-123", "--local"])

        # List tasks
        result = runner.invoke(app, ["list", "--dodo", "agent-session-123", "--local"])
        assert "Fetch data" in result.stdout
        assert "Process data" in result.stdout

        # Destroy
        result = runner.invoke(app, ["destroy", "agent-session-123", "--local"])
        assert result.exit_code == 0
        assert not (tmp_path / ".dodo" / "agent-session-123").exists()
```

**Step 2: Run integration test**

Run: `uv run pytest tests/test_integration.py::TestAIDodoWorkflow -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `uv run pytest`
Expected: All 140+ tests pass

**Step 4: Final commit**

```bash
git add tests/test_integration.py
git commit -m "test: add AI dodo workflow integration test"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add `dodo new` command | cli.py, test_cli.py |
| 2 | Add `dodo destroy` command | cli.py, test_cli.py |
| 3 | Add `--dodo` flag to commands | cli.py, test_cli.py |
| 4 | Update core resolution logic | core.py, storage.py, test_core.py |
| 5 | Remove `local_storage` config | config.py, storage.py, project_config.py |
| 6 | Deprecate `dodo init` | cli.py, test_cli.py |
| 7 | Rename "project" → "dodo" in UI | cli.py, interactive.py |
| 8 | Update interactive menu | interactive.py |
| 9 | Integration test | test_integration.py |
