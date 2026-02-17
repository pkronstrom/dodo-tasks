"""Tests for webhook backend wrapper."""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dodo.backends.sqlite import SqliteBackend
from dodo.config import Config
from dodo.models import Status


class TestWebhookWrapper:
    def test_fires_on_add(self, tmp_path: Path):
        from dodo.plugins.server.webhook import WebhookWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = WebhookWrapper(backend, "http://example.com/hook", "", "test")
        with patch("dodo.plugins.server.webhook._fire_webhook") as mock_fire:
            item = wrapper.add("Test")
            mock_fire.assert_called_once()
            args = mock_fire.call_args
            assert args[0][1] == "todo.added"

    def test_fires_on_delete(self, tmp_path: Path):
        from dodo.plugins.server.webhook import WebhookWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = WebhookWrapper(backend, "http://example.com/hook", "", "test")
        item = backend.add("Test")
        with patch("dodo.plugins.server.webhook._fire_webhook") as mock_fire:
            wrapper.delete(item.id)
            mock_fire.assert_called_once()
            args = mock_fire.call_args
            assert args[0][1] == "todo.deleted"

    def test_fires_on_set_metadata_key(self, tmp_path: Path):
        from dodo.plugins.server.webhook import WebhookWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = WebhookWrapper(backend, "http://example.com/hook", "", "test")
        item = backend.add("Test")
        with patch("dodo.plugins.server.webhook._fire_webhook") as mock_fire:
            wrapper.set_metadata_key(item.id, "k", "v")
            mock_fire.assert_called_once()

    def test_delegates_all_reads(self, tmp_path: Path):
        from dodo.plugins.server.webhook import WebhookWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = WebhookWrapper(backend, "http://example.com/hook", "", "test")
        item = backend.add("Test")
        assert wrapper.get(item.id) is not None
        assert len(wrapper.list()) == 1

    def test_no_webhook_when_url_empty(self, tmp_path: Path):
        from dodo.plugins.server.webhook import WebhookWrapper
        backend = SqliteBackend(tmp_path / "dodo.db")
        wrapper = WebhookWrapper(backend, "", "", "test")
        with patch("dodo.plugins.server.webhook._fire_webhook") as mock_fire:
            wrapper.add("Test")
            mock_fire.assert_not_called()
