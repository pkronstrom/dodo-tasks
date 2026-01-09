"""Tests for config system."""

import json
from pathlib import Path

import pytest

from dodo.config import Config, ConfigMeta


class TestConfigMeta:
    def test_toggles_defined(self):
        assert "worktree_shared" in ConfigMeta.TOGGLES
        assert "timestamps_enabled" in ConfigMeta.TOGGLES

    def test_settings_defined(self):
        assert "default_adapter" in ConfigMeta.SETTINGS


class TestConfigDefaults:
    def test_default_adapter(self):
        config = Config(Path("/tmp/dodo-test-nonexistent"))
        assert config.default_adapter == "markdown"

    def test_default_toggles(self):
        config = Config(Path("/tmp/dodo-test-nonexistent"))
        assert config.worktree_shared is True
        assert config.timestamps_enabled is True


class TestConfigLoad:
    def test_load_from_file(self, tmp_path: Path):
        config_dir = tmp_path / "dodo"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"worktree_shared": False, "default_adapter": "sqlite"}))

        config = Config.load(config_dir)

        assert config.worktree_shared is False
        assert config.default_adapter == "sqlite"

    def test_load_nonexistent_uses_defaults(self, tmp_path: Path):
        config = Config.load(tmp_path / "nonexistent")
        assert config.default_adapter == "markdown"


class TestConfigEnvOverrides:
    def test_env_overrides_bool(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_WORKTREE_SHARED", "false")
        config = Config.load(tmp_path)
        assert config.worktree_shared is False

    def test_env_overrides_string(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_DEFAULT_ADAPTER", "sqlite")
        config = Config.load(tmp_path)
        assert config.default_adapter == "sqlite"


class TestConfigPersistence:
    def test_set_and_save(self, tmp_path: Path):
        config_dir = tmp_path / "dodo"
        config = Config.load(config_dir)

        config.set("worktree_shared", False)

        # Reload and verify
        config2 = Config.load(config_dir)
        assert config2.worktree_shared is False

    def test_get_toggles(self, tmp_path: Path):
        config = Config.load(tmp_path)
        toggles = config.get_toggles()

        assert len(toggles) == 3
        names = [t[0] for t in toggles]
        assert "worktree_shared" in names
        assert "timestamps_enabled" in names

        # Check format: (name, description, value)
        for name, desc, value in toggles:
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(value, bool)
