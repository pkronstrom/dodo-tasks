# Plugin System v2 Design

**Date:** 2026-01-10
**Status:** Draft

## Overview

Improvements to the plugin system focusing on UX consistency, plugin metadata, migration tooling, and graph plugin completion.

## 1. Plugin Manifest

Each plugin gets a `plugin.json` alongside `__init__.py`:

```json
{
  "name": "sqlite",
  "version": "1.0.0",
  "description": "Store todos in a SQLite database file"
}
```

### Scan Behavior

During `dodo plugins scan`:
1. Read `plugin.json` (name, version, description)
2. Parse `__init__.py` for hooks (existing behavior)
3. Write combined info to `plugin_registry.json`

Registry entry format:
```json
{
  "sqlite": {
    "name": "sqlite",
    "version": "1.0.0",
    "description": "Store todos in a SQLite database file",
    "builtin": true,
    "hooks": ["register_adapter"]
  }
}
```

### Auto-scan

If `plugin_registry.json` doesn't exist, run scan automatically on first use.

```python
def _load_registry(config_dir: Path) -> dict:
    path = config_dir / "plugin_registry.json"
    if not path.exists():
        from dodo.cli_plugins import _scan_and_save
        _scan_and_save()
    return json.loads(path.read_text())
```

## 2. Unified Settings UI

Merge general settings and plugins into a single settings menu.

### Layout

```
Settings

  ✓ Worktree sharing: Use same todos file across all git worktrees
  ○ Local storage: Store todos in project dir (vs ~/.config/dodo)
  ✓ Timestamps: Add created/updated timestamps
  Adapter: markdown                              (only enabled shown)
  ↳ Migrate from sqlite                          (available)
  Default format: table                          (only enabled shown)
  Editor: vim

  ── Plugins ──────────────────────────

  ○ sqlite 1.0.0 - Store todos in a SQLite database file
  ○ obsidian 1.0.0 - Sync todos with Obsidian via REST API
      obsidian_api_key: (not set)
      obsidian_vault_path: dodo/todos.md
  ○ graph 1.0.0 - Track dependencies between todos
  ✓ ntfy-inbox 1.0.0 - Add todos by sending push notifications
      ntfy_topic: (not set)
      ntfy_server: https://ntfy.sh
```

### Key Bindings

- ↑↓ or j/k: navigate
- space: toggle/cycle
- enter or e: open editor (for edit items)
- q or Ctrl+C: exit

### Color Scheme

| Element | Color |
|---------|-------|
| Toggle icon enabled | green ✓ |
| Toggle icon disabled | dim ○ |
| Labels | white (dim if parent plugin disabled) |
| Values (set) | yellow |
| Values (default) | dim |
| Values (not set, required) | red |
| Descriptions | dim |
| Section header | dim |

### Section Header

Non-selectable, skipped during navigation:
```
  ── Plugins ──────────────────────────
```

## 3. Dynamic Adapter/Format Cycles

### Building Options

```python
def _get_available_adapters(enabled_plugins: set[str], registry: dict) -> list[str]:
    adapters = ["markdown"]  # Always available
    for name, info in registry.items():
        if name in enabled_plugins and "register_adapter" in info.get("hooks", []):
            adapters.append(name)
    return adapters

def _get_available_formats(enabled_plugins: set[str], registry: dict) -> list[str]:
    formats = ["table", "jsonl", "tsv"]  # Built-in
    for name, info in registry.items():
        if name in enabled_plugins and "register_formatter" in info.get("hooks", []):
            # Add plugin-provided formats
            formats.extend(info.get("formats", []))
    return formats
```

### Fallback on Plugin Disable

When user disables an adapter plugin that's currently selected:
1. Auto-switch `default_adapter` to `"markdown"`
2. Show inline notice: `[dim]Adapter switched to markdown[/dim]`

## 4. Storage per Adapter

Each adapter type has its own storage file:

```
~/.config/dodo/todos.md          # markdown
~/.config/dodo/todos.db          # sqlite (graph uses same file)

# Per-project:
~/.config/dodo/projects/myproj.md
~/.config/dodo/projects/myproj.db
```

### Behavior

- Switching adapter = switching which file is active
- Old files preserved, data coexists
- Both can have different content
- No automatic migration

## 5. Migration System

### Adapter Interface

Each adapter implements:
```python
class Adapter:
    def export_all(self) -> list[TodoItem]:
        """Export all todos for migration."""

    def import_all(self, items: list[TodoItem]) -> tuple[int, int]:
        """Import todos. Returns (imported, skipped)."""
```

### Settings UI Integration

"Migrate from X" rows shown below adapter toggle:
```
  Adapter: sqlite
  ↳ Migrate from markdown      (available)
  ↳ Migrate from obsidian      (available)
```

- Only shown if other adapter files exist
- File existence cached (fast), count on demand (when selected)
- Disappears if source has no todos

### Migration Flow

**No data loss:**
```
Scanning markdown... found 12 todos.
Migrate to sqlite? [y/n]
```

