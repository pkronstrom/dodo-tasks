# AI Plugin Extraction Design

**Date:** 2026-01-13
**Status:** Approved
**Goal:** Extract AI functionality from core into a separate plugin for lazy loading and clean architecture.

## Summary

Move all AI-related code (`ai.py`, `ai_commands.py`) into a new plugin at `src/dodo/plugins/ai/`. Migrate all plugin configs to a nested structure under `plugins.<name>`. Add a hook interface for cross-plugin communication (`ai dep` → graph).

## Design Decisions

| Decision | Choice |
|----------|--------|
| `ai dep` handling | Hook interface - AI plugin calls graph hook to store dependencies |
| Config structure | Nested under `plugins.ai`, `plugins.graph`, etc. |
| Existing plugin configs | Migrate all plugins to nested structure now |
| CLI hierarchy | Keep `dodo ai ...` as root commands via `register_root_commands` |
| Plugin enabling | Explicit - requires `dodo plugins enable ai` |

## Plugin Structure

```
src/dodo/plugins/ai/
├── __init__.py      # Hook registrations
├── cli.py           # CLI commands (add, prio, tag, reword, run, dep, sync)
├── engine.py        # AI execution (build_command, run_ai, run_ai_structured)
├── schemas.py       # JSON schemas (ADD_SCHEMA, RUN_SCHEMA, etc.)
└── prompts.py       # Default prompts
```

## Config Structure

```json
{
  "default_backend": "sqlite",
  "enabled_plugins": ["ai", "graph"],
  "plugins": {
    "ai": {
      "command": "claude -p {{prompt}} -s {{system}} --output-format json",
      "model": "sonnet",
      "run_command": "claude -p {{prompt}} -s {{system}} --output-format json --allowedTools ...",
      "run_model": "sonnet",
      "prompts": {
        "add": "...",
        "prioritize": "...",
        "tag": "...",
        "reword": "...",
        "run": "...",
        "dep": "..."
      }
    },
    "graph": {},
    "ntfy_inbox": {
      "topic": "my-dodo",
      "server": "https://ntfy.sh"
    },
    "obsidian": {
      "api_url": "http://localhost:27123",
      "api_key": "...",
      "vault_path": "..."
    }
  }
}
```

## Hook Interface for Cross-Plugin Communication

**Graph plugin exposes:**
```python
def register_hooks():
    return {
        "add_dependencies": "dodo.plugins.graph.wrapper:add_dependencies"
    }
```

**Plugin system addition:**
```python
def call_hook(hook_name: str, *args, **kwargs):
    """Call a named hook from any enabled plugin that provides it."""
    for plugin in _get_enabled_plugins_with_hook("register_hooks"):
        hooks = plugin.register_hooks()
        if hook_name in hooks:
            func = import_callable(hooks[hook_name])
            return func(*args, **kwargs)
    return None
```

**AI plugin usage:**
```python
result = call_hook("add_dependencies", backend, pairs)
if result is None:
    echo("Error: ai dep requires graph plugin. Enable with: dodo plugins enable graph")
```

## Lazy Loading

- Plugin registry is pre-scanned to `plugin_registry.json`
- AI code only imported when `dodo ai ...` is invoked
- Core (`cli.py`, `core.py`) has zero AI imports
- Config cached once per invocation

## Implementation Plan

### Phase 1: Config System Updates
1. Add `get_plugin_config(plugin_name, key, default)` to `config.py`
2. Update `Config.DEFAULTS` to use nested `plugins` structure
3. Migrate existing plugin config access in graph, ntfy_inbox, obsidian

### Phase 2: Plugin Hook System
4. Add `call_hook()` to `plugins/__init__.py`
5. Add `register_hooks()` to graph plugin with `add_dependencies`

### Phase 3: Create AI Plugin
6. Create `plugins/ai/__init__.py` with hook registrations
7. Create `plugins/ai/schemas.py` - move schemas from `ai.py`
8. Create `plugins/ai/prompts.py` - move prompts from `ai.py`
9. Create `plugins/ai/engine.py` - move execution logic from `ai.py`
10. Create `plugins/ai/cli.py` - move commands from `ai_commands.py`

### Phase 4: Remove Core AI Code
11. Remove `ai.py` from core
12. Remove `ai_commands.py` from core
13. Remove AI command registration from `cli.py`
14. Remove AI-related defaults from config

### Phase 5: Testing & Cleanup
15. Update tests for new import paths
16. Update tests for nested config structure
17. Run full test suite, fix failures
18. Update README if needed

## Files to Create
- `src/dodo/plugins/ai/__init__.py`
- `src/dodo/plugins/ai/cli.py`
- `src/dodo/plugins/ai/engine.py`
- `src/dodo/plugins/ai/schemas.py`
- `src/dodo/plugins/ai/prompts.py`

## Files to Delete
- `src/dodo/ai.py`
- `src/dodo/ai_commands.py`

## Files to Modify
- `src/dodo/config.py` - add `get_plugin_config()`, nested defaults
- `src/dodo/plugins/__init__.py` - add `call_hook()`
- `src/dodo/plugins/graph/__init__.py` - add `register_hooks()`
- `src/dodo/plugins/ntfy_inbox/__init__.py` - migrate config access
- `src/dodo/plugins/obsidian/__init__.py` - migrate config access
- `src/dodo/cli.py` - remove AI imports/registration
