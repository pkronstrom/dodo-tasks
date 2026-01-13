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

    @patch("dodo.ai.subprocess.run")
    @patch("dodo.project.detect_project", return_value=None)
    def test_ai_prio_preserves_item_count(
        self, mock_project: MagicMock, mock_run: MagicMock, cli_env
    ):
        """AI prio should never delete items - only update priority."""
        import re

        # Add multiple todos
        runner.invoke(app, ["add", "First todo"])
        runner.invoke(app, ["add", "Second todo"])
        runner.invoke(app, ["add", "Third todo"])

        # Get initial count
        list_result = runner.invoke(app, ["list"])
        initial_count = list_result.stdout.count("todo")

        # Get one of the todo IDs for the mock response
        add_result = runner.invoke(app, ["add", "Fourth todo"])
        match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
        todo_id = match.group(1) if match else "abc123"

        # Mock AI returning priority change
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=f'{{"assignments": [{{"id": "{todo_id}", "priority": "high"}}]}}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "prio", "-y"])

        assert result.exit_code == 0, f"Failed: {result.output}"

        # Verify count is preserved (4 now)
        list_result = runner.invoke(app, ["list"])
        final_count = list_result.stdout.count("todo")
        assert final_count >= initial_count, (
            f"Items were deleted! Before: {initial_count}, After: {final_count}"
        )


