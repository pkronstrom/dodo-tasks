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
        assert "default_backend" in ConfigMeta.SETTINGS


class TestConfigDefaults:
    def test_default_backend(self):
        config = Config(Path("/tmp/dodo-test-nonexistent"))
        assert config.default_backend == "sqlite"

    def test_default_toggles(self):
        config = Config(Path("/tmp/dodo-test-nonexistent"))
        assert config.worktree_shared is True
        assert config.timestamps_enabled is True


class TestConfigLoad:
    def test_load_from_file(self, tmp_path: Path):
        config_dir = tmp_path / "dodo"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"worktree_shared": False, "default_backend": "sqlite"}))

        config = Config.load(config_dir)

        assert config.worktree_shared is False
        assert config.default_backend == "sqlite"

    def test_load_nonexistent_uses_defaults(self, tmp_path: Path):
        config = Config.load(tmp_path / "nonexistent")
        assert config.default_backend == "sqlite"


class TestConfigEnvOverrides:
    def test_env_overrides_bool(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_WORKTREE_SHARED", "false")
        config = Config.load(tmp_path)
        assert config.worktree_shared is False

    def test_env_overrides_string(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_DEFAULT_BACKEND", "sqlite")
        config = Config.load(tmp_path)
        assert config.default_backend == "sqlite"


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

        assert len(toggles) == 2
        names = [t[0] for t in toggles]
        assert "worktree_shared" in names
        assert "timestamps_enabled" in names

        # Check format: (name, description, value)
        for name, desc, value in toggles:
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(value, bool)


class TestConfigDefaultDir:
    def test_get_default_dir_returns_path(self):
        """Config.get_default_dir() should return default config directory."""
        from dodo.config import get_default_config_dir

        result = get_default_config_dir()

        assert isinstance(result, Path)
        assert result == Path.home() / ".config" / "dodo"

    def test_get_default_dir_respects_env_var(self, tmp_path, monkeypatch):
        """get_default_config_dir() should respect DODO_CONFIG_DIR env var."""
        from dodo.config import get_default_config_dir

        custom_dir = tmp_path / "custom-dodo"
        monkeypatch.setenv("DODO_CONFIG_DIR", str(custom_dir))

        result = get_default_config_dir()

        assert result == custom_dir


class TestLocalStorageRemoved:
    def test_local_storage_not_in_toggles(self):
        """local_storage should be removed from config toggles."""
        assert "local_storage" not in ConfigMeta.TOGGLES


class TestConfigCaching:
    def test_config_load_caches_result(self, tmp_path, monkeypatch):
        """Config.load() should return cached instance on repeated calls."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Clear any existing cache
        from dodo import config

        config._config_cache = None

        cfg1 = config.Config.load()
        cfg2 = config.Config.load()

        # Should be the same instance
        assert cfg1 is cfg2

    def test_config_cache_can_be_cleared(self, tmp_path, monkeypatch):
        """Config cache can be explicitly cleared."""
        monkeypatch.setenv("HOME", str(tmp_path))

        from dodo import config

        config._config_cache = None

        cfg1 = config.Config.load()
        config.clear_config_cache()
        cfg2 = config.Config.load()

        # Should be different instances after cache clear
        assert cfg1 is not cfg2
