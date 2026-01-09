"""Configuration system with autodiscoverable toggles."""

import json
import os
from pathlib import Path
from typing import Any


class ConfigMeta:
    """Schema definition - separate from runtime state."""

    TOGGLES: dict[str, str] = {
        "worktree_shared": "Share todos across git worktrees",
        "local_storage": "Store todos in project dir (vs centralized)",
        "timestamps_enabled": "Add timestamps to todo entries",
    }

    SETTINGS: dict[str, str] = {
        "default_adapter": "Backend adapter (markdown|sqlite|obsidian)",
        "editor": "Editor command (empty = use $EDITOR)",
        "ai_command": "AI CLI command template",
        "ai_sys_prompt": "AI system prompt",
        "obsidian_api_url": "Obsidian REST API URL",
        "obsidian_api_key": "Obsidian API key",
        "obsidian_vault_path": "Path within Obsidian vault",
    }


class Config:
    """Runtime configuration with env override support."""

    DEFAULTS: dict[str, Any] = {
        # Toggles
        "worktree_shared": True,
        "local_storage": False,
        "timestamps_enabled": True,
        # Settings
        "default_adapter": "markdown",
        "editor": "",  # Empty = use $EDITOR or vim
        "ai_command": "claude -p '{{system}}\n\n{{prompt}}' --model haiku",
        "ai_sys_prompt": (
            "You are a todo formatter. Return a JSON array of clear, actionable todo items. "
            "If one task, return array with one item. If multiple implied, split them. "
            "Keep each under 100 chars. Return ONLY valid JSON array."
        ),
        "obsidian_api_url": "https://localhost:27124",
        "obsidian_api_key": "",
        "obsidian_vault_path": "dodo/todos.md",
    }

    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir or Path.home() / ".config" / "dodo"
        self._config_file = self._config_dir / "config.json"
        self._data: dict[str, Any] = {}

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @classmethod
    def load(cls, config_dir: Path | None = None) -> "Config":
        """Factory method - explicit loading."""
        config = cls(config_dir)
        config._load_from_file()
        config._apply_env_overrides()
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
            self._data = json.loads(self._config_file.read_text())

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
