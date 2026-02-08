"""Tests for server plugin MCP tools."""

from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")

from dodo.config import Config  # noqa: E402
from dodo.plugins.server.app import ServiceRegistry  # noqa: E402
from dodo.plugins.server.mcp_server import _validate_dodo, create_mcp_app  # noqa: E402


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

    def test_mcp_app_creates(self, registry):
        """Smoke test that create_mcp_app returns an ASGI app."""
        app = create_mcp_app(registry)
        assert app is not None
