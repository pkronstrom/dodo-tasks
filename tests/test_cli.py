"""Tests for CLI commands."""

import re
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dodo.cli import app
from dodo.config import clear_config_cache

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up isolated environment for CLI tests."""
    # Clear config cache to ensure fresh config with new HOME
    clear_config_cache()
    config_dir = tmp_path / ".config" / "dodo"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return config_dir


class TestCliAdd:
    def test_add_creates_todo(self, cli_env):
        with patch("dodo.cli.detect_project", return_value=None):
            result = runner.invoke(app, ["add", "Test todo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Added" in result.stdout
        assert "Test todo" in result.stdout

    def test_add_global_flag(self, cli_env):
        with patch("dodo.cli.detect_project", return_value=None):
            result = runner.invoke(app, ["add", "-g", "Global todo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "global" in result.stdout.lower()


class TestCliList:
    def test_list_empty(self, cli_env):
        with patch("dodo.cli.detect_project", return_value=None):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No todos" in result.stdout

    def test_list_shows_todos(self, cli_env):
        with patch("dodo.cli.detect_project", return_value=None):
            runner.invoke(app, ["add", "First todo"])
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "First todo" in result.stdout


class TestCliDone:
    def test_done_marks_complete(self, cli_env):
        with patch("dodo.cli.detect_project", return_value=None):
            # Add a todo first
            add_result = runner.invoke(app, ["add", "Test todo"])
            assert add_result.exit_code == 0, f"Add failed: {add_result.output}"

            # Extract ID from output (format: "Added to global: Test todo (abc123)")
            match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
            assert match, f"Could not find ID in: {add_result.stdout}"
            todo_id = match.group(1)

            result = runner.invoke(app, ["done", todo_id])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Done" in result.stdout


class TestCliUndo:
    def test_undo_removes_last_add(self, cli_env):
        with patch("dodo.cli.detect_project", return_value=None):
            runner.invoke(app, ["add", "To be undone"])
            result = runner.invoke(app, ["undo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Undid" in result.stdout


class TestCliRm:
    def test_rm_deletes_todo(self, cli_env):
        with patch("dodo.cli.detect_project", return_value=None):
            add_result = runner.invoke(app, ["add", "To delete"])
            assert add_result.exit_code == 0, f"Add failed: {add_result.output}"

            match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
            assert match, f"Could not find ID in: {add_result.stdout}"
            todo_id = match.group(1)

            result = runner.invoke(app, ["rm", todo_id])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Removed" in result.stdout
