"""ServiceRegistry — lazy cache for TodoService instances.

Separated from app.py so MCP stdio transport can use it
without importing starlette.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dodo.config import Config
    from dodo.core import TodoService


class ServiceRegistry:
    """Lazy cache for TodoService instances keyed by dodo name."""

    def __init__(self, config: Config):
        from dodo.core import TodoService  # noqa: F811

        self._config = config
        self._cache: dict[str, TodoService] = {}

    def get_service(self, dodo_name: str):
        """Get or create a TodoService for the given dodo name."""
        from dodo.core import TodoService  # noqa: F811

        if dodo_name not in self._cache:
            project_id = None if dodo_name == "_default" else dodo_name
            self._cache[dodo_name] = TodoService(self._config, project_id)
        return self._cache[dodo_name]

    def list_dodos(self) -> list[dict]:
        """List available dodos by scanning config directory."""
        config_dir = self._config.config_dir
        dodos = []

        # Global dodo is always available
        dodos.append({"name": "_default", "backend": self._config.default_backend})

        # Scan for named projects
        projects_dir = config_dir / "projects"
        if projects_dir.exists():
            for entry in sorted(projects_dir.iterdir()):
                if entry.is_dir() and not entry.name.startswith((".", "_")):
                    dodos.append({"name": entry.name, "backend": self._get_backend(entry)})

        # Scan for top-level named dodos (same level as config.json)
        for entry in sorted(config_dir.iterdir()):
            if (
                entry.is_dir()
                and not entry.name.startswith((".", "_"))
                and entry.name not in ("projects", "plugins")
                and (
                    (entry / "dodo.db").exists()
                    or (entry / "dodo.md").exists()
                    or (entry / "dodo.json").exists()
                )
            ):
                if not any(d["name"] == entry.name for d in dodos):
                    dodos.append({"name": entry.name, "backend": self._get_backend(entry)})

        return dodos

    def delete_dodo(self, dodo_name: str) -> None:
        """Delete a dodo and its data. Cannot delete _default."""
        import shutil

        from dodo.resolve import InvalidDodoNameError, validate_dodo_name

        if dodo_name == "_default":
            raise ValueError("Cannot delete the global dodo")

        try:
            validate_dodo_name(dodo_name)
        except InvalidDodoNameError:
            raise ValueError(f"Invalid dodo name: {dodo_name}")

        config_dir = self._config.config_dir

        # Check global config directory
        target = config_dir / dodo_name
        if not target.exists():
            # Check projects subdirectory
            target = config_dir / "projects" / dodo_name
        if not target.exists():
            raise KeyError(f"Dodo not found: {dodo_name}")

        # Close cached service before removing files (avoids dangling SQLite connections)
        cached = self._cache.pop(dodo_name, None)
        if cached:
            try:
                cached.backend.close()
            except Exception:
                pass

        shutil.rmtree(target)

    def _get_backend(self, path) -> str:
        """Detect backend type from project directory."""
        import json

        config_file = path / "dodo.json"
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                return data.get("backend", "sqlite")
            except (json.JSONDecodeError, KeyError):
                pass
        if (path / "dodo.db").exists():
            return "sqlite"
        if (path / "dodo.md").exists():
            return "markdown"
        return self._config.default_backend
