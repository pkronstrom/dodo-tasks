"""Tests for Obsidian formatter."""

from datetime import datetime

import pytest

from dodo.models import Priority, Status, TodoItem
from dodo.plugins.obsidian.formatter import (
    ObsidianDocument,
    ObsidianFormatter,
    ParsedTask,
    format_header,
    format_priority,
    format_tags,
    format_timestamp,
    get_tag_from_header,
    parse_header,
    parse_priority,
    parse_tags,
    sort_tasks,
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
        text, status, priority, tags, legacy_id = result
        assert text == "Buy groceries"
        assert status == Status.PENDING
        assert priority == Priority.HIGH
        assert tags == ["home"]
        assert legacy_id is None

    def test_parse_line_done(self):
        formatter = ObsidianFormatter()
        result = formatter.parse_line("- [x] Done task")
        assert result is not None
        text, status, priority, tags, legacy_id = result
        assert text == "Done task"
        assert status == Status.DONE
        assert legacy_id is None

    def test_parse_line_legacy_format(self):
        """Test parsing old format with embedded ID."""
        formatter = ObsidianFormatter()
        result = formatter.parse_line("- [ ] 2024-01-09 10:30 [abc12345] - First todo")
        assert result is not None
        text, status, priority, tags, legacy_id = result
        assert text == "First todo"
        assert status == Status.PENDING
        assert legacy_id == "abc12345"

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


class TestDependencyRendering:
    def test_format_with_children(self):
        formatter = ObsidianFormatter()
        parent = TodoItem(
            id="parent01",
            text="Parent task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
            priority=Priority.HIGH,
        )
        child1 = TodoItem(
            id="child001",
            text="Child one",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
        )
        child2 = TodoItem(
            id="child002",
            text="Child two",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
        )

        result = formatter.format_with_children(parent, [child1, child2])
        lines = result.split("\n")

        assert lines[0] == "- [ ] Parent task !!"
        assert lines[1] == "    - [ ] Child one"
        assert lines[2] == "    - [ ] Child two"

    def test_format_with_children_nested_depth(self):
        """Test formatting at different nesting depths."""
        formatter = ObsidianFormatter()
        parent = TodoItem(
            id="parent01",
            text="Parent task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
        )
        child = TodoItem(
            id="child001",
            text="Child task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
        )

        # At depth 1, parent is indented once, child twice
        result = formatter.format_with_children(parent, [child], depth=1)
        lines = result.split("\n")

        assert lines[0] == "    - [ ] Parent task"  # 4 spaces
        assert lines[1] == "        - [ ] Child task"  # 8 spaces

    def test_format_with_children_no_children(self):
        """Test formatting parent with empty children list."""
        formatter = ObsidianFormatter()
        parent = TodoItem(
            id="parent01",
            text="Standalone task",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15),
            priority=Priority.CRITICAL,
        )

        result = formatter.format_with_children(parent, [])

        assert result == "- [ ] Standalone task !!!"

    def test_parse_indentation(self):
        content = """- [ ] Parent !!
    - [ ] Child one
    - [ ] Child two
        - [ ] Grandchild
"""
        formatter = ObsidianFormatter()
        doc = ObsidianDocument.parse(content, formatter)

        tasks = doc.sections["_default"].tasks
        assert tasks[0].indent == 0
        assert tasks[1].indent == 4
        assert tasks[2].indent == 4
        assert tasks[3].indent == 8

    def test_parse_indentation_mixed_sections(self):
        """Test that indentation is preserved across sections."""
        content = """### work
- [ ] Work parent
    - [ ] Work child

### home
- [ ] Home task
"""
        formatter = ObsidianFormatter()
        doc = ObsidianDocument.parse(content, formatter)

        work_tasks = doc.sections["work"].tasks
        assert work_tasks[0].indent == 0
        assert work_tasks[1].indent == 4

        home_tasks = doc.sections["home"].tasks
        assert home_tasks[0].indent == 0

    def test_render_preserves_indentation(self):
        """Test that rendering preserves task indentation."""
        content = """- [ ] Parent
    - [ ] Child
"""
        formatter = ObsidianFormatter()
        doc = ObsidianDocument.parse(content, formatter)
        rendered = doc.render(formatter)

        lines = rendered.strip().split("\n")
        # Filter out empty lines
        lines = [l for l in lines if l.strip()]
        assert lines[0] == "- [ ] Parent"
        assert lines[1] == "    - [ ] Child"


