# Code Audit: dodo CLI - Recent Fixes

**Date**: 2026-01-13
**Scope**: Recent fixes (last 5 commits) with emphasis on DRY, code-smell, modularity, plugin interface ownership, and startup time
**Health Score**: Needs Work

## Executive Summary

The codebase shows good intent with lazy loading patterns for startup optimization, but has accumulated technical debt in several areas. Key concerns:

1. **Startup time**: Import-time plugin routing performs filesystem I/O for every CLI invocation
2. **Plugin ownership**: Brittle hook detection via regex, missing `register_root_commands` from known hooks
3. **DRY violations**: Repeated config/project/service resolution patterns across CLI commands
4. **UI coupling**: Interactive UI directly instantiates backends, bypassing the plugin system

Quick wins are available in config consolidation and hook registration. Larger architectural improvements needed for UI-backend decoupling.

## Findings by Category

### Startup-time Overhead

**ISSUE ST-1: Import-time Plugin Routing (Medium Severity, Medium Effort)**

Every CLI invocation reads `plugin_registry.json` and `config.json` at module load time:

```python
# src/dodo/cli.py:147-152 - runs at import time!
if "--help" in sys.argv or "-h" in sys.argv:
    _register_all_plugin_root_commands()
else:
    _plugin_match = _get_plugin_for_command(sys.argv)
    if _plugin_match:
        _register_plugin_for_command(_plugin_match[0], _plugin_match[1])
```

This means `_load_json_file()` is called before any command runs, adding ~10-20ms overhead for simple commands like `dodo add` or `dodo list`.

**Recommendation**: Defer plugin command routing until after typer parses known commands. Only read registry when an unknown command is encountered.

---

**ISSUE ST-2: Config Constructor vs _get_config_dir Mismatch (Medium Severity, Small Effort)**

`_get_config_dir()` in cli.py respects `DODO_CONFIG_DIR` env var, but `Config.__init__` hardcodes the default:

```python
# src/dodo/cli.py:61-72
def _get_config_dir():
    config_dir = os.environ.get("DODO_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    return Path.home() / ".config" / "dodo"

# src/dodo/config.py:68-70
def __init__(self, config_dir: Path | None = None):
    self._config_dir = config_dir or Path.home() / ".config" / "dodo"
```

Plugin routing could read a different config directory than the rest of the app.

**Recommendation**: Extract config dir resolution to a single shared function, or have `_get_config_dir` call `Config.get_default_dir()`.

---

### Plugin Interface Ownership

**ISSUE PO-1: Brittle Hook Detection via Regex (Medium Severity, Medium Effort)**

Hooks are detected by string-scanning `__init__.py`:

```python
# src/dodo/plugins/__init__.py:66-70
for hook in _KNOWN_HOOKS:
    if f"def {hook}(" in content:
        hooks.append(hook)
```

This can:
- Miss hooks defined dynamically or via decorators
- False-positive on commented-out code or docstrings
- Not detect hooks added via `__getattr__`

**Recommendation**: Use a declarative manifest (`plugin.json`) for hooks, or inspect the imported module's `__dict__` after loading.

---

**ISSUE PO-2: Root Command Registration Missing from Known Hooks (Medium Severity, Medium Effort)**

The CLI expects `register_root_commands`, but it's not in `_KNOWN_HOOKS`:

```python
# src/dodo/plugins/__init__.py:48-54
_KNOWN_HOOKS = [
    "register_commands",
    "register_config",
    "register_backend",
    "extend_backend",
    "extend_formatter",
]
# Missing: "register_root_commands"

# src/dodo/cli.py:111
if is_root and hasattr(plugin, "register_root_commands"):
    plugin.register_root_commands(app, cfg)
```

This means root commands won't be detected by the registry scanner and won't appear correctly in plugin info.

**Recommendation**: Add `register_root_commands` to `_KNOWN_HOOKS` or use a separate `COMMANDS` declaration pattern consistently.

---

**ISSUE PO-3: Inconsistent Command Declaration (Low Severity, Small Effort)**

Plugins can declare commands via either:
1. `COMMANDS = ["graph", "plugins/graph"]` in `__init__.py`
2. Implementing `register_commands` or `register_root_commands`

The registry only scans for `COMMANDS` declaration, leading to potential desync.

**Recommendation**: Standardize on one approach. Prefer `plugin.json` for static declarations.

---

### DRY Violations

**ISSUE DRY-1: Repeated Config/Project/Service Resolution (Low Severity, Small Effort)**

Almost every CLI command repeats the same pattern:

```python
# Appears in: add, done, rm, info, export, ai, undo, init, backend
cfg = _get_config()
project_id = _detect_project(worktree_shared=cfg.worktree_shared)
svc = _get_service(cfg, project_id)
```

**Recommendation**: Create a `@with_service` decorator or use typer's dependency injection to inject `cfg`, `project_id`, and `svc` as command parameters.

---

**ISSUE DRY-2: Multiple Overlapping Config Editors (Low Severity, Medium Effort)**

`ui/interactive.py` has four config editor implementations:
- `_unified_settings_loop` (1000+ lines)
- `_config_loop` (~80 lines)
- `_plugins_config_loop` (~90 lines)
- `_general_config` (~15 lines, unused?)

These duplicate rendering logic and input handling.

**Recommendation**: Consolidate into a single generic settings loop that accepts a schema/items list.

---

**ISSUE DRY-3: Duplicated Backend Instantiation Logic (Low Severity, Small Effort)**

Backend instantiation happens in multiple places:
- `core.py:_instantiate_backend` - main path
- `ui/interactive.py:_detect_other_backend_files` - directly creates `MarkdownBackend`/`SqliteBackend`
- `ui/interactive.py:_run_migration` - directly creates backends
- `ui/interactive.py:handle_delete_project` - directly creates backends

