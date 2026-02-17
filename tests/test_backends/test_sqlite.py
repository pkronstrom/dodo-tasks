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


class TestSqliteBackendDueAtMetadata:
    def test_add_with_due_at(self, tmp_path: Path):
        from datetime import datetime
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test", due_at=datetime(2026, 3, 1))
        assert item.due_at == datetime(2026, 3, 1)
        retrieved = backend.get(item.id)
        assert retrieved.due_at == datetime(2026, 3, 1)

    def test_add_with_metadata(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test", metadata={"status": "wip"})
        assert item.metadata == {"status": "wip"}
        retrieved = backend.get(item.id)
        assert retrieved.metadata == {"status": "wip"}

    def test_add_defaults_none(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")
        assert item.due_at is None
        assert item.metadata is None

    def test_update_due_at(self, tmp_path: Path):
        from datetime import datetime
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")
        updated = backend.update_due_at(item.id, datetime(2026, 6, 15))
        assert updated.due_at == datetime(2026, 6, 15)

    def test_update_due_at_clear(self, tmp_path: Path):
        from datetime import datetime
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test", due_at=datetime(2026, 3, 1))
        updated = backend.update_due_at(item.id, None)
        assert updated.due_at is None

    def test_update_due_at_nonexistent(self, tmp_path: Path):
        from datetime import datetime
        backend = SqliteBackend(tmp_path / "dodo.db")
        with pytest.raises(KeyError):
            backend.update_due_at("nonexistent", datetime(2026, 3, 1))

    def test_update_metadata(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")
        updated = backend.update_metadata(item.id, {"status": "wip"})
        assert updated.metadata == {"status": "wip"}

    def test_update_metadata_clear(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test", metadata={"k": "v"})
        updated = backend.update_metadata(item.id, None)
        assert updated.metadata is None

    def test_update_metadata_nonexistent(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        with pytest.raises(KeyError):
            backend.update_metadata("nonexistent", {"k": "v"})

    def test_migration_adds_columns(self, tmp_path: Path):
        """Opening existing DB without new columns triggers migration."""
        import sqlite3
        db_path = tmp_path / "dodo.db"
        # Create old-style DB with only original columns
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE todos (
                id TEXT PRIMARY KEY, text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', project TEXT,
                created_at TEXT NOT NULL, completed_at TEXT,
                priority TEXT, tags TEXT
            );
        """)
        conn.execute(
            "INSERT INTO todos VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("abc12345", "Old item", "pending", None,
             "2024-01-01T10:00:00", None, None, None),
        )
        conn.commit()
        conn.close()

        # Open with new backend — should migrate
        backend = SqliteBackend(db_path)
        item = backend.get("abc12345")
        assert item is not None
        assert item.due_at is None
        assert item.metadata is None

        # New fields should work
        from datetime import datetime
        updated = backend.update_due_at("abc12345", datetime(2026, 3, 1))
        assert updated.due_at is not None
