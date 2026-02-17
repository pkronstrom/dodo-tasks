"""Tests for server plugin REST API routes."""

from pathlib import Path

import pytest

# Skip entire module if starlette not installed
starlette = pytest.importorskip("starlette")

from starlette.testclient import TestClient  # noqa: E402

from dodo.config import Config  # noqa: E402
from dodo.plugins.server.app import create_app  # noqa: E402


@pytest.fixture
def config(tmp_path: Path):
    """Create a config with server plugin settings."""
    cfg = Config.load(tmp_path / "config")
    cfg.set("enabled_plugins", "server")
    cfg.set_plugin_config("server", "enable_api", "true")
    cfg.set_plugin_config("server", "enable_web_ui", "false")
    cfg.set_plugin_config("server", "enable_mcp", "false")
    return cfg


@pytest.fixture
def client(config):
    """Create a test client for the server app."""
    app = create_app(config)
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestListDodos:
    def test_list_dodos_returns_default(self, client):
        resp = client.get("/api/v1/dodos")
        assert resp.status_code == 200
        dodos = resp.json()
        assert any(d["name"] == "_default" for d in dodos)

    def test_list_dodos_includes_named(self, client, config):
        # Create a named project
        project_dir = config.config_dir / "projects" / "work"
        project_dir.mkdir(parents=True)
        (project_dir / "dodo.db").touch()

        resp = client.get("/api/v1/dodos")
        names = [d["name"] for d in resp.json()]
        assert "work" in names


