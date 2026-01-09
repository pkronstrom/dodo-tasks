# Dodo CLI Todo Manager - Design Document

## Overview

A modular CLI todo manager that routes todos to various backends (markdown files, SQLite, Obsidian, etc.) with smart project detection and AI-assisted todo creation.

## Key Features

- **Smart routing**: Adds to local project todo if exists, otherwise global
- **Multiple backends**: Markdown (default), SQLite, Obsidian REST API
- **AI-assisted**: `dodo ai` formats input and auto-splits into multiple todos
- **Interactive menu**: Rich TUI for config and todo management
- **Project detection**: Git-based with worktree support
- **Configurable**: Env vars with autodiscoverable toggles

## Project Structure

```
dodo/
├── pyproject.toml
├── .env.template
├── README.md
└── src/dodo/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py           # Typer commands
    ├── config.py        # Config with autodiscovery
    ├── core.py          # TodoService
    ├── project.py       # Git/worktree detection
    ├── models.py        # TodoItem, Status
    ├── ai.py            # AI integration
    ├── adapters/
    │   ├── __init__.py
    │   ├── base.py      # Protocol
    │   ├── markdown.py
    │   ├── sqlite.py
    │   └── obsidian.py
    └── ui/
        ├── __init__.py
        ├── base.py      # MenuUI protocol
        ├── rich_menu.py
        └── interactive.py
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `dodo` | Interactive menu |
| `dodo add "text"` | Add todo (local project or global) |
| `dodo add -g "text"` | Add to global list |
| `dodo list` | List pending todos |
| `dodo list --all` | List all todos |
| `dodo list --done` | List completed |
| `dodo done <id>` | Mark complete |
| `dodo rm <id>` | Delete todo |
| `dodo undo` | Undo last add |
| `dodo ai "text"` | AI-assisted add (returns 1 or many) |
| `dodo init` | Init project |
| `dodo config` | Interactive config editor |

## Design Decisions

### Project Identification

- Format: `dirname_shorthash` (e.g., `myapp_d1204e`)
- Uses SHA1 hash of absolute path for uniqueness
- Git root detection with worktree support
- Configurable: `worktree_shared` toggle for shared vs separate todos

### Storage Locations

- **Centralized (default)**: `~/.config/dodo/projects/<project-id>/todo.md`
- **In-project**: `./dodo.md` (when `local_storage` enabled)
- **Global**: `~/.config/dodo/todo.md`

### Todo Format (Markdown)

```md
- [ ] 2024-01-09 10:30 - Fix the login bug
- [x] 2024-01-09 09:15 - Add user validation
```

### Config System

Following pyafk pattern:
- `ConfigMeta` - Schema definition (TOGGLES, SETTINGS)
- `Config` - Runtime with `Config.load()` factory
- Precedence: defaults → config.json → DODO_* env vars
- Autodiscoverable toggles for interactive menu

### Adapter Protocol

```python
class TodoAdapter(Protocol):
    def add(self, text: str, project: str | None = None) -> TodoItem: ...
    def list(self, project: str | None = None, status: Status | None = None) -> list[TodoItem]: ...
    def get(self, id: str) -> TodoItem | None: ...
    def update(self, id: str, status: Status) -> TodoItem: ...
    def delete(self, id: str) -> None: ...
```

### AI Integration

- Default backend: `llm` CLI (configurable via `DODO_AI_COMMAND`)
- Returns JSON array of todo items
- Schema enforcement where supported (claude, llm, codex)
- Auto-detects piped input, adds context

**Config:**
```bash
DODO_AI_COMMAND="llm '{{prompt}}' -s '{{system}}' --schema '{{schema}}'"
DODO_AI_SYS_PROMPT="You are a todo formatter. Return a JSON array..."
```

### UI Layer

- `MenuUI` protocol for swappable implementations
- Default: Rich + simple-term-menu
- Abstracted for future rich-live-menu library

## Dependencies

```
typer>=0.9.0
rich>=13.0.0
simple-term-menu>=1.6.0
httpx>=0.27.0
```

## Adapters

### Markdown (default)
- Simple checklist format
- Extensible via `MarkdownFormat` dataclass
- Override `_parse_line`/`_format_item` for custom formats

### SQLite
- Better for large lists and complex queries
- Indexed by project and status
- UUID-based IDs

### Obsidian
- Uses Local REST API plugin (port 27124)
- Same markdown format as file adapter
- Configurable vault path
