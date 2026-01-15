"""ntfy-inbox plugin: Receive todos via ntfy.sh.

This plugin subscribes to an ntfy topic and automatically adds incoming
messages as todos.

Setup:
    dodo plugins enable ntfy-inbox
    dodo config                      # Set ntfy topic
    dodo plugins ntfy-inbox run      # Start listening

Message format:
    - Message body: Todo text
    - Title: Target dodo name (e.g., 'work', 'personal'). Empty = auto-detect.
    - Priority header (1-5): Maps to someday/low/normal/high/critical
    - No priority = unprioritized (null)

Text prefixes (override ntfy header):
    !!: or !!!: or !!!!:  -> critical
    !:                    -> high
    normal:               -> normal
    low:                  -> low
    someday:              -> someday

Tags: Include #hashtags in message text (e.g., "Buy milk #errands #shopping")

AI processing: Prefix message with "ai:" to process through AI plugin

Examples:
    # Simple todo to default dodo
    curl -d "Buy groceries" ntfy.sh/mytopic

    # High priority with tags to 'work' dodo
    curl -d "Fix bug #urgent" -H "Title: work" -H "Priority: 4" ntfy.sh/mytopic

    # Critical priority via text prefix
    curl -d "!!: Server down #incident" ntfy.sh/mytopic

    # AI-processed todo
    curl -d "ai: remember to call mom tomorrow" ntfy.sh/mytopic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer

    from dodo.config import Config

# Commands this plugin registers
COMMANDS = ["plugins/ntfy-inbox"]


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
        ConfigVar("topic", "", label="Topic", description="your secret topic"),
        ConfigVar("server", "https://ntfy.sh", label="Server", description="ntfy server URL"),
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
