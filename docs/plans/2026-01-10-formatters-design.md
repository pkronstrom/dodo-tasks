# Output Formatters Design

## Overview

Add configurable output formatters to `dodo list` for better AI agent support and flexible human output.

## Problem

Currently `dodo list` output is hardcoded as a Rich table in `cli.py`. AI agents need machine-parseable formats like JSON or TSV.

## Solution

Create a `formatters` module with pluggable formatters, format string parsing with parameters, and config integration.

## Format String Syntax

```
<formatter>:<datetime_fmt>:<options>
```

Examples:
- `table` - Default Rich table, no ID column
- `table:%Y-%m-%d` - Custom datetime format
- `table:%m-%d:id` - Show ID column
- `table::id` - Default datetime, show ID
- `jsonl` - JSON lines (one object per line)
- `tsv` - Tab-separated: `id\tstatus\ttext`

## Module Structure

```
src/dodo/formatters/
├── __init__.py      # Exports, FORMATTERS dict, get_formatter()
├── base.py          # FormatterProtocol
├── table.py         # TableFormatter (Rich)
├── jsonl.py         # JsonlFormatter
└── tsv.py           # TsvFormatter
```

## Formatter Protocol

```python
from typing import Protocol
from dodo.models import TodoItem

class FormatterProtocol(Protocol):
    def format(self, items: list[TodoItem]) -> str: ...
```

## Formatter Implementations

### TableFormatter

```python
class TableFormatter:
    NAME = "table"

    def __init__(self, datetime_fmt: str = "%m-%d %H:%M", show_id: bool = False):
        self.datetime_fmt = datetime_fmt
        self.show_id = show_id

    def format(self, items: list[TodoItem]) -> str:
        # Build Rich Table, return rendered string
```

Datetime format uses `strftime()` with fallback on invalid format:

```python
def format_datetime(dt: datetime, fmt: str) -> str:
    try:
        return dt.strftime(fmt)
    except ValueError:
        return dt.strftime("%m-%d %H:%M")
```

### JsonlFormatter

```python
class JsonlFormatter:
    NAME = "jsonl"

    def format(self, items: list[TodoItem]) -> str:
        return "\n".join(
            json.dumps({
                "id": item.id,
                "text": item.text,
                "status": item.status.value,
                "created_at": item.created_at.isoformat(),
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "project": item.project,
            })
            for item in items
        )
```

### TsvFormatter

```python
class TsvFormatter:
    NAME = "tsv"

    def format(self, items: list[TodoItem]) -> str:
        return "\n".join(
            f"{item.id}\t{item.status.value}\t{item.text}"
            for item in items
        )
```

## Factory Function

Explicit registration (fast startup, no autodiscovery):

```python
from .table import TableFormatter
from .jsonl import JsonlFormatter
from .tsv import TsvFormatter

FORMATTERS = {
    "table": TableFormatter,
    "jsonl": JsonlFormatter,
    "tsv": TsvFormatter,
}

def get_formatter(format_str: str) -> FormatterProtocol:
    parts = format_str.split(":")
    name = parts[0]

    if name not in FORMATTERS:
        raise ValueError(f"Unknown format: {name}")

    cls = FORMATTERS[name]

    if name == "table":
        datetime_fmt = parts[1] if len(parts) > 1 and parts[1] else "%m-%d %H:%M"
        show_id = len(parts) > 2 and parts[2] == "id"
        return cls(datetime_fmt=datetime_fmt, show_id=show_id)

    return cls()
```

## CLI Integration

Add `--format` flag to `list_todos()`:

```python
@app.command(name="list")
def list_todos(
    project: Annotated[str | None, typer.Option("-p", "--project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    done: Annotated[bool, typer.Option("--done")] = False,
    all_: Annotated[bool, typer.Option("-a", "--all")] = False,
    format_: Annotated[str | None, typer.Option("-f", "--format")] = None,
):
    config = Config.load()
    # ... existing logic ...

    items = svc.list(status=status)

    format_str = format_ or config.default_format or "table"
    formatter = get_formatter(format_str)
    output = formatter.format(items)

    if format_str.startswith("table"):
        console.print(output)
    else:
        print(output)
```

## Config Integration

Add to `config.py`:

```python
# ConfigMeta.SETTINGS
"default_format": "Output format (table|jsonl|tsv)",

# Config.DEFAULTS
"default_format": "table",
```

Supports:
- `config.default_format` attribute access
- `config.set("default_format", "jsonl")` to persist
- `DODO_DEFAULT_FORMAT=jsonl` env override

## Output Examples

### table (default)

```
 Done   Created       Todo
────────────────────────────────────
 [x]    01-09 10:30   Buy milk
 [ ]    01-10 14:00   Call dentist
```

### table::id

```
 ID       Done   Created       Todo
────────────────────────────────────────
 abc123   [x]    01-09 10:30   Buy milk
 def456   [ ]    01-10 14:00   Call dentist
```

### jsonl

```json
{"id":"abc123","text":"Buy milk","status":"done","created_at":"2024-01-09T10:30:00","completed_at":null,"project":null}
{"id":"def456","text":"Call dentist","status":"pending","created_at":"2024-01-10T14:00:00","completed_at":null,"project":null}
```

### tsv

```
abc123	done	Buy milk
def456	pending	Call dentist
```

## Testing

Test cases:
- Each formatter produces expected output
- Format string parsing handles all parameter combinations
- Invalid format string raises ValueError
- Empty items list returns empty string
- Datetime format fallback on invalid strftime
