"""ntfy-inbox plugin: Receive todos via ntfy.sh.

This plugin adds commands under `dodo ntfy` that subscribe to an ntfy topic
and automatically add incoming messages as todos.

Usage:
    dodo plugins enable ntfy-inbox
    dodo config     # Set ntfy_topic
    dodo ntfy run   # Start listening
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer

    from dodo.config import Config


@dataclass
class ConfigVar:
    """Configuration variable declaration."""

    name: str
    default: str


def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin."""
    return [
        ConfigVar("ntfy_topic", ""),  # Required - user's secret topic
        ConfigVar("ntfy_server", "https://ntfy.sh"),
    ]


def register_commands(app: typer.Typer, config: Config) -> None:
    """Register commands under 'dodo plugins ntfy-inbox' subcommand."""
    import typer as t

    from dodo.plugins.ntfy_inbox.inbox import inbox

    # Create subapp so commands are namespaced: dodo plugins ntfy-inbox <cmd>
    ntfy_app = t.Typer(
        name="ntfy-inbox",
        help="Receive todos via ntfy.sh push notifications.",
        no_args_is_help=True,
    )
    ntfy_app.command(name="run")(inbox)

    app.add_typer(ntfy_app, name="ntfy-inbox")
