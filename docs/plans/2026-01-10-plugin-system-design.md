# Dodo Plugin System Design

## Core Principles

1. **Zero overhead when unused** - Core commands (`add`, `list`, `done`) pay no cost if plugins disabled
2. **Lazy loading** - Plugin code imported only when enabled AND hook invoked
3. **Separation** - Plugins extend, they don't modify core. Core calls hooks, plugins respond.
4. **Explicit registration** - No runtime scanning. Plugins registered once via command.
5. **Pythonic** - Protocols, duck typing, simple module interface
6. **Minimal core** - Core ships with only `markdown` adapter (zero deps). Everything else is plugins.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Core                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │ cli.py  │  │ core.py │  │adapters │  │  formatters     │ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬────────┘ │
│       │            │            │                │          │
│       └────────────┴─────┬──────┴────────────────┘          │
│                          │                                  │
│                   apply_hooks()                             │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │   Plugin Registry       │
              │   (plugin_registry.json)│
              └────────────┬────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────┴────┐       ┌─────┴─────┐      ┌─────┴─────┐
   │  graph  │       │ ntfy-inbox│      │  custom   │
   │ plugin  │       │  plugin   │      │  plugin   │
   └─────────┘       └───────────┘      └───────────┘
```

---

## Plugin Locations

**Built-in plugins** ship with dodo:
```
src/dodo/plugins/
├── __init__.py                 # Plugin loader
└── graph/                      # Built-in graph plugin
    └── __init__.py
```

**User plugins** for extras/third-party:
```
~/.config/dodo/plugins/
└── my-custom-plugin/
    └── __init__.py
```

**Registry** (cached):
```
~/.config/dodo/plugin_registry.json
```

User plugins override built-ins if same name.

---

## Plugin Interface

A plugin is a Python package with optional hook functions:

```python
# plugins/graph/__init__.py

name = "graph"  # Required

# Optional hooks - implement only what you need

def register_commands(app: typer.Typer) -> None:
    """Add CLI commands."""
    ...

def register_config() -> list[ConfigVar]:
    """Declare config variables."""
    ...

def extend_adapter(adapter: TodoAdapter, config: Config) -> TodoAdapter:
    """Wrap/extend the adapter."""
    ...

def extend_formatter(formatter: FormatterProtocol, config: Config) -> FormatterProtocol:
    """Wrap/extend the formatter."""
    ...
```

**No base class required.** Duck typing - if the function exists, it's called.

---

## Config & Registry (Separation of Concerns)

**Config** stores user preferences (enabled state):
```json
// ~/.config/dodo/config.json
{
  "default_adapter": "sqlite",
  "default_format": "table",
  "enabled_plugins": "sqlite,graph"
}
```

**Registry** stores plugin metadata (discovered hooks):
```json
// ~/.config/dodo/plugin_registry.json
{
  "sqlite": {
    "builtin": true,
    "hooks": ["register_adapter"]
  },
  "graph": {
    "builtin": true,
    "hooks": ["extend_adapter", "extend_formatter", "register_commands"]
  },
  "my-custom": {
    "builtin": false,
    "path": "/Users/x/.config/dodo/plugins/my-custom",
    "hooks": ["register_commands"]
  }
}
```

**Benefits:**
- User settings in config, metadata in registry
- Env override works: `DODO_ENABLED_PLUGINS=sqlite,graph`
- Follows existing config patterns (`Config.set()`, `DODO_*` env vars)

**Config addition:**
```python
# config.py
DEFAULTS = {
    ...
    "enabled_plugins": "",  # Comma-separated
}

@property
def enabled_plugins(self) -> set[str]:
    raw = self._data.get("enabled_plugins", self.DEFAULTS["enabled_plugins"])
    return {p.strip() for p in raw.split(",") if p.strip()}
```

Populated by `dodo plugins scan` (scans all locations) or auto-populated for built-ins on first run.

---

## Core Integration

**Single entry point:**

```python
# plugins/__init__.py

def apply_hooks(hook: str, target: T, config_dir: Path) -> T:
    """Apply all enabled plugins for a hook phase."""
    for plugin in _get_enabled_plugins(hook, config_dir):
        fn = getattr(plugin, hook)
        result = fn(target)
        if result is not None:
            target = result
    return target
```

**Usage in core** (follows existing lazy import pattern from `core.py:49-66`):

```python
# core.py
def _create_adapter(self) -> TodoAdapter:
    adapter_name = self._config.default_adapter

    # Lazy imports inside conditionals (existing pattern)
    if adapter_name == "markdown":
        from dodo.adapters.markdown import MarkdownAdapter
        adapter = MarkdownAdapter(self._get_markdown_path())
    elif adapter_name == "sqlite":
        from dodo.adapters.sqlite import SqliteAdapter
        adapter = SqliteAdapter(self._get_sqlite_path())
    # ... etc

    # Plugin hooks (new - also lazy, only if registry has enabled plugins)
    from dodo.plugins import apply_hooks
    adapter = apply_hooks("extend_adapter", adapter, self._config.config_dir)

    return adapter
