"""Tests for plugin CLI commands."""

import json


def test_scan_reads_plugin_manifest(tmp_path):
    """Scan should read plugin.json for name, version, description."""
    from dodo import cli_plugins

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
    result = cli_plugins._scan_plugin_dir(plugin_dir.parent, builtin=False)

    assert "test-plugin" in result
    assert result["test-plugin"]["version"] == "2.0.0"
    assert result["test-plugin"]["description"] == "A test plugin"
