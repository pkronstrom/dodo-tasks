"""Tests for output formatters."""

import json
from datetime import datetime

import pytest

from dodo.formatters import FORMATTERS, get_formatter
from dodo.formatters.jsonl import JsonlFormatter
from dodo.formatters.table import TableFormatter
from dodo.formatters.tsv import TsvFormatter
from dodo.models import Status, TodoItem


@pytest.fixture
def sample_items():
    return [
        TodoItem(
            id="abc123",
            text="Buy milk",
            status=Status.DONE,
            created_at=datetime(2024, 1, 9, 10, 30),
            completed_at=datetime(2024, 1, 9, 11, 0),
        ),
        TodoItem(
            id="def456",
            text="Call dentist",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 10, 14, 0),
        ),
    ]


class TestFormatterRegistry:
    def test_all_formatters_registered(self):
        assert "table" in FORMATTERS
        assert "jsonl" in FORMATTERS
        assert "tsv" in FORMATTERS
        assert "csv" in FORMATTERS

    def test_get_formatter_table(self):
        formatter = get_formatter("table")
        assert isinstance(formatter, TableFormatter)

    def test_get_formatter_jsonl(self):
        formatter = get_formatter("jsonl")
        assert isinstance(formatter, JsonlFormatter)

    def test_get_formatter_tsv(self):
        formatter = get_formatter("tsv")
        assert isinstance(formatter, TsvFormatter)

    def test_get_formatter_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_formatter("unknown")


class TestTableFormatter:
    def test_format_empty(self):
        formatter = TableFormatter()
        output = formatter.format([])
        assert output == "[dim]No todos[/dim]"

    def test_format_default_no_id(self, sample_items):
        formatter = TableFormatter(show_id=False)
        output = formatter.format(sample_items)
        # Output is a Rich Table, check it exists
        assert output is not None

    def test_format_with_id(self, sample_items):
        formatter = TableFormatter(show_id=True)
        output = formatter.format(sample_items)
        assert output is not None

    def test_custom_datetime_format(self, sample_items):
        formatter = TableFormatter(datetime_fmt="%Y-%m-%d")
        output = formatter.format(sample_items)
        assert output is not None

    def test_invalid_datetime_format_fallback(self, sample_items):
        formatter = TableFormatter(datetime_fmt="%invalid")
        # Should not raise, uses fallback
        output = formatter.format(sample_items)
        assert output is not None


class TestTableFormatterParsing:
    def test_parse_default(self):
        formatter = get_formatter("table")
        assert isinstance(formatter, TableFormatter)
        assert formatter.datetime_fmt == "%m-%d %H:%M"
        assert formatter.show_id is False

    def test_parse_with_datetime_format(self):
        formatter = get_formatter("table:%Y-%m-%d")
        assert isinstance(formatter, TableFormatter)
        assert formatter.datetime_fmt == "%Y-%m-%d"
        assert formatter.show_id is False

    def test_parse_with_id(self):
        formatter = get_formatter("table::id")
        assert isinstance(formatter, TableFormatter)
        assert formatter.datetime_fmt == "%m-%d %H:%M"
        assert formatter.show_id is True

    def test_parse_with_datetime_and_id(self):
        formatter = get_formatter("table:%m-%d:id")
        assert isinstance(formatter, TableFormatter)
        assert formatter.datetime_fmt == "%m-%d"
        assert formatter.show_id is True


class TestJsonlFormatter:
    def test_format_empty(self):
        formatter = JsonlFormatter()
        output = formatter.format([])
        assert output == ""

    def test_format_single_item(self, sample_items):
        formatter = JsonlFormatter()
        output = formatter.format([sample_items[0]])
        data = json.loads(output)
        assert data["id"] == "abc123"
        assert data["text"] == "Buy milk"
        assert data["status"] == "done"
        assert data["created_at"] == "2024-01-09T10:30:00"
        assert data["completed_at"] == "2024-01-09T11:00:00"

    def test_format_multiple_items(self, sample_items):
        formatter = JsonlFormatter()
        output = formatter.format(sample_items)
        lines = output.strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["id"] == "abc123"
        assert first["status"] == "done"

        second = json.loads(lines[1])
        assert second["id"] == "def456"
        assert second["status"] == "pending"
        assert second["completed_at"] is None


