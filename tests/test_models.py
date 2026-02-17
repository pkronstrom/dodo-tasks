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


class TestTodoItemPriorityTags:
    def test_todoitem_with_priority(self):
        from dodo.models import Priority

        item = TodoItem(
            id="abc12345",
            text="Test",
            status=Status.PENDING,
            created_at=datetime.now(),
            priority=Priority.HIGH,
        )
        assert item.priority == Priority.HIGH

    def test_todoitem_with_tags(self):
        item = TodoItem(
            id="abc12345",
            text="Test",
            status=Status.PENDING,
            created_at=datetime.now(),
            tags=["backend", "urgent"],
        )
        assert item.tags == ["backend", "urgent"]

    def test_todoitem_defaults_none(self):
        item = TodoItem(
            id="abc12345",
            text="Test",
            status=Status.PENDING,
            created_at=datetime.now(),
        )
        assert item.priority is None
        assert item.tags is None

    def test_todoitem_to_dict_includes_priority_tags(self):
        from dodo.models import Priority

        item = TodoItem(
            id="abc12345",
            text="Test",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            priority=Priority.HIGH,
            tags=["api"],
        )
        d = item.to_dict()
        assert d["priority"] == "high"
        assert d["tags"] == ["api"]


class TestTodoItemDueAtMetadata:
    def test_todoitem_with_due_at(self):
        from dodo.models import TodoItem, Status
        from datetime import datetime
        item = TodoItem(
            id="abc12345", text="Test", status=Status.PENDING,
            created_at=datetime.now(), due_at=datetime(2026, 3, 1),
        )
        assert item.due_at == datetime(2026, 3, 1)

    def test_todoitem_with_metadata(self):
        from dodo.models import TodoItem, Status
        from datetime import datetime
        item = TodoItem(
            id="abc12345", text="Test", status=Status.PENDING,
            created_at=datetime.now(), metadata={"status": "wip", "assignee": "agent"},
        )
        assert item.metadata == {"status": "wip", "assignee": "agent"}

    def test_todoitem_defaults_none(self):
        from dodo.models import TodoItem, Status
        from datetime import datetime
        item = TodoItem(
            id="abc12345", text="Test", status=Status.PENDING,
            created_at=datetime.now(),
        )
        assert item.due_at is None
        assert item.metadata is None

    def test_todoitem_to_dict_includes_new_fields(self):
        from dodo.models import TodoItem, Status
        from datetime import datetime
        item = TodoItem(
            id="abc12345", text="Test", status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            due_at=datetime(2026, 3, 1),
            metadata={"status": "wip"},
        )
        d = item.to_dict()
        assert d["due_at"] == "2026-03-01T00:00:00"
        assert d["metadata"] == {"status": "wip"}

    def test_todoitem_to_dict_none_fields(self):
        from dodo.models import TodoItem, Status
        from datetime import datetime
        item = TodoItem(
            id="abc12345", text="Test", status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
        )
        d = item.to_dict()
        assert d["due_at"] is None
        assert d["metadata"] is None


class TestTodoItemViewNewFields:
    def test_view_delegates_due_at(self):
        from dodo.models import TodoItem, TodoItemView, Status
        from datetime import datetime
        item = TodoItem(
            id="abc12345", text="Test", status=Status.PENDING,
            created_at=datetime.now(), due_at=datetime(2026, 3, 1),
            metadata={"k": "v"},
        )
        view = TodoItemView(item=item)
        assert view.due_at == datetime(2026, 3, 1)
        assert view.metadata == {"k": "v"}

    def test_view_to_dict_includes_new_fields(self):
        from dodo.models import TodoItem, TodoItemView, Status
        from datetime import datetime
        item = TodoItem(
            id="abc12345", text="Test", status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            due_at=datetime(2026, 3, 1), metadata={"k": "v"},
        )
        view = TodoItemView(item=item)
        d = view.to_dict()
        assert d["due_at"] == "2026-03-01T00:00:00"
        assert d["metadata"] == {"k": "v"}
