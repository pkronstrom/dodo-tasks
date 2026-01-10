"""Obsidian Local REST API adapter."""

from datetime import datetime

import httpx

from dodo.adapters.utils import (
    format_todo_line,
    generate_todo_id,
    parse_todo_line,
)
from dodo.models import Status, TodoItem


class ObsidianAdapter:
    """Obsidian Local REST API backend.

    Requires: obsidian-local-rest-api plugin running.
    Docs: https://github.com/coddingtonbear/obsidian-local-rest-api
    """

    DEFAULT_API_URL = "https://localhost:27124"

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str = "",
        vault_path: str = "dodo/todos.md",
    ):
        self._api_url = (api_url or self.DEFAULT_API_URL).rstrip("/")
        self._api_key = api_key
        self._vault_path = vault_path
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            verify=False,  # Local self-signed cert
            timeout=10.0,
        )

    def add(self, text: str, project: str | None = None) -> TodoItem:
        timestamp = datetime.now()
        item = TodoItem(
            id=generate_todo_id(text, timestamp),
            text=text,
            status=Status.PENDING,
            created_at=timestamp,
            project=project,
        )

        line = format_todo_line(item)
        self._append_to_note(line)
        return item

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        content = self._read_note()
        items = self._parse_content(content)

        if status:
            items = [i for i in items if i.status == status]
        return items

    def get(self, id: str) -> TodoItem | None:
        return next((i for i in self.list() if i.id == id), None)

    def update(self, id: str, status: Status) -> TodoItem:
        content = self._read_note()
        lines = content.splitlines()
        updated_item = None

        for idx, line in enumerate(lines):
            item = parse_todo_line(line)
            if item and item.id == id:
                updated_item = TodoItem(
                    id=item.id,
                    text=item.text,
                    status=status,
                    created_at=item.created_at,
                    completed_at=datetime.now() if status == Status.DONE else None,
                    project=item.project,
                )
                lines[idx] = format_todo_line(updated_item)
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_note("\n".join(lines))
        return updated_item

    def update_text(self, id: str, text: str) -> TodoItem:
        content = self._read_note()
        lines = content.splitlines()
        updated_item = None

        for idx, line in enumerate(lines):
            item = parse_todo_line(line)
            if item and item.id == id:
                updated_item = TodoItem(
                    id=generate_todo_id(text, item.created_at),
                    text=text,
                    status=item.status,
                    created_at=item.created_at,
                    completed_at=item.completed_at,
                    project=item.project,
                )
                lines[idx] = format_todo_line(updated_item)
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_note("\n".join(lines))
        return updated_item

    def delete(self, id: str) -> None:
        content = self._read_note()
        lines = content.splitlines()
        new_lines = [ln for ln in lines if not self._line_matches_id(ln, id)]

        if len(new_lines) == len(lines):
            raise KeyError(f"Todo not found: {id}")

        self._write_note("\n".join(new_lines))

    def export_all(self) -> list[TodoItem]:
        """Export all todos for migration."""
        return self.list()

    def import_all(self, items: list[TodoItem]) -> tuple[int, int]:
        """Import todos. Returns (imported, skipped)."""
        existing_ids = {i.id for i in self.list()}
        imported, skipped = 0, 0
        for item in items:
            if item.id in existing_ids:
                skipped += 1
            else:
                line = format_todo_line(item)
                self._append_to_note(line)
                imported += 1
        return imported, skipped

    # REST API calls

    def _read_note(self) -> str:
        """GET /vault/{path}"""
        try:
            resp = self._client.get(f"{self._api_url}/vault/{self._vault_path}")
            if resp.status_code == 404:
                return ""
            resp.raise_for_status()
            return resp.text
        except httpx.RequestError as e:
            raise ConnectionError(f"Obsidian API error: {e}") from e

    def _write_note(self, content: str) -> None:
        """PUT /vault/{path}"""
        resp = self._client.put(
            f"{self._api_url}/vault/{self._vault_path}",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()

    def _append_to_note(self, line: str) -> None:
        """POST /vault/{path} with append."""
        resp = self._client.post(
            f"{self._api_url}/vault/{self._vault_path}",
            content=line + "\n",
            headers={
                "Content-Type": "text/markdown",
                "X-Append": "true",
            },
        )
        resp.raise_for_status()

    # Helper methods

    def _parse_content(self, content: str) -> list[TodoItem]:
        return [item for ln in content.splitlines() if (item := parse_todo_line(ln))]

    def _line_matches_id(self, line: str, id: str) -> bool:
        item = parse_todo_line(line)
        return item is not None and item.id == id
