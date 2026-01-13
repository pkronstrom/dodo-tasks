"""Tests for CLI commands."""

import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dodo.cli import app
from dodo.config import clear_config_cache

runner = CliRunner()


class TestCliImport:
    """Tests that verify cli module can be imported correctly."""

    def test_cli_module_imports_without_error(self):
        """Verify cli module can be imported without NameError or ImportError.

        This catches issues like missing imports that only manifest at module load time.
        """
        # Force reimport to catch any import-time errors
        import importlib

        import dodo.cli

        # Reload to catch any issues that might only appear on fresh import
        importlib.reload(dodo.cli)

    def test_help_command_works(self, cli_env, monkeypatch):
        """Verify --help works without errors.

        The --help flag triggers _register_all_plugin_root_commands at module load,
        which requires import_plugin to be properly imported.
        """
        # Simulate --help being in argv to trigger plugin registration path
        monkeypatch.setattr(sys, "argv", ["dodo", "--help"])

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0, f"--help failed: {result.output}"
        assert "Todo router" in result.stdout


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
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["add", "Test todo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Added" in result.stdout
        assert "Test todo" in result.stdout

    def test_add_global_flag(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["add", "-g", "Global todo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "global" in result.stdout.lower()


class TestCliList:
    def test_list_empty(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No todos" in result.stdout

    def test_list_shows_todos(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "First todo"])
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "First todo" in result.stdout


class TestCliDone:
    def test_done_marks_complete(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
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
        with patch("dodo.project.detect_project", return_value=None):
            runner.invoke(app, ["add", "To be undone"])
            result = runner.invoke(app, ["undo"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Undid" in result.stdout


class TestCliRm:
    def test_rm_deletes_todo(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            add_result = runner.invoke(app, ["add", "To delete"])
            assert add_result.exit_code == 0, f"Add failed: {add_result.output}"

            match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
            assert match, f"Could not find ID in: {add_result.stdout}"
            todo_id = match.group(1)

            result = runner.invoke(app, ["rm", todo_id])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Removed" in result.stdout


class TestGetServiceContext:
    def test_get_service_context_returns_tuple(self, tmp_path, monkeypatch):
        """get_service_context() should return (config, project_id, service) tuple."""
        monkeypatch.setenv("HOME", str(tmp_path))

        from dodo.config import clear_config_cache

        clear_config_cache()

        from dodo.cli_context import get_service_context

        cfg, project_id, svc = get_service_context()

        assert cfg is not None
        assert svc is not None
        # project_id can be None (global) or string

    def test_get_service_context_respects_global_flag(self, tmp_path, monkeypatch):
        """get_service_context(global_=True) should force global project."""
        monkeypatch.setenv("HOME", str(tmp_path))

        from dodo.config import clear_config_cache

        clear_config_cache()

        from dodo.cli_context import get_service_context

        cfg, project_id, svc = get_service_context(global_=True)

        assert project_id is None
