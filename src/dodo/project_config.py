"""Per-project configuration (dodo.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.config import Config


def get_project_config_dir(
    config: Config, project_id: str | None
) -> Path | None:
    """Get the directory where project config (dodo.json) should live.

    Args:
        config: Global dodo config
        project_id: Project identifier

    Returns:
        Path to project config directory, or None if no project
    """
    if not project_id:
        return None

    return config.config_dir / "projects" / project_id


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
