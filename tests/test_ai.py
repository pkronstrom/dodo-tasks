"""Tests for AI module."""

from unittest.mock import MagicMock, patch

from dodo.ai import _escape_single_quotes, build_command, run_ai


class TestEscapeSingleQuotes:
    def test_escapes_apostrophe(self):
        """Single quotes should be escaped for shell."""
        result = _escape_single_quotes("don't")
        # The escape pattern is '...'"'"'...'
        assert "'" not in result or "'\"'\"'" in result

    def test_handles_multiple_apostrophes(self):
        """Multiple apostrophes should all be escaped."""
        result = _escape_single_quotes("it's not working, isn't it?")
        # Should not raise when used with shlex
        import shlex

        cmd = f"echo '{result}'"
        # This should not raise ValueError
        shlex.split(cmd)

    def test_no_change_without_quotes(self):
        """Text without quotes should be unchanged."""
        result = _escape_single_quotes("hello world")
        assert result == "hello world"


class TestBuildCommand:
    def test_substitutes_prompt(self):
        template = "llm '{{prompt}}' -s '{{system}}'"
        cmd = build_command(template, prompt="test prompt", system="sys", schema="{}")

        # cmd is now a list of arguments
        cmd_str = " ".join(cmd)
        assert "test prompt" in cmd_str
        assert "sys" in cmd_str

    def test_substitutes_schema(self):
        template = "claude --json-schema '{{schema}}'"
        schema = '{"type": "array"}'
        cmd = build_command(template, prompt="test", system="sys", schema=schema)

        # cmd is now a list of arguments
        cmd_str = " ".join(cmd)
        assert schema in cmd_str

    def test_handles_apostrophes_in_prompt(self):
        """Apostrophes in prompt should not break shlex parsing."""
        template = "llm '{{prompt}}' -s '{{system}}'"
        # This would previously raise "No closing quotation"
        cmd = build_command(
            template,
            prompt="Fix the bug that doesn't work",
            system="You're a helpful assistant",
            schema="{}",
        )

        # Should successfully parse into list
        assert isinstance(cmd, list)
        assert len(cmd) > 0


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
        # cmd is now a list of arguments
        cmd_str = " ".join(cmd)
        assert "piped" in cmd_str.lower() or "some piped content" in cmd_str

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