```

```python
# cli.py
def list_todos(...):
    from dodo.formatters import get_formatter
    formatter = get_formatter(format_str)

    # Plugin hooks
    from dodo.plugins import apply_hooks
    cfg = Config.load()  # Cached after first call
    formatter = apply_hooks("extend_formatter", formatter, cfg.config_dir)

    output = formatter.format(items)
```

---

## Lazy Loading Strategy

Follows established patterns from `config.py` and `project.py`:

```python
# plugins/__init__.py

import importlib.util
import json
from pathlib import Path
from types import ModuleType

# Module-level cache (same pattern as config.py, project.py)
_registry_cache: dict | None = None
_plugin_cache: dict[str, ModuleType] = {}


def clear_plugin_cache() -> None:
    """Clear plugin caches. Useful for testing."""
    global _registry_cache, _plugin_cache
    _registry_cache = None
    _plugin_cache.clear()


def _load_registry(config_dir: Path) -> dict:
    """Load registry from file, with caching."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    path = config_dir / "plugin_registry.json"
    _registry_cache = json.loads(path.read_text()) if path.exists() else {}
    return _registry_cache


def _import_plugin(name: str, path: str | None) -> ModuleType:
    """Import plugin module, with caching."""
    cache_key = path or name
    if cache_key in _plugin_cache:
        return _plugin_cache[cache_key]

    if path is None:
        # Built-in plugin: use normal import
        module = importlib.import_module(f"dodo.plugins.{name}")
    else:
        # User/local plugin: dynamic import from path
        spec = importlib.util.spec_from_file_location(
            f"dodo_plugin_{name}",
            Path(path) / "__init__.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    _plugin_cache[cache_key] = module
    return module


def _get_enabled_plugins(hook: str, config: Config):
    """Yield plugin modules that are enabled and have this hook."""
    registry = _load_registry(config.config_dir)

    for name in config.enabled_plugins:  # From config, not registry
        if name not in registry:
            continue
        info = registry[name]
        if hook not in info.get("hooks", []):
            continue

        # Import happens HERE - only for enabled plugins with matching hook
        path = None if info.get("builtin") else info.get("path")
        yield _import_plugin(name, path)
```

---

## Overhead Analysis

| Scenario | Registry read | Plugin import | Hook call |
|----------|--------------|---------------|-----------|
| No plugins registered | 1 JSON read | 0 | 0 |
| Plugins disabled | 1 JSON read | 0 | 0 |
| Plugin enabled, hook not needed | 1 JSON read | 0 | 0 |
| Plugin enabled, hook called | 1 JSON read | 1 | 1 |

**Key:** JSON registry is read once per process, cached in memory.

---

## CLI Commands

```bash
# Scan plugin dirs, detect hooks, update registry
dodo plugins scan

# Register specific plugin path
dodo plugins register ./my-plugin

# Enable/disable (modifies config.json enabled_plugins)
dodo plugins enable sqlite
dodo plugins enable graph
dodo plugins disable graph

# List with status
dodo plugins list
# sqlite     [enabled]   register_adapter
# graph      [enabled]   extend_adapter, extend_formatter, register_commands
# obsidian   [disabled]  register_adapter, register_config
```

**Enable/disable implementation:**
```python
# cli_plugins.py

def enable(name: str):
    cfg = Config.load()
    enabled = cfg.enabled_plugins
    enabled.add(name)
    cfg.set("enabled_plugins", ",".join(sorted(enabled)))
    console.print(f"[green]Enabled:[/green] {name}")

def disable(name: str):
    cfg = Config.load()
    enabled = cfg.enabled_plugins
    enabled.discard(name)
    cfg.set("enabled_plugins", ",".join(sorted(enabled)))
    console.print(f"[yellow]Disabled:[/yellow] {name}")
```

**Env override (temporary):**
```bash
DODO_ENABLED_PLUGINS=sqlite,graph dodo list
```

---

## Plugin Hook API

> This API should be documented in `src/dodo/plugins/README.md`

### Registration Hooks (called at startup if plugin enabled)

| Hook | Signature | Purpose |
|------|-----------|---------|
| `register_commands` | `(app: Typer) -> None` | Add CLI commands/subcommands |
| `register_config` | `() -> list[ConfigVar]` | Declare config variables |
| `register_adapter` | `(registry: dict) -> None` | Add adapter type to registry |

### Extension Hooks (called at runtime)

| Hook | Signature | Purpose |
|------|-----------|---------|
| `extend_adapter` | `(adapter, config) -> Adapter` | Wrap/extend adapter |
| `extend_formatter` | `(formatter, config) -> Formatter` | Wrap/extend formatter |

### Example: Minimal Plugin

```python
# plugins/my-plugin/__init__.py

name = "my-plugin"  # Required

def register_commands(app):
    """Add CLI commands."""
    @app.command()
    def my_command():
        print("Hello from plugin!")
```

### Example: Adapter Plugin

```python
# plugins/sqlite/__init__.py

name = "sqlite"

def register_adapter(registry):
    """Register sqlite adapter."""
    from .adapter import SqliteAdapter
    registry["sqlite"] = SqliteAdapter
```

### Example: Feature Plugin (Graph)

```python
# plugins/graph/__init__.py

name = "graph"

def register_commands(app):
    from .cli import ready, blocked, dep_app
    app.command()(ready)
    app.command()(blocked)
    app.add_typer(dep_app, name="dep")

def extend_adapter(adapter, config):
    from .adapter import GraphWrapper
    if hasattr(adapter, 'db_path'):
        return GraphWrapper(adapter)
    return adapter

def extend_formatter(formatter, config):
    from .formatter import GraphFormatter
    return GraphFormatter(formatter)
```

### Future Hooks (not implemented yet)

Reserved for future use if needed:

| Hook | Purpose |
|------|---------|
| `on_todo_create` | Called after todo created |
| `on_todo_complete` | Called after todo completed |
| `on_list` | Called after list fetched, before display |

---

## Example: Graph Plugin

```python
# plugins/graph/__init__.py

name = "graph"

def register_commands(app):
    from .cli import ready, blocked, dep_app
    app.command()(ready)
    app.command()(blocked)
    app.add_typer(dep_app, name="dep")

def extend_adapter(adapter, config):
    from .adapter import GraphWrapper
    if hasattr(adapter, 'db_path'):  # SQLite only
        return GraphWrapper(adapter)
    return adapter

def extend_formatter(formatter, config):
    from .formatter import GraphFormatter
    return GraphFormatter(formatter)
```

**Note:** Imports inside functions = lazy loading.

---

## What This Enables

**Built-in plugins** (like graph) are already installed:
```bash
# Just enable - no install needed
dodo plugins enable graph

# Use
dodo list          # Auto-extended with blocked_by column
dodo ready         # New command
dodo dep add X Y   # New command

# Disable
dodo plugins disable graph
dodo list          # Back to normal, zero overhead
```

**User plugins** require install + scan:
```bash
# Install third-party plugin
cp -r some-plugin ~/.config/dodo/plugins/some-plugin

# Scan to detect hooks
dodo plugins scan

# Enable
dodo plugins enable some-plugin
```

---

## Testing

Follow existing pattern from `config.py` and `project.py`:

```python
# tests/conftest.py
import pytest
from dodo.config import clear_config_cache
from dodo.project import clear_project_cache
from dodo.plugins import clear_plugin_cache

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear module caches between tests."""
    yield
    clear_config_cache()
    clear_project_cache()
    clear_plugin_cache()
