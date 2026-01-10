# Plugin System v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve plugin UX with unified settings, manifests, migration tooling, and graph enhancements.

**Architecture:** Plugin metadata in JSON manifests cached in registry. Unified settings UI merges general config with plugins. Each adapter has separate storage file. Migration is explicit and idempotent.

**Tech Stack:** Python, Typer CLI, Rich TUI, SQLite, JSON

---

## Phase 1: Plugin Manifests

### Task 1.1: Create plugin.json for sqlite plugin

**Files:**
- Create: `src/dodo/plugins/sqlite/plugin.json`

**Step 1: Create manifest file**

```json
{
  "name": "sqlite",
  "version": "1.0.0",
  "description": "Store todos in a SQLite database file"
}
```

**Step 2: Commit**

```bash
git add src/dodo/plugins/sqlite/plugin.json
git commit -m "feat(sqlite): add plugin manifest"
```

### Task 1.2: Create plugin.json for obsidian plugin

**Files:**
- Create: `src/dodo/plugins/obsidian/plugin.json`

**Step 1: Create manifest file**

```json
{
  "name": "obsidian",
  "version": "1.0.0",
  "description": "Sync todos with Obsidian via REST API"
}
```

**Step 2: Commit**

```bash
git add src/dodo/plugins/obsidian/plugin.json
git commit -m "feat(obsidian): add plugin manifest"
```

### Task 1.3: Create plugin.json for graph plugin

**Files:**
- Create: `src/dodo/plugins/graph/plugin.json`

**Step 1: Create manifest file**

```json
{
  "name": "graph",
  "version": "1.0.0",
  "description": "Track dependencies between todos"
}
```

**Step 2: Commit**

```bash
git add src/dodo/plugins/graph/plugin.json
git commit -m "feat(graph): add plugin manifest"
```

### Task 1.4: Create plugin.json for ntfy-inbox plugin

**Files:**
- Create: `src/dodo/plugins/ntfy_inbox/plugin.json`

**Step 1: Create manifest file**

```json
{
  "name": "ntfy-inbox",
  "version": "1.0.0",
  "description": "Add todos by sending push notifications"
}
```

**Step 2: Commit**

```bash
git add src/dodo/plugins/ntfy_inbox/plugin.json
git commit -m "feat(ntfy-inbox): add plugin manifest"
```

### Task 1.5: Update cli_plugins.py to read manifests

**Files:**
- Modify: `src/dodo/cli_plugins.py`
- Test: `tests/test_cli_plugins.py`

**Step 1: Write failing test**

```python
# tests/test_cli_plugins.py
import json
import tempfile
from pathlib import Path

def test_scan_reads_plugin_manifest(tmp_path, monkeypatch):
    """Scan should read plugin.json for name, version, description."""
    from dodo import cli_plugins
    from dodo.config import clear_config_cache
    from dodo.plugins import clear_plugin_cache

    clear_config_cache()
    clear_plugin_cache()

    # Create a test plugin with manifest
    plugin_dir = tmp_path / "plugins" / "test_plugin"
    plugin_dir.mkdir(parents=True)

    (plugin_dir / "plugin.json").write_text(json.dumps({
        "name": "test-plugin",
        "version": "2.0.0",
        "description": "A test plugin"
    }))

    (plugin_dir / "__init__.py").write_text('''
def register_commands(app, config):
    pass
''')

    # Scan the directory
    result = cli_plugins._scan_plugin_dir(plugin_dir.parent, builtin=False)

    assert "test-plugin" in result
    assert result["test-plugin"]["version"] == "2.0.0"
    assert result["test-plugin"]["description"] == "A test plugin"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli_plugins.py::test_scan_reads_plugin_manifest -v
```

Expected: FAIL (version/description not in result)

**Step 3: Update _scan_plugin_dir to read manifest**

In `src/dodo/cli_plugins.py`, update `_scan_plugin_dir`:

