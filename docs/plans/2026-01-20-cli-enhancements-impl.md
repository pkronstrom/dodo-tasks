# CLI Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance dodo CLI with better flags, bulk operations, undo, export formats, and simplified project detection.

**Architecture:** Incremental changes organized by feature. Each task is self-contained and testable. Start with simple changes (formatters, flags) before complex ones (bulk, undo, detection).

**Tech Stack:** Python 3.11+, Typer CLI, Rich for output, pytest for testing

---

## Task 1: Add Txt Formatter

**Files:**
- Create: `src/dodo/formatters/txt.py`
- Modify: `src/dodo/formatters/__init__.py`
- Test: `tests/test_formatters.py`

**Step 1: Write the failing test**

Add to `tests/test_formatters.py`:

```python
class TestTxtFormatter:
    def test_format_empty(self):
        from dodo.formatters.txt import TxtFormatter

        formatter = TxtFormatter()
        output = formatter.format([])
        assert output == ""

    def test_format_simple(self, sample_items):
        from dodo.formatters.txt import TxtFormatter

        formatter = TxtFormatter()
        output = formatter.format(sample_items)
        lines = output.strip().split("\n")
        assert lines[0] == "Buy milk"
        assert lines[1] == "Call dentist"

    def test_format_with_priority(self):
        from dodo.formatters.txt import TxtFormatter
        from dodo.models import Priority, Status, TodoItem
        from datetime import datetime

        item = TodoItem(
            id="test1",
            text="Important task",
            status=Status.PENDING,
            priority=Priority.HIGH,
            created_at=datetime.now(),
        )
        formatter = TxtFormatter()
        output = formatter.format([item])
        assert output == "Important task !high"

    def test_format_with_tags(self):
        from dodo.formatters.txt import TxtFormatter
        from dodo.models import Status, TodoItem
        from datetime import datetime

        item = TodoItem(
            id="test1",
            text="Tagged task",
            status=Status.PENDING,
            tags=["work", "urgent"],
            created_at=datetime.now(),
        )
        formatter = TxtFormatter()
        output = formatter.format([item])
        assert output == "Tagged task #work #urgent"

    def test_format_with_priority_and_tags(self):
        from dodo.formatters.txt import TxtFormatter
        from dodo.models import Priority, Status, TodoItem
        from datetime import datetime

        item = TodoItem(
            id="test1",
            text="Full task",
            status=Status.PENDING,
            priority=Priority.CRITICAL,
            tags=["work"],
            created_at=datetime.now(),
        )
        formatter = TxtFormatter()
        output = formatter.format([item])
        assert output == "Full task !critical #work"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_formatters.py::TestTxtFormatter -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'dodo.formatters.txt'"

**Step 3: Create txt formatter**

Create `src/dodo/formatters/txt.py`:

```python
"""Plain text formatter."""

from dodo.models import TodoItem


class TxtFormatter:
    """Format todos as plain text lines with priority and tags."""

    NAME = "txt"

    def format(self, items: list[TodoItem]) -> str:
        if not items:
            return ""

        lines = []
        for item in items:
            line = item.text
            if item.priority:
                line += f" !{item.priority.value}"
            if item.tags:
                line += " " + " ".join(f"#{t}" for t in item.tags)
            lines.append(line)

        return "\n".join(lines)
```

**Step 4: Register formatter**

Edit `src/dodo/formatters/__init__.py`, add to imports and FORMATTERS dict:

```python
from .txt import TxtFormatter

FORMATTERS: dict[str, type] = {
    "table": TableFormatter,
    "jsonl": JsonlFormatter,
    "tsv": TsvFormatter,
    "csv": CsvFormatter,
    "txt": TxtFormatter,
}
```

Also add to `__all__`:

```python
__all__ = [
    ...
    "TxtFormatter",
    ...
]
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_formatters.py::TestTxtFormatter -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add src/dodo/formatters/txt.py src/dodo/formatters/__init__.py tests/test_formatters.py
git commit -m "feat(formatters): add txt formatter with priority and tags"
```

---

## Task 2: Add Markdown Formatter

**Files:**
- Create: `src/dodo/formatters/markdown.py`
- Modify: `src/dodo/formatters/__init__.py`
- Test: `tests/test_formatters.py`

**Step 1: Write the failing test**

Add to `tests/test_formatters.py`:

```python
class TestMarkdownFormatter:
    def test_format_empty(self):
        from dodo.formatters.markdown import MarkdownFormatter

        formatter = MarkdownFormatter()
        output = formatter.format([])
        assert output == ""

    def test_format_pending(self):
        from dodo.formatters.markdown import MarkdownFormatter
        from dodo.models import Status, TodoItem
        from datetime import datetime

        item = TodoItem(
            id="test1",
            text="Pending task",
            status=Status.PENDING,
            created_at=datetime.now(),
        )
        formatter = MarkdownFormatter()
        output = formatter.format([item])
        assert output == "- [ ] Pending task"

    def test_format_done(self):
        from dodo.formatters.markdown import MarkdownFormatter
        from dodo.models import Status, TodoItem
        from datetime import datetime

        item = TodoItem(
            id="test1",
            text="Done task",
            status=Status.DONE,
            created_at=datetime.now(),
        )
        formatter = MarkdownFormatter()
        output = formatter.format([item])
        assert output == "- [x] Done task"

    def test_format_with_priority_and_tags(self):
        from dodo.formatters.markdown import MarkdownFormatter
        from dodo.models import Priority, Status, TodoItem
        from datetime import datetime

        item = TodoItem(
            id="test1",
            text="Full task",
            status=Status.PENDING,
            priority=Priority.HIGH,
            tags=["work", "urgent"],
            created_at=datetime.now(),
        )
        formatter = MarkdownFormatter()
        output = formatter.format([item])
        assert output == "- [ ] Full task !high #work #urgent"

    def test_format_multiple(self, sample_items):
        from dodo.formatters.markdown import MarkdownFormatter

        formatter = MarkdownFormatter()
        output = formatter.format(sample_items)
        lines = output.strip().split("\n")
        assert lines[0] == "- [x] Buy milk"
        assert lines[1] == "- [ ] Call dentist"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_formatters.py::TestMarkdownFormatter -v
