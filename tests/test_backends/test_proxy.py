"""Tests for BackendProxy base class."""

from pathlib import Path

from dodo.backends.proxy import BackendProxy
from dodo.backends.sqlite import SqliteBackend
from dodo.models import Status


class TestBackendProxy:
    def test_delegates_add(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "test.db")
        proxy = BackendProxy(backend)

        item = proxy.add("Test todo")

        assert item.text == "Test todo"

    def test_delegates_list(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "test.db")
        proxy = BackendProxy(backend)
        proxy.add("Test")

        items = proxy.list()

        assert len(items) == 1

    def test_delegates_storage_path(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "test.db")
        proxy = BackendProxy(backend)

        assert proxy.storage_path == tmp_path / "test.db"

    def test_delegates_update(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "test.db")
        proxy = BackendProxy(backend)
        item = proxy.add("Test")

        updated = proxy.update(item.id, Status.DONE)

        assert updated.status == Status.DONE

    def test_delegates_delete(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "test.db")
        proxy = BackendProxy(backend)
        item = proxy.add("Test")

        proxy.delete(item.id)

        assert proxy.list() == []

    def test_delegates_unknown_attrs(self, tmp_path: Path):
        """Unknown attributes fall through to wrapped backend."""
        backend = SqliteBackend(tmp_path / "test.db")
        proxy = BackendProxy(backend)

        # _path is on SqliteBackend but not on proxy, so it should delegate.
        assert proxy._path == tmp_path / "test.db"
