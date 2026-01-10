"""SQLite adapter plugin for dodo.

This plugin provides SQLite-based todo storage, which is better for
querying and filtering large lists.
"""

name = "sqlite"


def register_adapter(registry: dict) -> None:
    """Register the SQLite adapter with the adapter registry."""
    from dodo.plugins.sqlite.adapter import SqliteAdapter

    registry["sqlite"] = SqliteAdapter
