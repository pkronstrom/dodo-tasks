"""Tests for markdown backend."""

from pathlib import Path

import pytest

from dodo.backends.markdown import MarkdownBackend, MarkdownFormat
from dodo.models import Status


class TestMarkdownBackendAdd:
    def test_add_creates_file(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)

        item = backend.add("Test todo")

        assert todo_file.exists()
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert len(item.id) == 8

    def test_add_appends_to_file(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)

        backend.add("First todo")
        backend.add("Second todo")

        lines = todo_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestMarkdownBackendList:
    def test_list_empty_file(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)

        items = backend.list()

        assert items == []

    def test_list_all(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)
        backend.add("First")
        backend.add("Second")

        items = backend.list()

        assert len(items) == 2

    def test_list_filter_by_status(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)
        item = backend.add("First")
        backend.add("Second")
        backend.update(item.id, Status.DONE)

        pending = backend.list(status=Status.PENDING)
        done = backend.list(status=Status.DONE)

        assert len(pending) == 1
        assert len(done) == 1


class TestMarkdownBackendUpdate:
    def test_update_status(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)
        item = backend.add("Test todo")

        updated = backend.update(item.id, Status.DONE)

        assert updated.status == Status.DONE
        assert "[x]" in todo_file.read_text()

    def test_update_nonexistent_raises(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)

        with pytest.raises(KeyError):
            backend.update("nonexistent", Status.DONE)


class TestMarkdownBackendDelete:
    def test_delete_removes_line(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)
        item1 = backend.add("First")
        backend.add("Second")

        backend.delete(item1.id)

        items = backend.list()
        assert len(items) == 1
        assert items[0].text == "Second"

    def test_delete_nonexistent_raises(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)

        with pytest.raises(KeyError):
            backend.delete("nonexistent")


class TestMarkdownBackendGet:
    def test_get_existing(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)
        item = backend.add("Test")

        result = backend.get(item.id)

        assert result is not None
        assert result.id == item.id

    def test_get_nonexistent(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        backend = MarkdownBackend(todo_file)

        result = backend.get("nonexistent")

        assert result is None


class TestMarkdownFormat:
    def test_custom_timestamp_format(self, tmp_path: Path):
        todo_file = tmp_path / "dodo.md"
        fmt = MarkdownFormat(timestamp_fmt="%Y/%m/%d")
        backend = MarkdownBackend(todo_file, format=fmt)

        backend.add("Test")

        content = todo_file.read_text()
        assert "/" in content  # Uses custom format
