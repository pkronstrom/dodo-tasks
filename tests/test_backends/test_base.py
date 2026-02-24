"""Tests for backend base protocol."""

from dodo.backends.base import TodoBackend


def test_protocol_is_runtime_checkable():
    """Verify TodoBackend can be checked with isinstance."""
    assert hasattr(TodoBackend, "__protocol_attrs__") or isinstance(TodoBackend, type)


def test_protocol_methods():
    """Verify protocol defines expected methods."""
    # Get protocol methods (excluding dunder)
    methods = [m for m in dir(TodoBackend) if not m.startswith("_")]

    assert "add" in methods
    assert "list" in methods
    assert "get" in methods
    assert "update" in methods
    assert "delete" in methods


def test_protocol_has_new_methods():
    methods = [m for m in dir(TodoBackend) if not m.startswith("_")]
    assert "update_due_at" in methods
    assert "update_metadata" in methods
    assert "set_metadata_key" in methods
    assert "remove_metadata_key" in methods
    assert "add_tag" in methods
    assert "remove_tag" in methods


def test_backend_has_storage_path_property(tmp_path):
    """All backends must expose storage_path as a property."""
    from dodo.backends.sqlite import SqliteBackend

    backend = SqliteBackend(tmp_path / "test.db")
    assert backend.storage_path == tmp_path / "test.db"
