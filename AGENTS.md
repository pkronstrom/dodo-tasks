# Dodo - AI Assistant Instructions

## Stack
Python 3.11+, Typer (CLI), Rich (UI), httpx (HTTP), SQLite (stdlib)

## Commands
```bash
uv run dodo              # Interactive menu
uv run pytest tests/     # Run tests (75 total)
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
├── cli.py             # Typer commands (add, list, done, rm, ai)
├── ai.py              # LLM-assisted todo formatting
├── adapters/          # Storage backends
│   ├── base.py        # TodoAdapter Protocol
│   ├── markdown.py    # File-based (todo.md)
│   ├── sqlite.py      # Database (todos.db)
│   └── obsidian.py    # REST API backend
└── ui/                # Interactive menus
    ├── base.py        # MenuUI Protocol
    ├── rich_menu.py   # simple-term-menu wrapper
    └── interactive.py # Main interactive flow
```

## Key Patterns

**Protocol-based adapters**: All adapters implement `TodoAdapter` Protocol (`adapters/base.py:11`). Add new backends by implementing the 5 methods.

**Autodiscoverable config toggles**: Boolean attrs with `toggle_` prefix auto-appear in config menu (`config.py:15`).

**Project isolation**: Todos stored per-project using git root hash. Global todos in `~/.config/dodo/`.

**Frozen dataclasses**: `TodoItem` is immutable. Use `dataclasses.replace()` for modifications.

## Conventions
- TDD: Write tests before implementation
- Type hints on all public functions
- Config via `DODO_*` environment variables
- Adapters handle their own storage paths

## Testing
- Unit tests mirror source structure: `tests/test_adapters/test_*.py`
- Use `tmp_path` fixture for isolated file operations
- Mock external services (Obsidian) with `monkeypatch`