class TestSortTasks:
    def test_sort_by_priority(self):
        tasks = [
            ParsedTask("Low", Status.PENDING, Priority.LOW, []),
            ParsedTask("Critical", Status.PENDING, Priority.CRITICAL, []),
            ParsedTask("High", Status.PENDING, Priority.HIGH, []),
        ]
        sorted_tasks = sort_tasks(tasks, "priority")
        assert [t.text for t in sorted_tasks] == ["Critical", "High", "Low"]

    def test_sort_by_priority_with_none(self):
        """Tasks with no priority sort last."""
        tasks = [
            ParsedTask("No priority", Status.PENDING, None, []),
            ParsedTask("Critical", Status.PENDING, Priority.CRITICAL, []),
            ParsedTask("Someday", Status.PENDING, Priority.SOMEDAY, []),
        ]
        sorted_tasks = sort_tasks(tasks, "priority")
        assert [t.text for t in sorted_tasks] == ["Critical", "Someday", "No priority"]

    def test_sort_by_priority_all_levels(self):
        """Test all priority levels sort correctly."""
        tasks = [
            ParsedTask("Someday", Status.PENDING, Priority.SOMEDAY, []),
            ParsedTask("Normal", Status.PENDING, Priority.NORMAL, []),
            ParsedTask("Low", Status.PENDING, Priority.LOW, []),
            ParsedTask("Critical", Status.PENDING, Priority.CRITICAL, []),
            ParsedTask("High", Status.PENDING, Priority.HIGH, []),
        ]
        sorted_tasks = sort_tasks(tasks, "priority")
        assert [t.text for t in sorted_tasks] == [
            "Critical",
            "High",
            "Normal",
            "Low",
            "Someday",
        ]

    def test_sort_by_content(self):
        tasks = [
            ParsedTask("Zebra", Status.PENDING, None, []),
            ParsedTask("Apple", Status.PENDING, None, []),
            ParsedTask("Mango", Status.PENDING, None, []),
        ]
        sorted_tasks = sort_tasks(tasks, "content")
        assert [t.text for t in sorted_tasks] == ["Apple", "Mango", "Zebra"]

    def test_sort_by_content_case_insensitive(self):
        """Content sorting should be case-insensitive."""
        tasks = [
            ParsedTask("banana", Status.PENDING, None, []),
            ParsedTask("Apple", Status.PENDING, None, []),
            ParsedTask("CHERRY", Status.PENDING, None, []),
        ]
        sorted_tasks = sort_tasks(tasks, "content")
        assert [t.text for t in sorted_tasks] == ["Apple", "banana", "CHERRY"]

    def test_sort_manual_preserves_order(self):
        tasks = [
            ParsedTask("First", Status.PENDING, None, []),
            ParsedTask("Second", Status.PENDING, None, []),
        ]
        sorted_tasks = sort_tasks(tasks, "manual")
        assert [t.text for t in sorted_tasks] == ["First", "Second"]

    def test_sort_by_tags(self):
        """Sort by first tag alphabetically."""
        tasks = [
            ParsedTask("Task Z", Status.PENDING, None, ["zebra"]),
            ParsedTask("Task A", Status.PENDING, None, ["apple"]),
            ParsedTask("Task M", Status.PENDING, None, ["mango"]),
        ]
        sorted_tasks = sort_tasks(tasks, "tags")
        assert [t.text for t in sorted_tasks] == ["Task A", "Task M", "Task Z"]

    def test_sort_by_tags_empty_tags_last(self):
        """Tasks without tags sort last."""
        tasks = [
            ParsedTask("No tags", Status.PENDING, None, []),
            ParsedTask("Has tag", Status.PENDING, None, ["work"]),
        ]
        sorted_tasks = sort_tasks(tasks, "tags")
        assert [t.text for t in sorted_tasks] == ["Has tag", "No tags"]

    def test_sort_by_status(self):
        """Pending tasks before done tasks."""
        tasks = [
            ParsedTask("Done task", Status.DONE, None, []),
            ParsedTask("Pending task", Status.PENDING, None, []),
        ]
        sorted_tasks = sort_tasks(tasks, "status")
        assert [t.text for t in sorted_tasks] == ["Pending task", "Done task"]

    def test_sort_unknown_preserves_order(self):
        """Unknown sort option preserves original order."""
        tasks = [
            ParsedTask("First", Status.PENDING, None, []),
            ParsedTask("Second", Status.PENDING, None, []),
        ]
        sorted_tasks = sort_tasks(tasks, "unknown_sort_option")
        assert [t.text for t in sorted_tasks] == ["First", "Second"]

    def test_sort_empty_list(self):
        """Sorting empty list returns empty list."""
        sorted_tasks = sort_tasks([], "priority")
        assert sorted_tasks == []

    def test_sort_single_task(self):
        """Sorting single task returns that task."""
        tasks = [ParsedTask("Only one", Status.PENDING, None, [])]
        sorted_tasks = sort_tasks(tasks, "priority")
        assert len(sorted_tasks) == 1
        assert sorted_tasks[0].text == "Only one"