```python
def _scan_plugin_dir(plugins_dir: Path, builtin: bool) -> dict[str, dict]:
    """Scan a directory for Python module plugins."""
    plugins = {}

    if not plugins_dir.exists():
        return plugins

    for entry in plugins_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith((".", "_")):
            continue
        if entry.name == "__pycache__":
            continue

        init_file = entry / "__init__.py"
        if not init_file.exists():
            continue

        # Read manifest if exists
        manifest_file = entry / "plugin.json"
        if manifest_file.exists():
            manifest = json.loads(manifest_file.read_text())
            name = manifest.get("name", entry.name)
            version = manifest.get("version", "0.0.0")
            description = manifest.get("description", "")
        else:
            # Fallback to parsing __init__.py for name
            name = entry.name
            version = "0.0.0"
            description = ""
            content = init_file.read_text()
            for line in content.splitlines():
                if line.strip().startswith("name ="):
                    try:
                        name = line.split("=", 1)[1].strip().strip("'\"")
                    except IndexError:
                        pass
                    break

        hooks = _detect_hooks(entry)
        if not hooks:
            continue  # Skip plugins with no hooks

        plugin_info: dict = {
            "builtin": builtin,
            "hooks": hooks,
            "version": version,
            "description": description,
        }
        if not builtin:
            plugin_info["path"] = str(entry)

        plugins[name] = plugin_info

    return plugins
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli_plugins.py::test_scan_reads_plugin_manifest -v
```

Expected: PASS

**Step 5: Run all tests**

```bash
uv run pytest tests/ -q
```

Expected: All pass

**Step 6: Commit**

```bash
git add src/dodo/cli_plugins.py tests/test_cli_plugins.py
git commit -m "feat: read plugin manifest during scan"
```

### Task 1.6: Add auto-scan if registry missing

**Files:**
- Modify: `src/dodo/plugins/__init__.py`

**Step 1: Write failing test**

```python
# In tests/test_cli_plugins.py
def test_auto_scan_when_registry_missing(tmp_path, monkeypatch):
    """Registry should be auto-created on first load if missing."""
    from dodo.config import Config, clear_config_cache
    from dodo.plugins import clear_plugin_cache, _load_registry

    clear_config_cache()
    clear_plugin_cache()

    # Use temp config dir with no registry
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Load registry - should trigger auto-scan
    registry = _load_registry(config_dir)

    # Should return empty dict (no plugins in temp dir) but not crash
    assert isinstance(registry, dict)
```

**Step 2: Run test**

```bash
uv run pytest tests/test_cli_plugins.py::test_auto_scan_when_registry_missing -v
```

**Step 3: Update _load_registry for auto-scan**

In `src/dodo/plugins/__init__.py`:

```python
def _load_registry(config_dir: Path) -> dict:
    """Load registry from file, with caching. Auto-scan if missing."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    path = config_dir / "plugin_registry.json"
    if path.exists():
        _registry_cache = json.loads(path.read_text())
    else:
        # Auto-scan on first run
        from dodo.cli_plugins import _scan_and_save_to
        _registry_cache = _scan_and_save_to(config_dir)

    return _registry_cache
```

Also add helper in `src/dodo/cli_plugins.py`:

```python
def _scan_and_save_to(config_dir: Path) -> dict:
    """Scan plugins and save registry to specified config dir."""
    registry: dict = {}

    # Scan built-in plugins
    builtin_plugins = _scan_plugin_dir(BUILTIN_PLUGINS_DIR, builtin=True)
    registry.update(builtin_plugins)

    # Scan user plugins
    user_plugins_dir = config_dir / "plugins"
    user_plugins = _scan_plugin_dir(user_plugins_dir, builtin=False)
    registry.update(user_plugins)

    # Save
    config_dir.mkdir(parents=True, exist_ok=True)
    registry_path = config_dir / "plugin_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2))

    return registry
```

**Step 4: Run tests**

```bash
uv run pytest tests/ -q
```

**Step 5: Commit**

```bash
git add src/dodo/plugins/__init__.py src/dodo/cli_plugins.py tests/test_cli_plugins.py
git commit -m "feat: auto-scan plugins if registry missing"
```

---

## Phase 2: Unified Settings UI

