"""Per-project configuration (dodo.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectConfig:
    """Project-level configuration stored in dodo.json."""

    backend: str

    @classmethod
    def load(cls, project_dir: Path) -> ProjectConfig | None:
        """Load project config from dodo.json.

        Args:
            project_dir: Directory containing dodo.json

        Returns:
            ProjectConfig if file exists, None otherwise
        """
        config_file = project_dir / "dodo.json"
        if not config_file.exists():
            return None

        try:
            data = json.loads(config_file.read_text())
            return cls(backend=data.get("backend", "sqlite"))
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, project_dir: Path) -> None:
        """Save project config to dodo.json."""
        project_dir.mkdir(parents=True, exist_ok=True)
        config_file = project_dir / "dodo.json"
        config_file.write_text(json.dumps({"backend": self.backend}, indent=2))

    @classmethod
    def ensure(cls, project_dir: Path, default_backend: str) -> ProjectConfig:
        """Load or create project config with default.

        Args:
            project_dir: Directory for dodo.json
            default_backend: Backend to use if creating new config

        Returns:
            Existing or newly created ProjectConfig
        """
        config = cls.load(project_dir)
        if config is not None:
            return config

        config = cls(backend=default_backend)
        config.save(project_dir)
        return config