class TestTodosCRUD:
    def test_add_todo(self, client):
        resp = client.post(
            "/api/v1/dodos/_default/todos",
            json={"text": "Buy milk"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "Buy milk"
        assert data["status"] == "pending"
        assert data["id"]

    def test_add_todo_with_priority_and_tags(self, client):
        resp = client.post(
            "/api/v1/dodos/_default/todos",
            json={"text": "Fix bug", "priority": "high", "tags": ["work"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "high"
        assert data["tags"] == ["work"]

    def test_add_todo_empty_text(self, client):
        resp = client.post(
            "/api/v1/dodos/_default/todos",
            json={"text": ""},
        )
        assert resp.status_code == 400

    def test_list_todos(self, client):
        client.post("/api/v1/dodos/_default/todos", json={"text": "First"})
        client.post("/api/v1/dodos/_default/todos", json={"text": "Second"})

        resp = client.get("/api/v1/dodos/_default/todos")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_todos_with_filter(self, client):
        r = client.post("/api/v1/dodos/_default/todos", json={"text": "Task"})
        todo_id = r.json()["id"]
        client.post(f"/api/v1/dodos/_default/todos/{todo_id}/complete")

        pending = client.get("/api/v1/dodos/_default/todos?status=pending")
        done = client.get("/api/v1/dodos/_default/todos?status=done")
        assert len(pending.json()) == 0
        assert len(done.json()) == 1

    def test_get_todo(self, client):
        r = client.post("/api/v1/dodos/_default/todos", json={"text": "Test"})
        todo_id = r.json()["id"]

        resp = client.get(f"/api/v1/dodos/_default/todos/{todo_id}")
        assert resp.status_code == 200
        assert resp.json()["text"] == "Test"

    def test_get_todo_not_found(self, client):
        resp = client.get("/api/v1/dodos/_default/todos/nonexistent")
        assert resp.status_code == 404

    def test_toggle_todo(self, client):
        r = client.post("/api/v1/dodos/_default/todos", json={"text": "Toggle me"})
        todo_id = r.json()["id"]

        resp = client.post(f"/api/v1/dodos/_default/todos/{todo_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

        resp = client.post(f"/api/v1/dodos/_default/todos/{todo_id}/toggle")
        assert resp.json()["status"] == "pending"

    def test_complete_todo(self, client):
        r = client.post("/api/v1/dodos/_default/todos", json={"text": "Complete me"})
        todo_id = r.json()["id"]

        resp = client.post(f"/api/v1/dodos/_default/todos/{todo_id}/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    def test_update_text(self, client):
        r = client.post("/api/v1/dodos/_default/todos", json={"text": "Old text"})
        todo_id = r.json()["id"]

        resp = client.patch(
            f"/api/v1/dodos/_default/todos/{todo_id}",
            json={"text": "New text"},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "New text"

    def test_update_priority(self, client):
        r = client.post("/api/v1/dodos/_default/todos", json={"text": "Prio test"})
        todo_id = r.json()["id"]

        resp = client.patch(
            f"/api/v1/dodos/_default/todos/{todo_id}",
            json={"priority": "critical"},
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == "critical"

    def test_delete_todo(self, client):
        r = client.post("/api/v1/dodos/_default/todos", json={"text": "Delete me"})
        todo_id = r.json()["id"]

        resp = client.delete(f"/api/v1/dodos/_default/todos/{todo_id}")
        assert resp.status_code == 200

        resp = client.get(f"/api/v1/dodos/_default/todos/{todo_id}")
        assert resp.status_code == 404


class TestMultiDodo:
    def test_todos_isolated_between_dodos(self, client, config):
        # Create a named project dir so it resolves
        project_dir = config.config_dir / "projects" / "work"
        project_dir.mkdir(parents=True)

        client.post("/api/v1/dodos/_default/todos", json={"text": "Global task"})
        client.post("/api/v1/dodos/work/todos", json={"text": "Work task"})

        global_todos = client.get("/api/v1/dodos/_default/todos").json()
        work_todos = client.get("/api/v1/dodos/work/todos").json()

        assert len(global_todos) == 1
        assert global_todos[0]["text"] == "Global task"
        assert len(work_todos) == 1
        assert work_todos[0]["text"] == "Work task"


class TestDeleteDodo:
    def test_delete_named_dodo(self, client, config):
        # Create a named dodo
        dodo_dir = config.config_dir / "testdodo"
        dodo_dir.mkdir(parents=True)
        (dodo_dir / "dodo.db").touch()

        # Verify it shows up
        dodos = client.get("/api/v1/dodos").json()
        assert any(d["name"] == "testdodo" for d in dodos)

        # Delete it
        resp = client.delete("/api/v1/dodos/testdodo")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}

        # Verify it's gone
        dodos = client.get("/api/v1/dodos").json()
        assert not any(d["name"] == "testdodo" for d in dodos)
        assert not dodo_dir.exists()

    def test_delete_default_rejected(self, client):
        resp = client.delete("/api/v1/dodos/_default")
        assert resp.status_code == 400
        assert "Cannot delete" in resp.json()["error"]

    def test_delete_nonexistent_dodo(self, client):
        resp = client.delete("/api/v1/dodos/nosuchdodo")
        assert resp.status_code == 404

    def test_delete_invalid_name(self, client):
        resp = client.delete("/api/v1/dodos/.evil")
        assert resp.status_code == 400
        assert "Invalid dodo name" in resp.json()["error"]

    def test_delete_dodo_from_projects_subdir(self, client, config):
        # Create a dodo under projects/
        project_dir = config.config_dir / "projects" / "myproject"
        project_dir.mkdir(parents=True)
        (project_dir / "dodo.db").touch()

        resp = client.delete("/api/v1/dodos/myproject")
        assert resp.status_code == 200
        assert not project_dir.exists()

    def test_delete_evicts_cached_service(self, client, config):
        # Create dodo and access it to populate cache
        dodo_dir = config.config_dir / "cached"
        dodo_dir.mkdir(parents=True)
        (dodo_dir / "dodo.db").touch()

        client.post("/api/v1/dodos/cached/todos", json={"text": "warm cache"})

        resp = client.delete("/api/v1/dodos/cached")
        assert resp.status_code == 200
        assert not dodo_dir.exists()

    def test_delete_path_traversal_rejected(self, client):
        # Slashes get normalized by Starlette routing (404), dots rejected by validation (400)
        resp = client.delete("/api/v1/dodos/..%2F..%2Fetc")
        assert resp.status_code in (400, 404)
        # Direct dot-prefix name is caught by validation
        resp = client.delete("/api/v1/dodos/..evil")
        assert resp.status_code == 400


class TestErrorPaths:
    def test_invalid_status_filter(self, client):
        resp = client.get("/api/v1/dodos/_default/todos?status=invalid")
        assert resp.status_code == 400
        assert "Invalid status" in resp.json()["error"]

    def test_invalid_priority_on_add(self, client):
        resp = client.post(
            "/api/v1/dodos/_default/todos",
            json={"text": "Task", "priority": "urgent"},
        )
        assert resp.status_code == 400
        assert "Invalid priority" in resp.json()["error"]

    def test_toggle_nonexistent_todo(self, client):
        resp = client.post("/api/v1/dodos/_default/todos/nonexistent/toggle")
        assert resp.status_code == 404

    def test_complete_nonexistent_todo(self, client):
        resp = client.post("/api/v1/dodos/_default/todos/nonexistent/complete")
        assert resp.status_code == 404

    def test_delete_nonexistent_todo(self, client):
        resp = client.delete("/api/v1/dodos/_default/todos/nonexistent")
        assert resp.status_code == 404

    def test_update_nonexistent_todo(self, client):
        resp = client.patch(
            "/api/v1/dodos/_default/todos/nonexistent",
            json={"text": "Updated"},
        )
        assert resp.status_code == 404

    def test_update_no_fields(self, client):
        r = client.post("/api/v1/dodos/_default/todos", json={"text": "Task"})
        todo_id = r.json()["id"]
        resp = client.patch(f"/api/v1/dodos/_default/todos/{todo_id}", json={})
        assert resp.status_code == 400
        assert "no fields" in resp.json()["error"]

    def test_invalid_dodo_name_rejected(self, client):
        # Names starting with . or _ (except _default) are invalid
        resp = client.get("/api/v1/dodos/.evil/todos")
        assert resp.status_code == 400
        assert "Invalid dodo name" in resp.json()["error"]

    def test_invalid_dodo_name_special_chars(self, client):
        resp = client.post(
            "/api/v1/dodos/bad%20name/todos",
            json={"text": "hack"},
        )
        assert resp.status_code == 400


class TestTodosNewFields:
    def test_add_todo_with_due_at(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "due_at": "2026-03-01T00:00:00",
        })
        assert resp.status_code == 201
        assert resp.json()["due_at"] == "2026-03-01T00:00:00"

    def test_add_todo_with_metadata(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "metadata": {"status": "wip"},
        })
        assert resp.status_code == 201
        assert resp.json()["metadata"] == {"status": "wip"}

    def test_update_todo_due_at(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={"text": "Test"})
        todo_id = resp.json()["id"]
        resp = client.patch(f"/api/v1/dodos/_default/todos/{todo_id}", json={
            "due_at": "2026-06-15T00:00:00",
        })
        assert resp.status_code == 200
        assert resp.json()["due_at"] == "2026-06-15T00:00:00"

    def test_update_todo_metadata(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={"text": "Test"})
        todo_id = resp.json()["id"]
        resp = client.patch(f"/api/v1/dodos/_default/todos/{todo_id}", json={
            "metadata": {"k": "v"},
        })
        assert resp.status_code == 200
        assert resp.json()["metadata"] == {"k": "v"}

    def test_get_todo_includes_new_fields(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "due_at": "2026-03-01T00:00:00",
            "metadata": {"k": "v"},
        })
        todo_id = resp.json()["id"]
        resp = client.get(f"/api/v1/dodos/_default/todos/{todo_id}")
        assert resp.json()["due_at"] == "2026-03-01T00:00:00"
        assert resp.json()["metadata"] == {"k": "v"}

    def test_list_todos_includes_new_fields(self, client):
        client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "due_at": "2026-03-01T00:00:00",
            "metadata": {"k": "v"},
        })
        resp = client.get("/api/v1/dodos/_default/todos")
        items = resp.json()
        assert items[0]["due_at"] == "2026-03-01T00:00:00"
        assert items[0]["metadata"] == {"k": "v"}


class TestAtomicTagEndpoints:
    def test_add_tag(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "tags": ["a"],
        })
        todo_id = resp.json()["id"]
        resp = client.post(
            f"/api/v1/dodos/_default/todos/{todo_id}/tags/add",
            json={"tag": "b"},
        )
        assert resp.status_code == 200
        assert "b" in resp.json()["tags"]
        assert "a" in resp.json()["tags"]

    def test_remove_tag(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "tags": ["a", "b"],
        })
        todo_id = resp.json()["id"]
        resp = client.post(
            f"/api/v1/dodos/_default/todos/{todo_id}/tags/remove",
            json={"tag": "a"},
        )
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["b"]

    def test_add_tag_not_found(self, client):
        resp = client.post(
            "/api/v1/dodos/_default/todos/nonexistent/tags/add",
            json={"tag": "x"},
        )
        assert resp.status_code == 404


class TestAtomicMetaEndpoints:
    def test_set_metadata(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={"text": "Test"})
        todo_id = resp.json()["id"]
        resp = client.post(
            f"/api/v1/dodos/_default/todos/{todo_id}/meta/set",
            json={"key": "status", "value": "wip"},
        )
        assert resp.status_code == 200
        assert resp.json()["metadata"] == {"status": "wip"}

    def test_remove_metadata(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "metadata": {"a": "1", "b": "2"},
        })
        todo_id = resp.json()["id"]
        resp = client.post(
            f"/api/v1/dodos/_default/todos/{todo_id}/meta/remove",
            json={"key": "a"},
        )
        assert resp.status_code == 200
        assert resp.json()["metadata"] == {"b": "2"}

    def test_set_metadata_not_found(self, client):
        resp = client.post(
            "/api/v1/dodos/_default/todos/nonexistent/meta/set",
            json={"key": "k", "value": "v"},
        )
        assert resp.status_code == 404


