"""Tests for project config (dodo.json)."""

import json

from dodo.project_config import ProjectConfig


def test_load_missing_returns_none(tmp_path):
    """Loading non-existent dodo.json returns None."""
    config = ProjectConfig.load(tmp_path / "nonexistent")
    assert config is None


def test_load_existing(tmp_path):
    """Loading existing dodo.json returns ProjectConfig."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "dodo.json").write_text('{"backend": "markdown"}')

    config = ProjectConfig.load(project_dir)
    assert config is not None
    assert config.backend == "markdown"


def test_save_creates_file(tmp_path):
    """Saving creates dodo.json."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = ProjectConfig(backend="sqlite")
    config.save(project_dir)

    assert (project_dir / "dodo.json").exists()
    data = json.loads((project_dir / "dodo.json").read_text())
    assert data["backend"] == "sqlite"


def test_ensure_creates_with_default(tmp_path):
    """ensure() creates config with default backend if missing."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = ProjectConfig.ensure(project_dir, default_backend="sqlite")

    assert config.backend == "sqlite"
    assert (project_dir / "dodo.json").exists()
