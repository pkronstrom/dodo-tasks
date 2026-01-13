"""Tests for SQLite backend."""

from pathlib import Path

import pytest

from dodo.backends.sqlite import SqliteBackend
from dodo.models import Status


class TestSqliteBackendAdd:
    def test_add_creates_db(self, tmp_path: Path):
        db_file = tmp_path / "dodo.db"
        backend = SqliteBackend(db_file)

        item = backend.add("Test todo")

        assert db_file.exists()
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert len(item.id) == 8


class TestSqliteBackendList:
    def test_list_empty(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        assert backend.list() == []

    def test_list_filter_by_status(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("First")
        backend.add("Second")
        backend.update(item.id, Status.DONE)

        assert len(backend.list(status=Status.PENDING)) == 1
        assert len(backend.list(status=Status.DONE)) == 1

    def test_list_filter_by_project(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        backend.add("Proj A todo", project="proj_a")
        backend.add("Proj B todo", project="proj_b")

        items = backend.list(project="proj_a")
        assert len(items) == 1
        assert items[0].text == "Proj A todo"


class TestSqliteBackendUpdate:
    def test_update_status(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")

        updated = backend.update(item.id, Status.DONE)

        assert updated.status == Status.DONE
        assert updated.completed_at is not None

    def test_update_nonexistent_raises(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")

        with pytest.raises(KeyError):
            backend.update("nonexistent", Status.DONE)


class TestSqliteBackendDelete:
    def test_delete(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")

        backend.delete(item.id)

        assert backend.get(item.id) is None

    def test_delete_nonexistent_raises(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")

        with pytest.raises(KeyError):
            backend.delete("nonexistent")


class TestSqliteBackendGet:
    def test_get_existing(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")

        result = backend.get(item.id)

        assert result is not None
        assert result.id == item.id

    def test_get_nonexistent(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        assert backend.get("nonexistent") is None


class TestSqliteBackendPriorityTags:
    def test_add_with_priority(self, tmp_path: Path):
        from dodo.models import Priority

        backend = SqliteBackend(tmp_path / "dodo.db")

        item = backend.add("Test", priority=Priority.HIGH)

        assert item.priority == Priority.HIGH
        # Verify persisted
        retrieved = backend.get(item.id)
        assert retrieved.priority == Priority.HIGH

    def test_add_with_tags(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")

        item = backend.add("Test", tags=["backend", "api"])

        assert item.tags == ["backend", "api"]
        retrieved = backend.get(item.id)
        assert retrieved.tags == ["backend", "api"]

    def test_add_defaults_none(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")

        item = backend.add("Test")

        assert item.priority is None
        assert item.tags is None

    def test_update_priority(self, tmp_path: Path):
        from dodo.models import Priority

        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")

        updated = backend.update_priority(item.id, Priority.CRITICAL)

        assert updated.priority == Priority.CRITICAL

    def test_update_tags(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")

        updated = backend.update_tags(item.id, ["new-tag"])

        assert updated.tags == ["new-tag"]