### Task 2.1: Create combined settings items list

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Create helper to build combined items**

```python
def _build_settings_items(cfg: Config) -> tuple[list, dict]:
    """Build combined settings items list with plugins."""
    from dodo.plugins import get_all_plugins

    items = []
    pending = {}

    # General settings
    general = [
        ("worktree_shared", "Worktree sharing", "toggle", None,
         "Use same todos file across all git worktrees"),
        ("local_storage", "Local storage", "toggle", None,
         "Store todos in project dir (vs ~/.config/dodo)"),
        ("timestamps_enabled", "Timestamps", "toggle", None,
         "Add created/updated timestamps"),
        ("default_adapter", "Adapter", "cycle", None, None),  # Options built dynamically
        ("default_format", "Default format", "cycle", None, None),
        ("editor", "Editor", "edit", None, None),
    ]

    for key, label, kind, options, desc in general:
        items.append((key, label, kind, options, None, desc))
        pending[key] = getattr(cfg, key)

    # Divider
    items.append(("_divider", "── Plugins ──", "divider", None, None, None))

    # Plugins
    plugins = get_all_plugins()
    for plugin in plugins:
        toggle_key = f"_plugin_{plugin.name}"
        desc = f"{plugin.version} - {plugin.description}" if plugin.description else plugin.version
        items.append((toggle_key, plugin.name, "toggle", None, plugin.name, desc))
        pending[toggle_key] = plugin.enabled

        # Plugin config vars
        for env in plugin.envs:
            items.append((env.name, f"  {env.name}", "edit", None, None, None))
            pending[env.name] = getattr(cfg, env.name, env.default) or ""

    return items, pending
```

**Step 2: Update interactive_config to use combined view**

Replace `_general_config` and `_plugins_config` references with unified `_settings_loop`.

**Step 3: Run tests**

```bash
uv run pytest tests/ -q
```

**Step 4: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "feat: unified settings UI with plugins"
```

### Task 2.2: Implement settings loop with divider support

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Update render function for new item types**

Add handling for "divider" kind that skips during navigation and renders as section header.

**Step 2: Add color scheme**

- Toggle enabled: green checkmark
- Toggle disabled: dim circle
- Labels: white (dim if parent plugin disabled)
- Values set: yellow
- Values default: dim
- Values not set: red
- Descriptions: dim

**Step 3: Test manually**

```bash
uv run dodo
# Navigate to settings, verify layout
```

**Step 4: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "feat: settings UI with divider and colors"
```

### Task 2.3: Dynamic adapter cycle options

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Create helper for available adapters**

```python
def _get_available_adapters(enabled_plugins: set[str], registry: dict) -> list[str]:
    """Get adapters: markdown + enabled adapter plugins."""
    adapters = ["markdown"]
    for name, info in registry.items():
        if name in enabled_plugins and "register_adapter" in info.get("hooks", []):
            adapters.append(name)
    return adapters
```

**Step 2: Build adapter options dynamically in settings**

When rendering adapter cycle, use `_get_available_adapters()`.

**Step 3: Add info text**

Show `[dim](only enabled shown)[/dim]` next to adapter row.

**Step 4: Test manually**

Enable sqlite plugin, verify it appears in adapter cycle.

**Step 5: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "feat: dynamic adapter cycle based on enabled plugins"
```

### Task 2.4: Fallback on adapter plugin disable

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Add fallback logic**

When saving plugin toggle to disabled:
- Check if it's an adapter plugin
- Check if it's the currently selected adapter
- If so, switch to markdown and show notice

```python
def save_plugin_toggle(plugin_name: str, enabled: bool) -> None:
    current = cfg.enabled_plugins
    if enabled:
        current.add(plugin_name)
    else:
        current.discard(plugin_name)
        # Fallback if this was the active adapter
        if cfg.default_adapter == plugin_name:
            cfg.set("default_adapter", "markdown")
            # Show notice (set status message)
    cfg.set("enabled_plugins", ",".join(sorted(current)))