```

---

## Planned Plugins

### Core ships with:
- `markdown` adapter only (zero dependencies)

### Built-in plugins (ship with dodo, disabled by default):

| Plugin | Hooks | Purpose |
|--------|-------|---------|
| `sqlite` | `register_adapter` | SQLite storage backend |
| `obsidian` | `register_adapter`, `register_config` | Obsidian REST API backend |
| `graph` | `extend_adapter`, `extend_formatter`, `register_commands` | Dependency tracking |
| `ai-ops` | `register_commands` | AI sort/prioritize/tag/dedupe |

### Future/community plugins:

| Plugin | Hooks | Purpose |
|--------|-------|---------|
| `linear` | `register_adapter`, `register_config` | Linear.app integration |
| `server` | `register_commands` | HTTP endpoint for phone sync |
| `aliases` | `register_commands` | Shell alias installer |

---

## Implementation Order

### Phase 1: Plugin Infrastructure

**Create `src/dodo/plugins/__init__.py`:**
- `_registry_cache`, `_plugin_cache` module-level caches
- `clear_plugin_cache()` for testing
- `_load_registry(config_dir)` - load JSON registry with caching
- `_import_plugin(name, path)` - import plugin module with caching
- `_get_enabled_plugins(hook, config)` - generator yielding plugin modules
- `apply_hooks(hook, target, config)` - main entry point for core

**Update `src/dodo/config.py`:**
- Add `"enabled_plugins": ""` to DEFAULTS
- Add `enabled_plugins` property returning `set[str]`

**Update `tests/conftest.py`:**
- Import and call `clear_plugin_cache()` in the autouse fixture

### Phase 2: Plugin CLI Commands

**Create `src/dodo/cli_plugins.py`:**
- `scan()` - scan plugin dirs, detect hooks, write registry
- `register(path)` - register plugin from specific path
- `enable(name)` - add to config enabled_plugins
- `disable(name)` - remove from config enabled_plugins
- `list_plugins()` - show plugins with status

**Update `src/dodo/cli.py`:**
- Add `plugins_app = typer.Typer()`
- Register as subcommand: `app.add_typer(plugins_app, name="plugins")`

### Phase 3: Hook Integration in Core

**Update `src/dodo/core.py`:**
- Import `apply_hooks` from `dodo.plugins`
- In `_create_adapter()`: after creating adapter, call `apply_hooks("extend_adapter", adapter, self._config)`

**Update `src/dodo/cli.py`:**
- After getting formatter, call `apply_hooks("extend_formatter", formatter, config)`
- After creating typer app, call `apply_hooks("register_commands", app, config)`

### Phase 4: Migrate SQLite Adapter to Plugin

**Create `src/dodo/plugins/sqlite/__init__.py`:**
```python
name = "sqlite"

