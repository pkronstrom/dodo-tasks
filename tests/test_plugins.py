"""Tests for plugin discovery and configuration."""

from pathlib import Path
from textwrap import dedent

from dodo.plugins import (
    Plugin,
    PluginEnv,
    find_plugin_script,
    parse_env_declarations,
    scan_plugins,
)


class TestPluginEnv:
    """Tests for PluginEnv dataclass."""

    def test_is_set_when_present(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "value")
        env = PluginEnv(name="TEST_VAR", description="Test", required=True, default=None)
        assert env.is_set is True

    def test_is_set_when_absent(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        env = PluginEnv(name="TEST_VAR", description="Test", required=True, default=None)
        assert env.is_set is False

    def test_current_value(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        env = PluginEnv(name="TEST_VAR", description="Test", required=True, default=None)
        assert env.current_value == "hello"

    def test_current_value_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        env = PluginEnv(name="TEST_VAR", description="Test", required=True, default=None)
        assert env.current_value is None


class TestPlugin:
    """Tests for Plugin dataclass."""

    def test_is_configured_all_required_set(self, monkeypatch):
        monkeypatch.setenv("REQ1", "val")
        monkeypatch.setenv("REQ2", "val")
        plugin = Plugin(
            name="test",
            path=Path("/test"),
            script=Path("/test/script"),
            envs=[
                PluginEnv(name="REQ1", description="", required=True, default=None),
                PluginEnv(name="REQ2", description="", required=True, default=None),
                PluginEnv(name="OPT1", description="", required=False, default="x"),
            ],
        )
        assert plugin.is_configured is True

    def test_is_configured_missing_required(self, monkeypatch):
        monkeypatch.setenv("REQ1", "val")
        monkeypatch.delenv("REQ2", raising=False)
        plugin = Plugin(
            name="test",
            path=Path("/test"),
            script=Path("/test/script"),
            envs=[
                PluginEnv(name="REQ1", description="", required=True, default=None),
                PluginEnv(name="REQ2", description="", required=True, default=None),
            ],
        )
        assert plugin.is_configured is False


class TestParseEnvDeclarations:
    """Tests for parse_env_declarations function."""

    def test_parses_required_env(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("#!/usr/bin/env python3\n# @env MY_VAR: Description here (required)\n")

        envs = parse_env_declarations(script)

        assert len(envs) == 1
        assert envs[0].name == "MY_VAR"
        assert envs[0].description == "Description here"
        assert envs[0].required is True
        assert envs[0].default is None

    def test_parses_default_env(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("# @env MY_VAR: Description (default: localhost)\n")

        envs = parse_env_declarations(script)

        assert len(envs) == 1
        assert envs[0].name == "MY_VAR"
        assert envs[0].required is False
        assert envs[0].default == "localhost"

    def test_parses_optional_env_no_modifier(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("# @env MY_VAR: Just a description\n")

        envs = parse_env_declarations(script)

        assert len(envs) == 1
        assert envs[0].required is False
        assert envs[0].default is None

    def test_parses_multiple_envs(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text(
            dedent(
                """\
            #!/usr/bin/env python3
            # @env VAR_ONE: First var (required)
            # @env VAR_TWO: Second var (default: https://example.com)
            # @env VAR_THREE: Third var

            import os
            """
            )
        )

        envs = parse_env_declarations(script)

        assert len(envs) == 3
        assert envs[0].name == "VAR_ONE"
        assert envs[1].name == "VAR_TWO"
        assert envs[2].name == "VAR_THREE"

    def test_handles_missing_file(self, tmp_path):
        script = tmp_path / "nonexistent.py"
        envs = parse_env_declarations(script)
        assert envs == []

    def test_case_insensitive_required(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("# @env MY_VAR: Desc (REQUIRED)\n")

        envs = parse_env_declarations(script)
        assert envs[0].required is True


class TestFindPluginScript:
    """Tests for find_plugin_script function."""

    def test_finds_dodo_prefixed_script(self, tmp_path):
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        script = plugin_dir / "dodo-my-plugin"
        script.write_text("#!/bin/bash\n")

        result = find_plugin_script(plugin_dir)
        assert result == script

    def test_finds_main_py(self, tmp_path):
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        script = plugin_dir / "main.py"
        script.write_text("#!/usr/bin/env python3\n")

        result = find_plugin_script(plugin_dir)
        assert result == script

    def test_returns_none_when_no_script(self, tmp_path):
        plugin_dir = tmp_path / "empty-plugin"
        plugin_dir.mkdir()

        result = find_plugin_script(plugin_dir)
        assert result is None


class TestScanPlugins:
    """Tests for scan_plugins function."""

    def test_discovers_plugin(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin = plugins_dir / "test-plugin"
        plugin.mkdir()
        script = plugin / "dodo-test-plugin"
        script.write_text("#!/bin/bash\n# @env TEST_VAR: Description (required)\n")

        plugins = scan_plugins(plugins_dir)

        assert len(plugins) == 1
        assert plugins[0].name == "test-plugin"
        assert len(plugins[0].envs) == 1

    def test_skips_hidden_directories(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        hidden = plugins_dir / ".hidden"
        hidden.mkdir()
        (hidden / "dodo-hidden").write_text("#!/bin/bash\n")

        plugins = scan_plugins(plugins_dir)
        assert len(plugins) == 0

    def test_skips_directories_without_scripts(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        empty = plugins_dir / "empty"
        empty.mkdir()
        (empty / "README.md").write_text("# Empty\n")

        plugins = scan_plugins(plugins_dir)
        assert len(plugins) == 0

    def test_returns_empty_for_missing_dir(self, tmp_path):
        plugins = scan_plugins(tmp_path / "nonexistent")
        assert plugins == []