class TestTsvFormatter:
    def test_format_empty(self):
        formatter = TsvFormatter()
        output = formatter.format([])
        # Still outputs header even with no items
        assert output == "id\tstatus\ttext"

    def test_format_single_item(self, sample_items):
        formatter = TsvFormatter()
        output = formatter.format([sample_items[0]])
        lines = output.strip().split("\n")
        assert lines[0] == "id\tstatus\ttext"
        assert lines[1] == "abc123\tdone\tBuy milk"

    def test_format_multiple_items(self, sample_items):
        formatter = TsvFormatter()
        output = formatter.format(sample_items)
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + 2 items
        assert lines[0] == "id\tstatus\ttext"
        assert lines[1] == "abc123\tdone\tBuy milk"
        assert lines[2] == "def456\tpending\tCall dentist"


class TestCsvFormatter:
    def test_format_empty(self):
        from dodo.formatters.csv import CsvFormatter

        formatter = CsvFormatter()
        output = formatter.format([])
        assert output == "id,status,text"

    def test_format_single_item(self, sample_items):
        from dodo.formatters.csv import CsvFormatter

        formatter = CsvFormatter()
        output = formatter.format([sample_items[0]])
        lines = output.strip().split("\n")
        assert lines[0] == "id,status,text"
        assert lines[1] == "abc123,done,Buy milk"

    def test_format_multiple_items(self, sample_items):
        from dodo.formatters.csv import CsvFormatter

        formatter = CsvFormatter()
        output = formatter.format(sample_items)
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + 2 items
        assert lines[0] == "id,status,text"
        assert lines[1] == "abc123,done,Buy milk"
        assert lines[2] == "def456,pending,Call dentist"

    def test_format_escapes_commas(self):
        from dodo.formatters.csv import CsvFormatter

        item = TodoItem(
            id="test1",
            text="Buy milk, eggs, bread",
            status=Status.PENDING,
            created_at=datetime.now(),
        )
        formatter = CsvFormatter()
        output = formatter.format([item])
        lines = output.strip().split("\n")
        assert lines[1] == 'test1,pending,"Buy milk, eggs, bread"'

    def test_format_escapes_quotes(self):
        from dodo.formatters.csv import CsvFormatter

        item = TodoItem(
            id="test2",
            text='Say "hello"',
            status=Status.PENDING,
            created_at=datetime.now(),
        )
        formatter = CsvFormatter()
        output = formatter.format([item])
        lines = output.strip().split("\n")
        assert lines[1] == 'test2,pending,"Say ""hello"""'


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


class TestTableFormatterDueDate:
    def test_due_column_shown_when_items_have_due_at(self):
        items = [
            TodoItem(
                id="abc123",
                text="Task with due",
                status=Status.PENDING,
                created_at=datetime(2024, 1, 9, 10, 0),
                due_at=datetime(2026, 6, 15),
            ),
            TodoItem(
                id="def456",
                text="Task without due",
                status=Status.PENDING,
                created_at=datetime(2024, 1, 9, 10, 0),
            ),
        ]
        formatter = TableFormatter()
        output = formatter.format(items)
        # Rich Table - check column headers
        assert output is not None
        assert any("Due" in str(col.header) for col in output.columns)

    def test_no_due_column_when_no_items_have_due(self, sample_items):
        formatter = TableFormatter()
        output = formatter.format(sample_items)
        assert output is not None
        assert not any("Due" in str(col.header) for col in output.columns)

    def test_overdue_highlighted(self):
        items = [
            TodoItem(
                id="abc123",
                text="Overdue task",
                status=Status.PENDING,
                created_at=datetime(2024, 1, 9, 10, 0),
                due_at=datetime(2020, 1, 1),
            ),
        ]
        formatter = TableFormatter()
        output = formatter.format(items)
        assert output is not None

    def test_timezone_aware_due_at_no_crash(self):
        """Timezone-aware due_at should not crash comparison with now()."""
        from datetime import UTC

        items = [
            TodoItem(
                id="abc123",
                text="TZ-aware task",
                status=Status.PENDING,
                created_at=datetime(2024, 1, 9, 10, 0),
                due_at=datetime(2020, 1, 1, tzinfo=UTC),
            ),
        ]
        formatter = TableFormatter()
        output = formatter.format(items)
        assert output is not None

    def test_timezone_aware_future_due_at(self):
        """Timezone-aware future due_at should render without red."""
        from datetime import UTC

        items = [
            TodoItem(
                id="abc123",
                text="Future TZ task",
                status=Status.PENDING,
                created_at=datetime(2024, 1, 9, 10, 0),
                due_at=datetime(2099, 1, 1, tzinfo=UTC),
            ),
        ]
        formatter = TableFormatter()
        output = formatter.format(items)
        assert output is not None


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
