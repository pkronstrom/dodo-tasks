"""Tests for bulk CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dodo.cli import app
from dodo.config import clear_config_cache

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Set up isolated environment for CLI tests."""
    clear_config_cache()
    config_dir = tmp_path / ".config" / "dodo"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return config_dir


class TestBulkDone:
    def test_bulk_done_args(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            # Add some todos
            r1 = runner.invoke(app, ["add", "Task 1"])
            r2 = runner.invoke(app, ["add", "Task 2"])

            # Extract IDs from output
            id1 = r1.stdout.split("(")[1].split(")")[0]
            id2 = r2.stdout.split("(")[1].split(")")[0]

            # Bulk done
            result = runner.invoke(app, ["bulk", "done", id1, id2])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "2" in result.stdout  # Should mention 2 items

    def test_bulk_done_stdin(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            # Bulk done via stdin
            result = runner.invoke(app, ["bulk", "done"], input=id1)

        assert result.exit_code == 0, f"Failed: {result.output}"


class TestBulkRm:
    def test_bulk_rm_args(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            r2 = runner.invoke(app, ["add", "Task 2"])

            id1 = r1.stdout.split("(")[1].split(")")[0]
            id2 = r2.stdout.split("(")[1].split(")")[0]

            result = runner.invoke(app, ["bulk", "rm", id1, id2])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "2" in result.stdout


class TestBulkAdd:
    def test_bulk_add_jsonl(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            jsonl = '{"text": "Task 1"}\n{"text": "Task 2"}'
            result = runner.invoke(app, ["bulk", "add"], input=jsonl)

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "2" in result.stdout


class TestBulkEdit:
    def test_bulk_edit_priority_args(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            result = runner.invoke(app, ["bulk", "edit", id1, "-p", "high"])

        assert result.exit_code == 0, f"Failed: {result.output}"

    def test_bulk_edit_tags_args(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            result = runner.invoke(app, ["bulk", "edit", id1, "-t", "work"])

        assert result.exit_code == 0, f"Failed: {result.output}"

    def test_bulk_edit_jsonl_stdin(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            jsonl = f'{{"id": "{id1}", "priority": "high"}}'
            result = runner.invoke(app, ["bulk", "edit"], input=jsonl)

        assert result.exit_code == 0, f"Failed: {result.output}"

    def test_bulk_edit_clear_with_null(self, cli_env):
        with patch("dodo.project.detect_project", return_value=None):
            r1 = runner.invoke(app, ["add", "Task 1", "-p", "high"])
            id1 = r1.stdout.split("(")[1].split(")")[0]

            jsonl = f'{{"id": "{id1}", "priority": null}}'
            result = runner.invoke(app, ["bulk", "edit"], input=jsonl)

        assert result.exit_code == 0, f"Failed: {result.output}"