```

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create markdown formatter**

Create `src/dodo/formatters/markdown.py`:

```python
"""Markdown checkbox formatter."""

from dodo.models import Status, TodoItem


class MarkdownFormatter:
    """Format todos as markdown checkbox list."""

    NAME = "md"

    def format(self, items: list[TodoItem]) -> str:
        if not items:
            return ""

        lines = []
        for item in items:
            checkbox = "[x]" if item.status == Status.DONE else "[ ]"
            line = f"- {checkbox} {item.text}"
            if item.priority:
                line += f" !{item.priority.value}"
            if item.tags:
                line += " " + " ".join(f"#{t}" for t in item.tags)
            lines.append(line)

        return "\n".join(lines)
```

**Step 4: Register formatter**

Edit `src/dodo/formatters/__init__.py`:

```python
from .markdown import MarkdownFormatter

FORMATTERS: dict[str, type] = {
    ...
    "md": MarkdownFormatter,
}
```

Add to `__all__`: `"MarkdownFormatter",`

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_formatters.py::TestMarkdownFormatter -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add src/dodo/formatters/markdown.py src/dodo/formatters/__init__.py tests/test_formatters.py
git commit -m "feat(formatters): add markdown checkbox formatter"
```

---

## Task 3: Add Export --format Flag

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestCliExport:
    def test_export_default_jsonl(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Test todo"])
            result = runner.invoke(app, ["export"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert '"text": "Test todo"' in result.stdout

    def test_export_format_txt(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Test todo"])
            result = runner.invoke(app, ["export", "--format", "txt"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert result.stdout.strip() == "Test todo"

    def test_export_format_md(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Test todo"])
            result = runner.invoke(app, ["export", "--format", "md"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert result.stdout.strip() == "- [ ] Test todo"

    def test_export_format_csv(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Test todo"])
            result = runner.invoke(app, ["export", "--format", "csv"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "id,status,text" in result.stdout

    def test_export_format_short_flag(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Test todo"])
            result = runner.invoke(app, ["export", "-f", "txt"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert result.stdout.strip() == "Test todo"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py::TestCliExport -v
```

Expected: FAIL (--format not recognized or wrong output)

**Step 3: Update export command**

In `src/dodo/cli.py`, update the `export` command:

```python
@app.command()
def export(
    output: Annotated[str | None, typer.Option("-o", "--output", help="Output file")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Global todos")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    format_: Annotated[str, typer.Option("-f", "--format", help="Output format: jsonl, csv, tsv, txt, md")] = "jsonl",
):
    """Export todos to various formats."""
    from dodo.formatters import get_formatter

    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)
    items = svc.list()

    try:
        formatter = get_formatter(format_)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    content = formatter.format(items)

    if output:
        from pathlib import Path

        Path(output).write_text(content + "\n" if content else "")
        console.print(f"[green]✓[/green] Exported {len(items)} todos to {output}")
    else:
        console.print(content)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli.py::TestCliExport -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): add --format flag to export command"
```

---

## Task 4: Add -p and -t Flags to Add Command

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestCliAddFlags:
    def test_add_priority_short_flag(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["add", "Task", "-p", "high"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Task" in result.stdout

    def test_add_tag_short_flag(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["add", "Task", "-t", "work"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Task" in result.stdout

    def test_add_tag_comma_separated(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Task", "-t", "work,urgent"])
            result = runner.invoke(app, ["export", "-f", "txt"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "#work" in result.stdout
        assert "#urgent" in result.stdout

    def test_add_tag_multiple_flags(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Task", "-t", "work", "-t", "urgent"])
            result = runner.invoke(app, ["export", "-f", "txt"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "#work" in result.stdout
        assert "#urgent" in result.stdout

    def test_add_tag_mixed(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Task", "-t", "work,urgent", "-t", "home"])
            result = runner.invoke(app, ["export", "-f", "txt"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "#work" in result.stdout
        assert "#urgent" in result.stdout
        assert "#home" in result.stdout

    def test_add_priority_and_tags(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Task", "-p", "high", "-t", "work"])
            result = runner.invoke(app, ["export", "-f", "txt"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "!high" in result.stdout
        assert "#work" in result.stdout
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py::TestCliAddFlags -v
```

Expected: FAIL (short flags not recognized)

**Step 3: Update add command**

In `src/dodo/cli.py`, update the `add` command signature:

```python
@app.command()
def add(
    text: Annotated[str, typer.Argument(help="Todo text (use quotes)")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    priority: Annotated[
        str | None,
        typer.Option("-p", "--priority", help="Priority: critical/high/normal/low/someday"),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("-t", "--tag", help="Tag (can repeat, comma-separated)"),
    ] = None,
    # Keep old --tags for backward compatibility
    tags: Annotated[str | None, typer.Option("--tags", help="Comma-separated tags (deprecated, use -t)")] = None,
):
    """Add a todo item."""
    from dodo.models import Priority

    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
        target = dodo_id or "local"
    else:
        svc = _get_service(cfg, dodo_id)
        target = dodo_id or "global"

    # Parse priority
    parsed_priority = None
    if priority:
        try:
            parsed_priority = Priority(priority.lower())
        except ValueError:
            console.print(
                f"[red]Error:[/red] Invalid priority '{priority}'. Use: critical/high/normal/low/someday"
            )
            raise typer.Exit(1)

    # Parse tags - merge from multiple sources
    parsed_tags = []

    # Handle new -t/--tag flags (list of potentially comma-separated values)
    if tag:
        for t in tag:
            parsed_tags.extend(x.strip() for x in t.split(",") if x.strip())

    # Handle old --tags flag for backward compatibility
    if tags:
        parsed_tags.extend(x.strip() for x in tags.split(",") if x.strip())

    # Deduplicate while preserving order
    seen = set()
    unique_tags = []
    for t in parsed_tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)

    parsed_tags = unique_tags if unique_tags else None

    item = svc.add(text, priority=parsed_priority, tags=parsed_tags)

    _save_last_action("add", item.id, target)

    dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"
    console.print(f"[green]✓[/green] Added to {dest}: {item.text} [dim]({item.id})[/dim]")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli.py::TestCliAddFlags -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): add -p and -t short flags for add command"
```

---

## Task 5: Create Bulk Input Parser

**Files:**
- Create: `src/dodo/bulk.py`
- Test: `tests/test_bulk.py`

**Step 1: Write the failing test**

Create `tests/test_bulk.py`:

```python
"""Tests for bulk input parser."""

import pytest

from dodo.bulk import parse_bulk_input, BulkInputType


class TestBulkInputParser:
    def test_parse_jsonl(self):
        input_text = '{"id": "abc123"}\n{"id": "def456"}'
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.JSONL
        assert result.items == [{"id": "abc123"}, {"id": "def456"}]

    def test_parse_json_array(self):
        input_text = '["abc123", "def456"]'
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.JSON_ARRAY
        assert result.items == ["abc123", "def456"]

    def test_parse_plain_ids(self):
        input_text = "abc123\ndef456\nghi789"
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.PLAIN_IDS
        assert result.items == ["abc123", "def456", "ghi789"]

    def test_parse_comma_separated(self):
        input_text = "abc123, def456, ghi789"
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.COMMA_SEPARATED
        assert result.items == ["abc123", "def456", "ghi789"]

    def test_parse_empty(self):
        result = parse_bulk_input("")
        assert result.items == []

    def test_parse_whitespace_only(self):
        result = parse_bulk_input("   \n   ")
        assert result.items == []

    def test_parse_jsonl_with_empty_lines(self):
        input_text = '{"id": "abc123"}\n\n{"id": "def456"}\n'
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.JSONL
        assert len(result.items) == 2

    def test_parse_ids_strips_whitespace(self):
        input_text = "  abc123  \n  def456  "
        result = parse_bulk_input(input_text)
        assert result.items == ["abc123", "def456"]


class TestBulkInputFromArgs:
    def test_from_args(self):
        from dodo.bulk import parse_bulk_args

        result = parse_bulk_args(["abc123", "def456"])
        assert result.items == ["abc123", "def456"]

    def test_from_args_empty(self):
        from dodo.bulk import parse_bulk_args

        result = parse_bulk_args([])
        assert result.items == []
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_bulk.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'dodo.bulk'"

**Step 3: Create bulk parser**

Create `src/dodo/bulk.py`:

```python
"""Bulk input parser for dodo CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum


class BulkInputType(Enum):
    """Type of bulk input detected."""

    JSONL = "jsonl"
    JSON_ARRAY = "json_array"
    PLAIN_IDS = "plain_ids"
    COMMA_SEPARATED = "comma_separated"
    ARGS = "args"
    EMPTY = "empty"


@dataclass
class BulkInput:
    """Parsed bulk input."""

    type: BulkInputType
    items: list  # list of dicts for JSONL, list of strings for IDs


def parse_bulk_input(text: str) -> BulkInput:
    """Parse bulk input, auto-detecting format.

    Supports:
    - JSONL: lines starting with {
    - JSON array: input starts with [
    - Plain IDs: one per line
    - Comma-separated: single line with commas
    """
    text = text.strip()

    if not text:
        return BulkInput(type=BulkInputType.EMPTY, items=[])

    # Try JSON array first
    if text.startswith("["):
        try:
            items = json.loads(text)
            if isinstance(items, list):
                return BulkInput(type=BulkInputType.JSON_ARRAY, items=items)
        except json.JSONDecodeError:
            pass

    # Try JSONL (lines starting with {)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines and lines[0].startswith("{"):
        items = []
        for line in lines:
            if line.startswith("{"):
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Skip invalid lines
        if items:
            return BulkInput(type=BulkInputType.JSONL, items=items)

    # Check for comma-separated (single line with commas)
    if len(lines) == 1 and "," in lines[0]:
        items = [item.strip() for item in lines[0].split(",") if item.strip()]
        return BulkInput(type=BulkInputType.COMMA_SEPARATED, items=items)

    # Plain IDs (one per line)
    items = [line.strip() for line in lines if line.strip()]
    return BulkInput(type=BulkInputType.PLAIN_IDS, items=items)


def parse_bulk_args(args: list[str]) -> BulkInput:
    """Parse bulk input from command line arguments."""
    if not args:
        return BulkInput(type=BulkInputType.EMPTY, items=[])
    return BulkInput(type=BulkInputType.ARGS, items=list(args))
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_bulk.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/bulk.py tests/test_bulk.py
git commit -m "feat(bulk): add smart bulk input parser"
```

---

## Task 6: Add Bulk Subcommand (done/rm)

**Files:**
- Create: `src/dodo/cli_bulk.py`
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli_bulk.py`

**Step 1: Write the failing test**

Create `tests/test_cli_bulk.py`:

```python
"""Tests for bulk CLI commands."""

import sys
from io import StringIO
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dodo.cli import app
from dodo.config import clear_config_cache

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Set up isolated environment for CLI tests."""
    clear_config_cache()
    config_dir = tmp_path / ".config" / "dodo"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return config_dir


class TestBulkDone:
    def test_bulk_done_args(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            # Add some todos
            r1 = runner.invoke(app, ["add", "Task 1"])
            r2 = runner.invoke(app, ["add", "Task 2"])

            # Extract IDs from output
            id1 = r1.stdout.split("(")[1].split(")")[0]
            id2 = r2.stdout.split("(")[1].split(")")[0]

            # Bulk done
            result = runner.invoke(app, ["bulk", "done", id1, id2])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "2" in result.stdout  # Should mention 2 items

    def test_bulk_done_stdin(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            # Bulk done via stdin
            result = runner.invoke(app, ["bulk", "done"], input=id1)

        assert result.exit_code == 0, f"Failed: {result.output}"


class TestBulkRm:
    def test_bulk_rm_args(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            r2 = runner.invoke(app, ["add", "Task 2"])

            id1 = r1.stdout.split("(")[1].split(")")[0]
            id2 = r2.stdout.split("(")[1].split(")")[0]

            result = runner.invoke(app, ["bulk", "rm", id1, id2])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "2" in result.stdout


class TestBulkAdd:
    def test_bulk_add_jsonl(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            jsonl = '{"text": "Task 1"}\n{"text": "Task 2"}'
            result = runner.invoke(app, ["bulk", "add"], input=jsonl)

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "2" in result.stdout
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli_bulk.py -v
```

Expected: FAIL (no "bulk" command)

**Step 3: Create bulk CLI subcommand**

Create `src/dodo/cli_bulk.py`:

```python
"""Bulk CLI commands."""

from __future__ import annotations

import sys
from typing import Annotated

import typer
from rich.console import Console

console = Console()

bulk_app = typer.Typer(
    name="bulk",
    help="Bulk operations on todos.",
    no_args_is_help=True,
)


def _get_config():
    from dodo.config import Config
    return Config.load()


def _resolve_dodo(config, dodo_name=None, global_=False):
    from dodo.resolve import resolve_dodo
    result = resolve_dodo(config, dodo_name, global_)
    return result.name, result.path


def _get_service(config, project_id):
    from dodo.core import TodoService
    return TodoService(config, project_id)


def _get_service_with_path(config, path):
    from dodo.core import TodoService
    return TodoService(config, project_id=None, storage_path=path)


def _get_ids_from_input(args: list[str]) -> list[str]:
    """Get IDs from args or stdin."""
    from dodo.bulk import parse_bulk_args, parse_bulk_input

    if args:
        return parse_bulk_args(args).items

    # Read from stdin if no args
    if not sys.stdin.isatty():
        text = sys.stdin.read()
        result = parse_bulk_input(text)
        # For non-JSONL input, items are IDs
        if result.items and isinstance(result.items[0], str):
            return result.items
        # For JSONL, extract IDs
        return [item.get("id") for item in result.items if item.get("id")]

    return []


def _save_bulk_undo(action: str, items: list, target: str):
    """Save undo state for bulk operation."""
    import json
    from dodo.config import Config

    cfg = Config.load()
    state_file = cfg.config_dir / ".last_action"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert TodoItem objects to dicts
    items_data = []
    for item in items:
        if hasattr(item, "to_dict"):
            items_data.append(item.to_dict())
        elif isinstance(item, dict):
            items_data.append(item)

    state_file.write_text(json.dumps({
        "action": action,
        "target": target,
        "items": items_data,
    }))


@bulk_app.command()
def done(
    ids: Annotated[list[str] | None, typer.Argument(help="Todo IDs")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Mark multiple todos as done."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"
    id_list = _get_ids_from_input(ids or [])

    if not id_list:
        console.print("[yellow]No IDs provided[/yellow]")
        raise typer.Exit(1)

    # Store snapshots for undo
    snapshots = []
    completed = 0

    for id_ in id_list:
        item = svc.get(id_)
        if item:
            snapshots.append(item)
            svc.complete(id_)
            completed += 1
            if quiet:
                console.print(id_)
            else:
                console.print(f"[green]✓[/green] {id_}: {item.text[:50]}")
        else:
            if not quiet:
                console.print(f"[yellow]![/yellow] {id_}: not found")

    if snapshots:
        _save_bulk_undo("done", snapshots, target)

    if not quiet:
        console.print(f"[dim]Completed {completed} todos[/dim]")


@bulk_app.command()
def rm(
    ids: Annotated[list[str] | None, typer.Argument(help="Todo IDs")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Remove multiple todos."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"
    id_list = _get_ids_from_input(ids or [])

    if not id_list:
        console.print("[yellow]No IDs provided[/yellow]")
        raise typer.Exit(1)

    # Store snapshots for undo
    snapshots = []
    removed = 0

    for id_ in id_list:
        item = svc.get(id_)
        if item:
            snapshots.append(item)
            svc.delete(id_)
            removed += 1
            if quiet:
                console.print(id_)
            else:
                console.print(f"[yellow]✓[/yellow] {id_}: {item.text[:50]}")
        else:
            if not quiet:
                console.print(f"[yellow]![/yellow] {id_}: not found")

    if snapshots:
        _save_bulk_undo("rm", snapshots, target)

    if not quiet:
        console.print(f"[dim]Removed {removed} todos[/dim]")


@bulk_app.command()
def remove(
    ids: Annotated[list[str] | None, typer.Argument(help="Todo IDs")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Remove multiple todos (alias for rm)."""
    rm(ids, global_, dodo, quiet)


@bulk_app.command()
def add(
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Bulk add todos from JSONL stdin."""
    import json
    from dodo.models import Priority

    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"

    if sys.stdin.isatty():
        console.print("[yellow]No input provided. Pipe JSONL to stdin.[/yellow]")
        raise typer.Exit(1)

    text = sys.stdin.read().strip()
    if not text:
        console.print("[yellow]Empty input[/yellow]")
        raise typer.Exit(1)

    from dodo.bulk import parse_bulk_input
    result = parse_bulk_input(text)

    added_items = []
    prev_id = None
    errors = 0

    for data in result.items:
        if not isinstance(data, dict):
            errors += 1
            continue

        item_text = data.get("text", "")
        if not item_text:
            errors += 1
            continue

        # Replace $prev placeholder
        if prev_id and "$prev" in item_text:
            item_text = item_text.replace("$prev", prev_id)

        # Parse priority
        parsed_priority = None
        if prio_str := data.get("priority"):
            try:
                parsed_priority = Priority(prio_str.lower())
            except ValueError:
                pass

        # Parse tags
        parsed_tags = data.get("tags")
        if parsed_tags and not isinstance(parsed_tags, list):
            parsed_tags = None

        item = svc.add(item_text, priority=parsed_priority, tags=parsed_tags)
        added_items.append(item)
        prev_id = item.id

        if quiet:
            console.print(item.id)
        else:
            console.print(f"[green]✓[/green] {item.id}: {item.text[:50]}")

    if added_items:
        _save_bulk_undo("add", added_items, target)

    if not quiet:
        console.print(f"[dim]Added {len(added_items)} todos ({errors} errors)[/dim]")
```

**Step 4: Register bulk subcommand**

In `src/dodo/cli.py`, add after other imports:

```python
from dodo.cli_bulk import bulk_app
```

And near the end of the file, before the helpers section:

```python
app.add_typer(bulk_app, name="bulk")
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_cli_bulk.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add src/dodo/cli_bulk.py src/dodo/cli.py tests/test_cli_bulk.py
git commit -m "feat(cli): add bulk subcommand for done/rm/add"
```

---

## Task 7: Add Bulk Edit Command

**Files:**
- Modify: `src/dodo/cli_bulk.py`
- Test: `tests/test_cli_bulk.py`

**Step 1: Write the failing test**

Add to `tests/test_cli_bulk.py`:

```python
class TestBulkEdit:
    def test_bulk_edit_priority_args(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            result = runner.invoke(app, ["bulk", "edit", id1, "-p", "high"])

        assert result.exit_code == 0, f"Failed: {result.output}"

    def test_bulk_edit_tags_args(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            result = runner.invoke(app, ["bulk", "edit", id1, "-t", "work"])

        assert result.exit_code == 0, f"Failed: {result.output}"

    def test_bulk_edit_jsonl_stdin(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            jsonl = f'{{"id": "{id1}", "priority": "high"}}'
            result = runner.invoke(app, ["bulk", "edit"], input=jsonl)

        assert result.exit_code == 0, f"Failed: {result.output}"

    def test_bulk_edit_clear_with_null(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1", "-p", "high"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            jsonl = f'{{"id": "{id1}", "priority": null}}'
            result = runner.invoke(app, ["bulk", "edit"], input=jsonl)

        assert result.exit_code == 0, f"Failed: {result.output}"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli_bulk.py::TestBulkEdit -v
```

Expected: FAIL (no "edit" command in bulk)

**Step 3: Add edit command**

Add to `src/dodo/cli_bulk.py`:

```python
@bulk_app.command()
def edit(
    ids: Annotated[list[str] | None, typer.Argument(help="Todo IDs")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
    priority: Annotated[str | None, typer.Option("-p", "--priority", help="Set priority")] = None,
    tag: Annotated[list[str] | None, typer.Option("-t", "--tag", help="Set tags")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Edit multiple todos.

    With args: applies same changes to all IDs.
    With stdin JSONL: applies per-item changes (partial updates).
    """
    from dodo.models import Priority

    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"
    snapshots = []
    edited = 0

    # Mode 1: IDs as args with flags
    if ids:
        if not priority and not tag:
            console.print("[yellow]No changes specified. Use -p or -t flags.[/yellow]")
            raise typer.Exit(1)

        parsed_priority = None
        if priority:
            try:
                parsed_priority = Priority(priority.lower())
            except ValueError:
                console.print(f"[red]Error:[/red] Invalid priority '{priority}'")
                raise typer.Exit(1)

        parsed_tags = None
        if tag:
            parsed_tags = []
            for t in tag:
                parsed_tags.extend(x.strip() for x in t.split(",") if x.strip())

        for id_ in ids:
            item = svc.get(id_)
            if item:
                snapshots.append(item)
                if parsed_priority is not None:
                    svc.update_priority(id_, parsed_priority)
                if parsed_tags is not None:
                    svc.update_tags(id_, parsed_tags)
                edited += 1
                if quiet:
                    console.print(id_)
                else:
                    console.print(f"[green]✓[/green] {id_}: updated")
            else:
                if not quiet:
                    console.print(f"[yellow]![/yellow] {id_}: not found")

    # Mode 2: JSONL from stdin
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if not text:
            console.print("[yellow]Empty input[/yellow]")
            raise typer.Exit(1)

        from dodo.bulk import parse_bulk_input
        result = parse_bulk_input(text)

        for data in result.items:
            if not isinstance(data, dict):
                continue

            id_ = data.get("id")
            if not id_:
                continue

            item = svc.get(id_)
            if not item:
                if not quiet:
                    console.print(f"[yellow]![/yellow] {id_}: not found")
                continue

            snapshots.append(item)

            # Update priority if present (null clears)
            if "priority" in data:
                prio_val = data["priority"]
                if prio_val is None:
                    svc.update_priority(id_, None)
                else:
                    try:
                        svc.update_priority(id_, Priority(prio_val.lower()))
                    except ValueError:
                        pass

            # Update tags if present (null clears)
            if "tags" in data:
                tags_val = data["tags"]
                if tags_val is None:
                    svc.update_tags(id_, None)
                elif isinstance(tags_val, list):
                    svc.update_tags(id_, tags_val)

            # Update text if present
            if "text" in data and data["text"]:
                svc.update_text(id_, data["text"])

            edited += 1
            if quiet:
                console.print(id_)
            else:
                console.print(f"[green]✓[/green] {id_}: updated")

    else:
        console.print("[yellow]Provide IDs as arguments or pipe JSONL to stdin.[/yellow]")
        raise typer.Exit(1)

    if snapshots:
        _save_bulk_undo("edit", snapshots, target)

    if not quiet:
        console.print(f"[dim]Edited {edited} todos[/dim]")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli_bulk.py::TestBulkEdit -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli_bulk.py tests/test_cli_bulk.py
git commit -m "feat(cli): add bulk edit command"
```

---

## Task 8: Enhanced Undo (All Operations)

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestCliUndo:
    def test_undo_add(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Task to undo"])
            result = runner.invoke(app, ["undo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Undid" in result.stdout

    def test_undo_done(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r = runner.invoke(app, ["add", "Task"])
            id_ = r.stdout.split("(")[1].split(")")[0]
            runner.invoke(app, ["done", id_])
            result = runner.invoke(app, ["undo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Undid" in result.stdout

    def test_undo_rm(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r = runner.invoke(app, ["add", "Task to delete"])
            id_ = r.stdout.split("(")[1].split(")")[0]
            runner.invoke(app, ["rm", id_])
            result = runner.invoke(app, ["undo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Undid" in result.stdout

    def test_undo_nothing(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["undo"])

        assert result.exit_code == 0
        assert "Nothing to undo" in result.stdout

    def test_undo_clears_after_use(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Task"])
            runner.invoke(app, ["undo"])
            result = runner.invoke(app, ["undo"])

        assert "Nothing to undo" in result.stdout
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py::TestCliUndo -v
```

Expected: Some tests may fail (undo done/rm not implemented)

**Step 3: Update undo command and save functions**

In `src/dodo/cli.py`, update `_save_last_action`:

```python
def _save_last_action(action: str, id_or_items, target: str) -> None:
    """Save last action for undo.

    Args:
        action: The action type (add, done, rm, edit)
        id_or_items: Either a single ID string or a list of TodoItem snapshots
        target: The dodo target name
    """
    cfg = _get_config()
    state_file = cfg.config_dir / ".last_action"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Handle both old format (single ID) and new format (item snapshots)
    if isinstance(id_or_items, str):
        # Old format for backward compatibility with add
        items_data = [{"id": id_or_items}]
    elif isinstance(id_or_items, list):
        items_data = []
        for item in id_or_items:
            if hasattr(item, "to_dict"):
                items_data.append(item.to_dict())
            elif isinstance(item, dict):
                items_data.append(item)
            else:
                items_data.append({"id": str(item)})
    else:
        items_data = [{"id": str(id_or_items)}]

    state_file.write_text(json.dumps({
        "action": action,
        "target": target,
        "items": items_data,
    }))
```

Update `done` command to save snapshot:

```python
@app.command()
def done(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
):
    """Mark todo as done."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"

    # Try to find matching ID
    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    # Save snapshot before modification
    _save_last_action("done", [item], target)

    completed = svc.complete(item.id)
    console.print(f"[green]✓[/green] Done: {completed.text}")
```

Update `rm` command to save snapshot:

```python
@app.command(name="remove")
@app.command()
def rm(
    id: Annotated[str, typer.Argument(help="Todo ID (or partial)")],
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
):
    """Remove a todo."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"

    item = _find_item_by_partial_id(svc, id)
    if not item:
        console.print(f"[red]Error:[/red] Todo not found: {id}")
        raise typer.Exit(1)

    # Save snapshot before deletion
    _save_last_action("rm", [item], target)

    svc.delete(item.id)
    console.print(f"[yellow]✓[/yellow] Removed: {item.text}")
```

Update `undo` command:

```python
@app.command()
def undo():
    """Undo the last operation."""
    from dodo.models import Priority, Status

    last = _load_last_action()

    if not last:
        console.print("[yellow]Nothing to undo[/yellow]")
        raise typer.Exit(0)

    action = last.get("action")
    target = last.get("target")
    items = last.get("items", [])

    # Handle old format (single id field)
    if "id" in last and not items:
        items = [{"id": last["id"]}]

    if not items:
        console.print("[yellow]Nothing to undo[/yellow]")
        _clear_last_action()
        raise typer.Exit(0)

    cfg = _get_config()
    project_id = None if target == "global" else target
    svc = _get_service(cfg, project_id)

    restored = 0

    if action == "add":
        # Undo add: delete the added items
        for item_data in items:
            item_id = item_data.get("id")
            if item_id:
                try:
                    svc.delete(item_id)
                    restored += 1
                except Exception:
                    pass
        console.print(f"[yellow]↩[/yellow] Undid add: removed {restored} item(s)")

    elif action == "done":
        # Undo done: restore to pending status
        for item_data in items:
            item_id = item_data.get("id")
            if item_id:
                try:
                    # Update status back to pending
                    svc._backend.update(item_id, Status.PENDING)
                    restored += 1
                except Exception:
                    pass
        console.print(f"[yellow]↩[/yellow] Undid done: restored {restored} item(s) to pending")

    elif action == "rm":
        # Undo rm: re-create the deleted items
        for item_data in items:
            try:
                # Re-create with original data
                priority = None
                if item_data.get("priority"):
                    try:
                        priority = Priority(item_data["priority"])
                    except ValueError:
                        pass

                svc._backend.add(
                    text=item_data.get("text", ""),
                    project=project_id,
                    priority=priority,
                    tags=item_data.get("tags"),
                )
                restored += 1
            except Exception:
                pass
        console.print(f"[yellow]↩[/yellow] Undid rm: restored {restored} item(s)")

    elif action == "edit":
        # Undo edit: restore original values
        for item_data in items:
            item_id = item_data.get("id")
            if item_id:
                try:
                    if "priority" in item_data:
                        priority = None
                        if item_data["priority"]:
                            try:
                                priority = Priority(item_data["priority"])
                            except ValueError:
                                pass
                        svc.update_priority(item_id, priority)
                    if "tags" in item_data:
                        svc.update_tags(item_id, item_data.get("tags"))
                    if "text" in item_data:
                        svc.update_text(item_id, item_data["text"])
                    restored += 1
                except Exception:
                    pass
        console.print(f"[yellow]↩[/yellow] Undid edit: restored {restored} item(s)")

    else:
        console.print(f"[yellow]Unknown action: {action}[/yellow]")

    _clear_last_action()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli.py::TestCliUndo -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): enhance undo to support all operations"
```

---

## Task 9: Update README with Simplified Detection

**Files:**
- Modify: `README.md`

**Step 1: Read current README**

Already read in earlier exploration.

**Step 2: Update README**

Replace the "Project Routing" section with the new "How Dodo Finds Your Todos" section from the design document. The full replacement content is in `docs/plans/2026-01-20-cli-enhancements-design.md` Section 6.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: clarify project detection in README"
```

---

## Task 10: Add dodo show Command

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestCliShow:
    def test_show_global_fallback(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["show"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "global" in result.stdout.lower()

    def test_show_with_dodo(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["new", "testdodo"])
            result = runner.invoke(app, ["show"])

        assert result.exit_code == 0, f"Failed: {result.output}"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py::TestCliShow -v
```

Expected: FAIL (no "show" command)

**Step 3: Add show command**

In `src/dodo/cli.py`:

```python
@app.command()
def show():
    """Show detected dodos and current default."""
    from pathlib import Path
    from dodo.models import Status
    from dodo.project import detect_project, _get_git_root

    cfg = _get_config()
    cwd = Path.cwd()

    # Detect context
    git_root = _get_git_root(cwd)

    console.print("[bold]Context:[/bold]")
    if git_root:
        console.print(f"  Git repo: {git_root.name} ({git_root})")
    console.print(f"  Directory: {cwd}")
    console.print()

    # Find available dodos
    console.print("[bold]Available dodos:[/bold]")

    available = []

    # Check local .dodo/
    local_dodo = cwd / ".dodo"
    if not local_dodo.exists() and git_root:
        local_dodo = git_root / ".dodo"

    if local_dodo.exists():
        # Default local dodo
        if (local_dodo / "dodo.json").exists() or (local_dodo / "dodo.db").exists():
            available.append(("local", str(local_dodo), "local"))
        # Named local dodos
        for subdir in local_dodo.iterdir():
            if subdir.is_dir() and (subdir / "dodo.json").exists():
                available.append((subdir.name, str(subdir), "local"))

    # Check central dodos
    for item in cfg.config_dir.iterdir():
        if item.is_dir() and item.name not in ("projects", ".last_action"):
            if (item / "dodo.json").exists() or (item / "dodo.db").exists():
                available.append((item.name, str(item), "central"))

    # Determine current default
    dodo_id, explicit_path = _resolve_dodo(cfg)
    current = dodo_id or "global"

    if not available:
        console.print("  [dim](none created yet)[/dim]")
        console.print()
        console.print(f"[bold]Current:[/bold] global (fallback)")
        console.print("[dim]Hint: Run 'dodo new' to create a dodo for this project[/dim]")
        return

    for name, path, location in available:
        marker = "→ " if name == current else "  "
        path_short = path.replace(str(Path.home()), "~")
        hint = f"(default)" if name == current else f"(use: dodo -d {name})"
        console.print(f"  {marker}[cyan]{name}[/cyan]  {path_short}  [dim]{hint}[/dim]")

    console.print()

    # Show stats for current
    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    items = svc.list()
    pending = sum(1 for i in items if i.status == Status.PENDING)
    done = sum(1 for i in items if i.status == Status.DONE)

    console.print(f"[bold]Current:[/bold] {current} ({pending} pending, {done} done)")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli.py::TestCliShow -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): add show command for dodo discovery"
```

---

## Task 11: Add dodo use/unuse Commands

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestCliUse:
    def test_use_existing_dodo(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["new", "testdodo"])
            result = runner.invoke(app, ["use", "testdodo"])

        assert result.exit_code == 0, f"Failed: {result.output}"

    def test_use_nonexistent_dodo(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["use", "nonexistent"])

        assert result.exit_code == 1

    def test_unuse(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["new", "testdodo"])
            runner.invoke(app, ["use", "testdodo"])
            result = runner.invoke(app, ["unuse"])

        assert result.exit_code == 0, f"Failed: {result.output}"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py::TestCliUse -v
```

Expected: FAIL (no "use" command)

**Step 3: Add use/unuse commands**

In `src/dodo/cli.py`:

```python
@app.command()
def use(
    name: Annotated[str, typer.Argument(help="Name of the dodo to use")],
):
    """Set current directory to use a specific dodo.

    This stores a mapping so commands from this directory use the specified dodo.
    """
    from pathlib import Path

    cfg = _get_config()
    cwd = str(Path.cwd())

    # Check if the named dodo exists (local or central)
    found = False

    # Check local
    local_path = Path.cwd() / ".dodo" / name
    if local_path.exists():
        found = True

    # Check central
    if not found:
        central_path = cfg.config_dir / name
        if central_path.exists():
            found = True

    if not found:
        console.print(f"[red]Error:[/red] Dodo '{name}' not found")
        console.print(f"  Create it first with: dodo new {name}")
        raise typer.Exit(1)

    # Check if already mapped
    existing = cfg.get_directory_mapping(cwd)
    if existing:
        console.print(f"[yellow]Directory already uses '{existing}'[/yellow]")
        console.print("  Use 'dodo unuse' to remove the mapping first")
        raise typer.Exit(1)

    cfg.set_directory_mapping(cwd, name)
    console.print(f"[green]✓[/green] Now using '{name}' for {Path.cwd().name}")


@app.command()
def unuse():
    """Remove the dodo mapping for current directory."""
    from pathlib import Path

    cfg = _get_config()
    cwd = str(Path.cwd())

    if cfg.remove_directory_mapping(cwd):
        console.print(f"[green]✓[/green] Removed mapping for {Path.cwd().name}")
    else:
        console.print("[yellow]No mapping exists for this directory[/yellow]")
```

**Step 4: Keep link/unlink as aliases**

The existing `link` and `unlink` commands can remain as aliases (or we can make them call `use`/`unuse`).

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_cli.py::TestCliUse -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): add use/unuse commands"
```

---

## Task 12: Update dodo new Command

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestCliNew:
    def test_new_auto_names_from_dir(self, cli_env, tmp_path, monkeypatch):
        test_dir = tmp_path / "myproject"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        with patch("dodo.project.detect_project", return_value=None):
            with patch("dodo.project._get_git_root", return_value=None):
                result = runner.invoke(app, ["new"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "myproject" in result.stdout

    def test_new_local_creates_dodo_dir(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            with patch("dodo.project._get_git_root", return_value=None):
                result = runner.invoke(app, ["new", "--local"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert ".dodo" in result.stdout

    def test_new_with_name(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["new", "customname"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "customname" in result.stdout

    def test_new_prints_detection_message(self, cli_env, tmp_path, monkeypatch):
        git_dir = tmp_path / "gitrepo"
        git_dir.mkdir()
        monkeypatch.chdir(git_dir)

        with patch("dodo.project._get_git_root", return_value=git_dir):
            result = runner.invoke(app, ["new"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "git" in result.stdout.lower() or "Detected" in result.stdout
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py::TestCliNew -v
```

Expected: Some tests may fail due to different output messages

**Step 3: Update new command**

The `new` command needs to be updated to:
1. Auto-name from git repo or directory
2. Print detection messages
3. Create at git root for `--local` in git repos

This is a larger refactor of the existing `new` command. See design document Section 5 for full output examples.

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli.py::TestCliNew -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): update new command with auto-naming and detection messages"
```

---

## Task 13: Update Add Output Format

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestCliAddOutput:
    def test_add_shows_dodo_name(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["add", "Test task"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Added to" in result.stdout

    def test_add_shows_priority_and_tags(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["add", "Task", "-p", "high", "-t", "work"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "!high" in result.stdout
        assert "#work" in result.stdout
```

**Step 2: Run test**

```bash
pytest tests/test_cli.py::TestCliAddOutput -v
```

**Step 3: Update add command output**

Update the output line in the `add` command to include priority and tags:

```python
    # Format output
    output_text = item.text
    if item.priority:
        output_text += f" !{item.priority.value}"
    if item.tags:
        output_text += " " + " ".join(f"#{t}" for t in item.tags)

    console.print(f"[green]✓[/green] Added to '{target}': {output_text} [dim]({item.id})[/dim]")
```

**Step 4: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): improve add command output with priority and tags"
```

---

## Final: Run Full Test Suite

```bash
pytest tests/ -v
```

Ensure all tests pass before considering implementation complete.

---

## Summary

| Task | Description | Complexity |
|------|-------------|------------|
| 1 | Txt formatter | Simple |
| 2 | Markdown formatter | Simple |
| 3 | Export --format flag | Simple |
| 4 | Add -p/-t flags | Medium |
| 5 | Bulk input parser | Medium |
| 6 | Bulk done/rm/add | Medium |
| 7 | Bulk edit | Medium |
| 8 | Enhanced undo | Medium |
| 9 | README update | Simple |
| 10 | Show command | Medium |
| 11 | Use/unuse commands | Simple |
| 12 | Update new command | Medium |
| 13 | Update add output | Simple |

Total: ~13 tasks, each 10-30 minutes