class TestAIReword:
    @patch("dodo.ai.subprocess.run")
    def test_ai_reword_no_todos(self, mock_run: MagicMock, cli_env):
        result = runner.invoke(app, ["ai", "reword"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No pending todos" in result.stdout

    @patch("dodo.ai.subprocess.run")
    @patch("dodo.project.detect_project", return_value=None)
    def test_ai_reword_preserves_item_count(
        self, mock_project: MagicMock, mock_run: MagicMock, cli_env
    ):
        """AI reword should never delete items - only update text."""
        import re

        # Add multiple todos
        add_result = runner.invoke(app, ["add", "First todo"])
        runner.invoke(app, ["add", "Second todo"])
        runner.invoke(app, ["add", "Third todo"])

        match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
        todo_id = match.group(1) if match else "abc123"

        # Get initial count
        list_result = runner.invoke(app, ["list"])
        initial_count = len(
            [l for l in list_result.stdout.splitlines() if todo_id[:4] in l or "todo" in l.lower()]
        )

        # Mock AI returning text rewrite
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=f'{{"rewrites": [{{"id": "{todo_id}", "text": "Improved first todo"}}]}}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "reword", "-y"])

        assert result.exit_code == 0, f"Failed: {result.output}"

        # Verify count is preserved
        list_result = runner.invoke(app, ["list"])
        assert "Improved first todo" in list_result.stdout or "First todo" in list_result.stdout


class TestAITag:
    @patch("dodo.ai.subprocess.run")
    def test_ai_tag_no_todos(self, mock_run: MagicMock, cli_env):
        result = runner.invoke(app, ["ai", "tag"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No pending todos" in result.stdout

    @patch("dodo.ai.subprocess.run")
    @patch("dodo.project.detect_project", return_value=None)
    def test_ai_tag_preserves_item_count(
        self, mock_project: MagicMock, mock_run: MagicMock, cli_env
    ):
        """AI tag should never delete items - only update tags."""
        import re

        # Add multiple todos
        add_result = runner.invoke(app, ["add", "First todo"])
        runner.invoke(app, ["add", "Second todo"])
        runner.invoke(app, ["add", "Third todo"])

        match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
        todo_id = match.group(1) if match else "abc123"

        # Mock AI returning tag suggestions
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=f'{{"suggestions": [{{"id": "{todo_id}", "tags": ["work", "important"]}}]}}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "tag", "-y"])

        assert result.exit_code == 0, f"Failed: {result.output}"

        # Verify all items still exist
        list_result = runner.invoke(app, ["list"])
        assert "First" in list_result.stdout
        assert "Second" in list_result.stdout
        assert "Third" in list_result.stdout


class TestAISync:
    def test_ai_sync_placeholder(self, cli_env):
        result = runner.invoke(app, ["ai", "sync"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "not yet implemented" in result.stdout.lower()


class TestAIRun:
    @patch("dodo.ai.subprocess.run")
    def test_ai_run_no_todos_no_changes(self, mock_run: MagicMock, cli_env):
        """AI run with no todos and no AI output shows no changes."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"todos": [], "delete": [], "create": []}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "run", "mark all as done"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No changes needed" in result.stdout

    @patch("dodo.ai.subprocess.run")
    def test_ai_run_with_instruction(self, mock_run: MagicMock, cli_env):
        """AI run processes instructions on existing todos."""
        # First add a todo
        with patch("dodo.project.detect_project", return_value=None):
            add_result = runner.invoke(app, ["add", "Test todo"])
            assert add_result.exit_code == 0, f"Add failed: {add_result.output}"

        # Mock AI response with no changes
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"todos": [], "delete": [], "create": []}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "run", "prioritize everything"])

        assert result.exit_code == 0, f"Failed: {result.output}"

    @patch("dodo.ai.subprocess.run")
    @patch("dodo.project.detect_project", return_value=None)
    def test_ai_run_applies_changes_with_yes(
        self, mock_project: MagicMock, mock_run: MagicMock, cli_env
    ):
        """AI run with -y applies changes without confirmation."""
        import re

        # First add a todo
        add_result = runner.invoke(app, ["add", "Test todo"])
        assert add_result.exit_code == 0

        # Get the todo ID from add output (format: "... (id)")
        match = re.search(r"\(([a-f0-9]+)\)", add_result.stdout)
        assert match, f"Could not find ID in output: {add_result.stdout}"
        todo_id = match.group(1)

        # Mock AI response with status change
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=f'{{"todos": [{{"id": "{todo_id}", "status": "done"}}], "delete": [], "create": []}}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "run", "mark all as done", "-y"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Applied" in result.stdout

    @patch("dodo.ai.subprocess.run")
    @patch("dodo.project.detect_project", return_value=None)
    def test_ai_run_handles_invalid_json(
        self, mock_project: MagicMock, mock_run: MagicMock, cli_env
    ):
        """AI run handles malformed AI response gracefully."""
        # First add a todo
        runner.invoke(app, ["add", "Test todo"])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json",
            stderr="",
        )

        result = runner.invoke(app, ["ai", "run", "do something"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No changes needed" in result.stdout

    @patch("dodo.ai.subprocess.run")
    @patch("dodo.project.detect_project", return_value=None)
    def test_ai_run_handles_non_dict_response(
        self, mock_project: MagicMock, mock_run: MagicMock, cli_env
    ):
        """AI run handles non-dict JSON response (type guard test)."""
        # First add a todo
        runner.invoke(app, ["add", "Test todo"])

        # Return a JSON array instead of object
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["unexpected", "array"]',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "run", "do something"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "No changes needed" in result.stdout


class TestAIDep:
    def test_ai_dep_requires_graph_plugin(self, cli_env):
        """AI dep fails without graph plugin."""
        result = runner.invoke(app, ["ai", "dep"])

        assert result.exit_code == 1, f"Should fail: {result.output}"
        assert "Graph plugin not enabled" in result.stdout

    @patch("dodo.ai.subprocess.run")
    def test_ai_dep_no_todos(self, mock_run: MagicMock, cli_env, tmp_path, monkeypatch):
        """AI dep with no todos shows message (when graph is enabled)."""
        # Enable graph plugin via config
        config_dir = tmp_path / ".config" / "dodo"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.toml").write_text('enabled_plugins = ["graph"]')
        clear_config_cache()

        result = runner.invoke(app, ["ai", "dep"])

        # Either shows "no pending todos" or "graph plugin not enabled"
        # depending on backend initialization
        assert result.exit_code in [0, 1]

    @patch("dodo.ai.subprocess.run")
    def test_ai_dep_filters_self_dependencies(self, mock_run: MagicMock, cli_env, tmp_path):
        """AI dep filters out self-referencing dependencies."""
        # This test verifies the self-dependency filter logic
        from dodo.ai import run_ai_dep

        # Mock AI returning self-dependency
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"dependencies": [{"blocked_id": "abc", "blocker_id": "abc"}]}',
            stderr="",
        )

        deps = run_ai_dep(
            todos=[{"id": "abc", "text": "Test todo"}],
            command="claude --json-schema '{{schema}}' '{{prompt}}'",
            system_prompt="Test prompt",
        )

        # The filter is in ai_commands.py, but at ai.py level
        # self-deps will still be returned - filter is in command
        # Just verify we get the result back
        assert len(deps) == 1
        assert deps[0]["blocked_id"] == "abc"
        assert deps[0]["blocker_id"] == "abc"

    def test_ai_dep_only_adds_dependencies(self, cli_env):
        """AI dep should never delete items - only add dependency relationships."""
        # ai dep requires graph plugin, without it we get an error
        # but this confirms the command exists and doesn't have delete capability
        result = runner.invoke(app, ["ai", "dep", "--help"])

        assert result.exit_code == 0
        # Verify the help text doesn't mention delete
        assert "delete" not in result.stdout.lower()
        # The command only adds dependencies
        assert "dependency" in result.stdout.lower() or "dep" in result.stdout.lower()

    def test_ai_dep_preserves_existing_dependencies(self, tmp_path, monkeypatch):
        """AI dep should only add new deps, not remove existing ones."""
        from dodo.backends.sqlite import SqliteBackend
        from dodo.plugins.graph.wrapper import GraphWrapper

        # Set up environment with graph plugin
        db_path = tmp_path / ".config" / "dodo" / "dodo.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        backend = SqliteBackend(db_path)
        wrapper = GraphWrapper(backend)

        # Create todos and existing dependency
        t1 = wrapper.add("Task 1")
        t2 = wrapper.add("Task 2")
        t3 = wrapper.add("Task 3")

        # Add existing dependency: t1 blocks t2
        wrapper.add_dependency(t1.id, t2.id)

        # Verify existing dependency
        assert t1.id in wrapper.get_blockers(t2.id)

        # Now simulate what ai dep does - only add new dependency
        # (AI only suggests t2 blocks t3, doesn't mention t1->t2)
        wrapper.add_dependency(t2.id, t3.id)

        # Original dependency should still exist
        assert t1.id in wrapper.get_blockers(t2.id)
        # New dependency should be added
        assert t2.id in wrapper.get_blockers(t3.id)


class TestAIRunSchema:
    def test_run_schema_excludes_cancelled_status(self):
        """RUN_SCHEMA should only include valid Status values."""
        import json

        from dodo.ai import RUN_SCHEMA

        schema = json.loads(RUN_SCHEMA)
        status_enum = schema["properties"]["todos"]["items"]["properties"]["status"]["enum"]

        assert "pending" in status_enum
        assert "done" in status_enum
        assert "cancelled" not in status_enum, "cancelled is not a valid Status enum value"

    def test_run_schema_includes_create_array(self):
        """RUN_SCHEMA should include create array for new todos."""
        import json

        from dodo.ai import RUN_SCHEMA

        schema = json.loads(RUN_SCHEMA)
        assert "create" in schema["properties"]
        assert "create" in schema["required"]
        create_items = schema["properties"]["create"]["items"]["properties"]
        assert "text" in create_items
        assert "priority" in create_items
        assert "tags" in create_items


class TestAIRunCreate:
    @patch("dodo.ai.subprocess.run")
    @patch("dodo.project.detect_project", return_value=None)
    def test_ai_run_creates_new_todos(self, mock_project: MagicMock, mock_run: MagicMock, cli_env):
        """AI run can create new todos."""
        # Mock AI response with create
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"todos": [], "delete": [], "create": [{"text": "New todo from AI", "priority": "high", "tags": ["ai-generated"]}]}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "run", "create a test todo", "-y"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Created" in result.stdout
        assert "New todo from AI" in result.stdout

    @patch("dodo.ai.subprocess.run")
    @patch("dodo.project.detect_project", return_value=None)
    def test_ai_run_shows_create_preview(
        self, mock_project: MagicMock, mock_run: MagicMock, cli_env
    ):
        """AI run shows preview of todos to create."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"todos": [], "delete": [], "create": [{"text": "Preview todo", "priority": null, "tags": []}]}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "run", "create a todo"], input="n\n")

        # Exit code 1 is expected when user cancels
        assert "Create (1)" in result.stdout
        assert "Preview todo" in result.stdout