class TestListTodosFiltering:
    def test_filter_overdue(self, client):
        client.post("/api/v1/dodos/_default/todos", json={
            "text": "Overdue", "due_at": "2020-01-01T00:00:00",
        })
        client.post("/api/v1/dodos/_default/todos", json={
            "text": "Future", "due_at": "2099-01-01T00:00:00",
        })
        resp = client.get("/api/v1/dodos/_default/todos?overdue=true")
        items = resp.json()
        assert len(items) == 1
        assert items[0]["text"] == "Overdue"

    def test_filter_by_metadata(self, client):
        client.post("/api/v1/dodos/_default/todos", json={
            "text": "WIP", "metadata": {"status": "wip"},
        })
        client.post("/api/v1/dodos/_default/todos", json={
            "text": "Normal",
        })
        resp = client.get("/api/v1/dodos/_default/todos?meta.status=wip")
        items = resp.json()
        assert len(items) == 1
        assert items[0]["text"] == "WIP"


class TestMetadataValidation:
    def test_add_todo_rejects_non_dict_metadata(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "metadata": "not-a-dict",
        })
        assert resp.status_code == 400
        assert "metadata must be" in resp.json()["error"]

    def test_add_todo_rejects_list_metadata(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={
            "text": "Test", "metadata": ["a", "b"],
        })
        assert resp.status_code == 400

    def test_patch_rejects_non_dict_metadata(self, client):
        resp = client.post("/api/v1/dodos/_default/todos", json={"text": "Test"})
        todo_id = resp.json()["id"]
        resp = client.patch(f"/api/v1/dodos/_default/todos/{todo_id}", json={
            "metadata": 42,
        })
        assert resp.status_code == 400
        assert "metadata must be" in resp.json()["error"]

    def test_patch_invalid_due_at_does_not_partial_apply(self, client):
        """PATCH with valid text + invalid due_at should not apply text change."""
        resp = client.post("/api/v1/dodos/_default/todos", json={"text": "Original"})
        todo_id = resp.json()["id"]
        resp = client.patch(f"/api/v1/dodos/_default/todos/{todo_id}", json={
            "text": "Changed", "due_at": "not-a-date",
        })
        assert resp.status_code == 400
        # Verify original text is unchanged
        resp = client.get(f"/api/v1/dodos/_default/todos/{todo_id}")
        assert resp.json()["text"] == "Original"


