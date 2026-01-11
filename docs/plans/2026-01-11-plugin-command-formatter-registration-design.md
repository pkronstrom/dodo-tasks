# Plugin Command & Formatter Registration Design

## Problem

Two issues with the current plugin system:

1. **CLI commands don't work**: `dodo plugins graph` fails because typer resolves commands before the callback registers them
2. **No formatter registration**: Can't use `dodo list -f tree` because plugins can't register custom formatters

## Solution Overview

Unify plugin command and formatter registration using the existing `plugin_registry.json` as the source of truth for plugin metadata, with `config.json` controlling which plugins are enabled.

**Key principles:**
- Fast startup: Only load plugins when their commands/formatters are actually used
- Single mechanism: Same pattern for root commands, nested commands, and formatters
- Clean separation: Registry owns metadata, config owns enabled state

## Design

### 1. Plugin Declaration

Plugins declare their commands and formatters in `__init__.py`:

```python
# src/dodo/plugins/graph/__init__.py

# Detected by scan, stored in registry
COMMANDS = ["graph", "dep", "plugins/graph"]
FORMATTERS = ["tree"]

def register_commands(app: typer.Typer, config: Config) -> None:
    """Register CLI commands."""
    from dodo.plugins.graph.cli import blocked, dep_app, ready

    graph_app = typer.Typer(name="graph", help="Dependency tracking.")
    graph_app.command()(ready)
    graph_app.command()(blocked)
    graph_app.add_typer(dep_app, name="dep")

    # Register based on which command was invoked
    # The CLI will call this with the appropriate app
    app.add_typer(graph_app, name="graph")

def register_root_commands(app: typer.Typer, config: Config) -> None:
    """Register root-level commands (dodo graph, dodo dep)."""
    from dodo.plugins.graph.cli import blocked, dep_app, ready

    graph_app = typer.Typer(name="graph", help="Dependency tracking.")
    graph_app.command()(ready)
    graph_app.command()(blocked)

    app.add_typer(graph_app, name="graph")
    app.add_typer(dep_app, name="dep")

def register_formatters() -> dict[str, type]:
    """Return formatter classes for registration."""
    from dodo.plugins.graph.tree import TreeFormatter
    return {"tree": TreeFormatter}
```

### 2. Plugin Registry

`dodo plugins scan` detects `COMMANDS` and `FORMATTERS` and stores them:

```json
// ~/.config/dodo/plugin_registry.json
{
  "graph": {
    "builtin": true,
    "hooks": ["register_commands", "register_root_commands", "register_formatters", "extend_adapter", "extend_formatter"],
    "commands": ["graph", "dep", "plugins/graph"],
    "formatters": ["tree"]
  },
  "ntfy-inbox": {
    "builtin": true,
    "hooks": ["register_commands"],
    "commands": ["plugins/ntfy-inbox"],
    "formatters": []
  },
  "sqlite": {
    "builtin": true,
    "hooks": ["register_adapter"],
    "commands": [],
    "formatters": []
  }
}
```

### 3. Config (Unchanged)

```json
// ~/.config/dodo/config.json
{
  "enabled_plugins": "graph,sqlite,ntfy-inbox",
  "default_adapter": "sqlite",
  ...
}
```

### 4. CLI Startup

Fast check at startup to register plugin commands only when needed:

```python
# src/dodo/cli.py

def _load_json(path: Path) -> dict:
    """Load JSON file, return empty dict if missing."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _get_plugin_for_command(argv: list[str]) -> str | None:
    """Check if argv matches an enabled plugin's command."""
    if len(argv) < 2:
        return None

    config_dir = Path.home() / ".config/dodo"
    registry = _load_json(config_dir / "plugin_registry.json")
    config = _load_json(config_dir / "config.json")
    enabled = set(config.get("enabled_plugins", "").split(","))

    # Build lookup key from argv
    if argv[1] == "plugins" and len(argv) > 2:
        key = f"plugins/{argv[2]}"
    else:
        key = argv[1]

    # Find plugin that owns this command
    for plugin_name, info in registry.items():
        if plugin_name in enabled and key in info.get("commands", []):
            return plugin_name

    return None


def _register_plugin_commands(plugin_name: str, is_root: bool) -> None:
    """Load plugin and register its commands."""
    from dodo.plugins import _import_plugin

    plugin = _import_plugin(plugin_name, path=None)  # builtin
    cfg = _get_config()

    if is_root and hasattr(plugin, "register_root_commands"):
        plugin.register_root_commands(app, cfg)
    elif hasattr(plugin, "register_commands"):
        from dodo.cli_plugins import plugins_app
        plugin.register_commands(plugins_app, cfg)


# At module load time
import sys
_plugin = _get_plugin_for_command(sys.argv)
if _plugin:
    _is_root = len(sys.argv) > 1 and sys.argv[1] != "plugins"
    _register_plugin_commands(_plugin, _is_root)
```

### 5. Formatter Loading

