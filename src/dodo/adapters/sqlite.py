"""SQLite adapter."""

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from dodo.models import Status, TodoItem


class SqliteAdapter:
    """SQLite backend - better for querying/filtering large lists."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            project TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_project ON todos(project);
        CREATE INDEX IF NOT EXISTS idx_status ON todos(status);
    """

    def __init__(self, db_path: Path):
        self._path = db_path
        self._ensure_schema()

    def add(self, text: str, project: str | None = None) -> TodoItem:
        item = TodoItem(
            id=uuid.uuid4().hex[:8],
            text=text,
            status=Status.PENDING,
            created_at=datetime.now(),
            project=project,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO todos (id, text, status, project, created_at) VALUES (?, ?, ?, ?, ?)",
                (item.id, item.text, item.status.value, item.project, item.created_at.isoformat()),
            )
        return item

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        query = "SELECT id, text, status, project, created_at, completed_at FROM todos WHERE 1=1"
        params: list[str] = []

        if project:
            query += " AND project = ?"
            params.append(project)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_item(row) for row in rows]

    def get(self, id: str) -> TodoItem | None:
        query = """
            SELECT id, text, status, project, created_at, completed_at
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

    def delete(self, id: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM todos WHERE id = ?", (id,))
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)

    def _row_to_item(self, row: tuple) -> TodoItem:
        id, text, status, project, created_at, completed_at = row
        return TodoItem(
            id=id,
            text=text,
            status=Status(status),
            project=project,
            created_at=datetime.fromisoformat(created_at),
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
        )
