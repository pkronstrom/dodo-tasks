"""Tests for server plugin MCP tools."""

from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")

from dodo.config import Config  # noqa: E402
from dodo.plugins.server.registry import ServiceRegistry  # noqa: E402
from dodo.plugins.server.mcp_server import (  # noqa: E402
    _build_mcp,
    _validate_dodo,
    create_mcp_app,
)


@pytest.fixture
def registry(tmp_path: Path):
    """Create a ServiceRegistry with a temp config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    cfg = Config.load(config_dir)
    return ServiceRegistry(cfg)


class TestValidateDodo:
    """Test the _validate_dodo helper used by all MCP tools."""

    def test_default_passes(self):
        _validate_dodo("_default")  # should not raise

    def test_valid_name_passes(self):
        _validate_dodo("work")  # should not raise

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Invalid dodo name"):
            _validate_dodo("../evil")

    def test_dot_prefix_raises(self):
        with pytest.raises(ValueError, match="Invalid dodo name"):
            _validate_dodo(".hidden")


class TestMcpServiceIntegration:
    """Test MCP tool logic via the ServiceRegistry it wraps.

    MCP tool functions are closures inside create_mcp_app() and not directly
    importable. These tests verify the registry operations the tools call.
    """

    def test_list_dodos(self, registry):
        dodos = registry.list_dodos()
        assert any(d["name"] == "_default" for d in dodos)

    def test_add_and_list(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("MCP test task")
        items = svc.list()
        assert any(t.id == item.id for t in items)

    def test_complete(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Complete me")
        done = svc.complete(item.id)
        assert done.status.value == "done"

    def test_toggle(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Toggle me")
        toggled = svc.toggle(item.id)
        assert toggled.status.value == "done"
        toggled_back = svc.toggle(item.id)
        assert toggled_back.status.value == "pending"

    def test_update_text(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Old text")
        updated = svc.update_text(item.id, "New text")
        assert updated.text == "New text"

    def test_delete(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Delete me")
        svc.delete(item.id)
        assert svc.get(item.id) is None

    def test_add_with_due_at(self, registry):
        from datetime import datetime
        svc = registry.get_service("_default")
        item = svc.add("Due task", due_at=datetime(2026, 3, 1))
        assert item.due_at == datetime(2026, 3, 1)

    def test_add_with_metadata(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Meta task", metadata={"status": "wip"})
        assert item.metadata == {"status": "wip"}

    def test_update_due_at(self, registry):
        from datetime import datetime
        svc = registry.get_service("_default")
        item = svc.add("Test")
        updated = svc.update_due_at(item.id, datetime(2026, 6, 15))
        assert updated.due_at == datetime(2026, 6, 15)

    def test_update_metadata(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Test")
        updated = svc.update_metadata(item.id, {"k": "v"})
        assert updated.metadata == {"k": "v"}

    def test_set_metadata_key(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Test")
        updated = svc.set_metadata_key(item.id, "status", "wip")
        assert updated.metadata == {"status": "wip"}

    def test_remove_metadata_key(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Test", metadata={"a": "1", "b": "2"})
        updated = svc.remove_metadata_key(item.id, "a")
        assert updated.metadata == {"b": "2"}

    def test_add_tag(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Test", tags=["a"])
        updated = svc.add_tag(item.id, "b")
        assert "b" in updated.tags

    def test_remove_tag(self, registry):
        svc = registry.get_service("_default")
        item = svc.add("Test", tags=["a", "b"])
        updated = svc.remove_tag(item.id, "a")
        assert updated.tags == ["b"]

    def test_mcp_app_creates(self, registry):
        """Smoke test that create_mcp_app returns an ASGI app."""
        app = create_mcp_app(registry)
        assert app is not None

    def test_build_mcp_returns_fastmcp(self, registry):
        """_build_mcp returns a FastMCP instance (not an ASGI app)."""
        from mcp.server.fastmcp import FastMCP

        mcp_instance = _build_mcp(registry)
        assert isinstance(mcp_instance, FastMCP)

    def test_build_mcp_has_single_dodo_tool(self, registry):
        """_build_mcp registers a single 'dodo' tool (action dispatch pattern)."""
        mcp_instance = _build_mcp(registry)
        tool_names = {t.name for t in mcp_instance._tool_manager.list_tools()}
        assert tool_names == {"dodo"}
