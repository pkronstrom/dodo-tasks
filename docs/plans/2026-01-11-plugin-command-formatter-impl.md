# Plugin Command & Formatter Registration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable plugins to register CLI commands (root-level and nested) and custom formatters with lazy loading.

**Architecture:** Plugins declare `COMMANDS` and `FORMATTERS` lists in `__init__.py`. Scan detects these and stores in `plugin_registry.json`. At startup, fast JSON lookup determines if a plugin needs loading. Formatters loaded on-demand when requested.

**Tech Stack:** Python, Typer CLI, JSON registry

---

### Task 1: Update Scan to Detect COMMANDS and FORMATTERS

**Files:**
- Modify: `src/dodo/plugins/__init__.py`
- Modify: `src/dodo/cli_plugins.py`

**Step 1: Add detection functions to plugins/__init__.py**

Add after `_detect_hooks` function (~line 67):

```python
def _detect_commands(plugin_path: Path) -> list[str]:
    """Detect COMMANDS declaration in plugin __init__.py."""
    init_file = plugin_path / "__init__.py"
    if not init_file.exists():
        return []

    content = init_file.read_text()
    # Match COMMANDS = ["x", "y"] or COMMANDS = ['x', 'y']
    import re
    match = re.search(r'COMMANDS\s*=\s*\[([^\]]*)\]', content)
    if match:
        items = match.group(1)
        return [s.strip().strip('"\'') for s in items.split(",") if s.strip().strip('"\'')]
    return []


def _detect_formatters(plugin_path: Path) -> list[str]:
    """Detect FORMATTERS declaration in plugin __init__.py."""
    init_file = plugin_path / "__init__.py"
    if not init_file.exists():
        return []

    content = init_file.read_text()
    import re
    match = re.search(r'FORMATTERS\s*=\s*\[([^\]]*)\]', content)
    if match:
        items = match.group(1)
        return [s.strip().strip('"\'') for s in items.split(",") if s.strip().strip('"\'')]
    return []
```

**Step 2: Update _scan_plugin_dir to include commands and formatters**

In `_scan_plugin_dir` function (~line 119), add after `hooks = _detect_hooks(entry)`:

```python
        commands = _detect_commands(entry)
        formatters = _detect_formatters(entry)
```

And update `plugin_info` dict to include:

```python
        plugin_info: dict = {
            "builtin": builtin,
            "hooks": hooks,
            "commands": commands,
            "formatters": formatters,
            "version": version,
            "description": description,
        }
```

**Step 3: Mirror changes in cli_plugins.py**

The `cli_plugins.py` file has duplicate `_scan_plugin_dir` and `_detect_hooks` functions. Add the same `_detect_commands` and `_detect_formatters` functions and update `_scan_plugin_dir` identically.

**Step 4: Test scan detects new fields**

```bash
# First add COMMANDS/FORMATTERS to graph plugin (Task 2), then:
dodo plugins scan
cat ~/.config/dodo/plugin_registry.json | python3 -m json.tool
```

Expected: graph plugin entry includes `"commands": [...]` and `"formatters": [...]`

**Step 5: Commit**

```bash
git add src/dodo/plugins/__init__.py src/dodo/cli_plugins.py
git commit -m "feat: detect COMMANDS and FORMATTERS in plugin scan"
```

---

### Task 2: Declare Commands and Formatters in Graph Plugin

**Files:**
- Modify: `src/dodo/plugins/graph/__init__.py`

**Step 1: Add COMMANDS and FORMATTERS declarations**

Add after imports at top of file (~line 9):

```python
# Commands this plugin registers
# - Root level: "graph", "dep" (dodo graph, dodo dep)
# - Nested: "plugins/graph" (dodo plugins graph)
COMMANDS = ["graph", "dep", "plugins/graph"]

# Formatters this plugin provides
FORMATTERS = ["tree"]
```

**Step 2: Add register_root_commands function**

Add after `register_commands` function:

