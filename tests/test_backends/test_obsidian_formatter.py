"""Tests for Obsidian formatter."""

from datetime import datetime

import pytest

from dodo.models import Priority, Status, TodoItem
from dodo.plugins.obsidian.formatter import (
    ObsidianDocument,
    ObsidianFormatter,
    format_header,
    format_priority,
    format_tags,
    format_timestamp,
    get_tag_from_header,
    parse_header,
    parse_priority,
    parse_tags,
)


class TestHeaderParsing:
    def test_parse_h1(self):
        level, text = parse_header("# Work")
        assert level == 1
        assert text == "Work"

    def test_parse_h3(self):
        level, text = parse_header("### home tasks")
        assert level == 3
        assert text == "home tasks"

    def test_not_a_header(self):
        assert parse_header("- [ ] task") is None
        assert parse_header("just text") is None

    def test_get_tag_from_header(self):
        assert get_tag_from_header("Work Projects") == "work"
        assert get_tag_from_header("home") == "home"
        assert get_tag_from_header("My Work Tasks") == "my"

    def test_format_header(self):
        assert format_header("work", 3) == "### work"
        assert format_header("home", 2) == "## home"


class TestFormatPriority:
    def test_symbols_critical(self):
        assert format_priority(Priority.CRITICAL, "symbols") == "!!!"

    def test_symbols_high(self):
        assert format_priority(Priority.HIGH, "symbols") == "!!"

    def test_symbols_normal(self):
        assert format_priority(Priority.NORMAL, "symbols") == "!"

    def test_symbols_low(self):
        assert format_priority(Priority.LOW, "symbols") == ""

    def test_symbols_someday(self):
        assert format_priority(Priority.SOMEDAY, "symbols") == "~"

    def test_symbols_none(self):
        assert format_priority(None, "symbols") == ""

    def test_hidden(self):
        assert format_priority(Priority.CRITICAL, "hidden") == ""

    def test_emoji_high(self):
        assert format_priority(Priority.HIGH, "emoji") == "🔼"

    def test_dataview_critical(self):
        assert format_priority(Priority.CRITICAL, "dataview") == "[priority:: critical]"


class TestParsePriority:
    def test_parse_symbols_critical(self):
        assert parse_priority("task !!!", "symbols") == (Priority.CRITICAL, "task")

    def test_parse_symbols_high(self):
        assert parse_priority("task !!", "symbols") == (Priority.HIGH, "task")

    def test_parse_symbols_normal(self):
        assert parse_priority("task !", "symbols") == (Priority.NORMAL, "task")

    def test_parse_symbols_someday(self):
        assert parse_priority("task ~", "symbols") == (Priority.SOMEDAY, "task")

    def test_parse_symbols_none(self):
        assert parse_priority("task", "symbols") == (None, "task")

    def test_parse_emoji(self):
        assert parse_priority("task ⏫", "emoji") == (Priority.CRITICAL, "task")

    def test_parse_dataview(self):
        assert parse_priority("task [priority:: high]", "dataview") == (Priority.HIGH, "task")


class TestFormatTimestamp:
    def test_hidden(self):
        ts = datetime(2024, 1, 15, 10, 30)
        assert format_timestamp(ts, "hidden") == ""

    def test_plain(self):
        ts = datetime(2024, 1, 15, 10, 30)
        assert format_timestamp(ts, "plain") == "2024-01-15 10:30"

    def test_emoji(self):
        ts = datetime(2024, 1, 15, 10, 30)
        assert format_timestamp(ts, "emoji") == "📅 2024-01-15"

    def test_dataview(self):
        ts = datetime(2024, 1, 15, 10, 30)
        assert format_timestamp(ts, "dataview") == "[created:: 2024-01-15]"


class TestFormatTags:
    def test_hidden(self):
        assert format_tags(["work", "urgent"], "hidden") == ""

    def test_hashtags(self):
        assert format_tags(["work", "urgent"], "hashtags") == "#work #urgent"

    def test_dataview(self):
        assert format_tags(["work", "urgent"], "dataview") == "[tags:: work, urgent]"

    def test_empty_tags(self):
        assert format_tags([], "hashtags") == ""
        assert format_tags(None, "hashtags") == ""


