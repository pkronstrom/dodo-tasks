"""Tests for graph plugin."""


def test_list_attaches_blocked_by(tmp_path):
    """GraphWrapper.list() should attach blocked_by to items."""
    from dodo.plugins.graph.wrapper import GraphWrapper
    from dodo.plugins.sqlite.adapter import SqliteAdapter

    db_path = tmp_path / "test.db"
    adapter = SqliteAdapter(db_path)
    wrapper = GraphWrapper(adapter)

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
