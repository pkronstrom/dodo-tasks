"""Configuration system with autodiscoverable toggles."""

import json
import os
from pathlib import Path
from typing import Any

# Module-level cache for singleton pattern
_config_cache: "Config | None" = None


def clear_config_cache() -> None:
    """Clear the config cache. Useful for testing or config reload."""
    global _config_cache
    _config_cache = None


def get_default_config_dir() -> Path:
    """Get default config directory, respecting DODO_CONFIG_DIR env var.

    This is the single source of truth for config directory resolution.
    """
    config_dir = os.environ.get("DODO_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    return Path.home() / ".config" / "dodo"


class ConfigMeta:
    """Schema definition - separate from runtime state."""

    TOGGLES: dict[str, str] = {
        "worktree_shared": "Share todos across git worktrees",
        "timestamps_enabled": "Add timestamps to todo entries",
    }

    SETTINGS: dict[str, str] = {
        "default_backend": "Backend (markdown|sqlite|obsidian)",
        "default_format": "Output format (table|jsonl|tsv)",
        "editor": "Editor command (empty = use $EDITOR)",
        "interactive_width": "Max width for interactive menu (default: 120)",
    }


class Config:
    """Runtime configuration with env override support."""

    DEFAULTS: dict[str, Any] = {
        # Toggles
        "worktree_shared": True,
        "timestamps_enabled": True,
        # Settings
        "default_backend": "sqlite",
        "default_format": "table",
        "editor": "",  # Empty = use $EDITOR or vim
        "interactive_width": 120,  # Max width for interactive menu
        # Plugin system
        "enabled_plugins": "",  # Comma-separated list of enabled plugins
    }

    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir or get_default_config_dir()
        self._config_file = self._config_dir / "config.json"
        self._data: dict[str, Any] = {}

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @classmethod
    def load(cls, config_dir: Path | None = None) -> "Config":
        """Factory method - explicit loading with caching."""
        global _config_cache

        # Return cached instance if available and no custom dir specified
        if _config_cache is not None and config_dir is None:
            return _config_cache

        config = cls(config_dir)
        config._load_from_file()
        config._apply_env_overrides()

        # Cache if using default directory
        if config_dir is None:
            _config_cache = config

        return config

    def __getattr__(self, name: str) -> Any:
        """Access config values as attributes."""
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._data:
            return self._data[name]
        if name in self.DEFAULTS:
            return self.DEFAULTS[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def get_plugin_config(self, plugin_name: str, key: str, default: Any = None) -> Any:
        """Get config value for a plugin from nested plugins.<name> structure.

        Handles both dash and underscore variants for backwards compatibility
        (e.g., ntfy-inbox and ntfy_inbox are treated as equivalent).
        """
        plugins = self._data.get("plugins", {})
        plugin_config = plugins.get(plugin_name, {})

        # Fallback: try alternate naming (dash <-> underscore)
        if not plugin_config:
            alt_name = (
                plugin_name.replace("-", "_")
                if "-" in plugin_name
                else plugin_name.replace("_", "-")
            )
            plugin_config = plugins.get(alt_name, {})

        return plugin_config.get(key, default)

    def set_plugin_config(self, plugin_name: str, key: str, value: Any) -> None:
        """Set config value for a plugin in nested plugins.<name> structure."""
        if "plugins" not in self._data:
            self._data["plugins"] = {}
        if plugin_name not in self._data["plugins"]:
            self._data["plugins"][plugin_name] = {}
        self._data["plugins"][plugin_name][key] = value
        self._save()

    @property
    def enabled_plugins(self) -> set[str]:
        """Get set of enabled plugin names."""
        raw = self._data.get("enabled_plugins", self.DEFAULTS["enabled_plugins"])
        return {p.strip() for p in raw.split(",") if p.strip()}

    def get_toggles(self) -> list[tuple[str, str, bool]]:
        """Return (attr, description, enabled) for interactive menu."""
        return [
            (name, desc, bool(getattr(self, name))) for name, desc in ConfigMeta.TOGGLES.items()
        ]

    def set(self, key: str, value: Any) -> None:
        """Set value and persist."""
        self._data[key] = value
        self._save()

    def _load_from_file(self) -> None:
        if self._config_file.exists():
            try:
                content = self._config_file.read_text()
                if content.strip():
                    self._data = json.loads(content)
            except json.JSONDecodeError:
                # Corrupted config - use defaults, will be fixed on next save
                self._data = {}

    def _save(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._config_file.write_text(json.dumps(self._data, indent=2))

    def _apply_env_overrides(self) -> None:
        """Apply DODO_* env vars (highest priority)."""
        for key, default in self.DEFAULTS.items():
            env_key = f"DODO_{key.upper()}"
            if env_key in os.environ:
                self._data[key] = self._coerce(os.environ[env_key], type(default))

    @staticmethod
    def _coerce(value: str, target_type: type) -> Any:
        """Coerce string env value to target type."""
        if target_type is bool:
            return value.lower() in ("true", "1", "yes")
        if target_type is int:
            return int(value)
        return value

    # Directory mapping methods
    def get_directory_mapping(self, directory: str) -> str | None:
        """Get the dodo name mapped to a directory path."""
        mappings = self._data.get("directory_mappings", {})
        return mappings.get(directory)

    def set_directory_mapping(self, directory: str, dodo_name: str) -> None:
        """Map a directory path to a dodo name."""
        if "directory_mappings" not in self._data:
            self._data["directory_mappings"] = {}
        self._data["directory_mappings"][directory] = dodo_name
        self._save()

    def remove_directory_mapping(self, directory: str) -> bool:
        """Remove a directory mapping. Returns True if it existed."""
        mappings = self._data.get("directory_mappings", {})
        if directory in mappings:
            del mappings[directory]
            self._save()
            return True
        return False

    def get_all_directory_mappings(self) -> dict[str, str]:
        """Get all directory mappings."""
        return self._data.get("directory_mappings", {})
