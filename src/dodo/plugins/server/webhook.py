"""Webhook backend wrapper — fires POST on mutations."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from dodo.backends.proxy import BackendProxy

if TYPE_CHECKING:
    from dodo.models import Priority, TodoItem

logger = logging.getLogger("dodo.webhook")


def _fire_webhook(url: str, event: str, dodo_name: str, item_dict: dict | None, secret: str):
    """Fire-and-forget POST to webhook URL."""
    import hashlib
    import hmac
    import json

    import httpx

    payload = {
        "event": event,
        "dodo": dodo_name,
        "item": item_dict,
        "timestamp": datetime.now().isoformat(),
    }
    headers = {"Content-Type": "application/json"}
    body = json.dumps(payload)
    if secret:
        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Dodo-Signature"] = sig
    try:
        httpx.post(url, content=body, headers=headers, timeout=3.0)
    except Exception:
        logger.warning("Webhook delivery failed to %s", url)


class WebhookWrapper(BackendProxy):
    """Wraps a backend to fire webhooks on mutations."""

    def __init__(self, backend, webhook_url: str, webhook_secret: str, dodo_name: str):
        super().__init__(backend)
        self._url = webhook_url
        self._secret = webhook_secret
        self._dodo = dodo_name

    def _fire(self, event: str, item: TodoItem | None = None):
        if self._url:
            _fire_webhook(
                self._url, event, self._dodo,
                item.to_dict() if item else None, self._secret,
            )

    # Mutation methods — delegate + fire webhook

    def add(self, text, project=None, priority=None, tags=None, due_at=None, metadata=None):
        item = self._backend.add(text, project=project, priority=priority, tags=tags,
                                  due_at=due_at, metadata=metadata)
        self._fire("todo.added", item)
        return item

    def update(self, id, status):
        item = self._backend.update(id, status)
        self._fire("todo.updated", item)
        return item

    def update_text(self, id, text):
        item = self._backend.update_text(id, text)
        self._fire("todo.updated", item)
        return item

    def update_priority(self, id, priority):
        item = self._backend.update_priority(id, priority)
        self._fire("todo.updated", item)
        return item

    def update_tags(self, id, tags):
        item = self._backend.update_tags(id, tags)
        self._fire("todo.updated", item)
        return item

    def update_due_at(self, id, due_at):
        item = self._backend.update_due_at(id, due_at)
        self._fire("todo.updated", item)
        return item

    def update_metadata(self, id, metadata):
        item = self._backend.update_metadata(id, metadata)
        self._fire("todo.updated", item)
        return item

    def set_metadata_key(self, id, key, value):
        item = self._backend.set_metadata_key(id, key, value)
        self._fire("todo.updated", item)
        return item

    def remove_metadata_key(self, id, key):
        item = self._backend.remove_metadata_key(id, key)
        self._fire("todo.updated", item)
        return item

    def add_tag(self, id, tag):
        item = self._backend.add_tag(id, tag)
        self._fire("todo.updated", item)
        return item

    def remove_tag(self, id, tag):
        item = self._backend.remove_tag(id, tag)
        self._fire("todo.updated", item)
        return item

    def delete(self, id):
        item = self._backend.get(id)
        self._backend.delete(id)
        self._fire("todo.deleted", item)