```python
def register_root_commands(app: typer.Typer, config: Config) -> None:
    """Register root-level commands (dodo graph, dodo dep)."""
    import typer as t

    from dodo.plugins.graph.cli import blocked, dep_app, ready

    graph_app = t.Typer(
        name="graph",
        help="Todo dependency tracking and visualization.",
        no_args_is_help=True,
    )
    graph_app.command()(ready)
    graph_app.command()(blocked)
    graph_app.add_typer(dep_app, name="dep")

    app.add_typer(graph_app, name="graph")
    app.add_typer(dep_app, name="dep")
```

**Step 3: Add register_formatters function**

Add after `register_root_commands`:

```python
def register_formatters() -> dict[str, type]:
    """Return formatter classes for registration."""
    from dodo.plugins.graph.tree import TreeFormatter

    return {"tree": TreeFormatter}
```

**Step 4: Run scan and verify**

```bash
dodo plugins scan
cat ~/.config/dodo/plugin_registry.json | grep -A5 '"graph"'
```

Expected output includes:
```json
"commands": ["graph", "dep", "plugins/graph"],
"formatters": ["tree"]
```

**Step 5: Commit**

```bash
git add src/dodo/plugins/graph/__init__.py
git commit -m "feat(graph): declare COMMANDS, FORMATTERS, add registration hooks"
```

---

### Task 3: Implement CLI Command Routing

**Files:**
- Modify: `src/dodo/cli.py`

**Step 1: Add helper to load config/registry JSON directly**

Add near top of file, after imports (~line 21):

```python
def _load_json_file(path: Path) -> dict:
    """Load JSON file directly, return empty dict if missing."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _get_config_dir() -> Path:
    """Get config directory path."""
    return Path.home() / ".config" / "dodo"
```

**Step 2: Add plugin command lookup function**

Add after the helpers above:

```python
def _get_plugin_for_command(argv: list[str]) -> tuple[str, bool] | None:
    """Check if argv matches an enabled plugin's command.

    Returns (plugin_name, is_root_command) or None if no match.
    """
    if len(argv) < 2:
        return None

    config_dir = _get_config_dir()
    registry = _load_json_file(config_dir / "plugin_registry.json")
    config = _load_json_file(config_dir / "config.json")
    enabled = set(filter(None, config.get("enabled_plugins", "").split(",")))

    # Build lookup key from argv
    if argv[1] == "plugins" and len(argv) > 2:
        key = f"plugins/{argv[2]}"
        is_root = False
    else:
        key = argv[1]
        is_root = True

    # Find plugin that owns this command
    for plugin_name, info in registry.items():
        if plugin_name in enabled and key in info.get("commands", []):
            return (plugin_name, is_root)

    return None
```

**Step 3: Add plugin command registration function**

```python
def _register_plugin_for_command(plugin_name: str, is_root: bool) -> None:
    """Load plugin and register its commands."""
    from dodo.plugins import _import_plugin

    plugin = _import_plugin(plugin_name, None)
    cfg = _get_config()

    if is_root and hasattr(plugin, "register_root_commands"):
        plugin.register_root_commands(app, cfg)
    elif hasattr(plugin, "register_commands"):
        from dodo.cli_plugins import plugins_app
        plugin.register_commands(plugins_app, cfg)
```

**Step 4: Add startup command routing**

Add before `_register_plugins_subapp()` call (~line 320):

```python
# Check if argv matches a plugin command and register it
import sys as _sys
_plugin_match = _get_plugin_for_command(_sys.argv)
if _plugin_match:
    _register_plugin_for_command(_plugin_match[0], _plugin_match[1])
```

**Step 5: Test root command works**

```bash
dodo graph ready
```

Expected: Shows ready todos (not "No such command")

**Step 6: Test nested command works**

```bash
dodo plugins graph ready
```

Expected: Same output as above

**Step 7: Test unrelated commands stay fast**

```bash
time dodo list -f table > /dev/null
```

Expected: Fast execution (< 200ms typically)

**Step 8: Commit**

```bash
git add src/dodo/cli.py
git commit -m "feat: lazy plugin command registration based on argv"
```

---

### Task 4: Implement Formatter Registration

**Files:**
- Modify: `src/dodo/formatters/__init__.py`

**Step 1: Add import for Path and json**

Add at top of file:

