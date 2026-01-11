"""Tests for project detection error handling."""

from pathlib import Path
from unittest.mock import patch

from dodo.project import clear_project_cache, detect_project


def test_missing_git_returns_none(tmp_path: Path):
    """Missing git binary should return None, not crash."""
    clear_project_cache()

    # Mock subprocess.run to raise FileNotFoundError (git not found)
    def mock_run(*args, **kwargs):
        raise FileNotFoundError("git not found")

    with patch("subprocess.run", mock_run):
        result = detect_project(tmp_path)

    assert result is None
