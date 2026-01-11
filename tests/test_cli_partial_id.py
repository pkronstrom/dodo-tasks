"""Tests for partial ID matching."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
import typer

from dodo.cli import _find_item_by_partial_id
from dodo.models import Status, TodoItem


def test_ambiguous_partial_id_raises_exit():
    """Ambiguous partial ID should exit with error, not pick first."""
    mock_svc = MagicMock()
    mock_svc.get.return_value = None
    mock_svc.list.return_value = [
        TodoItem(id="abc123", text="First", status=Status.PENDING, created_at=datetime.now()),
        TodoItem(id="abc456", text="Second", status=Status.PENDING, created_at=datetime.now()),
    ]

    with pytest.raises(typer.Exit) as exc_info:
        _find_item_by_partial_id(mock_svc, "abc")

    assert exc_info.value.exit_code == 1


def test_unique_partial_id_returns_item():
    """Unique partial ID should return the matching item."""
    mock_svc = MagicMock()
    mock_svc.get.return_value = None
    item = TodoItem(id="xyz789", text="Only one", status=Status.PENDING, created_at=datetime.now())
    mock_svc.list.return_value = [item]

    result = _find_item_by_partial_id(mock_svc, "xyz")
    assert result == item
