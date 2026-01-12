"""Markdown file backend."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dodo.adapters.utils import (
    format_todo_line,
    generate_todo_id,
    parse_todo_line,
)
from dodo.models import Status, TodoItem


@dataclass
class MarkdownFormat:
    """Format settings - tweak these to change output."""

    timestamp_fmt: str = "%Y-%m-%d %H:%M"
    frontmatter: dict[str, str] | None = None
    section_header: str | None = None


class MarkdownBackend:
    """Markdown file backend.

    Uses shared utilities from dodo.adapters.utils for parsing and formatting.
    """

    def __init__(self, file_path: Path, format: MarkdownFormat | None = None):
        self._path = file_path
        self._format = format or MarkdownFormat()

    def add(self, text: str, project: str | None = None) -> TodoItem:
        timestamp = datetime.now()
        item = TodoItem(
            id=generate_todo_id(text, timestamp),
            text=text,
            status=Status.PENDING,
            created_at=timestamp,
            project=project,
        )
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
                )
                lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_lines(lines)
        return updated_item

    def update_text(self, id: str, text: str) -> TodoItem:
        lines, items = self._read_lines_with_items()
        updated_item = None

        for idx, (line, item) in enumerate(zip(lines, items)):
            if item and item.id == id:
                updated_item = TodoItem(
                    id=generate_todo_id(text, item.created_at),
                    text=text,
                    status=item.status,
                    created_at=item.created_at,
                    completed_at=item.completed_at,
                    project=item.project,
                )
                lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_lines(lines)
        return updated_item

    def delete(self, id: str) -> None:
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
        """Import todos. Returns (imported, skipped)."""
        existing_ids = {i.id for i in self._read_items()}
        imported, skipped = 0, 0
        for item in items:
            if item.id in existing_ids:
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