Lazy-load plugin formatters in `get_formatter()`:

```python
# src/dodo/formatters/__init__.py

FORMATTERS: dict[str, type] = {
    "table": TableFormatter,
    "jsonl": JsonlFormatter,
    "tsv": TsvFormatter,
}


def _get_plugin_formatter(name: str) -> type | None:
    """Load formatter from enabled plugin if available."""
    config_dir = Path.home() / ".config/dodo"
    registry_path = config_dir / "plugin_registry.json"
    config_path = config_dir / "config.json"

    if not registry_path.exists():
        return None

    registry = json.loads(registry_path.read_text())
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    enabled = set(config.get("enabled_plugins", "").split(","))

    for plugin_name, info in registry.items():
        if plugin_name in enabled and name in info.get("formatters", []):
            from dodo.plugins import _import_plugin
            plugin = _import_plugin(plugin_name, path=None)
            if hasattr(plugin, "register_formatters"):
                return plugin.register_formatters().get(name)

    return None


def get_formatter(format_str: str) -> FormatterProtocol:
    """Parse format string and return configured formatter."""
    parts = format_str.split(":")
    name = parts[0]

    # Check built-in formatters first
    if name in FORMATTERS:
        cls = FORMATTERS[name]
    else:
        # Check plugin formatters
        cls = _get_plugin_formatter(name)
        if cls is None:
            available = list(FORMATTERS.keys())
            # Could also list plugin formatters here
            raise ValueError(f"Unknown format: {name}. Available: {', '.join(available)}")

    # Build formatter with options
    if name == "table":
        datetime_fmt = parts[1] if len(parts) > 1 and parts[1] else DEFAULT_DATETIME_FMT
        show_id = len(parts) > 2 and parts[2] == "id"
        return cls(datetime_fmt=datetime_fmt, show_id=show_id)

    return cls()
```

### 6. Scan Updates

Update `_detect_*` functions to find `COMMANDS` and `FORMATTERS`:

```python
# src/dodo/plugins/__init__.py (or cli_plugins.py)

def _detect_commands(plugin_path: Path) -> list[str]:
    """Detect COMMANDS declaration in plugin."""
    content = (plugin_path / "__init__.py").read_text()
    match = re.search(r'COMMANDS\s*=\s*\[([^\]]*)\]', content)
    if match:
        items = match.group(1)
        return [s.strip().strip('"\'') for s in items.split(",") if s.strip()]
    return []


def _detect_formatters(plugin_path: Path) -> list[str]:
    """Detect FORMATTERS declaration in plugin."""
    content = (plugin_path / "__init__.py").read_text()
    match = re.search(r'FORMATTERS\s*=\s*\[([^\]]*)\]', content)
    if match:
        items = match.group(1)
        return [s.strip().strip('"\'') for s in items.split(",") if s.strip()]
    return []


def _scan_plugin_dir(plugins_dir: Path, builtin: bool) -> dict[str, dict]:
    """Scan a directory for plugins."""
    # ... existing code ...

    for entry in plugins_dir.iterdir():
        # ... existing detection ...

        hooks = _detect_hooks(entry)
        commands = _detect_commands(entry)
        formatters = _detect_formatters(entry)

        plugin_info = {
            "builtin": builtin,
            "hooks": hooks,
            "commands": commands,
            "formatters": formatters,
        }
        # ...
```

## Usage

After implementation:

```bash
# Root-level commands (new)
dodo graph ready          # List todos ready to work on
dodo graph blocked        # List blocked todos
dodo dep add X Y          # Add dependency
dodo dep list --tree      # Show dependency tree

# Nested commands (fixed)
dodo plugins graph ready  # Same as above, also works now

# Formatter (new)
dodo list -f tree         # Tree view of dependencies
dodo list -f table        # Default table view
```

## Migration

1. Run `dodo plugins scan` to update registry with new fields
2. Existing plugins without `COMMANDS`/`FORMATTERS` continue to work (empty arrays)
3. Graph plugin updated to declare its commands and formatters

## Performance

Startup overhead for non-plugin commands (`dodo add`, `dodo list -f table`):
- Read 2 small JSON files: ~0.2ms
- Parse JSON: ~0.2ms
- Dict lookup: ~0.01ms
- **Total: < 0.5ms**

Plugin commands (`dodo graph ready`, `dodo list -f tree`):
- Above checks + plugin import + command/formatter registration
- Similar to current behavior, only when actually needed

## Files to Modify

1. `src/dodo/plugins/__init__.py` - Add `_detect_commands`, `_detect_formatters`
2. `src/dodo/cli_plugins.py` - Update scan to include new fields
3. `src/dodo/cli.py` - Add `_get_plugin_for_command`, update startup
4. `src/dodo/formatters/__init__.py` - Add `_get_plugin_formatter`
5. `src/dodo/plugins/graph/__init__.py` - Add `COMMANDS`, `FORMATTERS`, `register_root_commands`, `register_formatters`
