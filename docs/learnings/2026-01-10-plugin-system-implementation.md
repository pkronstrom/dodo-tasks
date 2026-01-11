# Learnings: Plugin System Implementation

**Date**: 2026-01-10
**Objective**: Implement hook-based plugin system with lazy loading
**Outcome**: Success - merged to master

## Summary

Replaced shell-script plugin system with Python module plugins using hooks. Key insight: explicit enable for all plugins is simpler than auto-enable logic, and plugin commands should be namespaced under `dodo plugins <name>` to keep root CLI clean.

## Key Learnings

### Typer Subapp Registration

Use `app.add_typer(subapp, name="x")` instead of manual dispatch functions:

```python
# Bad - manual dispatch
@app.command()
def plugins(action: str, name: str | None = None):
    if action == "list": list_plugins()
    elif action == "show": show(name)
    # ...

# Good - proper Typer subapp
app.add_typer(plugins_app, name="plugins")
```

The dispatch pattern loses Typer's help generation and argument validation.

### Plugin Command Namespacing

Plugin commands should live under `dodo plugins <plugin-name> <cmd>`:

```python
def register_commands(app: typer.Typer, config: Config) -> None:
    # app is plugins_app, not the root app
    my_app = typer.Typer(name="my-plugin", help="...")
    my_app.command()(my_command)
    app.add_typer(my_app, name="my-plugin")
```

Result: `dodo plugins my-plugin <cmd>` - keeps root namespace clean.

### Editor Empty Value Bug

When using `_edit_in_editor`, ensure empty strings can be saved:

```python
# Bug - can't clear values (empty string is falsy)
return new_value if new_value and new_value != current_value else None

# Fix - allow clearing by removing truthy check
return new_value if new_value != current_value else None
```

## Design Decisions

### Lazy Loading via String Refs

Adapters registered as strings, resolved at runtime:

```python
_adapter_registry = {
    "markdown": "dodo.adapters.markdown:MarkdownAdapter",
    "sqlite": "dodo.plugins.sqlite.adapter:SqliteAdapter",
}

def _resolve_adapter_class(ref: str | type) -> type:
    if isinstance(ref, type):
        return ref
    module_path, class_name = ref.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
```

Zero import cost until adapter is actually used.

### Module-Level Caches

Follow existing pattern from `config.py` and `project.py`:

```python
_registry_cache: dict | None = None
_plugin_cache: dict[str, ModuleType] = {}

def clear_plugin_cache() -> None:
    global _registry_cache, _plugin_cache
    _registry_cache = None
    _plugin_cache.clear()
```

Tests call `clear_*_cache()` in fixtures to ensure isolation.

### Hook-Based Extension

Plugins implement hooks, called at specific points:

| Hook | Purpose | Called From |
|------|---------|-------------|
| `register_commands` | Add CLI commands | `cli.py` startup |
| `register_adapter` | Add adapter type | `core.py` |
| `extend_adapter` | Wrap adapter instance | `core.py` |
| `extend_formatter` | Wrap formatter | `core.py` |
| `register_config` | Declare config vars | Plugin loader |

## References

- `src/dodo/plugins/__init__.py` - Core plugin loader
- `src/dodo/plugins/ntfy_inbox/` - Example command plugin
- `src/dodo/plugins/sqlite/` - Example adapter plugin
