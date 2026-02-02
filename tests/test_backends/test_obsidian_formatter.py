"""Tests for Obsidian formatter."""

from datetime import datetime

import pytest

from dodo.models import Priority
from dodo.plugins.obsidian.formatter import (
    format_priority,
    format_tags,
    format_timestamp,
    parse_priority,
    parse_tags,
)


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
