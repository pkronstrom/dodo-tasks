---
paths:
  - "src/dodo/**/*.py"
  - "tests/**/*.py"
---

# Design Philosophy

## Performance: Fast Core, Lazy Everything Else

Dodo is a CLI tool — every command must feel instant. The critical path for `dodo add` or `dodo list` should import the minimum needed.

- **Lazy imports in plugins**: Never import heavy deps (starlette, uvicorn, httpx, mcp) at module level. Use `TYPE_CHECKING` for type hints and import inside functions/hooks.
- **Lazy imports in core**: Backends and formatters are registered as strings (`"dodo.plugins.server.remote:RemoteBackend"`), resolved only when actually used.
- **Plugin scanning is static**: Hooks and commands are detected by string matching `__init__.py` — no imports needed to build the registry.
- **Module-level caches**: Registry, plugin modules, and config use `_*_cache` globals with `clear_*_cache()` helpers for test isolation.

If a change adds a new import to a hot path (`cli.py`, `core.py`, `resolve.py`, `config.py`), justify why it can't be deferred.

## Plugin Interface

Plugins extend dodo through hooks declared in `__init__.py`:

| Hook | Receives | Purpose |
|------|----------|---------|
| `register_commands` | `plugins_app` | Commands under `dodo plugins <name>` |
| `register_root_commands` | `root_app` | Top-level commands (`dodo server`) |
| `register_config` | — | Return `list[ConfigVar]` for settings UI |
| `register_backend` | `registry, config` | Add backend string ref to registry |
| `extend_backend` | `backend, config` | Wrap/decorate backend instance |
| `extend_formatter` | `formatter, config` | Wrap/decorate formatter instance |
| `register_hooks` | — | Cross-plugin callable hooks |

Rules:
- A plugin's `__init__.py` should be lightweight — only dataclass defs, hook functions with lazy imports inside.
- Declare `COMMANDS = [...]` and `FORMATTERS = [...]` at module level for static scanning.
- Each plugin defines its own `ConfigVar` dataclass (no shared import needed).
- Config goes through `cfg.get_plugin_config(name, key)` / `set_plugin_config()`.
- When adding a new `ConfigVar`, the settings UI picks it up automatically via `register_config`.

## Settings UI

The interactive config menu (`dodo config`) dynamically renders plugin settings from `register_config()` hooks. When adding or changing plugin config:

- Always expose it via `ConfigVar` with a descriptive `label` and `description`.
- Use appropriate `kind`: `toggle` for booleans, `cycle` for fixed option sets, `edit` for freeform.
- Keep defaults sensible — plugins should work with zero config where possible.
