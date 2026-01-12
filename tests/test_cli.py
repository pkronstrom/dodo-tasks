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


class TestCliNew:
    def test_new_creates_default_dodo(self, cli_env):
        """dodo new creates default dodo in ~/.config/dodo/"""
        result = runner.invoke(app, ["new"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Created dodo" in result.stdout
        # Check file was created
        config_dir = cli_env
        assert (config_dir / "dodo.db").exists() or (config_dir / "dodo.md").exists()

    def test_new_creates_named_dodo(self, cli_env):
        """dodo new <name> creates named dodo in ~/.config/dodo/<name>/"""
        result = runner.invoke(app, ["new", "my-session"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "my-session" in result.stdout
        config_dir = cli_env
        assert (config_dir / "my-session").is_dir()

    def test_new_local_creates_in_cwd(self, cli_env, tmp_path, monkeypatch):
        """dodo new --local creates .dodo/ in current directory"""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["new", "--local"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert ".dodo" in result.stdout
        assert (tmp_path / ".dodo").is_dir()

    def test_new_named_local_creates_subdir(self, cli_env, tmp_path, monkeypatch):
        """dodo new <name> --local creates .dodo/<name>/"""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["new", "agent-123", "--local"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert (tmp_path / ".dodo" / "agent-123").is_dir()

    def test_new_with_backend(self, cli_env):
        """dodo new --backend sqlite uses specified backend"""
        result = runner.invoke(app, ["new", "test-proj", "--backend", "sqlite"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        config_dir = cli_env
        assert (config_dir / "test-proj" / "dodo.db").exists()

    def test_new_idempotent_shows_hint(self, cli_env):
        """dodo new when dodo exists shows hint to use name"""
        runner.invoke(app, ["new"])
        result = runner.invoke(app, ["new"])

        assert result.exit_code == 0
        assert "already exists" in result.stdout.lower()
        assert "dodo new <name>" in result.stdout


class TestCliDestroy:
    def test_destroy_removes_named_dodo(self, cli_env):
        """dodo destroy <name> removes the dodo"""
        # Create first
        runner.invoke(app, ["new", "temp-session"])
        config_dir = cli_env
        assert (config_dir / "temp-session").exists()

        # Destroy
        result = runner.invoke(app, ["destroy", "temp-session"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Removed" in result.stdout or "Destroyed" in result.stdout
        assert not (config_dir / "temp-session").exists()

    def test_destroy_local_removes_local_dodo(self, cli_env, tmp_path, monkeypatch):
        """dodo destroy <name> --local removes .dodo/<name>/"""
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["new", "agent-456", "--local"])
        assert (tmp_path / ".dodo" / "agent-456").exists()

        result = runner.invoke(app, ["destroy", "agent-456", "--local"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert not (tmp_path / ".dodo" / "agent-456").exists()

    def test_destroy_nonexistent_errors(self, cli_env):
        """dodo destroy <name> errors if dodo doesn't exist"""
        result = runner.invoke(app, ["destroy", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_destroy_default_local(self, cli_env, tmp_path, monkeypatch):
        """dodo destroy --local removes default .dodo/"""
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["new", "--local"])
        assert (tmp_path / ".dodo").exists()

        result = runner.invoke(app, ["destroy", "--local"])

        assert result.exit_code == 0
        assert not (tmp_path / ".dodo").exists()


class TestCliInitDeprecation:
    def test_init_shows_deprecation_warning(self, cli_env, tmp_path, monkeypatch):
        """dodo init shows deprecation warning pointing to dodo new"""
        # Create a fake git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        with patch("dodo.project.detect_project", return_value="test_abc123"):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "deprecated" in result.stdout.lower() or "dodo new" in result.stdout


class TestCliDodoFlag:
    def test_add_with_dodo_flag(self, cli_env):
        """dodo add --dodo <name> adds to specific dodo"""
        runner.invoke(app, ["new", "my-tasks"])
        result = runner.invoke(app, ["add", "Test task", "--dodo", "my-tasks"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Test task" in result.stdout

    def test_list_with_dodo_flag(self, cli_env):
        """dodo list --dodo <name> lists from specific dodo"""
        runner.invoke(app, ["new", "my-tasks"])
        runner.invoke(app, ["add", "Task in my-tasks", "--dodo", "my-tasks"])

        result = runner.invoke(app, ["list", "--dodo", "my-tasks"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Task in my-tasks" in result.stdout

    def test_dodo_flag_local(self, cli_env, tmp_path, monkeypatch):
        """dodo add --dodo <name> auto-detects local .dodo/<name>/"""
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["new", "local-tasks", "--local"])
        # --dodo auto-detects local vs global - no --local needed
        result = runner.invoke(app, ["add", "Local task", "--dodo", "local-tasks"])

        assert result.exit_code == 0, f"Failed: {result.output}"