```

**Step 2: Test manually**

1. Enable sqlite, set as adapter
2. Disable sqlite
3. Verify adapter switches to markdown with notice

**Step 3: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "feat: fallback to markdown when adapter plugin disabled"
```

---

## Phase 3: Graph Plugin Enhancements

### Task 3.1: Attach blocked_by in GraphWrapper.list()

**Files:**
- Modify: `src/dodo/plugins/graph/wrapper.py`
- Test: `tests/test_graph_plugin.py`

**Step 1: Write failing test**

```python
# tests/test_graph_plugin.py
import tempfile
from pathlib import Path

def test_list_attaches_blocked_by(tmp_path):
    """GraphWrapper.list() should attach blocked_by to items."""
    from dodo.plugins.sqlite.adapter import SqliteAdapter
    from dodo.plugins.graph.wrapper import GraphWrapper

    db_path = tmp_path / "test.db"
    adapter = SqliteAdapter(db_path)
    wrapper = GraphWrapper(adapter)

    # Add todos
    t1 = wrapper.add("Task 1")
    t2 = wrapper.add("Task 2")

    # Add dependency: t1 blocks t2
    wrapper.add_dependency(t1.id, t2.id)

    # List todos
    items = wrapper.list()

    # Find t2 and check blocked_by
    t2_item = next(i for i in items if i.id == t2.id)
    assert hasattr(t2_item, 'blocked_by')
    assert t1.id in t2_item.blocked_by
```

**Step 2: Run test**

```bash
uv run pytest tests/test_graph_plugin.py::test_list_attaches_blocked_by -v
```

Expected: FAIL

**Step 3: Update wrapper.list()**

```python
def list(
    self,
    project: str | None = None,
    status: Status | None = None,
) -> list[TodoItem]:
    items = self._adapter.list(project, status)
    # Attach blocked_by as dynamic attribute
    for item in items:
        item.blocked_by = self.get_blockers(item.id)
    return items
```

**Step 4: Run test**

```bash
uv run pytest tests/test_graph_plugin.py::test_list_attaches_blocked_by -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/plugins/graph/wrapper.py tests/test_graph_plugin.py
git commit -m "feat(graph): attach blocked_by in list()"
```

### Task 3.2: Update GraphFormatter to show blocked_by column

**Files:**
- Modify: `src/dodo/plugins/graph/formatter.py`

**Step 1: Write failing test**

```python
def test_formatter_shows_blocked_by_column():
    """GraphFormatter should add blocked_by column when items have it."""
    from dodo.formatters import TableFormatter
    from dodo.plugins.graph.formatter import GraphFormatter
    from dodo.models import TodoItem, Status

    base = TableFormatter()
    formatter = GraphFormatter(base)

    # Create items with blocked_by
    item1 = TodoItem(id="abc", text="Task 1", status=Status.PENDING)
    item2 = TodoItem(id="def", text="Task 2", status=Status.PENDING)
    item2.blocked_by = ["abc"]

    output = formatter.format([item1, item2])

    assert "Blocked by" in output or "blocked" in output.lower()
    assert "abc" in output
```

**Step 2: Implement formatter**

```python
class GraphFormatter:
    """Wraps a formatter to add blocked_by info to output."""

    def __init__(self, formatter):
        self._formatter = formatter

    def format(self, items: list[TodoItem]) -> str:
        # Check if any item has blocked_by
        has_deps = any(getattr(item, 'blocked_by', None) for item in items)

        if not has_deps:
            return self._formatter.format(items)

        # Build table with blocked_by column
        from rich.console import Console
        from rich.table import Table
        from io import StringIO

        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Status", width=8)
        table.add_column("Todo")
        table.add_column("Blocked by", style="yellow")

        for item in items:
            status_icon = "○" if item.status.value == "pending" else "✓"
            blocked = getattr(item, 'blocked_by', [])
            blocked_str = ", ".join(blocked[:3])
            if len(blocked) > 3:
                blocked_str += f" (+{len(blocked) - 3})"
            table.add_row(item.id[:8], status_icon, item.text, blocked_str)

        console = Console(file=StringIO(), force_terminal=True)
        console.print(table)
        return console.file.getvalue()
```

