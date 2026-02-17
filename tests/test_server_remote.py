"""Tests for server plugin remote backend."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dodo.config import Config
from dodo.models import Priority, Status
from dodo.plugins.server.remote import RemoteBackend, _parse_todo


@pytest.fixture
def config(tmp_path: Path):
    """Create a config with remote backend settings."""
    cfg = Config.load(tmp_path / "config")
    cfg.set_plugin_config("server", "remote_url", "http://localhost:8080")
    cfg.set_plugin_config("server", "remote_key", "")
    return cfg


class TestRemoteBackendInit:
    def test_creates_with_config(self, config):
        backend = RemoteBackend(config, project_id="work")
        assert backend._dodo_name == "work"
        assert backend._base_url == "http://localhost:8080"

    def test_default_dodo_name(self, config):
        backend = RemoteBackend(config)
        assert backend._dodo_name == "_default"

    def test_raises_without_url(self, tmp_path):
        cfg = Config.load(tmp_path / "config")
        with pytest.raises(ValueError, match="Remote URL not configured"):
            RemoteBackend(cfg)

    def test_strips_trailing_slash(self, tmp_path):
        cfg = Config.load(tmp_path / "config")
        cfg.set_plugin_config("server", "remote_url", "http://localhost:8080/")
        backend = RemoteBackend(cfg)
        assert backend._base_url == "http://localhost:8080"


class TestParseTodo:
    def test_parse_minimal(self):
        data = {
            "id": "abc123",
            "text": "Test todo",
            "status": "pending",
            "created_at": "2024-01-01T12:00:00",
        }
        item = _parse_todo(data)
        assert item.id == "abc123"
        assert item.text == "Test todo"
        assert item.status == Status.PENDING
        assert item.priority is None
        assert item.tags is None

    def test_parse_full(self):
        data = {
            "id": "abc123",
            "text": "Test todo",
            "status": "done",
            "created_at": "2024-01-01T12:00:00",
            "completed_at": "2024-01-02T10:00:00",
            "project": "work",
            "priority": "high",
            "tags": ["urgent", "bug"],
        }
        item = _parse_todo(data)
        assert item.status == Status.DONE
        assert item.priority == Priority.HIGH
        assert item.tags == ["urgent", "bug"]
        assert item.completed_at is not None

    def test_parse_with_new_fields(self):
        data = {
            "id": "abc123",
            "text": "Test",
            "status": "pending",
            "created_at": "2024-01-01T12:00:00",
            "due_at": "2026-03-01T00:00:00",
            "metadata": {"status": "wip"},
        }
        item = _parse_todo(data)
        from datetime import datetime
        assert item.due_at == datetime(2026, 3, 1)
        assert item.metadata == {"status": "wip"}


class TestRemoteBackendMethods:
    """Test remote backend methods with mocked httpx."""

    @pytest.fixture
    def backend(self, config):
        return RemoteBackend(config, project_id="work")

    def test_add(self, backend):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": "1",
            "text": "New task",
            "status": "pending",
            "created_at": "2024-01-01T12:00:00",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "post", return_value=mock_resp) as mock_post:
            item = backend.add("New task", priority=Priority.HIGH, tags=["work"])

        mock_post.assert_called_once_with(
            "/api/v1/dodos/work/todos",
            json={"text": "New task", "priority": "high", "tags": ["work"]},
        )
        assert item.text == "New task"

    def test_list(self, backend):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"id": "1", "text": "Task 1", "status": "pending", "created_at": "2024-01-01T12:00:00"},
            {"id": "2", "text": "Task 2", "status": "done", "created_at": "2024-01-01T12:00:00"},
        ]
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "get", return_value=mock_resp) as mock_get:
            items = backend.list(status=Status.PENDING)

        mock_get.assert_called_once_with(
            "/api/v1/dodos/work/todos",
            params={"status": "pending"},
        )
        assert len(items) == 2

    def test_get(self, backend):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "1",
            "text": "Task 1",
            "status": "pending",
            "created_at": "2024-01-01T12:00:00",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "get", return_value=mock_resp):
            item = backend.get("1")
        assert item.id == "1"

    def test_get_not_found(self, backend):
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch.object(backend._client, "get", return_value=mock_resp):
            item = backend.get("nonexistent")
        assert item is None

    def test_delete(self, backend):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "delete", return_value=mock_resp) as mock_del:
            backend.delete("1")

        mock_del.assert_called_once_with("/api/v1/dodos/work/todos/1")

    def test_update_to_done(self, backend):
        """update(id, DONE) toggles a PENDING item."""
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
        }
        get_resp.raise_for_status = MagicMock()

        toggle_resp = MagicMock()
        toggle_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "done",
            "created_at": "2024-01-01T12:00:00",
        }
        toggle_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "get", return_value=get_resp), \
             patch.object(backend._client, "post", return_value=toggle_resp):
            item = backend.update("1", Status.DONE)
        assert item.status == Status.DONE

    def test_update_noop_when_already_correct(self, backend):
        """update(id, PENDING) on an already-pending item is a no-op."""
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
        }
        get_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "get", return_value=get_resp), \
             patch.object(backend._client, "post") as mock_post:
            item = backend.update("1", Status.PENDING)
        assert item.status == Status.PENDING
        mock_post.assert_not_called()

    def test_update_text(self, backend):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "1",
            "text": "Updated",
            "status": "pending",
            "created_at": "2024-01-01T12:00:00",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "patch", return_value=mock_resp):
            item = backend.update_text("1", "Updated")
        assert item.text == "Updated"

    def test_add_with_due_at_and_metadata(self, backend):
        from datetime import datetime
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
            "due_at": "2026-03-01T00:00:00",
            "metadata": {"k": "v"},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "post", return_value=mock_resp) as mock_post:
            item = backend.add("Task", due_at=datetime(2026, 3, 1), metadata={"k": "v"})

        call_body = mock_post.call_args[1]["json"]
        assert call_body["due_at"] == "2026-03-01T00:00:00"
        assert call_body["metadata"] == {"k": "v"}
        assert item.due_at == datetime(2026, 3, 1)

    def test_update_due_at(self, backend):
        from datetime import datetime
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
            "due_at": "2026-06-15T00:00:00",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "patch", return_value=mock_resp):
            item = backend.update_due_at("1", datetime(2026, 6, 15))
        assert item.due_at == datetime(2026, 6, 15)

    def test_update_metadata(self, backend):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
            "metadata": {"k": "v"},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "patch", return_value=mock_resp):
            item = backend.update_metadata("1", {"k": "v"})
        assert item.metadata == {"k": "v"}

    def test_set_metadata_key(self, backend):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
            "metadata": {"status": "wip"},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "post", return_value=mock_resp) as mock_post:
            item = backend.set_metadata_key("1", "status", "wip")
        mock_post.assert_called_once_with(
            "/api/v1/dodos/work/todos/1/meta/set",
            json={"key": "status", "value": "wip"},
        )
        assert item.metadata == {"status": "wip"}

    def test_remove_metadata_key(self, backend):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
            "metadata": {"b": "2"},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "post", return_value=mock_resp):
            item = backend.remove_metadata_key("1", "a")
        assert item.metadata == {"b": "2"}

    def test_add_tag(self, backend):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
            "tags": ["a", "b"],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "post", return_value=mock_resp) as mock_post:
            item = backend.add_tag("1", "b")
        mock_post.assert_called_once_with(
            "/api/v1/dodos/work/todos/1/tags/add",
            json={"tag": "b"},
        )
        assert "b" in item.tags

    def test_remove_tag(self, backend):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "1", "text": "Task", "status": "pending",
            "created_at": "2024-01-01T12:00:00",
            "tags": ["b"],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._client, "post", return_value=mock_resp):
            item = backend.remove_tag("1", "a")
        assert item.tags == ["b"]