**Recommendation**: All backend instantiation should go through `TodoService` or a factory function.

---

### Code Smells

**ISSUE CS-1: Large Nested UI Functions (Medium Severity, Medium Effort)**

Several UI functions are difficult to reason about:
- `_todos_loop`: ~250 lines with nested `build_display()` closure
- `_interactive_switch`: ~300 lines with multiple nested functions
- `_unified_settings_loop`: ~280 lines with nested functions

These functions mix state management, rendering, and input handling.

**Recommendation**: Extract to classes with clear state/render/handle separation, or use a state machine pattern.

---

**ISSUE CS-2: Backend Constructor try/except TypeError (Medium Severity, Small Effort)**

```python
# src/dodo/core.py:176-180
try:
    return backend_cls(config=self._config, project_id=self._project_id)
except TypeError:
    # Fall back to no-args construction
    return backend_cls()
```

This masks real TypeErrors from plugin backends. A bug in a plugin's `__init__` would silently fall back to no-args construction.

**Recommendation**: Use `inspect.signature()` to check constructor parameters, or require plugins to implement a factory method.

---

**ISSUE CS-3: Magic Numbers in UI (Low Severity, Small Effort)**

```python
# src/dodo/ui/interactive.py
DEFAULT_PANEL_WIDTH = 80
DEFAULT_TERMINAL_HEIGHT = 24
STATUS_MSG_MAX_LEN = 30
CONFIG_DISPLAY_MAX_LEN = 35
```

These are defined, but other magic numbers appear inline:
- `width - 6`, `width - 9`, `width - 10`
- `max_val_len = 18`
- `value_col = 28`, `desc_col = 50`

**Recommendation**: Extract to named constants or compute dynamically.

---

### Modularity Issues

**ISSUE MOD-1: UI Directly Couples to Backend Classes (Medium Severity, Medium Effort)**

Interactive UI bypasses `TodoService` and directly instantiates backends:

```python
# src/dodo/ui/interactive.py:603-609
if str(path).endswith(".db"):
    backend = SqliteBackend(path)
else:
    backend = MarkdownBackend(path)
count = len(backend.list())
```

This means:
- Plugin backends can't participate in migration, delete, or count operations
- UI must know about all backend types

**Recommendation**: Add `TodoService.get_backend_for_path(path)` or similar factory method.

---

**ISSUE MOD-2: Storage Path Display Uses Wrong Backend (Low Severity, Small Effort)**

```python
# src/dodo/ui/interactive.py:356-360
def _get_project_storage_path(cfg: Config, project_id: str | None, worktree_shared: bool) -> Path:
    from dodo.storage import get_storage_path
    return get_storage_path(cfg, project_id, cfg.default_backend, worktree_shared)
```

Uses `cfg.default_backend` instead of the project's resolved backend, so UI can show wrong storage path.

**Recommendation**: Get the resolved backend from `TodoService` or project config.

---

## Priority Matrix

| Issue | Category | Severity | Effort | Recommended Action |
|-------|----------|----------|--------|-------------------|
| ST-2 | Startup-time | Medium | Small | Unify config dir resolution |
| CS-2 | Code-smell | Medium | Small | Use inspect.signature() for backend construction |
| PO-2 | Plugin-ownership | Medium | Small | Add register_root_commands to _KNOWN_HOOKS |
| DRY-1 | DRY | Low | Small | Create @with_service decorator |
| MOD-2 | Modularity | Low | Small | Use resolved backend for storage path |
| CS-3 | Code-smell | Low | Small | Extract magic numbers to constants |
| ST-1 | Startup-time | Medium | Medium | Defer plugin routing until needed |
| PO-1 | Plugin-ownership | Medium | Medium | Use declarative plugin.json for hooks |
| PO-3 | Plugin-ownership | Low | Small | Standardize command declaration |
| DRY-3 | DRY | Low | Small | Centralize backend instantiation |
| DRY-2 | DRY | Low | Medium | Consolidate config editors |
| CS-1 | Code-smell | Medium | Medium | Extract UI to state machine classes |
| MOD-1 | Modularity | Medium | Medium | Add backend factory to TodoService |

## Recommended Cleanup Plan

### Phase 1: Quick Wins (Low effort, high impact)

1. **ST-2**: Add `Config.get_default_dir()` class method, use in `_get_config_dir()`
2. **PO-2**: Add `"register_root_commands"` to `_KNOWN_HOOKS`
3. **CS-2**: Replace try/except TypeError with signature inspection
4. **DRY-1**: Create `@with_service` decorator for CLI commands
5. **MOD-2**: Pass resolved backend name to `_get_project_storage_path()`

### Phase 2: Core Improvements (Medium effort)

1. **ST-1**: Refactor plugin routing to defer until unknown command encountered
2. **PO-1**: Migrate hook detection to `plugin.json` manifest
3. **DRY-3**: Add `BackendFactory` class or extend TodoService
4. **MOD-1**: Add `TodoService.create_backend_for_path()` method

### Phase 3: Architectural Changes (Larger effort)

1. **CS-1**: Extract UI functions to classes with state/render/handle separation
2. **DRY-2**: Create unified `SettingsEditor` class that handles all config types
3. **Long-term**: Consider using a proper TUI framework (textual, urwid) for interactive.py

## Auditor Notes

- Codex (GPT-5.2) provided the primary analysis with specific code references
- Gemini analysis timed out but core areas were covered
- The codebase shows good awareness of startup optimization (lazy imports) but the plugin system adds overhead that partially negates these gains
- The plugin API would benefit from clearer documentation of the hook contract