**With data loss** (e.g., dependencies lost):
```
Found 8 todos with 3 dependencies in sqlite.
Warning: Markdown adapter does not support dependencies.

  1. Export to jsonl, then migrate (recommended)
  2. Migrate without dependencies
  3. Cancel

Choice [1/2/3]:
```

### Duplicate Detection

ID-based deduplication - migration is idempotent:
```python
def import_all(self, items: list[TodoItem]) -> tuple[int, int]:
    imported, skipped = 0, 0
    for item in items:
        if self.get(item.id):  # Already exists
            skipped += 1
        else:
            self._insert(item)  # Preserve original ID
            imported += 1
    return imported, skipped
```

Output:
```
Migrated 10 todos from markdown.
Skipped 2 (already exist).
```

### Post-Migration

Old file preserved (not deleted). User can manually delete if desired.

## 6. New Commands

### dodo export

Export todos to jsonl:
```bash
dodo export                  # Current project (auto-detect)
dodo export -g               # Global todos
dodo export -p myproj        # Specific project
dodo export -o backup.jsonl  # Custom output file
```

### dodo migrate

Run migration between adapters:
```bash
dodo migrate                 # Migrate current project
dodo migrate -g              # Migrate global
dodo migrate -p myproj       # Migrate specific project
```

### dodo info

Show current state:
```bash
$ dodo info

Project: myproj (detected from git)
Adapter: sqlite
Storage: ~/.config/dodo/projects/myproj.db
Todos: 12 (8 pending, 4 done)
Dependencies: 3
Plugins: sqlite, graph, ntfy-inbox
```

```bash
$ dodo info -g

Project: global
Adapter: markdown
Storage: ~/.config/dodo/todos.md
Todos: 5 (3 pending, 2 done)
```

## 7. Graph Plugin Enhancements

### blocked_by Display

`GraphWrapper.list()` attaches dynamic attribute:
```python
def list(self, project=None, status=None):
    items = self._adapter.list(project, status)
    for item in items:
        item.blocked_by = self.get_blockers(item.id)
    return items
```

`GraphFormatter.format()` adds column when data present:
```python
def format(self, items):
    if any(getattr(item, 'blocked_by', None) for item in items):
        # Add "Blocked by" column to table output
        ...
    return self._formatter.format(items)
```

### Tree Formatter

New format registered via `register_formatter` hook:

```bash
$ dodo list --format tree

○ Setup database
  └── ○ Write migration scripts
      └── ○ Test migrations
○ Design API
○ Review docs
```

- Root items: todos with no blockers
- Nested: todos blocked by parent
- Items without dependencies shown at root level
- All todos shown (not just those with dependencies)

## 8. New Hooks

### register_formatter

Plugins can register output formats:
```python
def register_formatter(registry: dict, config: Config) -> None:
    from mymodule.tree import TreeFormatter
    registry["tree"] = TreeFormatter
```

## 9. Files to Modify

| File | Changes |
|------|---------|
| `src/dodo/plugins/**/plugin.json` | New manifest files |
| `src/dodo/cli_plugins.py` | Read manifest, auto-scan |
| `src/dodo/plugins/__init__.py` | Auto-scan in `_load_registry()` |
| `src/dodo/ui/interactive.py` | Unified settings UI |
| `src/dodo/cli.py` | Add export, migrate, info commands |
| `src/dodo/core.py` | Add export_all, import_all to adapters |
| `src/dodo/adapters/markdown.py` | Implement migration interface |
| `src/dodo/plugins/sqlite/adapter.py` | Implement migration interface |
| `src/dodo/plugins/obsidian/adapter.py` | Implement migration interface |
| `src/dodo/plugins/graph/wrapper.py` | Attach blocked_by in list() |
| `src/dodo/plugins/graph/formatter.py` | Add blocked_by column |
| `src/dodo/plugins/graph/tree.py` | New tree formatter |
| `src/dodo/plugins/graph/__init__.py` | Add register_formatter hook |

## 10. Performance Principles

### Lazy Loading

- Plugin modules only imported when their hooks are actually called
- Adapter classes loaded via string refs, resolved at first use
- No module imports at CLI startup unless needed for the command

### Caching

- `plugin_registry.json` - plugin metadata cached, no filesystem scan on every run
- `_config_cache` / `_plugin_cache` - module-level caches for singleton patterns
- Storage file existence cached in registry (updated on adapter change)

### Fast Paths

| Command | What loads |
|---------|-----------|
| `dodo add "task"` | Config, adapter only |
| `dodo list` | Config, adapter, formatter |
| `dodo` (interactive) | Deferred - loads on menu selection |
| `dodo plugins list` | Registry JSON only (no plugin imports) |
| `dodo info` | Config, counts from adapter |

### Avoid

- Scanning filesystem on every command
- Importing all plugins at startup
- Counting todos just to show settings menu
- Network calls unless command requires them (obsidian)

## 11. Testing

- Test dynamic adapter/format list building
- Test fallback on plugin disable
- Test migration with ID deduplication
- Test migration with data loss warning
- Test tree formatter output
- Test auto-scan behavior
- Test dodo info output
- Test export/migrate commands with -g/-p flags
