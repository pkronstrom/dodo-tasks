"""Tests for markdown adapter."""

from pathlib import Path

import pytest

from dodo.adapters.markdown import MarkdownAdapter, MarkdownFormat
from dodo.models import Status


class TestMarkdownAdapterAdd:
    def test_add_creates_file(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        item = adapter.add("Test todo")

        assert todo_file.exists()
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert len(item.id) == 8

    def test_add_appends_to_file(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        adapter.add("First todo")
        adapter.add("Second todo")

        lines = todo_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestMarkdownAdapterList:
    def test_list_empty_file(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        items = adapter.list()

        assert items == []

    def test_list_all(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        adapter.add("First")
        adapter.add("Second")

        items = adapter.list()

        assert len(items) == 2

    def test_list_filter_by_status(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        item = adapter.add("First")
        adapter.add("Second")
        adapter.update(item.id, Status.DONE)

        pending = adapter.list(status=Status.PENDING)
        done = adapter.list(status=Status.DONE)

        assert len(pending) == 1
        assert len(done) == 1


class TestMarkdownAdapterUpdate:
    def test_update_status(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        item = adapter.add("Test todo")

        updated = adapter.update(item.id, Status.DONE)

        assert updated.status == Status.DONE
        assert "[x]" in todo_file.read_text()

    def test_update_nonexistent_raises(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        with pytest.raises(KeyError):
            adapter.update("nonexistent", Status.DONE)


class TestMarkdownAdapterDelete:
    def test_delete_removes_line(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        item1 = adapter.add("First")
        adapter.add("Second")

        adapter.delete(item1.id)

        items = adapter.list()
        assert len(items) == 1
        assert items[0].text == "Second"

    def test_delete_nonexistent_raises(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        with pytest.raises(KeyError):
            adapter.delete("nonexistent")


class TestMarkdownAdapterGet:
    def test_get_existing(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)
        item = adapter.add("Test")

        result = adapter.get(item.id)

        assert result is not None
        assert result.id == item.id

    def test_get_nonexistent(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        adapter = MarkdownAdapter(todo_file)

        result = adapter.get("nonexistent")

        assert result is None


class TestMarkdownFormat:
    def test_custom_timestamp_format(self, tmp_path: Path):
        todo_file = tmp_path / "todo.md"
        fmt = MarkdownFormat(timestamp_fmt="%Y/%m/%d")
        adapter = MarkdownAdapter(todo_file, format=fmt)

        adapter.add("Test")

        content = todo_file.read_text()
        assert "/" in content  # Uses custom format
