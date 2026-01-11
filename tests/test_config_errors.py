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


def test_corrupted_registry_triggers_rescan(tmp_path: Path, monkeypatch):
    """Corrupted plugin registry should trigger rescan."""
    from dodo.plugins import _load_registry, clear_plugin_cache

    clear_plugin_cache()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    registry_file = config_dir / "plugin_registry.json"
    registry_file.write_text("not valid json {{{")

    # Mock _scan_and_save to avoid actual scanning
    def mock_scan(path):
        return {"test-plugin": {"hooks": [], "builtin": True}}

    monkeypatch.setattr("dodo.plugins._scan_and_save", mock_scan)

    result = _load_registry(config_dir)

    # Should have rescanned instead of crashing
    assert "test-plugin" in result


def test_corrupted_last_action_returns_none(tmp_path: Path, monkeypatch):
    """Corrupted .last_action file should return None."""
    from unittest.mock import MagicMock

    from dodo.cli import _load_last_action

    clear_config_cache()

    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    last_action_file = cfg_dir / ".last_action"
    last_action_file.write_text("{broken json")

    # Mock _get_config to return our temp dir
    mock_config = MagicMock()
    mock_config.config_dir = cfg_dir

    monkeypatch.setattr("dodo.cli._get_config", lambda: mock_config)

    result = _load_last_action()
    assert result is None
