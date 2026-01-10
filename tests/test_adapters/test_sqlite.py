"""Tests for SQLite adapter."""

from pathlib import Path

import pytest

from dodo.models import Status
from dodo.plugins.sqlite.adapter import SqliteAdapter


class TestSqliteAdapterAdd:
    def test_add_creates_db(self, tmp_path: Path):
        db_file = tmp_path / "todos.db"
        adapter = SqliteAdapter(db_file)

        item = adapter.add("Test todo")

        assert db_file.exists()
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert len(item.id) == 8


class TestSqliteAdapterList:
    def test_list_empty(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        assert adapter.list() == []

    def test_list_filter_by_status(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        item = adapter.add("First")
        adapter.add("Second")
        adapter.update(item.id, Status.DONE)

        assert len(adapter.list(status=Status.PENDING)) == 1
        assert len(adapter.list(status=Status.DONE)) == 1

    def test_list_filter_by_project(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        adapter.add("Proj A todo", project="proj_a")
        adapter.add("Proj B todo", project="proj_b")

        items = adapter.list(project="proj_a")
        assert len(items) == 1
        assert items[0].text == "Proj A todo"


class TestSqliteAdapterUpdate:
    def test_update_status(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        item = adapter.add("Test")

        updated = adapter.update(item.id, Status.DONE)

        assert updated.status == Status.DONE
        assert updated.completed_at is not None

    def test_update_nonexistent_raises(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")

        with pytest.raises(KeyError):
            adapter.update("nonexistent", Status.DONE)


class TestSqliteAdapterDelete:
    def test_delete(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        item = adapter.add("Test")

        adapter.delete(item.id)

        assert adapter.get(item.id) is None

    def test_delete_nonexistent_raises(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")

        with pytest.raises(KeyError):
            adapter.delete("nonexistent")


class TestSqliteAdapterGet:
    def test_get_existing(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        item = adapter.add("Test")

        result = adapter.get(item.id)

        assert result is not None
        assert result.id == item.id

    def test_get_nonexistent(self, tmp_path: Path):
        adapter = SqliteAdapter(tmp_path / "todos.db")
        assert adapter.get("nonexistent") is None
