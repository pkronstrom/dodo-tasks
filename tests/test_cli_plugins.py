"""Tests for plugin CLI commands."""

import json


def test_scan_reads_plugin_manifest(tmp_path):
    """Scan should read plugin.json for name, version, description."""
    from dodo import plugins

    # Create a test plugin with manifest
    plugin_dir = tmp_path / "plugins" / "test_plugin"
    plugin_dir.mkdir(parents=True)

    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "test-plugin", "version": "2.0.0", "description": "A test plugin"})
    )

    (plugin_dir / "__init__.py").write_text("""
def register_commands(app, config):
    pass
""")

    # Scan the directory
    result = plugins._scan_plugin_dir(plugin_dir.parent, builtin=False)

    assert "test-plugin" in result
    assert result["test-plugin"]["version"] == "2.0.0"
    assert result["test-plugin"]["description"] == "A test plugin"


def test_auto_scan_when_registry_missing(tmp_path):
    """Registry should be auto-created on first load if missing."""
    from dodo.plugins import load_registry

    # Use temp config dir with no registry
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Load registry - should trigger auto-scan and find builtin plugins
    registry = load_registry(config_dir)

    # Should return dict with builtin plugins (sqlite, obsidian, graph, ntfy-inbox)
    assert isinstance(registry, dict)
    assert len(registry) > 0, "Should auto-scan and find builtin plugins"
    assert "sqlite" in registry, "Should find sqlite builtin plugin"
