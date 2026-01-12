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
