"""Markdown file backend."""

from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dodo.backends.utils import (
    format_todo_line,
    generate_todo_id,
    parse_todo_line,
)
from dodo.models import Priority, Status, TodoItem


@contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    """Acquire exclusive file lock for atomic operations.

    Uses flock() for advisory locking. Creates lock file if needed.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@dataclass
class MarkdownFormat:
    """Format settings - tweak these to change output."""

    timestamp_fmt: str = "%Y-%m-%d %H:%M"
    frontmatter: dict[str, str] | None = None
    section_header: str | None = None


class MarkdownBackend:
    """Markdown file backend.

    Uses shared utilities from dodo.backends.utils for parsing and formatting.
    """

    def __init__(self, file_path: Path, format: MarkdownFormat | None = None):
        self._path = file_path
        self._format = format or MarkdownFormat()
        self._lock_path = file_path.with_suffix(".lock")

    @property
    def storage_path(self) -> Path | None:
        return self._path

    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        due_at: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> TodoItem:
        # due_at and metadata not supported by markdown backend
        timestamp = datetime.now()
        item = TodoItem(
            id=generate_todo_id(text, timestamp),
            text=text,
            status=Status.PENDING,
            created_at=timestamp,
            project=project,
            priority=priority,
            tags=tags,
        )
        with _file_lock(self._lock_path):
            self._append_item(item)
        return item

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        items = self._read_items()
        if status:
            items = [i for i in items if i.status == status]
        return items

    def get(self, id: str) -> TodoItem | None:
        return next((i for i in self._read_items() if i.id == id), None)

    def update(self, id: str, status: Status) -> TodoItem:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            updated_item = None

            for idx, (line, item) in enumerate(zip(lines, items)):
                if item and item.id == id:
                    updated_item = TodoItem(
                        id=item.id,
                        text=item.text,
                        status=status,
                        created_at=item.created_at,
                        completed_at=datetime.now() if status == Status.DONE else None,
                        project=item.project,
                        priority=item.priority,
                        tags=item.tags,
                    )
                    lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                    break

            if not updated_item:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(lines)
            return updated_item

    def update_text(self, id: str, text: str) -> TodoItem:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            updated_item = None

            for idx, (line, item) in enumerate(zip(lines, items)):
                if item and item.id == id:
                    updated_item = TodoItem(
                        id=item.id,  # Keep original ID stable on text edit
                        text=text,
                        status=item.status,
                        created_at=item.created_at,
                        completed_at=item.completed_at,
                        project=item.project,
                        priority=item.priority,
                        tags=item.tags,
                    )
                    lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                    break

            if not updated_item:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(lines)
            return updated_item

    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            updated_item = None

            for idx, (line, item) in enumerate(zip(lines, items)):
                if item and item.id == id:
                    updated_item = TodoItem(
                        id=item.id,
                        text=item.text,
                        status=item.status,
                        created_at=item.created_at,
                        completed_at=item.completed_at,
                        project=item.project,
                        priority=priority,
                        tags=item.tags,
                    )
                    lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                    break

            if not updated_item:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(lines)
            return updated_item

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            updated_item = None

            for idx, (line, item) in enumerate(zip(lines, items)):
                if item and item.id == id:
                    updated_item = TodoItem(
                        id=item.id,
                        text=item.text,
                        status=item.status,
                        created_at=item.created_at,
                        completed_at=item.completed_at,
                        project=item.project,
                        priority=item.priority,
                        tags=tags,
                    )
                    lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                    break

            if not updated_item:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(lines)
            return updated_item

    def update_due_at(self, id: str, due_at: datetime | None) -> TodoItem:
        raise NotImplementedError("Markdown backend does not support due dates")

    def update_metadata(self, id: str, metadata: dict[str, str] | None) -> TodoItem:
        raise NotImplementedError("Markdown backend does not support metadata")

    def set_metadata_key(self, id: str, key: str, value: str) -> TodoItem:
        raise NotImplementedError("Markdown backend does not support metadata")

    def remove_metadata_key(self, id: str, key: str) -> TodoItem:
        raise NotImplementedError("Markdown backend does not support metadata")

    def add_tag(self, id: str, tag: str) -> TodoItem:
        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        tags = list(item.tags) if item.tags else []
        if tag not in tags:
            tags.append(tag)
        return self.update_tags(id, tags)

    def remove_tag(self, id: str, tag: str) -> TodoItem:
        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        tags = list(item.tags) if item.tags else []
        if tag in tags:
            tags.remove(tag)
        return self.update_tags(id, tags if tags else None)

    def delete(self, id: str) -> None:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            original_len = len(lines)
            new_lines = [ln for ln, item in zip(lines, items) if not item or item.id != id]

            if len(new_lines) == original_len:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(new_lines)

    def export_all(self) -> list[TodoItem]:
        """Export all todos for migration."""
        return self._read_items()

    def import_all(self, items: list[TodoItem]) -> tuple[int, int]:
        """Import todos. Returns (imported, skipped).

        Skips duplicates by ID or by text+created_at to prevent
        duplicate imports when backends have different IDs for same todos.
        """
        with _file_lock(self._lock_path):
            existing = self._read_items()
            existing_ids = {i.id for i in existing}
            # Also track by content to catch different IDs, same todo
            existing_content = {(i.text, i.created_at.isoformat()) for i in existing}

            imported, skipped = 0, 0
            for item in items:
                if item.id in existing_ids:
                    skipped += 1
                elif (item.text, item.created_at.isoformat()) in existing_content:
                    skipped += 1
                else:
                    self._append_item(item)
                    imported += 1
            return imported, skipped

    # Customization methods (kept for frontmatter/section support)

    def _render_file(self, lines: list[str]) -> str:
        """Full file content. Modify to add frontmatter/sections."""
        parts: list[str] = []

        if self._format.frontmatter:
            parts.append("---")
            for k, v in self._format.frontmatter.items():
                parts.append(f"{k}: {v}")
            parts.append("---")
            parts.append("")

        if self._format.section_header:
            parts.append(self._format.section_header)
            parts.append("")

        parts.extend(lines)
        return "\n".join(parts) + "\n" if parts else ""

    # Private helpers

    def _read_items(self) -> list[TodoItem]:
        if not self._path.exists():
            return []
        content = self._path.read_text()
        return [item for ln in content.splitlines() if (item := parse_todo_line(ln))]

    def _read_lines_with_items(self) -> tuple[list[str], list[TodoItem | None]]:
        """Read lines paired with parsed items (None for non-todo lines)."""
        if not self._path.exists():
            return [], []
        lines = self._path.read_text().splitlines()
        items = [parse_todo_line(ln) for ln in lines]
        return lines, items

    def _write_lines(self, lines: list[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Keep all lines (including non-todo lines like headers)
        self._path.write_text("\n".join(lines) + "\n" if lines else "")

    def _append_item(self, item: TodoItem) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if not self._path.exists():
            content = self._render_file([format_todo_line(item, self._format.timestamp_fmt)])
            self._path.write_text(content)
        else:
            with self._path.open("a") as f:
                f.write(format_todo_line(item, self._format.timestamp_fmt) + "\n")
