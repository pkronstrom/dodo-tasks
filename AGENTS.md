# Dodo - AI Assistant Instructions

## Stack
Python 3.11+, Typer (CLI), Rich (UI), httpx (HTTP), SQLite (stdlib)

## Commands
```bash
uv run dodo              # Interactive menu
uv run pytest tests/     # Run tests
uv run ruff check src/   # Lint
uv run mypy src/dodo/    # Type check
```

## Structure
```
src/dodo/
├── models.py          # TodoItem, Status, TodoItemView (frozen dataclasses)
├── config.py          # Config with autodiscoverable toggles
├── project.py         # Git/worktree project detection
├── storage.py         # Centralized storage path calculation
├── core.py            # TodoService - routes to adapters
├── cli.py             # Typer commands (add, list, done, rm, ai, plugins)
├── cli_plugins.py     # Plugin CLI: scan, enable, disable, run
├── ai.py              # LLM-assisted todo formatting
├── adapters/          # Core adapter only
│   ├── base.py        # TodoAdapter Protocol
│   ├── utils.py       # ID gen, line parsing
│   └── markdown.py    # File-based (dodo.md)
├── plugins/           # Hook-based plugin system
│   ├── __init__.py    # apply_hooks(), get_all_plugins(), _scan_and_save()
│   ├── sqlite/        # SQLite adapter plugin
│   ├── obsidian/      # Obsidian REST API plugin
│   ├── ntfy_inbox/    # ntfy.sh todo ingestion
│   └── graph/         # Dependency tracking
├── formatters/        # Output formatters (table, jsonl, tsv)
└── ui/                # Interactive menus
```

## Key Patterns

**Hook-based plugins**: Plugins implement hooks:
- `register_adapter` - Add adapter to registry
- `extend_adapter` - Wrap/modify adapter instance
- `register_config` - Declare config variables
- `register_commands` - Add CLI subcommands
- `extend_formatter` - Modify output formatting

**Lazy adapter loading**: Adapters registered as strings in `core.py`, imported on first use.

**Protocol-based adapters**: Implement `TodoAdapter` Protocol (`adapters/base.py`).

**Autodiscoverable config toggles**: Boolean attrs with `toggle_` prefix auto-appear in config menu.

**Project isolation**: Todos stored per-project using git root hash. Global in `~/.config/dodo/`.

**Frozen dataclasses**: `TodoItem` is immutable. Create new instances for modifications. Use `TodoItemView` wrapper to add fields.

**Centralized storage**: Use `storage.get_storage_path()` for adapter path calculations.

**Module-level caching**: `Config.load()`, `detect_project()`, plugin registry. Clear with `clear_*_cache()` in tests.

## Conventions
- TDD: Write tests before implementation
- Type hints on all public functions
- Config via `DODO_*` environment variables
- Plugins require explicit enable: `dodo plugins enable <name>`

## Testing
- Tests mirror source: `tests/test_adapters/`, `tests/test_plugins/`
- Use `tmp_path` fixture for file isolation
- `conftest.py` auto-clears all caches (autouse fixture)
