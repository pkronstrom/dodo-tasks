"""Tests for UndoAction model."""

from datetime import datetime

from dodo.models import Status, TodoItem, UndoAction


def test_undo_action_toggle():
    """UndoAction stores toggle information."""
    item = TodoItem(
        id="abc123",
        text="Test todo",
        status=Status.PENDING,
        created_at=datetime.now(),
    )
    action = UndoAction(kind="toggle", item=item)
    assert action.kind == "toggle"
    assert action.item == item
    assert action.new_id is None


def test_undo_action_edit_with_new_id():
    """UndoAction stores edit with new ID."""
    item = TodoItem(
        id="abc123",
        text="Original text",
        status=Status.PENDING,
        created_at=datetime.now(),
    )
    action = UndoAction(kind="edit", item=item, new_id="def456")
    assert action.kind == "edit"
    assert action.new_id == "def456"
