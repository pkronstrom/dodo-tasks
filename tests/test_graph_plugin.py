"""Tests for graph plugin."""


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
