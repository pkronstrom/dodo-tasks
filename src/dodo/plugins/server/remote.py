"""Remote backend - connects to a dodo server's REST API.

Implements TodoBackend protocol using httpx. Only needs httpx (core dep),
so no extra installation required for client-only use.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import httpx

from dodo.models import Priority, Status, TodoItem

if TYPE_CHECKING:
    from dodo.config import Config


class RemoteBackend:
    """Backend that proxies to a remote dodo server via REST API."""

    def __init__(self, config: Config, project_id: str | None = None):
        base_url = config.get_plugin_config("server", "remote_url", "")
        if not base_url:
            raise ValueError(
                "Remote URL not configured. Set it with: dodo config"
            )
        self._base_url = base_url.rstrip("/")
        self._dodo_name = project_id or "_default"

        api_key = config.get_plugin_config("server", "remote_key", "")
        auth = httpx.BasicAuth("dodo", api_key) if api_key else None
        self._client = httpx.Client(
            base_url=self._base_url,
            auth=auth,
            timeout=15.0,
        )

    @property
    def _todos_url(self) -> str:
        return f"/api/v1/dodos/{self._dodo_name}/todos"

    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        due_at: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> TodoItem:
        body: dict = {"text": text}
        if priority:
            body["priority"] = priority.value
        if tags:
            body["tags"] = tags
        if due_at:
            body["due_at"] = due_at.isoformat()
        if metadata:
            body["metadata"] = metadata
        resp = self._client.post(self._todos_url, json=body)
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        params = {}
        if status:
            params["status"] = status.value
        resp = self._client.get(self._todos_url, params=params)
        resp.raise_for_status()
        return [_parse_todo(t) for t in resp.json()]

    def get(self, id: str) -> TodoItem | None:
        resp = self._client.get(f"{self._todos_url}/{id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def update(self, id: str, status: Status) -> TodoItem:
        # Get current state to avoid toggling in the wrong direction
        current = self.get(id)
        if not current:
            raise KeyError(f"Todo not found: {id}")
        if current.status == status:
            return current
        resp = self._client.post(f"{self._todos_url}/{id}/toggle")
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def update_text(self, id: str, text: str) -> TodoItem:
        resp = self._client.patch(f"{self._todos_url}/{id}", json={"text": text})
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        resp = self._client.patch(
            f"{self._todos_url}/{id}",
            json={"priority": priority.value if priority else None},
        )
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        resp = self._client.patch(f"{self._todos_url}/{id}", json={"tags": tags})
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def update_due_at(self, id: str, due_at: datetime | None) -> TodoItem:
        resp = self._client.patch(
            f"{self._todos_url}/{id}",
            json={"due_at": due_at.isoformat() if due_at else None},
        )
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def update_metadata(self, id: str, metadata: dict[str, str] | None) -> TodoItem:
        resp = self._client.patch(
            f"{self._todos_url}/{id}", json={"metadata": metadata},
        )
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def set_metadata_key(self, id: str, key: str, value: str) -> TodoItem:
        resp = self._client.post(
            f"{self._todos_url}/{id}/meta/set", json={"key": key, "value": value},
        )
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def remove_metadata_key(self, id: str, key: str) -> TodoItem:
        resp = self._client.post(
            f"{self._todos_url}/{id}/meta/remove", json={"key": key},
        )
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def add_tag(self, id: str, tag: str) -> TodoItem:
        resp = self._client.post(
            f"{self._todos_url}/{id}/tags/add", json={"tag": tag},
        )
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def remove_tag(self, id: str, tag: str) -> TodoItem:
        resp = self._client.post(
            f"{self._todos_url}/{id}/tags/remove", json={"tag": tag},
        )
        resp.raise_for_status()
        return _parse_todo(resp.json())

    def delete(self, id: str) -> None:
        resp = self._client.delete(f"{self._todos_url}/{id}")
        resp.raise_for_status()

    def close(self) -> None:
        self._client.close()


def _parse_todo(data: dict) -> TodoItem:
    """Parse a JSON dict into a TodoItem."""
    return TodoItem(
        id=data["id"],
        text=data["text"],
        status=Status(data["status"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        completed_at=(
            datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None
        ),
        project=data.get("project"),
        priority=Priority(data["priority"]) if data.get("priority") else None,
        tags=data.get("tags"),
        due_at=(
            datetime.fromisoformat(data["due_at"])
            if data.get("due_at")
            else None
        ),
        metadata=data.get("metadata"),
    )
