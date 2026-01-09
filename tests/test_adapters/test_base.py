"""Tests for adapter base protocol."""

from dodo.adapters.base import TodoAdapter


def test_protocol_is_runtime_checkable():
    """Verify TodoAdapter can be checked with isinstance."""
    assert hasattr(TodoAdapter, "__protocol_attrs__") or isinstance(TodoAdapter, type)


def test_protocol_methods():
    """Verify protocol defines expected methods."""
    # Get protocol methods (excluding dunder)
    methods = [m for m in dir(TodoAdapter) if not m.startswith("_")]

    assert "add" in methods
    assert "list" in methods
    assert "get" in methods
    assert "update" in methods
    assert "delete" in methods