```python
import json
from pathlib import Path
```

**Step 2: Add plugin formatter loader**

Add after `get_formatter` function:

```python
def _get_plugin_formatter(name: str) -> type | None:
    """Load formatter from enabled plugin if available."""
    config_dir = Path.home() / ".config" / "dodo"
    registry_path = config_dir / "plugin_registry.json"
    config_path = config_dir / "config.json"

    if not registry_path.exists():
        return None

    try:
        registry = json.loads(registry_path.read_text())
    except json.JSONDecodeError:
        return None

    try:
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
    except json.JSONDecodeError:
        config = {}

    enabled = set(filter(None, config.get("enabled_plugins", "").split(",")))

    for plugin_name, info in registry.items():
        if plugin_name in enabled and name in info.get("formatters", []):
            from dodo.plugins import _import_plugin

            plugin = _import_plugin(plugin_name, None)
            if hasattr(plugin, "register_formatters"):
                formatters = plugin.register_formatters()
                return formatters.get(name)

    return None
```

**Step 3: Update get_formatter to check plugins**

Replace the `get_formatter` function:

```python
def get_formatter(format_str: str) -> FormatterProtocol:
    """Parse format string and return configured formatter.

    Format string syntax: <name>:<datetime_fmt>:<options>

    Examples:
        "table"           -> TableFormatter()
        "table:%Y-%m-%d"  -> TableFormatter(datetime_fmt="%Y-%m-%d")
        "table::id"       -> TableFormatter(show_id=True)
        "table:%m-%d:id"  -> TableFormatter(datetime_fmt="%m-%d", show_id=True)
        "jsonl"           -> JsonlFormatter()
        "tsv"             -> TsvFormatter()
        "tree"            -> TreeFormatter (from graph plugin)
    """
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
            raise ValueError(f"Unknown format: {name}. Available: {', '.join(available)}")

    # Build formatter with options (table-specific)
    if name == "table":
        datetime_fmt = parts[1] if len(parts) > 1 and parts[1] else DEFAULT_DATETIME_FMT
        show_id = len(parts) > 2 and parts[2] == "id"
        return cls(datetime_fmt=datetime_fmt, show_id=show_id)

    return cls()
```

**Step 4: Test tree formatter works**

```bash
dodo list -f tree
```

Expected: Shows todos in tree format with dependency hierarchy

**Step 5: Test built-in formatters still work**

```bash
dodo list -f table
dodo list -f tsv
dodo list -f jsonl
```

Expected: All work as before

**Step 6: Commit**

```bash
git add src/dodo/formatters/__init__.py
git commit -m "feat: lazy plugin formatter loading"
```

---

### Task 5: Final Testing and Cleanup

**Step 1: Rescan plugins to update registry**

```bash
dodo plugins scan
```

**Step 2: Verify all command paths work**

```bash
# Root commands
dodo graph ready
dodo graph blocked
dodo dep list

# Nested commands
dodo plugins graph ready
dodo plugins graph blocked
dodo plugins graph dep list

# Add a dependency
dodo dep add da5ef63f 34b47935 2>/dev/null || echo "Already exists or IDs changed"
```

**Step 3: Verify formatters work**

```bash
dodo list -f tree
dodo list -f table
```

**Step 4: Verify performance**

```bash
# These should be fast (no plugin loading needed)
time dodo add "test performance" && dodo undo
time dodo list > /dev/null
```

**Step 5: Final commit if any changes**

```bash
git status
# If clean, done. Otherwise:
git add -A
git commit -m "chore: final cleanup for plugin registration"
```

---

## Summary

| Task | What it does |
|------|--------------|
| 1 | Scan detects `COMMANDS` and `FORMATTERS` |
| 2 | Graph plugin declares its commands/formatters |
| 3 | CLI routes commands to plugins lazily |
| 4 | Formatters load from plugins on demand |
| 5 | Integration testing |

After completion:
- `dodo graph ready` works (root command)
- `dodo plugins graph ready` works (nested command)
- `dodo list -f tree` works (plugin formatter)
- `dodo add` / `dodo list` stay fast (no unnecessary plugin loading)
