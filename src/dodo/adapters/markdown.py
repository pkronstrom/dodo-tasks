"""Markdown file adapter."""

import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from pathlib import Path

from dodo.models import Status, TodoItem


@dataclass
class MarkdownFormat:
    """Format settings - tweak these to change output."""

    timestamp_fmt: str = "%Y-%m-%d %H:%M"
    frontmatter: dict[str, str] | None = None
    section_header: str | None = None


class MarkdownAdapter:
    """Markdown file backend.

    To extend: modify _parse_line/_format_item or subclass.
    """

    LINE_PATTERN = re.compile(r"^- \[([ xX])\] (\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}) - (.+)$")

    def __init__(self, file_path: Path, format: MarkdownFormat | None = None):
        self._path = file_path
        self._format = format or MarkdownFormat()

    def add(self, text: str, project: str | None = None) -> TodoItem:
        timestamp = datetime.now()
        item = TodoItem(
            id=self._generate_id(text, timestamp),
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
                lines[idx] = self._format_item(updated_item)
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

    # Extension points

    def _parse_line(self, line: str) -> TodoItem | None:
        """Parse line -> TodoItem. Modify for different formats."""
        match = self.LINE_PATTERN.match(line.strip())
        if not match:
            return None

        checkbox, ts_str, text = match.groups()
        # Handle both - and / date separators
        ts_str = ts_str.replace("/", "-").replace("T", " ")
        timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")

        return TodoItem(
            id=self._generate_id(text, timestamp),
            text=text,
            status=Status.DONE if checkbox.lower() == "x" else Status.PENDING,
            created_at=timestamp,
        )

    def _format_item(self, item: TodoItem) -> str:
        """TodoItem -> line. Modify for different formats."""
        checkbox = "x" if item.status == Status.DONE else " "
        ts = item.created_at.strftime(self._format.timestamp_fmt)
        return f"- [{checkbox}] {ts} - {item.text}"

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

    def _generate_id(self, text: str, timestamp: datetime) -> str:
        # Truncate to minute precision for consistent ID generation
        ts_normalized = timestamp.replace(second=0, microsecond=0)
        content = f"{text}{ts_normalized.isoformat()}"
        return sha1(content.encode()).hexdigest()[:8]

    def _read_items(self) -> list[TodoItem]:
        if not self._path.exists():
            return []
        content = self._path.read_text()
        return [item for ln in content.splitlines() if (item := self._parse_line(ln))]

    def _read_lines_with_items(self) -> tuple[list[str], list[TodoItem | None]]:
        """Read lines paired with parsed items (None for non-todo lines)."""
        if not self._path.exists():
            return [], []
        lines = self._path.read_text().splitlines()
        items = [self._parse_line(ln) for ln in lines]
        return lines, items

    def _write_lines(self, lines: list[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Keep all lines (including non-todo lines like headers)
        self._path.write_text("\n".join(lines) + "\n" if lines else "")

    def _append_item(self, item: TodoItem) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if not self._path.exists():
            content = self._render_file([self._format_item(item)])
            self._path.write_text(content)
        else:
            with self._path.open("a") as f:
                f.write(self._format_item(item) + "\n")
