"""Graph wrapper for dependency tracking on SQLite backend."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from dodo.models import Status, TodoItem


class GraphWrapper:
    """Wraps a SQLite backend to add dependency tracking.

    Stores dependencies in a separate table in the same database.
    """

    DEPS_SCHEMA = """
        CREATE TABLE IF NOT EXISTS dependencies (
            blocker_id TEXT NOT NULL,
            blocked_id TEXT NOT NULL,
            PRIMARY KEY (blocker_id, blocked_id)
        );
        CREATE INDEX IF NOT EXISTS idx_blocked ON dependencies(blocked_id);
        CREATE INDEX IF NOT EXISTS idx_blocker ON dependencies(blocker_id);
    """

    def __init__(self, backend):
        self._backend = backend
        self._path: Path = backend._path
        self._ensure_deps_schema()

    # Delegate standard backend methods

    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
    ) -> TodoItem:
        return self._backend.add(text, project=project, priority=priority, tags=tags)

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        from dodo.models import TodoItemView

        items = self._backend.list(project, status)
        # Wrap items with dependency info using TodoItemView
        views = []
        for item in items:
            view = TodoItemView(item=item, blocked_by=self.get_blockers(item.id))
            views.append(view)
        return views

    def get(self, id: str) -> TodoItem | None:
        return self._backend.get(id)

    def update(self, id: str, status: Status) -> TodoItem:
        return self._backend.update(id, status)

    def update_text(self, id: str, text: str) -> TodoItem:
        return self._backend.update_text(id, text)

    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        return self._backend.update_priority(id, priority)

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        return self._backend.update_tags(id, tags)

    def delete(self, id: str) -> None:
        # Also clean up dependencies
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM dependencies WHERE blocker_id = ? OR blocked_id = ?", (id, id)
            )
        self._backend.delete(id)

    # Dependency management methods

    def add_dependency(self, blocker_id: str, blocked_id: str) -> None:
        """Add a dependency: blocker_id blocks blocked_id."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO dependencies (blocker_id, blocked_id) VALUES (?, ?)",
                (blocker_id, blocked_id),
            )

    def remove_dependency(self, blocker_id: str, blocked_id: str) -> None:
        """Remove a dependency."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM dependencies WHERE blocker_id = ? AND blocked_id = ?",
                (blocker_id, blocked_id),
            )

    def get_blockers(self, todo_id: str) -> list[str]:
        """Get IDs of todos blocking this one."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT blocker_id FROM dependencies WHERE blocked_id = ?",
                (todo_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def get_blocked(self, todo_id: str) -> list[str]:
        """Get IDs of todos blocked by this one."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT blocked_id FROM dependencies WHERE blocker_id = ?",
                (todo_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def list_all_dependencies(self) -> list[tuple[str, str]]:
        """List all dependencies as (blocker_id, blocked_id) tuples."""
        with self._connect() as conn:
            rows = conn.execute("SELECT blocker_id, blocked_id FROM dependencies").fetchall()
        return list(rows)

    def get_ready(self, project: str | None = None) -> list[TodoItem]:
        """Get todos with no uncompleted blockers (ready to work on)."""
        from dodo.models import Status

        all_todos = self.list(project=project, status=Status.PENDING)

        # Get all dependencies where blocker is still pending
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT d.blocked_id
                FROM dependencies d
                JOIN todos t ON d.blocker_id = t.id
                WHERE t.status = ?
                """,
                (Status.PENDING.value,),
            ).fetchall()
        blocked_ids = {row[0] for row in rows}

        return [t for t in all_todos if t.id not in blocked_ids]

    def get_blocked_todos(self, project: str | None = None) -> list[TodoItem]:
        """Get todos that have uncompleted blockers."""
        from dodo.models import Status

        all_todos = self.list(project=project, status=Status.PENDING)

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT d.blocked_id
                FROM dependencies d
                JOIN todos t ON d.blocker_id = t.id
                WHERE t.status = ?
                """,
                (Status.PENDING.value,),
            ).fetchall()
        blocked_ids = {row[0] for row in rows}

        return [t for t in all_todos if t.id in blocked_ids]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        # Pragmas for concurrent access (multiple agents)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_deps_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(self.DEPS_SCHEMA)
