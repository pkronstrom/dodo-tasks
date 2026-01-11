"""Tests for config error handling."""

from pathlib import Path

from dodo.config import Config, clear_config_cache


def test_corrupted_config_loads_defaults(tmp_path: Path):
    """Corrupted config file should fall back to defaults."""
    clear_config_cache()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text("{ invalid json }")

    cfg = Config.load(config_dir)

    # Should load defaults instead of crashing
    assert cfg.default_adapter == "markdown"
    assert cfg.worktree_shared is True


def test_empty_config_file_loads_defaults(tmp_path: Path):
    """Empty config file should load defaults."""
    clear_config_cache()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text("")

    cfg = Config.load(config_dir)
    assert cfg.default_adapter == "markdown"
