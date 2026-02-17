# Dodo Python API Design

## Goal

Expose a public Python API (`dodo.api`) for programmatic access to dodo from external tools. First consumer: NH integration. Eliminates subprocess overhead and JSONL parsing.

## API Surface

```python
from dodo.api import Dodo

# Construction — always explicit, no implicit cwd magic
d = Dodo.named("work")               # ~/.config/dodo/work/
d = Dodo.local("/path/to/proj")      # .dodo/ at that path
d = Dodo.auto()                      # cwd-based resolve, same as CLI

# CRUD
item = d.add("Fix bug", priority="high", tags=["backend"], due="2026-03-01")
items = d.list()                      # list[TodoItem]
items = d.list(status="done")         # filtered
item = d.get("abc123")                # TodoItem | None
item = d.complete("abc123")           # returns updated TodoItem
d.delete("abc123")                    # raises KeyError if missing

# General update — kwargs for each field, sentinel distinguishes "not provided" from None
item = d.update("abc123", text="New text")
item = d.update("abc123", priority="critical", due="2026-04-01")
item = d.update("abc123", priority=None)   # clear priority
item = d.update("abc123", due=None)        # clear due date

# Atomic ops
item = d.add_tag("abc123", "urgent")
item = d.remove_tag("abc123", "urgent")
item = d.set_meta("abc123", "state", "wip")
item = d.remove_meta("abc123", "state")
```

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Return type | `TodoItem` directly | Frozen dataclass, already stable, has `.to_dict()` for dict access |
| Resolution | Explicit classmethods only | No bare constructor, no implicit cwd detection |
| Enum inputs | Strings (`"high"`, `"done"`) | Consumers only import `Dodo`, API coerces internally |
| Error handling | Standard exceptions | `KeyError` (not found), `ValueError` (bad input) |
| Atomic ops | Included | Prevents read-modify-write races, only 4 extra methods |
| Update API | Single `update()` with kwargs | Sentinel default distinguishes "clear" (`None`) from "unchanged" (omitted) |

## Internals

### `Dodo` class

Thin wrapper over `TodoService`. Constructor takes a `TodoService` (private by convention). Each classmethod wires `Config` + resolve + `TodoService`:

```python
class Dodo:
    _UNSET = object()

    def __init__(self, service: TodoService):
        self._svc = service

    @classmethod
    def named(cls, name: str) -> Dodo:
        config = Config.load()
        return cls(TodoService(config, project_id=name))

    @classmethod
    def local(cls, path: str | Path) -> Dodo:
        config = Config.load()
        dodo_dir = Path(path) / ".dodo"
        return cls(TodoService(config, storage_path=dodo_dir))

    @classmethod
    def auto(cls) -> Dodo:
        config = Config.load()
        name, path = resolve_dodo(config)
        return cls(TodoService(config, project_id=name, storage_path=path))
```

### Coercion

Two internal helpers:

- `_to_priority(str | None) -> Priority | None` — lowercases, converts via `Priority(value)`, raises `ValueError` with valid options on failure.
- `_to_status(str | None) -> Status | None` — same pattern.
- Due dates: `str | datetime | None` — strings parsed with `datetime.fromisoformat()`, `datetime` passed through, `None` clears.

### Update method

```python
def update(self, id: str, *, text=_UNSET, priority=_UNSET,
           due=_UNSET, tags=_UNSET, metadata=_UNSET) -> TodoItem:
```

Calls the specific `TodoService` method for each provided kwarg. Sentinel `_UNSET` means "don't change", `None` means "clear".

## File

Single file: `src/dodo/api.py`, ~80-100 lines. No new dependencies.