**Step 3: Run tests**

```bash
uv run pytest tests/test_graph_plugin.py -v
```

**Step 4: Commit**

```bash
git add src/dodo/plugins/graph/formatter.py tests/test_graph_plugin.py
git commit -m "feat(graph): show blocked_by column in formatter"
```

### Task 3.3: Add tree formatter

**Files:**
- Create: `src/dodo/plugins/graph/tree.py`
- Modify: `src/dodo/plugins/graph/__init__.py`

**Step 1: Write failing test**

```python
def test_tree_formatter_output():
    """Tree formatter should show dependency hierarchy."""
    from dodo.plugins.graph.tree import TreeFormatter
    from dodo.models import TodoItem, Status

    formatter = TreeFormatter()

    # Create hierarchy: t1 -> t2 -> t3
    t1 = TodoItem(id="aaa", text="Setup", status=Status.PENDING)
    t2 = TodoItem(id="bbb", text="Build", status=Status.PENDING)
    t3 = TodoItem(id="ccc", text="Test", status=Status.PENDING)
    t4 = TodoItem(id="ddd", text="Standalone", status=Status.PENDING)

    t1.blocked_by = []
    t2.blocked_by = ["aaa"]
    t3.blocked_by = ["bbb"]
    t4.blocked_by = []

    output = formatter.format([t1, t2, t3, t4])

    # Should show tree structure
    assert "Setup" in output
    assert "Build" in output
    assert "└──" in output or "├──" in output
```

**Step 2: Implement TreeFormatter**

```python
# src/dodo/plugins/graph/tree.py
"""Tree formatter for dependency visualization."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.models import TodoItem


class TreeFormatter:
    """Format todos as dependency tree."""

    def format(self, items: list[TodoItem]) -> str:
        # Build lookup
        by_id = {item.id: item for item in items}

        # Find roots (no blockers or blockers not in list)
        roots = []
        for item in items:
            blockers = getattr(item, 'blocked_by', [])
            if not blockers or not any(b in by_id for b in blockers):
                roots.append(item)

        # Build children map
        children: dict[str, list] = {item.id: [] for item in items}
        for item in items:
            for blocker_id in getattr(item, 'blocked_by', []):
                if blocker_id in children:
                    children[blocker_id].append(item)

        # Render tree
        lines = []
        rendered = set()

        def render(item: TodoItem, prefix: str = "", is_last: bool = True):
            if item.id in rendered:
                return
            rendered.add(item.id)

            icon = "○" if item.status.value == "pending" else "✓"
            lines.append(f"{prefix}{icon} {item.text}")

            kids = children.get(item.id, [])
            for i, child in enumerate(kids):
                is_child_last = (i == len(kids) - 1)
                child_prefix = prefix + ("    " if is_last else "│   ")
                connector = "└── " if is_child_last else "├── "
                lines.append(f"{child_prefix}{connector}", end="")
                render(child, child_prefix + "    ", is_child_last)

        for i, root in enumerate(roots):
            render(root)

        return "\n".join(lines)
```

**Step 3: Register formatter in __init__.py**

Add `register_formatter` hook.

**Step 4: Run tests**

```bash
uv run pytest tests/test_graph_plugin.py -v
```

**Step 5: Commit**

```bash
git add src/dodo/plugins/graph/tree.py src/dodo/plugins/graph/__init__.py tests/test_graph_plugin.py
git commit -m "feat(graph): add tree formatter for dependencies"
```

---

## Phase 4: Storage and Migration

### Task 4.1: Implement adapter export_all/import_all interface

**Files:**
- Modify: `src/dodo/adapters/markdown.py`
- Modify: `src/dodo/plugins/sqlite/adapter.py`
- Modify: `src/dodo/plugins/obsidian/adapter.py`

**Step 1: Add to markdown adapter**

```python
def export_all(self) -> list[TodoItem]:
    """Export all todos for migration."""
    return self.list()

def import_all(self, items: list[TodoItem]) -> tuple[int, int]:
    """Import todos. Returns (imported, skipped)."""
    imported, skipped = 0, 0
    for item in items:
        if self.get(item.id):
            skipped += 1
        else:
            # Insert with original ID
            self._todos[item.id] = item
            self._save()
            imported += 1
    return imported, skipped
```

