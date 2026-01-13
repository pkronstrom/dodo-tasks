"""SQLite backend."""

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from dodo.models import Priority, Status, TodoItem


class SqliteBackend:
    """SQLite backend - better for querying/filtering large lists."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            project TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            priority TEXT,
            tags TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_project ON todos(project);
        CREATE INDEX IF NOT EXISTS idx_status ON todos(status);
        CREATE INDEX IF NOT EXISTS idx_priority ON todos(priority);
    """

    def __init__(self, db_path: Path):
        self._path = db_path
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def __del__(self) -> None:
        """Clean up connection on garbage collection."""
        self.close()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
    ) -> TodoItem:
        item = TodoItem(
            id=uuid.uuid4().hex[:8],
            text=text,
            status=Status.PENDING,
            created_at=datetime.now(),
            project=project,
            priority=priority,
            tags=tags,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO todos (id, text, status, project, created_at, priority, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    item.text,
                    item.status.value,
                    item.project,
                    item.created_at.isoformat(),
                    item.priority.value if item.priority else None,
                    json.dumps(item.tags) if item.tags else None,
                ),
            )
        return item

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        query = "SELECT id, text, status, project, created_at, completed_at, priority, tags FROM todos WHERE 1=1"
        params: list[str] = []

        if project:
            query += " AND project = ?"
            params.append(project)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_item(row) for row in rows]

    def get(self, id: str) -> TodoItem | None:
        query = """
            SELECT id, text, status, project, created_at, completed_at, priority, tags
            FROM todos WHERE id = ?
        """
        with self._connect() as conn:
            row = conn.execute(query, (id,)).fetchone()
        return self._row_to_item(row) if row else None

    def update(self, id: str, status: Status) -> TodoItem:
        completed_at = datetime.now().isoformat() if status == Status.DONE else None

        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE todos SET status = ?, completed_at = ? WHERE id = ?",
                (status.value, completed_at, id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        return item

    def update_text(self, id: str, text: str) -> TodoItem:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE todos SET text = ? WHERE id = ?",
                (text, id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        return item

    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE todos SET priority = ? WHERE id = ?",
                (priority.value if priority else None, id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        return item

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE todos SET tags = ? WHERE id = ?",
                (json.dumps(tags) if tags else None, id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        return item

    def delete(self, id: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM todos WHERE id = ?", (id,))
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

    def export_all(self) -> list[TodoItem]:
        """Export all todos for migration."""
        return self.list()

    def import_all(self, items: list[TodoItem]) -> tuple[int, int]:
        """Import todos. Returns (imported, skipped).

        Skips duplicates by ID or by text+created_at to prevent
        duplicate imports when backends have different IDs for same todos.
        """
        imported, skipped = 0, 0
        with self._connect() as conn:
            for item in items:
                # Check if exists by ID
                existing = conn.execute("SELECT 1 FROM todos WHERE id = ?", (item.id,)).fetchone()
                if existing:
                    skipped += 1
                    continue

                # Also check by text + created_at (catches different IDs, same content)
                existing_by_content = conn.execute(
                    "SELECT 1 FROM todos WHERE text = ? AND created_at = ?",
                    (item.text, item.created_at.isoformat()),
                ).fetchone()
                if existing_by_content:
                    skipped += 1
                    continue

                conn.execute(
                    "INSERT INTO todos (id, text, status, project, created_at, completed_at, priority, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        item.id,
                        item.text,
                        item.status.value,
                        item.project,
                        item.created_at.isoformat(),
                        item.completed_at.isoformat() if item.completed_at else None,
                        item.priority.value if item.priority else None,
                        json.dumps(item.tags) if item.tags else None,
                    ),
                )
                imported += 1
        return imported, skipped

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Get database connection, reusing existing connection if available."""
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path)
            # Pragmas for concurrent access (multiple agents)
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA busy_timeout = 5000")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
            self._run_migrations(conn)

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Run any pending migrations."""
        # Check if priority column exists
        cursor = conn.execute("PRAGMA table_info(todos)")
        columns = {row[1] for row in cursor.fetchall()}

        if "priority" not in columns:
            # Run migration - split statements since ALTER TABLE can't be batched
            conn.execute("ALTER TABLE todos ADD COLUMN priority TEXT")
            conn.execute("ALTER TABLE todos ADD COLUMN tags TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON todos(priority)")

    def _row_to_item(self, row: tuple) -> TodoItem:
        id, text, status, project, created_at, completed_at, priority, tags = row
        return TodoItem(
            id=id,
            text=text,
            status=Status(status),
            project=project,
            created_at=datetime.fromisoformat(created_at),
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
            priority=Priority(priority) if priority else None,
            tags=json.loads(tags) if tags else None,
        )
