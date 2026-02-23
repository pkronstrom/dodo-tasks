"""Tests for MCP single-tool action dispatch (handle_action)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dodo.config import Config
from dodo.core import TodoService
from dodo.plugins.server.mcp_server import handle_action


class _TestRegistry:
    """Lightweight ServiceRegistry that doesn't import starlette."""

    def __init__(self, config: Config):
        self._config = config
        self._cache: dict[str, TodoService] = {}

    def get_service(self, dodo_name: str) -> TodoService:
        if dodo_name not in self._cache:
            project_id = None if dodo_name == "_default" else dodo_name
            self._cache[dodo_name] = TodoService(self._config, project_id)
        return self._cache[dodo_name]

    def list_dodos(self) -> list[dict]:
        return [{"name": "_default", "backend": self._config.default_backend}]


@pytest.fixture()
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _TestRegistry:
    monkeypatch.setenv("HOME", str(tmp_path))
    config_dir = tmp_path / ".config" / "dodo"
    config_dir.mkdir(parents=True)
    cfg = Config.load(config_dir)
    return _TestRegistry(cfg)


class TestDescribe:
    def test_describe_all(self, registry):
        result = handle_action({"action": "describe"}, registry)
        assert isinstance(result, list)
        names = [r["action"] for r in result]
        assert "list_dodos" in names
        assert "add_todo" in names
        assert "describe" not in names  # describe itself not in _ACTIONS

    def test_describe_one(self, registry):
        result = handle_action(
            {"action": "describe", "action_name": "add_todo"}, registry
        )
        assert result["action"] == "add_todo"
        assert "text" in result["params"]
        assert result["params"]["text"]["required"] is True

    def test_describe_unknown(self, registry):
        with pytest.raises(ValueError, match="Unknown action 'nope'"):
            handle_action({"action": "describe", "action_name": "nope"}, registry)


class TestListDodos:
    def test_returns_default(self, registry):
        result = handle_action({"action": "list_dodos"}, registry)
        assert isinstance(result, list)
        names = [d["name"] for d in result]
        assert "_default" in names


class TestCRUD:
    def test_add_and_get(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "buy milk"}, registry
        )
        assert item["text"] == "buy milk"
        assert item["status"] == "pending"

        got = handle_action(
            {"action": "get_todo", "dodo": "_default", "id": item["id"]}, registry
        )
        assert got["text"] == "buy milk"

    def test_add_with_priority(self, registry):
        item = handle_action(
            {
                "action": "add_todo",
                "dodo": "_default",
                "text": "urgent task",
                "priority": "high",
            },
            registry,
        )
        assert item["priority"] == "high"

    def test_complete(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "do it"}, registry
        )
        done = handle_action(
            {"action": "complete_todo", "dodo": "_default", "id": item["id"]}, registry
        )
        assert done["status"] == "done"

    def test_toggle(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "toggle me"}, registry
        )
        toggled = handle_action(
            {"action": "toggle_todo", "dodo": "_default", "id": item["id"]}, registry
        )
        assert toggled["status"] == "done"
        toggled2 = handle_action(
            {"action": "toggle_todo", "dodo": "_default", "id": item["id"]}, registry
        )
        assert toggled2["status"] == "pending"

    def test_delete(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "remove me"}, registry
        )
        result = handle_action(
            {"action": "delete_todo", "dodo": "_default", "id": item["id"]}, registry
        )
        assert result["status"] == "deleted"
        assert result["id"] == item["id"]

    def test_list_todos(self, registry):
        handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "a"}, registry
        )
        handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "b"}, registry
        )
        items = handle_action(
            {"action": "list_todos", "dodo": "_default"}, registry
        )
        assert len(items) == 2

    def test_list_todos_filter(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "a"}, registry
        )
        handle_action(
            {"action": "complete_todo", "dodo": "_default", "id": item["id"]}, registry
        )
        handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "b"}, registry
        )
        pending = handle_action(
            {"action": "list_todos", "dodo": "_default", "status": "pending"}, registry
        )
        assert len(pending) == 1
        assert pending[0]["text"] == "b"


class TestUpdate:
    def test_update_text(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "old"}, registry
        )
        updated = handle_action(
            {
                "action": "update_todo",
                "dodo": "_default",
                "id": item["id"],
                "text": "new",
            },
            registry,
        )
        assert updated["text"] == "new"

    def test_update_no_fields_errors(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "x"}, registry
        )
        with pytest.raises(ValueError, match="No fields to update"):
            handle_action(
                {"action": "update_todo", "dodo": "_default", "id": item["id"]},
                registry,
            )


class TestTags:
    def test_add_and_remove_tag(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "tagged"}, registry
        )
        tagged = handle_action(
            {
                "action": "add_tag",
                "dodo": "_default",
                "id": item["id"],
                "tag": "work",
            },
            registry,
        )
        assert "work" in tagged["tags"]

        untagged = handle_action(
            {
                "action": "remove_tag",
                "dodo": "_default",
                "id": item["id"],
                "tag": "work",
            },
            registry,
        )
        assert "work" not in (untagged["tags"] or [])


class TestMetadata:
    def test_set_and_remove(self, registry):
        item = handle_action(
            {"action": "add_todo", "dodo": "_default", "text": "meta"}, registry
        )
        updated = handle_action(
            {
                "action": "set_metadata",
                "dodo": "_default",
                "id": item["id"],
                "key": "source",
                "value": "api",
            },
            registry,
        )
        assert updated["metadata"]["source"] == "api"

        removed = handle_action(
            {
                "action": "remove_metadata",
                "dodo": "_default",
                "id": item["id"],
                "key": "source",
            },
            registry,
        )
        assert "source" not in (removed["metadata"] or {})


class TestValidation:
    def test_missing_action(self, registry):
        with pytest.raises(ValueError, match="Missing 'action'"):
            handle_action({}, registry)

    def test_unknown_action(self, registry):
        with pytest.raises(ValueError, match="Unknown action 'nope'"):
            handle_action({"action": "nope"}, registry)

    def test_missing_required_param(self, registry):
        with pytest.raises(ValueError, match="Missing required parameter 'text'"):
            handle_action(
                {"action": "add_todo", "dodo": "_default"}, registry
            )

    def test_invalid_priority(self, registry):
        with pytest.raises(ValueError, match="got 'urgent'"):
            handle_action(
                {
                    "action": "add_todo",
                    "dodo": "_default",
                    "text": "x",
                    "priority": "urgent",
                },
                registry,
            )

    def test_invalid_status_filter(self, registry):
        with pytest.raises(ValueError, match="got 'active'"):
            handle_action(
                {"action": "list_todos", "dodo": "_default", "status": "active"},
                registry,
            )

    def test_invalid_dodo_name(self, registry):
        with pytest.raises(ValueError, match="Invalid dodo name"):
            handle_action(
                {"action": "list_todos", "dodo": "../escape"}, registry
            )

    def test_get_not_found(self, registry):
        result = handle_action(
            {"action": "get_todo", "dodo": "_default", "id": "nonexistent"}, registry
        )
        assert result.get("error") == "not_found"
