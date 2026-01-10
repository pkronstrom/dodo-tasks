# Dodo - AI Assistant Instructions

## Stack
Python 3.11+, Typer (CLI), Rich (UI), httpx (HTTP), SQLite (stdlib)

## Commands
```bash
uv run dodo              # Interactive menu
uv run pytest tests/     # Run tests (135 total)
uv run ruff check src/   # Lint
uv run mypy src/dodo/    # Type check
```

## Structure
```
src/dodo/
├── models.py          # TodoItem, Status (frozen dataclasses)
├── config.py          # Config with autodiscoverable toggles
├── project.py         # Git/worktree project detection
├── core.py            # TodoService - routes to adapters
├── cli.py             # Typer commands (add, list, done, rm, ai, plugins)
├── cli_plugins.py     # Plugin commands (lazy-loaded)
├── plugins.py         # Plugin discovery, @env parsing
├── ai.py              # LLM-assisted todo formatting
├── adapters/          # Storage backends (lazy-loaded)
│   ├── base.py        # TodoAdapter Protocol
│   ├── utils.py       # Shared: ID gen, line parsing, formatting
│   ├── markdown.py    # File-based (todo.md)
│   ├── sqlite.py      # Database (todos.db)
│   └── obsidian.py    # REST API backend
├── formatters/        # Output formatters (table, jsonl, tsv)
└── ui/                # Interactive menus
    ├── base.py        # MenuUI Protocol
    ├── rich_menu.py   # simple-term-menu wrapper
    └── interactive.py # Main interactive flow

plugins/               # Standalone plugin scripts
└── ntfy-inbox/        # Receive todos via ntfy.sh
```

## Key Patterns

**Protocol-based adapters**: All adapters implement `TodoAdapter` Protocol (`adapters/base.py:11`). Add new backends by implementing the 5 methods.

**Autodiscoverable config toggles**: Boolean attrs with `toggle_` prefix auto-appear in config menu (`config.py:15`).

**Project isolation**: Todos stored per-project using git root hash. Global todos in `~/.config/dodo/`.

**Frozen dataclasses**: `TodoItem` is immutable. Use `dataclasses.replace()` for modifications.

**Plugin system**: Standalone scripts in `plugins/` with `@env` comments for config. Lazy-loaded to avoid CLI overhead.

**Lazy adapter loading**: Adapters imported only when used (`core.py:49-64`). Avoids ~53ms httpx import for markdown users.

**Module-level caching**: `Config.load()` and `detect_project()` cache results within single invocation. Clear with `clear_config_cache()` / `clear_project_cache()` in tests.

## Conventions
- TDD: Write tests before implementation
- Type hints on all public functions
- Config via `DODO_*` environment variables
- Adapters handle their own storage paths

## Testing
- Unit tests mirror source structure: `tests/test_adapters/test_*.py`
- Use `tmp_path` fixture for isolated file operations
- Mock external services (Obsidian) with `monkeypatch`
- `conftest.py` auto-clears caches between tests (autouse fixture)
