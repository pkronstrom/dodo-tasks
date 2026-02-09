"""CLI commands for the server plugin."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

console = Console()


def build_server_app() -> typer.Typer:
    """Build the server command Typer app."""
    server_app = typer.Typer(
        name="server",
        help="Run dodo as a server (REST API, Web UI, MCP).",
        no_args_is_help=True,
    )
    server_app.command()(start)
    return server_app


def start(
    host: Annotated[
        str | None, typer.Option(help="Bind address (overrides config)")
    ] = None,
    port: Annotated[
        int | None, typer.Option(help="Port number (overrides config)")
    ] = None,
) -> None:
    """Start the dodo server."""
    try:
        import uvicorn  # noqa: F401
        from starlette.applications import Starlette  # noqa: F401
    except ImportError:
        console.print("[red]Server dependencies not installed.[/red]")
        console.print("Install with:")
        console.print("  [bold]uv pip install -e \".\\[server]\"[/bold]")
        console.print("  [bold]pip install -e \".\\[server]\"[/bold]")
        console.print(
            "\n[dim]Remote backend mode works without extra deps.[/dim]"
        )
        raise typer.Exit(1)

    from dodo.config import Config

    from .app import create_app

    cfg = Config.load()
    bind_host = host or cfg.get_plugin_config("server", "host", "127.0.0.1")
    bind_port = int(port or cfg.get_plugin_config("server", "port", "8080"))
    api_key = cfg.get_plugin_config("server", "api_key", "")

    # Security warning
    if bind_host == "0.0.0.0" and not api_key:
        console.print(
            "[yellow]Warning:[/yellow] Binding to 0.0.0.0 without an API key. "
            "Set api_key in config for authentication."
        )

    app = create_app(cfg)

    # Startup banner
    _print_banner(cfg, bind_host, bind_port, mcp_active=app.state.mcp_active)

    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")


def _print_banner(cfg, host: str, port: int, *, mcp_active: bool) -> None:
    """Print server startup info."""
    base_url = f"http://{host}:{port}"

    enable_api = cfg.get_plugin_config("server", "enable_api", "true") in ("true", "1", True)
    enable_mcp = cfg.get_plugin_config("server", "enable_mcp", "false") in ("true", "1", True)
    enable_web = cfg.get_plugin_config("server", "enable_web_ui", "true") in ("true", "1", True)
    api_key = cfg.get_plugin_config("server", "api_key", "")

    console.print()
    console.print("[bold]dodo server[/bold]")
    console.print(f"  Listening on [cyan]{base_url}[/cyan]")
    if enable_web:
        console.print(f"  Web UI:   [green]{base_url}/[/green]")
    if enable_api:
        console.print(f"  REST API: [green]{base_url}/api/v1/[/green]")
    if enable_mcp:
        if mcp_active:
            console.print(f"  MCP:      [green]{base_url}/mcp[/green]")
        else:
            console.print("  MCP:      [yellow]enabled but deps missing[/yellow]")
    auth_status = "[green]enabled[/green]" if api_key else "[yellow]disabled[/yellow]"
    console.print(f"  Auth:     {auth_status}")
    console.print("\n[dim]Press Ctrl+C to stop.[/dim]\n")
