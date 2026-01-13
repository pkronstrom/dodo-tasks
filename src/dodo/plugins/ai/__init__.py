"""AI plugin for todo management.

This plugin adds AI-assisted commands for todo creation and management:
- `dodo ai add` - Create todos with AI-inferred priority and tags
- `dodo ai prio` - AI-assisted bulk priority assignment
- `dodo ai tag` - AI-assisted tag suggestions
- `dodo ai reword` - AI-assisted todo rewording
- `dodo ai run` - Execute natural language instructions
- `dodo ai dep` - AI-assisted dependency detection (requires graph plugin)

Requires explicit enabling: `dodo plugins enable ai`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer

    from dodo.config import Config

# Commands this plugin registers at root level
COMMANDS = ["ai"]

# Default config values (single source of truth)
DEFAULT_COMMAND = "claude -p '{{prompt}}' --system-prompt '{{system}}' --json-schema '{{schema}}' --output-format json --model {{model}} --tools ''"
DEFAULT_RUN_COMMAND = "claude -p '{{prompt}}' --system-prompt '{{system}}' --json-schema '{{schema}}' --output-format json --model {{model}} --tools 'Read,Glob,Grep,WebSearch,Bash(git log:*,git status:*,git diff:*,git show:*,git blame:*,git branch:*)'"
DEFAULT_MODEL = "sonnet"
MODEL_OPTIONS = ["haiku", "sonnet", "opus"]


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
    """Declare config variables for this plugin.

    Note: These are registered for display in the config UI.
    Actual config is stored under plugins.ai in the config file.
    """
    return [
        ConfigVar(
            "command",
            DEFAULT_COMMAND,
            label="AI Command",
            description="Command template for AI operations",
        ),
        ConfigVar(
            "run_command",
            DEFAULT_RUN_COMMAND,
            label="AI Run Command",
            description="Command template for ai run (with tools)",
        ),
        ConfigVar(
            "model",
            DEFAULT_MODEL,
            label="AI Model",
            kind="cycle",
            options=MODEL_OPTIONS,
            description="Model for basic AI commands",
        ),
        ConfigVar(
            "run_model",
            DEFAULT_MODEL,
            label="AI Run Model",
            kind="cycle",
            options=MODEL_OPTIONS,
            description="Model for ai run command",
        ),
    ]


def register_root_commands(app: typer.Typer, config: Config) -> None:
    """Register AI commands at root level (dodo ai ...)."""
    from dodo.plugins.ai.cli import ai_app

    app.add_typer(ai_app, name="ai")
