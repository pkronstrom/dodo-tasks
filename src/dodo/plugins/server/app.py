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
    add_tag_endpoint,
    add_todo,
    complete_todo,
    delete_dodo,
    delete_todo,
    get_todo,
    health,
    list_dodos,
    list_todos,
    remove_metadata_endpoint,
    remove_tag_endpoint,
    set_metadata_endpoint,
    toggle_todo,
    update_todo,
)
from dodo.plugins.server.registry import ServiceRegistry  # noqa: F401 — re-export


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
            Route(
                "/api/v1/dodos/{name}/todos/{todo_id}/tags/add",
                add_tag_endpoint,
                methods=["POST"],
            ),
            Route(
                "/api/v1/dodos/{name}/todos/{todo_id}/tags/remove",
                remove_tag_endpoint,
                methods=["POST"],
            ),
            Route(
                "/api/v1/dodos/{name}/todos/{todo_id}/meta/set",
                set_metadata_endpoint,
                methods=["POST"],
            ),
            Route(
                "/api/v1/dodos/{name}/todos/{todo_id}/meta/remove",
                remove_metadata_endpoint,
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