class TestAuth:
    def test_auth_required_when_configured(self, tmp_path):
        cfg = Config.load(tmp_path / "config")
        cfg.set_plugin_config("server", "enable_api", "true")
        cfg.set_plugin_config("server", "enable_web_ui", "false")
        cfg.set_plugin_config("server", "enable_mcp", "false")
        cfg.set_plugin_config("server", "api_key", "secret123")

        app = create_app(cfg)
        client = TestClient(app)

        # No auth -> 401
        resp = client.get("/api/v1/dodos")
        assert resp.status_code == 401

        # Wrong password -> 401
        resp = client.get("/api/v1/dodos", auth=("dodo", "wrong"))
        assert resp.status_code == 401

        # Correct auth -> 200
        resp = client.get("/api/v1/dodos", auth=("dodo", "secret123"))
        assert resp.status_code == 200

    def test_health_bypasses_auth(self, tmp_path):
        cfg = Config.load(tmp_path / "config")
        cfg.set_plugin_config("server", "enable_api", "true")
        cfg.set_plugin_config("server", "enable_web_ui", "false")
        cfg.set_plugin_config("server", "enable_mcp", "false")
        cfg.set_plugin_config("server", "api_key", "secret123")

        app = create_app(cfg)
        client = TestClient(app)

        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