class TestParseTags:
    def test_parse_hashtags(self):
        tags, clean = parse_tags("task text #work #urgent", "hashtags")
        assert tags == ["work", "urgent"]
        assert clean == "task text"

    def test_parse_dataview(self):
        tags, clean = parse_tags("task [tags:: work, urgent]", "dataview")
        assert tags == ["work", "urgent"]
        assert clean == "task"

    def test_no_tags(self):
        tags, clean = parse_tags("task text", "hashtags")
        assert tags == []
        assert clean == "task text"


class TestObsidianFormatter:
    def test_format_minimal_default(self):
        formatter = ObsidianFormatter()
        item = TodoItem(
            id="abc12345",
            text="Buy groceries",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            priority=Priority.HIGH,
            tags=["home", "errand"],
        )
        line = formatter.format_line(item)
        assert line == "- [ ] Buy groceries !! #home #errand"

    def test_format_done_task(self):
        formatter = ObsidianFormatter()
        item = TodoItem(
            id="abc12345",
            text="Done task",
            status=Status.DONE,
            created_at=datetime(2024, 1, 15, 10, 30),
        )
        line = formatter.format_line(item)
        assert line == "- [x] Done task"

    def test_format_with_timestamp(self):
        formatter = ObsidianFormatter(timestamp_syntax="plain")
        item = TodoItem(
            id="abc12345",
            text="Task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
        )
        line = formatter.format_line(item)
        assert line == "- [ ] 2024-01-15 10:30 Task"

    def test_format_emoji_priority(self):
        formatter = ObsidianFormatter(priority_syntax="emoji")
        item = TodoItem(
            id="abc12345",
            text="Task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            priority=Priority.CRITICAL,
        )
        line = formatter.format_line(item)
        assert line == "- [ ] Task ⏫"

    def test_parse_line_minimal(self):
        formatter = ObsidianFormatter()
        result = formatter.parse_line("- [ ] Buy groceries !! #home")
        assert result is not None
        text, status, priority, tags = result
        assert text == "Buy groceries"
        assert status == Status.PENDING
        assert priority == Priority.HIGH
        assert tags == ["home"]

    def test_parse_line_done(self):
        formatter = ObsidianFormatter()
        result = formatter.parse_line("- [x] Done task")
        assert result is not None
        text, status, priority, tags = result
        assert text == "Done task"
        assert status == Status.DONE

    def test_parse_line_not_a_task(self):
        formatter = ObsidianFormatter()
        assert formatter.parse_line("Just some text") is None
        assert formatter.parse_line("## Header") is None


class TestObsidianDocument:
    def test_parse_simple(self):
        content = """### work
- [ ] Task one !!
- [ ] Task two

### home
- [ ] Buy groceries
"""
        doc = ObsidianDocument.parse(content, ObsidianFormatter())

        assert len(doc.sections) == 2
        assert doc.sections["work"].header == "### work"
        assert len(doc.sections["work"].tasks) == 2
        assert doc.sections["home"].header == "### home"
        assert len(doc.sections["home"].tasks) == 1

    def test_parse_preserves_header_style(self):
        content = """## Work Projects
- [ ] Task one
"""
        doc = ObsidianDocument.parse(content, ObsidianFormatter())
        assert doc.sections["work"].header == "## Work Projects"

    def test_parse_tasks_without_header(self):
        content = """- [ ] Orphan task
"""
        doc = ObsidianDocument.parse(content, ObsidianFormatter())
        # Tasks without header go to "_default" section
        assert "_default" in doc.sections
        assert len(doc.sections["_default"].tasks) == 1

    def test_render(self):
        content = """### work
- [ ] Task one !!

### home
- [ ] Buy groceries
"""
        formatter = ObsidianFormatter()
        doc = ObsidianDocument.parse(content, formatter)
        rendered = doc.render(formatter)

        assert "### work" in rendered
        assert "### home" in rendered
        assert "Task one" in rendered
        assert "Buy groceries" in rendered
