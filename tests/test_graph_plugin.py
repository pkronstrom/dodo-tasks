"""Tests for graph plugin."""

import pytest


@pytest.fixture
def graph_wrapper(tmp_path):
    """Create a GraphWrapper with SQLite backend for testing."""
    from dodo.backends.sqlite import SqliteBackend
    from dodo.plugins.graph.wrapper import GraphWrapper

    db_path = tmp_path / "test.db"
    backend = SqliteBackend(db_path)
    return GraphWrapper(backend)


class TestGraphWrapperDependencies:
    """Tests for dependency management in GraphWrapper."""

    def test_add_dependency(self, graph_wrapper):
        """add_dependency creates a dependency relationship."""
        t1 = graph_wrapper.add("Task 1")
        t2 = graph_wrapper.add("Task 2")

        graph_wrapper.add_dependency(t1.id, t2.id)

        blockers = graph_wrapper.get_blockers(t2.id)
        assert t1.id in blockers

    def test_add_dependency_idempotent(self, graph_wrapper):
        """Adding same dependency twice doesn't create duplicates."""
        t1 = graph_wrapper.add("Task 1")
        t2 = graph_wrapper.add("Task 2")

        graph_wrapper.add_dependency(t1.id, t2.id)
        graph_wrapper.add_dependency(t1.id, t2.id)  # Second time

        blockers = graph_wrapper.get_blockers(t2.id)
        assert blockers.count(t1.id) == 1

    def test_remove_dependency(self, graph_wrapper):
        """remove_dependency removes a dependency relationship."""
        t1 = graph_wrapper.add("Task 1")
        t2 = graph_wrapper.add("Task 2")

        graph_wrapper.add_dependency(t1.id, t2.id)
        assert t1.id in graph_wrapper.get_blockers(t2.id)

        graph_wrapper.remove_dependency(t1.id, t2.id)
        assert t1.id not in graph_wrapper.get_blockers(t2.id)

    def test_get_blockers(self, graph_wrapper):
        """get_blockers returns IDs of todos blocking this one."""
        t1 = graph_wrapper.add("Blocker 1")
        t2 = graph_wrapper.add("Blocker 2")
        t3 = graph_wrapper.add("Blocked task")

        graph_wrapper.add_dependency(t1.id, t3.id)
        graph_wrapper.add_dependency(t2.id, t3.id)

        blockers = graph_wrapper.get_blockers(t3.id)
        assert t1.id in blockers
        assert t2.id in blockers
        assert len(blockers) == 2

    def test_get_blocked(self, graph_wrapper):
        """get_blocked returns IDs of todos blocked by this one."""
        t1 = graph_wrapper.add("Blocker")
        t2 = graph_wrapper.add("Blocked 1")
        t3 = graph_wrapper.add("Blocked 2")

        graph_wrapper.add_dependency(t1.id, t2.id)
        graph_wrapper.add_dependency(t1.id, t3.id)

        blocked = graph_wrapper.get_blocked(t1.id)
        assert t2.id in blocked
        assert t3.id in blocked
        assert len(blocked) == 2

    def test_list_all_dependencies(self, graph_wrapper):
        """list_all_dependencies returns all dependency tuples."""
        t1 = graph_wrapper.add("Task 1")
        t2 = graph_wrapper.add("Task 2")
        t3 = graph_wrapper.add("Task 3")

        graph_wrapper.add_dependency(t1.id, t2.id)
        graph_wrapper.add_dependency(t2.id, t3.id)

        deps = graph_wrapper.list_all_dependencies()
        assert (t1.id, t2.id) in deps
        assert (t2.id, t3.id) in deps
        assert len(deps) == 2

    def test_delete_cascades_dependencies(self, graph_wrapper):
        """Deleting a todo removes its dependencies."""
        t1 = graph_wrapper.add("Blocker")
        t2 = graph_wrapper.add("Blocked")
        t3 = graph_wrapper.add("Also blocked")

        graph_wrapper.add_dependency(t1.id, t2.id)
        graph_wrapper.add_dependency(t1.id, t3.id)

        # Delete the blocker
        graph_wrapper.delete(t1.id)

        # Dependencies should be cleaned up
        assert graph_wrapper.get_blockers(t2.id) == []
        assert graph_wrapper.get_blockers(t3.id) == []
        assert graph_wrapper.list_all_dependencies() == []


