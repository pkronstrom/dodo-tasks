"""Tests for AI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

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
    def test_ai_add_requires_input(self, cli_env):
        """AI add requires text or piped input."""
        result = runner.invoke(app, ["ai", "add"])

        # Should error when no input provided
        assert result.exit_code == 1 or "Error" in result.stdout

    @patch("dodo.ai.subprocess.run")
    def test_ai_add_with_text(self, mock_run: MagicMock, cli_env):
        """AI add with text creates todos."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"tasks": [{"text": "Fix bug", "priority": "high", "tags": ["backend"]}]}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "add", "fix the bug in the API"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Fix bug" in result.stdout or "Added" in result.stdout


class TestAIPrioritize:
    @patch("dodo.ai.subprocess.run")
    def test_ai_prio_no_todos(self, mock_run: MagicMock, cli_env):
        """AI prio with no todos shows message."""
        result = runner.invoke(app, ["ai", "prio"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No pending todos" in result.stdout

    @patch("dodo.ai.subprocess.run")
    def test_ai_prio_with_todos(self, mock_run: MagicMock, cli_env):
        """AI prio with todos shows suggestions."""
        # First add a todo
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "Test todo"])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"assignments": []}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "prio"])

        assert result.exit_code == 0, f"Failed: {result.output}"

    def test_ai_prioritize_alias_works(self, cli_env):
        result = runner.invoke(app, ["ai", "prioritize"])

        assert result.exit_code == 0, f"Failed: {result.output}"


class TestAIReword:
    @patch("dodo.ai.subprocess.run")
    def test_ai_reword_no_todos(self, mock_run: MagicMock, cli_env):
        result = runner.invoke(app, ["ai", "reword"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No pending todos" in result.stdout


class TestAITag:
    @patch("dodo.ai.subprocess.run")
    def test_ai_tag_no_todos(self, mock_run: MagicMock, cli_env):
        result = runner.invoke(app, ["ai", "tag"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No pending todos" in result.stdout


class TestAISync:
    def test_ai_sync_placeholder(self, cli_env):
        result = runner.invoke(app, ["ai", "sync"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "not yet implemented" in result.stdout.lower()
