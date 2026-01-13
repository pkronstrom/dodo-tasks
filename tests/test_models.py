"""Tests for data models."""

from datetime import datetime

import pytest

from dodo.models import Status, TodoItem


class TestPriority:
    def test_priority_values(self):
        from dodo.models import Priority

        assert Priority.CRITICAL.value == "critical"
        assert Priority.HIGH.value == "high"
        assert Priority.NORMAL.value == "normal"
        assert Priority.LOW.value == "low"
        assert Priority.SOMEDAY.value == "someday"

    def test_priority_sort_order(self):
        from dodo.models import Priority

        # critical > high > normal > low > someday
        assert Priority.CRITICAL.sort_order == 5
        assert Priority.HIGH.sort_order == 4
        assert Priority.NORMAL.sort_order == 3
        assert Priority.LOW.sort_order == 2
        assert Priority.SOMEDAY.sort_order == 1


class TestStatus:
    def test_pending_value(self):
        assert Status.PENDING.value == "pending"

    def test_done_value(self):
        assert Status.DONE.value == "done"


class TestTodoItem:
    def test_create_minimal(self):
        item = TodoItem(
            id="abc123",
            text="Test todo",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 9, 10, 30),
        )
        assert item.id == "abc123"
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert item.completed_at is None
        assert item.project is None

    def test_immutable(self):
        item = TodoItem(
            id="abc123",
            text="Test todo",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 9, 10, 30),
        )
        with pytest.raises(AttributeError):
            item.text = "Changed"  # type: ignore

    def test_with_project(self):
        item = TodoItem(
            id="abc123",
            text="Test todo",
            status=Status.DONE,
            created_at=datetime(2024, 1, 9, 10, 30),
            completed_at=datetime(2024, 1, 9, 11, 0),
            project="myapp_d1204e",
        )
        assert item.project == "myapp_d1204e"
        assert item.completed_at is not None
