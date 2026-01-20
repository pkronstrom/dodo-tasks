# Dodo - AI Assistant Instructions

## Stack
Python 3.11+, Typer (CLI), Rich (UI), SQLite (default backend)

## Commands
```bash
uv run dodo              # Interactive menu
uv run pytest tests/     # Run tests
uv run ruff check src/   # Lint
```

## Structure
```
src/dodo/
├── models.py          # TodoItem, Status, Priority (frozen dataclasses)
├── config.py          # Config with nested plugin config (plugins.<name>.<key>)
├── resolve.py         # Dodo resolution (local, global, mapped, git-based)
├── core.py            # TodoService - routes to backends
├── cli.py             # Typer commands (add, list, done, rm, new, destroy, etc.)
├── cli_bulk.py        # Bulk operations (bulk add/done/rm/edit/dep)
├── bulk.py            # Smart input parser (JSONL, JSON array, plain IDs)
├── backends/          # Storage backends
│   ├── base.py        # TodoBackend Protocol, GraphCapable Protocol
│   ├── sqlite.py      # SQLite (default)
│   └── markdown.py    # File-based (dodo.md)
├── plugins/           # Hook-based plugin system
│   ├── __init__.py    # apply_hooks(), load_registry(), import_plugin()
│   ├── ai/            # AI-assisted todo management (add, prio, tag, run, dep)
│   ├── graph/         # Dependency tracking (blocked_by, ready, blocked)
│   ├── ntfy_inbox/    # ntfy.sh todo ingestion
│   └── obsidian/      # Obsidian vault backend
├── formatters/        # Output formatters (table, jsonl, tree, txt, md, csv)
└── ui/                # Interactive menus (interactive.py)
```

## Key Patterns

**Hook-based plugins**: Plugins declare hooks in `__init__.py`:
- `register_commands` - Add `dodo plugins <name> <cmd>`
- `register_root_commands` - Add top-level commands (`dodo graph`)
- `register_config` - Declare plugin config vars
- `register_backend` - Add backend to registry
- `extend_backend` / `extend_formatter` - Wrap instances

**Plugin commands**: Declare `COMMANDS = ["plugins/<name>"]` for discoverability.

**Lazy loading**: Backends/plugins registered as strings, imported on first use.

**Dodo resolution**: `resolve.py` determines which dodo to use:
1. `--global` flag → global
2. `--dodo <name>` → explicit
3. `.dodo/` in cwd/parents → local
4. Directory mapping → config-based
5. Git root hash → project-based

**Plugin config**: Use `cfg.get_plugin_config(name, key)` / `set_plugin_config()`.

**Frozen dataclasses**: `TodoItem` is immutable. Create new instances for modifications.

## Conventions
- Type hints on all public functions
- Plugins require explicit enable: `dodo plugins enable <name>`
- Plugin config in nested structure: `plugins.<name>.<key>`