def register_adapter(registry):
    from .adapter import SqliteAdapter
    registry["sqlite"] = SqliteAdapter
```

**Move `src/dodo/adapters/sqlite.py` to `src/dodo/plugins/sqlite/adapter.py`**

**Update `src/dodo/core.py`:**
- Remove direct sqlite import
- Use adapter registry populated by plugins

### Phase 5: Migrate Obsidian Adapter to Plugin

**Create `src/dodo/plugins/obsidian/__init__.py`:**
```python
name = "obsidian"

def register_adapter(registry):
    from .adapter import ObsidianAdapter
    registry["obsidian"] = ObsidianAdapter

def register_config():
    return [
        ConfigVar("obsidian_api_url", "https://localhost:27124"),
        ConfigVar("obsidian_api_key", ""),
        ConfigVar("obsidian_vault_path", "dodo/todos.md"),
    ]
```

**Move `src/dodo/adapters/obsidian.py` to `src/dodo/plugins/obsidian/adapter.py`**

### Phase 6: Create Graph Plugin (New)

**Create `src/dodo/plugins/graph/__init__.py`:**
- `register_commands(app)` - add `ready`, `blocked`, `dep` commands
- `extend_adapter(adapter, config)` - wrap with GraphWrapper if sqlite
- `extend_formatter(formatter, config)` - add blocked_by column

**Create supporting files:**
- `src/dodo/plugins/graph/adapter.py` - GraphWrapper with dependency methods
- `src/dodo/plugins/graph/cli.py` - CLI commands
- `src/dodo/plugins/graph/formatter.py` - Extended formatter

### Phase 7: Refactor Adapter Registry

**Update `src/dodo/core.py`:**
```python
# Module-level adapter registry
_adapter_registry: dict[str, type] = {}

def register_builtin_adapters():
    from dodo.adapters.markdown import MarkdownAdapter
    _adapter_registry["markdown"] = MarkdownAdapter

def _create_adapter(self) -> TodoAdapter:
    # Let plugins register adapters
    apply_hooks("register_adapter", _adapter_registry, self._config)

    adapter_cls = _adapter_registry.get(self._config.default_adapter)
    if not adapter_cls:
        raise ValueError(f"Unknown adapter: {self._config.default_adapter}")

    # Instantiate and extend
    adapter = adapter_cls(self._get_path())
    return apply_hooks("extend_adapter", adapter, self._config)
```

---

## Files Created/Modified Summary

| File | Action |
|------|--------|
| `src/dodo/plugins/__init__.py` | Create - plugin loader |
| `src/dodo/plugins/sqlite/__init__.py` | Create - sqlite plugin |
| `src/dodo/plugins/sqlite/adapter.py` | Move from adapters/sqlite.py |
| `src/dodo/plugins/obsidian/__init__.py` | Create - obsidian plugin |
| `src/dodo/plugins/obsidian/adapter.py` | Move from adapters/obsidian.py |
| `src/dodo/plugins/graph/__init__.py` | Create - graph plugin |
| `src/dodo/plugins/graph/adapter.py` | Create - dependency wrapper |
| `src/dodo/plugins/graph/cli.py` | Create - dep commands |
| `src/dodo/plugins/graph/formatter.py` | Create - extended formatter |
| `src/dodo/cli_plugins.py` | Create - plugin CLI |
| `src/dodo/config.py` | Update - add enabled_plugins |
| `src/dodo/core.py` | Update - use plugin hooks |
| `src/dodo/cli.py` | Update - register plugin commands |
| `tests/conftest.py` | Update - clear plugin cache |
| `tests/test_plugins.py` | Create - plugin tests |

---

## Non-Goals

- Hot reloading (restart dodo after changes)
- Plugin dependencies (keep plugins independent)
- Plugin versioning (user manages compatibility)
- Remote plugin installation (manual copy for now)
