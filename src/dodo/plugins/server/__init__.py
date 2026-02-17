"""Server plugin: REST API, Web UI, MCP endpoint, and remote backend.

Dual mode:
- Server: `dodo server start` exposes all local dodos via REST/MCP/Web UI
- Client: Set backend to `remote` to use a remote dodo server as storage

Server mode requires: pip install dodo[server]
Client mode (remote backend) works with no extra deps (uses httpx).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer

    from dodo.config import Config

# Commands this plugin registers
# - Root level: "server" (dodo server start)
# - Nested: "plugins/server" (dodo plugins server)
COMMANDS = ["server", "plugins/server"]


@dataclass
class ConfigVar:
    """Configuration variable declaration."""

    name: str
    default: str
    label: str | None = None
    kind: str = "edit"
    options: list[str] | None = None
    description: str | None = None


def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin."""
    return [
        # Server settings
        ConfigVar(
            "enable_web_ui", "true",
            label="Web UI", kind="toggle",
        ),
        ConfigVar(
            "enable_api", "true",
            label="REST API", kind="toggle",
        ),
        ConfigVar(
            "enable_mcp", "false",
            label="MCP Server", kind="toggle",
        ),
        ConfigVar(
            "host", "127.0.0.1",
            label="Host",
            description="0.0.0.0 for remote access",
        ),
        ConfigVar(
            "port", "8080",
            label="Port",
        ),
        ConfigVar(
            "api_key", "",
            label="API Key",
            description="Empty = no auth",
        ),
        ConfigVar(
            "cors_origins", "*",
            label="CORS Origins",
        ),
        # Remote backend (use with: dodo new <name> --backend remote)
        ConfigVar(
            "remote_url", "",
            label="Remote URL",
            description="e.g. http://myserver:8080",
        ),
        ConfigVar(
            "remote_key", "",
            label="Remote API Key",
            description="Matches api_key on the server",
        ),
        # Webhook
        ConfigVar(
            "webhook_url", "",
            label="Webhook URL",
            description="POST on change (empty = disabled)",
        ),
        ConfigVar(
            "webhook_secret", "",
            label="Webhook Secret",
            description="HMAC signing key",
        ),
    ]


def register_backend(registry: dict, config: Config) -> None:
    """Register the remote backend with the backend registry."""
    registry["remote"] = "dodo.plugins.server.remote:RemoteBackend"


def register_commands(app: typer.Typer, config: Config) -> None:
    """Register commands under 'dodo plugins server' subcommand."""
    from dodo.plugins.server.cli import build_server_app

    app.add_typer(build_server_app(), name="server")


def extend_backend(backend, config: Config):
    """Wrap backend with webhook support if configured."""
    url = config.get_plugin_config("server", "webhook_url", "")
    if not url:
        return backend
    secret = config.get_plugin_config("server", "webhook_secret", "")
    from dodo.plugins.server.webhook import WebhookWrapper
    return WebhookWrapper(backend, url, secret, "default")


def register_root_commands(app: typer.Typer, config: Config) -> None:
    """Register root-level command: dodo server start."""
    from dodo.plugins.server.cli import build_server_app

    app.add_typer(build_server_app(), name="server")
