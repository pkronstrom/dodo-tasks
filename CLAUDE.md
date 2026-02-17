# Dodo

Python 3.11+, Typer (CLI), Rich (UI), SQLite (default backend)

```bash
uv run pytest tests/     # Run tests
uv run ruff check src/   # Lint
```

## Structure
```
src/dodo/
├── models.py          # TodoItem, Status, Priority (frozen dataclasses, with due_at/metadata)
├── config.py          # Config with nested plugin config (plugins.<name>.<key>)
├── resolve.py         # Dodo resolution (local, global, mapped, git-based)
├── core.py            # TodoService - routes to backends
├── cli.py             # Typer commands (add, list, done, rm, new, destroy, meta, tag, due, etc.)
├── cli_bulk.py        # Bulk operations (bulk add/done/rm/edit/dep)
├── backends/
│   ├── base.py        # TodoBackend Protocol (add_tag, set_metadata_key, etc.), GraphCapable
│   ├── sqlite.py      # SQLite (default)
│   └── markdown.py    # File-based (dodo.md)
├── plugins/           # Hook-based plugin system
│   ├── ai/            # AI-assisted todo management
│   ├── graph/         # Dependency tracking
│   ├── ntfy_inbox/    # ntfy.sh todo ingestion
│   ├── obsidian/      # Obsidian vault backend
│   └── server/        # REST API, Web UI, MCP, remote backend
├── formatters/        # Output formatters (table, jsonl, tree, txt, md, csv)
└── ui/                # Interactive menus
```

## Key Patterns

- **TodoItem fields**: id, text, status, created_at, completed_at, project, priority, tags, due_at, metadata
- **Plugin hooks** in `__init__.py`: `register_commands`, `register_root_commands`, `register_config`, `register_backend`, `extend_backend`, `extend_formatter`
- **Plugin commands**: `register_commands` receives `plugins_app` (→ `dodo plugins <name> <cmd>`); `register_root_commands` receives root app. Declare `COMMANDS = ["plugins/<name>"]` for discoverability.
- **Lazy loading**: Backends/plugins registered as strings, imported on first use
- **Frozen dataclasses**: `TodoItem` is immutable; create new instances for modifications
- **Plugin config**: `cfg.get_plugin_config(name, key)` / `set_plugin_config()`
- **Dodo resolution** (`resolve.py`): `--global` → `--dodo <name>` → `.dodo/` in parents → dir mapping → git root hash
- **Testing**: Use `tmp_path` fixture; call `clear_*_cache()` helpers to ensure isolation
- Type hints on all public functions