class TestGraphWrapperQueries:
    """Tests for dependency-aware queries."""

    def test_get_ready_returns_unblocked_todos(self, graph_wrapper):
        """get_ready returns todos with no pending blockers."""

        t1 = graph_wrapper.add("Ready task")
        t2 = graph_wrapper.add("Blocker")
        t3 = graph_wrapper.add("Blocked task")

        graph_wrapper.add_dependency(t2.id, t3.id)

        ready = graph_wrapper.get_ready()
        ready_ids = [t.id for t in ready]

        assert t1.id in ready_ids  # No blockers
        assert t2.id in ready_ids  # Is a blocker but not blocked
        assert t3.id not in ready_ids  # Blocked by t2

    def test_get_ready_includes_todo_when_blocker_done(self, graph_wrapper):
        """get_ready includes todo when its blocker is completed."""
        from dodo.models import Status

        t1 = graph_wrapper.add("Blocker")
        t2 = graph_wrapper.add("Blocked task")

        graph_wrapper.add_dependency(t1.id, t2.id)

        # Initially blocked
        ready = graph_wrapper.get_ready()
        assert t2.id not in [t.id for t in ready]

        # Complete the blocker
        graph_wrapper.update(t1.id, Status.DONE)

        # Now unblocked
        ready = graph_wrapper.get_ready()
        assert t2.id in [t.id for t in ready]

    def test_get_blocked_todos(self, graph_wrapper):
        """get_blocked_todos returns todos with pending blockers."""
        t1 = graph_wrapper.add("Blocker")
        t2 = graph_wrapper.add("Blocked")
        t3 = graph_wrapper.add("Free")

        graph_wrapper.add_dependency(t1.id, t2.id)

        blocked = graph_wrapper.get_blocked_todos()
        blocked_ids = [t.id for t in blocked]

        assert t2.id in blocked_ids
        assert t1.id not in blocked_ids
        assert t3.id not in blocked_ids


class TestGraphWrapperNewMethods:
    def test_add_with_due_at(self, tmp_path):
        from datetime import datetime
        from dodo.backends.sqlite import SqliteBackend
        from dodo.plugins.graph.wrapper import GraphWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = GraphWrapper(backend)
        item = wrapper.add("Test", due_at=datetime(2026, 3, 1))
        assert item.due_at == datetime(2026, 3, 1)

    def test_update_due_at(self, tmp_path):
        from datetime import datetime
        from dodo.backends.sqlite import SqliteBackend
        from dodo.plugins.graph.wrapper import GraphWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = GraphWrapper(backend)
        item = wrapper.add("Test")
        updated = wrapper.update_due_at(item.id, datetime(2026, 3, 1))
        assert updated.due_at == datetime(2026, 3, 1)

    def test_update_metadata(self, tmp_path):
        from dodo.backends.sqlite import SqliteBackend
        from dodo.plugins.graph.wrapper import GraphWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = GraphWrapper(backend)
        item = wrapper.add("Test")
        updated = wrapper.update_metadata(item.id, {"k": "v"})
        assert updated.metadata == {"k": "v"}

    def test_set_metadata_key(self, tmp_path):
        from dodo.backends.sqlite import SqliteBackend
        from dodo.plugins.graph.wrapper import GraphWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = GraphWrapper(backend)
        item = wrapper.add("Test")
        updated = wrapper.set_metadata_key(item.id, "k", "v")
        assert updated.metadata == {"k": "v"}

    def test_remove_metadata_key(self, tmp_path):
        from dodo.backends.sqlite import SqliteBackend
        from dodo.plugins.graph.wrapper import GraphWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = GraphWrapper(backend)
        item = wrapper.add("Test", metadata={"a": "1"})
        updated = wrapper.remove_metadata_key(item.id, "a")
        assert updated.metadata is None or updated.metadata == {}

    def test_add_tag(self, tmp_path):
        from dodo.backends.sqlite import SqliteBackend
        from dodo.plugins.graph.wrapper import GraphWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = GraphWrapper(backend)
        item = wrapper.add("Test", tags=["a"])
        updated = wrapper.add_tag(item.id, "b")
        assert "b" in updated.tags

    def test_remove_tag(self, tmp_path):
        from dodo.backends.sqlite import SqliteBackend
        from dodo.plugins.graph.wrapper import GraphWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = GraphWrapper(backend)
        item = wrapper.add("Test", tags=["a", "b"])
        updated = wrapper.remove_tag(item.id, "a")
        assert updated.tags == ["b"]


