"""Starlette app factory for dodo server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route

from dodo.plugins.server.auth import BasicAuthMiddleware

if TYPE_CHECKING:
    from dodo.config import Config

from dodo.plugins.server.api import (
    add_todo,
    complete_todo,
    delete_dodo,
    delete_todo,
    get_todo,
    health,
    list_dodos,
    list_todos,
    toggle_todo,
    update_todo,
)


class ServiceRegistry:
    """Lazy cache for TodoService instances keyed by dodo name."""

    def __init__(self, config: Config):
        from dodo.core import TodoService

        self._config = config
        self._cache: dict[str, TodoService] = {}

    def get_service(self, dodo_name: str):
        """Get or create a TodoService for the given dodo name."""
        from dodo.core import TodoService

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


def create_app(config: Config) -> Starlette:
    """Create the Starlette ASGI application."""
    registry = ServiceRegistry(config)

    # Build routes based on config toggles
    routes: list[Route | Mount] = []

    enable_api = config.get_plugin_config("server", "enable_api", "true") in ("true", "1", True)
    enable_mcp = config.get_plugin_config("server", "enable_mcp", "false") in ("true", "1", True)
    enable_web = config.get_plugin_config(
        "server", "enable_web_ui", "true"
    ) in ("true", "1", True)

    # Health endpoint (always available, no auth)
    routes.append(Route("/api/v1/health", health))

    if enable_api or enable_web:
        routes.extend([
            Route("/api/v1/dodos", list_dodos),
            Route("/api/v1/dodos/{name}", delete_dodo, methods=["DELETE"]),
            Route("/api/v1/dodos/{name}/todos", list_todos, methods=["GET"]),
            Route("/api/v1/dodos/{name}/todos", add_todo, methods=["POST"]),
            Route("/api/v1/dodos/{name}/todos/{todo_id}", get_todo, methods=["GET"]),
            Route("/api/v1/dodos/{name}/todos/{todo_id}", update_todo, methods=["PATCH"]),
            Route("/api/v1/dodos/{name}/todos/{todo_id}", delete_todo, methods=["DELETE"]),
            Route(
                "/api/v1/dodos/{name}/todos/{todo_id}/toggle",
                toggle_todo,
                methods=["POST"],
            ),
            Route(
                "/api/v1/dodos/{name}/todos/{todo_id}/complete",
                complete_todo,
                methods=["POST"],
            ),
        ])

    mcp_mounted = False
    if enable_mcp:
        try:
            from dodo.plugins.server.mcp_server import create_mcp_app

            mcp_app = create_mcp_app(registry)
            routes.append(Mount("/mcp", app=mcp_app))
            mcp_mounted = True
        except ImportError:
            import logging

            logging.getLogger("dodo.server").warning(
                "MCP enabled in config but mcp package not installed. "
                "Install with: pip install dodo[server]"
            )

    if enable_web:
        from pathlib import Path

        from starlette.responses import FileResponse
        from starlette.staticfiles import StaticFiles

        static_dir = Path(__file__).parent / "static"

        async def index(request):
            return FileResponse(static_dir / "index.html")

        routes.append(Route("/", index))
        routes.append(Mount("/static", app=StaticFiles(directory=str(static_dir))))

    # Middleware
    cors_origins = config.get_plugin_config("server", "cors_origins", "*")
    origins = [o.strip() for o in cors_origins.split(",")]

    middleware = [
        Middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"]),
    ]

    api_key = config.get_plugin_config("server", "api_key", "")
    if api_key:
        middleware.append(Middleware(BasicAuthMiddleware, api_key=api_key))

    app = Starlette(routes=routes, middleware=middleware)

    # Attach registry and feature flags to app state
    app.state.registry = registry
    app.state.mcp_active = mcp_mounted

    return app
