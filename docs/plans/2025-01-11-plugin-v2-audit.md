# Code Audit: Plugin V2 Branch

**Date**: 2025-01-11
**Scope**: All changes in feature/plugin-v2 worktree vs master
**Health Score**: Needs Work (but solid foundation)

## Executive Summary

The plugin-v2 branch adds significant functionality (hook-based plugins, interactive UI enhancements). The architecture is sound and lazy loading is mostly implemented correctly. However, there are performance issues on the fast path (CLI startup), some code duplication, and a few hacky patterns that should be cleaned up before merge.

## Findings by Category

### 1. Performance Issues (Fast Path)

**Critical**: CLI startup imports too much upfront.

**cli.py lines 1-14**:
```python
from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Status
from dodo.project import detect_project
```

These imports happen even for `dodo --help`. The `project.py` imports `subprocess` and `hashlib` at module level. Every CLI invocation pays this cost.

**cli.py line 299**: `_register_plugins_subapp()` runs at import time.
**cli.py line 387**: `_register_plugin_commands()` runs at import time, calling `Config.load()` and `apply_hooks()`.

**Fix**: Move registrations to callbacks, use lazy imports.

**interactive.py line 384-414 `_shorten_path()`**:
```python
def _shorten_path(path: Path, max_len: int = 50) -> str:
    from dodo.config import Config  # Import inside function
    ...
    config_dir = str(Config.load().config_dir)  # Loads config every call!
```

This re-loads Config on every path shortening call (multiple times per render).

**Fix**: Pass config_dir as parameter or cache at function scope.

### 2. Code Duplication (DRY Violations)

**`_get_project_storage_path()` exists in two places**:
- `core.py` lines 134-153: `_get_markdown_path()` and `_get_sqlite_path()`
- `interactive.py` lines 362-381: `_get_project_storage_path()`

Same logic, different implementations. Risk of divergence (already caused bugs with `local_storage`).

**Fix**: Single source of truth, import from one location.

**`_load_registry()` duplicated**:
- `plugins/__init__.py` line 40: `_load_registry()` with caching
- `cli_plugins.py` line 44: `_load_registry()` without caching

**Fix**: Import from `plugins/__init__.py`, remove duplicate.

### 3. Hacky Patterns

**core.py lines 86-89 & 115-132**: Hard-coded adapter instantiation logic:
```python
if adapter_name == "markdown":
    return adapter_cls(self._get_markdown_path())
elif adapter_name == "sqlite":
    return adapter_cls(self._get_sqlite_path())
elif adapter_name == "obsidian":
    ...
else:
    # Try calling with config (hacky fallback)
```

This doesn't scale well and requires core changes for new adapters.

**Fix**: Each adapter should know its own factory pattern. Registry could store callable factories.

**interactive.py line 265**: Magic number for cursor positioning:
```python
cursor = 999999  # Jump to end (clamped to last item)
```

While functional, this is unclear. Better to explicitly set to `len(items) - 1`.

### 4. Dead Code / Unused

**cli_plugins.py lines 317-348**: `dispatch()` function marked as "legacy" but still present. If not needed, remove it.

**interactive.py line 93-99**: `_interactive_add()` function appears unused (quick-add replaced it).

### 5. Coupling Issues

**interactive.py is 1480 lines** - doing too much:
- Main menu
- Todo management
- Project switching
- Config editing
- Settings loop
- Migration
- Path utilities

This file has grown organically and should be split for maintainability.

**plugins/__init__.py `get_all_plugins()`** (lines 149-202):
- Creates Config instance internally
- Imports plugin modules
- Accesses environment variables

This does too much for what should be a data retrieval function. Side effects make it hard to test.

### 6. Error Handling

**interactive.py line 402-403**: Silent exception swallowing:
```python
except Exception:
    pass
```

Should at least log or handle specific exceptions.

**plugins/__init__.py line 188-189**: Same pattern:
```python
except Exception:
    pass  # Skip config loading errors
```

### 7. Module-Level Side Effects

**core.py line 47**: `_register_builtin_adapters()` runs at module import.

This is fine for registering strings (lazy), but couples module loading to registration.

**project.py lines 64-99**: `subprocess.run()` calls at function level are fine, but consider caching git commands more aggressively.

## Priority Matrix

| Issue | Severity | Effort | Recommended Action |
|-------|----------|--------|-------------------|
| CLI imports at module level | High | Small | Defer imports to commands |
| `_register_plugin_commands()` at import | High | Small | Move to lazy callback |
| `_shorten_path()` calls Config.load() | Medium | Small | Pass config_dir as param |
| `_load_registry()` duplicated | Medium | Small | Import from one place |
| `_get_project_storage_path()` duplicated | Medium | Medium | Centralize path logic |
| `dispatch()` dead code | Low | Small | Remove if unused |
| `_interactive_add()` dead code | Low | Small | Remove if unused |
| Magic number 999999 | Low | Small | Use explicit length |
| Exception swallowing | Low | Small | Log or handle specifically |
| interactive.py size | Low | Large | Future refactor |

## Recommended Cleanup Plan

### Phase 1: Quick Wins (Do Now)

1. **Defer plugin command registration** - Move `_register_plugin_commands()` to a callback
2. **Fix `_shorten_path()`** - Pass config_dir parameter instead of loading Config
3. **Remove `_load_registry()` duplicate** - Import from plugins/__init__.py
4. **Remove dead code** - `dispatch()` and `_interactive_add()` if unused
5. **Replace magic 999999** - Use `len(items)` with bounds check

### Phase 2: Core Improvements (Do Before Merge)

1. **Lazy CLI imports** - Defer heavy imports to command functions
2. **Centralize storage path logic** - Single `get_storage_path()` function
3. **Improve exception handling** - Replace bare `except Exception: pass`

### Phase 3: Architectural (Future)

1. **Split interactive.py** - Extract settings, projects, migration to separate modules
2. **Adapter factory pattern** - Let adapters define their own instantiation
3. **Plugin config isolation** - Plugins should manage their own config vars
