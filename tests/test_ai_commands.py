"""Tests for AI commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from dodo.cli import app
from dodo.config import clear_config_cache

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up isolated environment for CLI tests."""
    clear_config_cache()
    config_dir = tmp_path / ".config" / "dodo"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return config_dir


class TestAICommandsHelp:
    def test_ai_help_shows_subcommands(self, cli_env):
        result = runner.invoke(app, ["ai", "--help"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "add" in result.stdout
        assert "prioritize" in result.stdout or "prio" in result.stdout
        assert "reword" in result.stdout
        assert "tag" in result.stdout
        assert "sync" in result.stdout


class TestAIAdd:
    def test_ai_add_placeholder(self, cli_env):
        result = runner.invoke(app, ["ai", "add", "test input"])

        # Currently shows placeholder message
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "not yet implemented" in result.stdout.lower()


class TestAIPrioritize:
    def test_ai_prio_placeholder(self, cli_env):
        result = runner.invoke(app, ["ai", "prio"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "not yet implemented" in result.stdout.lower()

    def test_ai_prioritize_alias_works(self, cli_env):
        result = runner.invoke(app, ["ai", "prioritize"])

        assert result.exit_code == 0, f"Failed: {result.output}"


class TestAIReword:
    def test_ai_reword_placeholder(self, cli_env):
        result = runner.invoke(app, ["ai", "reword"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "not yet implemented" in result.stdout.lower()


class TestAITag:
    def test_ai_tag_placeholder(self, cli_env):
        result = runner.invoke(app, ["ai", "tag"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "not yet implemented" in result.stdout.lower()


class TestAISync:
    def test_ai_sync_placeholder(self, cli_env):
        result = runner.invoke(app, ["ai", "sync"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "not yet implemented" in result.stdout.lower()