def test_list_attaches_blocked_by(tmp_path):
    """GraphWrapper.list() should attach blocked_by to items."""
    from dodo.backends.sqlite import SqliteBackend
    from dodo.plugins.graph.wrapper import GraphWrapper

    db_path = tmp_path / "test.db"
    backend = SqliteBackend(db_path)
    wrapper = GraphWrapper(backend)

    # Add todos
    t1 = wrapper.add("Task 1")
    t2 = wrapper.add("Task 2")

    # Add dependency: t1 blocks t2
    wrapper.add_dependency(t1.id, t2.id)

    # List todos
    items = wrapper.list()

    # Find t2 and check blocked_by
    t2_item = next(i for i in items if i.id == t2.id)
    assert hasattr(t2_item, "blocked_by")
    assert t1.id in t2_item.blocked_by


def test_formatter_shows_blocked_by_column():
    """GraphFormatter wrapper should add blocked_by column when items have it."""
    from datetime import datetime
    from io import StringIO

    from rich.console import Console

    from dodo.formatters import TableFormatter
    from dodo.models import Status, TodoItem
    from dodo.plugins.graph.formatter import GraphFormatter

    # GraphFormatter wraps the base TableFormatter
    formatter = GraphFormatter(TableFormatter())

    now = datetime.now()
    # Create items with blocked_by
    item1 = TodoItem(id="abc12345", text="Task 1", status=Status.PENDING, created_at=now)
    item2 = TodoItem(id="def67890", text="Task 2", status=Status.PENDING, created_at=now)
    object.__setattr__(item1, "blocked_by", [])
    object.__setattr__(item2, "blocked_by", ["abc12345"])

    result = formatter.format([item1, item2])

    # Render table to string
    output_buf = StringIO()
    console = Console(file=output_buf, force_terminal=True)
    console.print(result)
    output = output_buf.getvalue()

    assert "Blocked" in output or "blocked" in output.lower()
    assert "abc12345" in output


def test_tree_formatter_output():
    """Tree formatter should show dependency hierarchy."""
    from datetime import datetime
    from io import StringIO

    from rich.console import Console

    from dodo.models import Status, TodoItem
    from dodo.plugins.graph.tree import TreeFormatter

    formatter = TreeFormatter()

    now = datetime.now()
    # Create hierarchy: t1 -> t2 -> t3, and t4 standalone
    t1 = TodoItem(id="aaa11111", text="Setup", status=Status.PENDING, created_at=now)
    t2 = TodoItem(id="bbb22222", text="Build", status=Status.PENDING, created_at=now)
    t3 = TodoItem(id="ccc33333", text="Test", status=Status.PENDING, created_at=now)
    t4 = TodoItem(id="ddd44444", text="Standalone", status=Status.PENDING, created_at=now)

    object.__setattr__(t1, "blocked_by", [])
    object.__setattr__(t2, "blocked_by", ["aaa11111"])
    object.__setattr__(t3, "blocked_by", ["bbb22222"])
    object.__setattr__(t4, "blocked_by", [])

    result = formatter.format([t1, t2, t3, t4])

    # Render to string
    output_buf = StringIO()
    console = Console(file=output_buf, force_terminal=True)
    console.print(result)
    output = output_buf.getvalue()

    # Should show tree structure
    assert "Setup" in output
    assert "Build" in output
    assert "└" in output or "├" in output
