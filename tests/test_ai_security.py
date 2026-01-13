"""Tests for AI module security."""

from unittest.mock import MagicMock, patch

from dodo.plugins.ai.engine import run_ai


def test_ai_command_uses_argument_list():
    """AI command should use argument list, not shell=True."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"tasks": ["test todo"]}'

    with patch("dodo.plugins.ai.engine.subprocess.run", return_value=mock_result) as mock_run:
        run_ai(
            user_input="test",
            command="echo '{{prompt}}'",
            system_prompt="test system",
        )

        # Should be called with a list, not a string
        call_args = mock_run.call_args
        assert isinstance(call_args[0][0], list), "Should pass command as list"
        # Should NOT have shell=True
        call_kwargs = call_args.kwargs
        assert "shell" not in call_kwargs or call_kwargs["shell"] is False
