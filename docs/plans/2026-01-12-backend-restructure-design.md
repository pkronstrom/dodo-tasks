# Backend Restructure Design

## Overview

Restructure dodo to make SQLite the core default backend, add per-project backend configuration, and clean up CLI argument parsing.

## Storage Architecture

### SQLite becomes core default

- Move `plugins/sqlite/adapter.py` → `backends/sqlite.py`
- Delete `plugins/sqlite/` entirely
- Change `Config.DEFAULTS["default_backend"]` to `"sqlite"`

### Per-project backend metadata

**When `local_storage=false` (centralized):**
```
~/.config/dodo/projects/<project_id>/
├── dodo.json          # {"backend": "sqlite"}
└── dodo.db
```

**When `local_storage=true` (in project root):**
```
myproject/
├── .dodo/
│   ├── dodo.json      # {"backend": "sqlite"}
│   └── dodo.db
└── dodo.md            # only if markdown backend (visible in root)
```

### Resolution order

1. Project `dodo.json` (if exists)
2. Auto-detect from existing files (`dodo.db` → sqlite, `dodo.md` → markdown)
3. Global `default_backend` setting

### New projects

First `dodo add` inherits global default, writes `dodo.json` automatically.

## CLI Changes

### Argument parsing (hard switch)

```bash
# Old (remove)
dodo add my task without quotes

# New (required)
dodo add "my task in quotes"
dodo add "task" --some-future-flag
```

Single positional argument for text, enables flags after.

### New `dodo backend` command

```bash
dodo backend                              # show current project's backend
dodo backend sqlite                       # set backend (new project or no data)
dodo backend markdown --migrate           # switch + migrate (auto-detect source)
dodo backend markdown --migrate-from sqlite  # explicit source
```

When switching with existing data and no `--migrate`:
```
Project has 38 todos in sqlite. Use --migrate to copy to markdown.
```

### Settings menu additions

```
Settings
────────────────────────────────
Global:
  ● Default backend: sqlite
  ○ Local storage: false
  ...

This Project (dodo_d1204e):
  ● Backend: sqlite
  ○ Location: ~/.config/dodo/projects/dodo_d1204e/
  → Switch backend...
```

"Switch backend" opens submenu with backend choices, triggers migration flow.

## Code Structure Changes

### Directory rename

```
src/dodo/adapters/       →  src/dodo/backends/
  base.py                →    base.py (TodoAdapter → TodoBackend)
  markdown.py            →    markdown.py
  sqlite.py              ←    moved from plugins/sqlite/adapter.py
  __init__.py
```

### Delete

```
src/dodo/plugins/sqlite/     # entire directory
```

### Config changes

```python
# config.py
DEFAULTS = {
    "default_backend": "sqlite",  # was "default_adapter": "markdown"
    ...
}
```

### Core changes

```python
# core.py
class TodoService:
    def _create_backend(self) -> TodoBackend:
        # 1. Check project dodo.json for backend
        # 2. Auto-detect from files
        # 3. Fall back to config.default_backend
```

### New files

```
src/dodo/project_config.py   # load/save per-project dodo.json
```

### CLI changes

```python
# cli.py
@click.command()
@click.argument("text")  # single quoted arg, not *args
def add(text): ...

@click.group()
def backend(): ...
```

## Plugin & Test Updates

### Obsidian plugin

```
src/dodo/plugins/obsidian/
  adapter.py  →  backend.py
  __init__.py  # register_backend instead of register_adapter
```

### Plugin hook rename

```python
# Before
def register_adapter(registry, config): ...
def extend_adapter(adapter, config): ...

# After
def register_backend(registry, config): ...
def extend_backend(backend, config): ...
```

### Graph plugin

- Update adapter references to backend

### Tests

```
tests/test_adapters/  →  tests/test_backends/
```

### Global rename

- `adapter` → `backend` in all `.py` files
- `Adapter` → `Backend` in class names
- `_adapter` → `_backend` in variable names

## Behavior

### dodo.json creation

- Created automatically on first `dodo add` if doesn't exist
- Contains `{"backend": "<inherited-from-global-default>"}`

### Edge cases

| Situation | Behavior |
|-----------|----------|
| Both `dodo.db` and `dodo.md` exist, no `dodo.json` | Use global default, warn about orphaned file |
| Obsidian project (no local files) | Requires `dodo.json` or `dodo backend obsidian` |

## Breaking Changes

- `dodo add foo bar baz` → `dodo add "foo bar baz"`
- Config key: `default_adapter` → `default_backend`
- `plugins/sqlite/` deleted
