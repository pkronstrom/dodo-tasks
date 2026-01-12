"""Integration tests for full workflow."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

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


class TestFullWorkflow:
    def test_add_list_done_workflow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test complete workflow: add -> list -> done -> list."""
        config_dir = tmp_path / ".config" / "dodo"
        monkeypatch.setenv("HOME", str(tmp_path))

        from dodo.config import Config
        from dodo.core import TodoService
        from dodo.models import Status

        cfg = Config.load(config_dir)
        svc = TodoService(cfg, project_id=None)

        # Add
        item1 = svc.add("First todo")
        svc.add("Second todo")

        # List pending
        pending = svc.list(status=Status.PENDING)
        assert len(pending) == 2

        # Complete one
        svc.complete(item1.id)

        # Verify status
        pending = svc.list(status=Status.PENDING)
        done = svc.list(status=Status.DONE)
        assert len(pending) == 1
        assert len(done) == 1
        assert done[0].id == item1.id

    def test_project_isolation(self, tmp_path: Path):
        """Test that projects have isolated todos."""
        config_dir = tmp_path / ".config" / "dodo"

        from dodo.config import Config
        from dodo.core import TodoService

        cfg = Config.load(config_dir)

        # Add to project A
        svc_a = TodoService(cfg, project_id="project_a")
        svc_a.add("Project A todo")

        # Add to project B
        svc_b = TodoService(cfg, project_id="project_b")
        svc_b.add("Project B todo")

        # Add to global
        svc_global = TodoService(cfg, project_id=None)
        svc_global.add("Global todo")

        # Verify isolation
        assert len(svc_a.list()) == 1
        assert svc_a.list()[0].text == "Project A todo"

        assert len(svc_b.list()) == 1
        assert svc_b.list()[0].text == "Project B todo"

        assert len(svc_global.list()) == 1
        assert svc_global.list()[0].text == "Global todo"

    def test_backend_switching(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test switching between backends."""
        config_dir = tmp_path / ".config" / "dodo"

        from dodo.config import Config
        from dodo.core import TodoService

        # Test with markdown (explicit env override since default is sqlite)
        monkeypatch.setenv("DODO_DEFAULT_BACKEND", "markdown")
        cfg = Config.load(config_dir)
        svc = TodoService(cfg, project_id=None)
        svc.add("Markdown todo")
        assert (config_dir / "dodo.md").exists()

        # Switch to SQLite
        monkeypatch.setenv("DODO_DEFAULT_BACKEND", "sqlite")
        cfg2 = Config.load(config_dir)
        svc2 = TodoService(cfg2, project_id=None)
        svc2.add("SQLite todo")
        assert (config_dir / "dodo.db").exists()


class TestAIDodoWorkflow:
    """Integration tests for AI agent dodo workflow."""

    def test_ai_ephemeral_dodo_workflow(self, cli_env, tmp_path, monkeypatch):
        """Full AI workflow: create, add tasks, list, destroy."""
        from dodo.cli import app

        monkeypatch.chdir(tmp_path)

        # Create ephemeral dodo
        result = runner.invoke(app, ["new", "agent-session-123", "--local", "--backend", "sqlite"])
        assert result.exit_code == 0, f"Failed to create dodo: {result.output}"

        # Add tasks (--dodo auto-detects local vs global)
        result = runner.invoke(app, ["add", "Fetch data", "--dodo", "agent-session-123"])
        assert result.exit_code == 0, f"Failed to add first task: {result.output}"

        result = runner.invoke(app, ["add", "Process data", "--dodo", "agent-session-123"])
        assert result.exit_code == 0, f"Failed to add second task: {result.output}"

        # List tasks
        result = runner.invoke(app, ["list", "--dodo", "agent-session-123"])
        assert result.exit_code == 0, f"Failed to list tasks: {result.output}"
        assert "Fetch data" in result.stdout
        assert "Process data" in result.stdout

        # Destroy (auto-detects local)
        result = runner.invoke(app, ["destroy", "agent-session-123"])
        assert result.exit_code == 0, f"Failed to destroy dodo: {result.output}"
        assert not (tmp_path / ".dodo" / "agent-session-123").exists()