**Step 2: Add to sqlite adapter**

Similar implementation.

**Step 3: Add to obsidian adapter**

Similar implementation.

**Step 4: Write test**

```python
def test_migration_interface():
    """Adapters should support export_all and import_all."""
    # Test with markdown adapter
    ...
```

**Step 5: Commit**

```bash
git add src/dodo/adapters/markdown.py src/dodo/plugins/sqlite/adapter.py src/dodo/plugins/obsidian/adapter.py
git commit -m "feat: add migration interface to adapters"
```

### Task 4.2: Add dodo export command

**Files:**
- Modify: `src/dodo/cli.py`

**Step 1: Add command**

```python
@app.command()
def export(
    output: Annotated[str | None, typer.Option("-o", help="Output file")] = None,
    project: Annotated[str | None, typer.Option("-p", help="Project name")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Global todos")] = False,
):
    """Export todos to jsonl."""
    ...
```

**Step 2: Test**

```bash
uv run dodo export -o test.jsonl
cat test.jsonl
```

**Step 3: Commit**

```bash
git add src/dodo/cli.py
git commit -m "feat: add dodo export command"
```

### Task 4.3: Add dodo info command

**Files:**
- Modify: `src/dodo/cli.py`

**Step 1: Add command**

```python
@app.command()
def info(
    project: Annotated[str | None, typer.Option("-p", help="Project name")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Global todos")] = False,
):
    """Show current storage info."""
    ...
```

**Step 2: Test**

```bash
uv run dodo info
uv run dodo info -g
```

**Step 3: Commit**

```bash
git add src/dodo/cli.py
git commit -m "feat: add dodo info command"
```

### Task 4.4: Add migrate row to settings UI

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Detect other adapter files**

Check for `todos.md`, `todos.db` etc.

**Step 2: Add migrate row below adapter**

Only show if other files exist.

**Step 3: Implement migration flow on select**

Count todos, prompt, run import_all.

**Step 4: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "feat: add migrate option to settings UI"
```

---

## Phase 5: Final Polish

### Task 5.1: Remove old name= from plugin __init__.py files

**Files:**
- Modify: `src/dodo/plugins/sqlite/__init__.py`
- Modify: `src/dodo/plugins/obsidian/__init__.py`
- Modify: `src/dodo/plugins/graph/__init__.py`
- Modify: `src/dodo/plugins/ntfy_inbox/__init__.py`

Remove `name = "..."` lines since name comes from manifest now.

**Step 1: Remove name declarations**

**Step 2: Run tests**

```bash
uv run pytest tests/ -q
```

**Step 3: Commit**

```bash
git add src/dodo/plugins/
git commit -m "refactor: use manifest for plugin names"
```

### Task 5.2: Update plugin loader to use manifest name

**Files:**
- Modify: `src/dodo/plugins/__init__.py`

Ensure plugin loading uses registry name, not module attribute.

**Step 1: Verify and update if needed**

**Step 2: Run all tests**

```bash
uv run pytest tests/ -q
```

**Step 3: Commit**

```bash
git add src/dodo/plugins/__init__.py
git commit -m "refactor: plugin loader uses manifest names"
```

### Task 5.3: Run full test suite and manual verification

**Step 1: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 2: Manual testing**

```bash
uv run dodo plugins scan
uv run dodo plugins list
uv run dodo  # Interactive menu
uv run dodo info
uv run dodo export -o backup.jsonl
```

**Step 3: Final commit if any fixes**

---

## Completion

After all tasks complete:
1. Merge to master
2. Clean up worktree
3. Update CHANGELOG if exists

```bash
cd /Users/pkronstrom/Projects/own/dodo
git merge feature/plugin-v2 --no-ff -m "Merge feature/plugin-v2: unified settings, manifests, migration"
git worktree remove .worktrees/plugin-v2
git branch -d feature/plugin-v2
```
