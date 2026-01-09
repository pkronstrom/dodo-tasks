"""Tests for AI module."""

from unittest.mock import MagicMock, patch

from dodo.ai import build_command, run_ai


class TestBuildCommand:
    def test_substitutes_prompt(self):
        template = "llm '{{prompt}}' -s '{{system}}'"
        cmd = build_command(template, prompt="test prompt", system="sys", schema="{}")

        assert "test prompt" in cmd
        assert "sys" in cmd

    def test_substitutes_schema(self):
        template = "claude --json-schema '{{schema}}'"
        schema = '{"type": "array"}'
        cmd = build_command(template, prompt="test", system="sys", schema=schema)

        assert schema in cmd


class TestRunAi:
    @patch("dodo.ai.subprocess.run")
    def test_returns_list_from_json(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["Todo one", "Todo two"]',
            stderr="",
        )

        result = run_ai(
            user_input="test",
            command="llm '{{prompt}}'",
            system_prompt="format todos",
        )

        assert result == ["Todo one", "Todo two"]

    @patch("dodo.ai.subprocess.run")
    def test_includes_piped_content_in_prompt(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["From pipe"]',
            stderr="",
        )

        run_ai(
            user_input="what to do",
            piped_content="some piped content",
            command="llm '{{prompt}}'",
            system_prompt="format",
        )

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "piped" in cmd.lower() or "some piped content" in cmd

    @patch("dodo.ai.subprocess.run")
    def test_handles_single_item(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='["Single todo"]',
            stderr="",
        )

        result = run_ai(
            user_input="test",
            command="llm '{{prompt}}'",
            system_prompt="format",
        )

        assert result == ["Single todo"]

    @patch("dodo.ai.subprocess.run")
    def test_error_returns_empty(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error",
        )

        result = run_ai(
            user_input="test",
            command="llm '{{prompt}}'",
            system_prompt="format",
        )

        assert result == []
