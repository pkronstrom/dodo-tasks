"""Graph plugin for todo dependency tracking.

This plugin adds dependency management between todos:
- `dodo graph ready` - list todos with no blocking dependencies
- `dodo graph blocked` - list blocked todos
- `dodo dep add/rm/list` - manage dependencies
- `dodo list -f tree` - show todos as dependency tree

Also available under `dodo plugins graph` for discoverability.

Only works with SQLite backend (requires database for dependency storage).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer

    from dodo.config import Config

# Commands this plugin registers
# - Root level: "graph", "dep" (dodo graph, dodo dep)
# - Nested: "plugins/graph" (dodo plugins graph)
COMMANDS = ["graph", "dep", "plugins/graph"]

# Formatters this plugin provides
FORMATTERS = ["tree"]


@dataclass
class ConfigVar:
    """Configuration variable declaration.

    Attributes:
        name: Config key name
        default: Default value as string
        label: Human-readable label (defaults to name)
        kind: Type of setting - "toggle", "edit", or "cycle"
        options: List of options for cycle type
        description: Help text for the setting
    """

    name: str
    default: str
    label: str | None = None
    kind: str = "edit"  # "toggle", "edit", "cycle"
    options: list[str] | None = None
    description: str | None = None


def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin."""
    return [
        ConfigVar(
            "tree_view",
            "false",
            label="Tree view",
            kind="toggle",
            description="Show deps as tree in list view",
        ),
    ]


def _build_graph_app() -> typer.Typer:
    """Build the graph command Typer app."""
    import typer as t

    from dodo.plugins.graph.cli import blocked, dep_app, ready

    graph_app = t.Typer(
        name="graph",
        help="Todo dependency tracking and visualization.",
        no_args_is_help=True,
    )
    graph_app.command()(ready)
    graph_app.command()(blocked)
    graph_app.add_typer(dep_app, name="dep")
    return graph_app


def register_commands(app: typer.Typer, config: Config) -> None:
    """Add dependency tracking CLI commands under 'dodo plugins graph'."""
    graph_app = _build_graph_app()
    app.add_typer(graph_app, name="graph")


def register_root_commands(app: typer.Typer, config: Config) -> None:
    """Register root-level commands (dodo graph, dodo dep)."""
    from dodo.plugins.graph.cli import dep_app

    graph_app = _build_graph_app()
    app.add_typer(graph_app, name="graph")
    app.add_typer(dep_app, name="dep")


def register_formatters() -> dict[str, type]:
    """Return formatter classes for registration."""
    from dodo.plugins.graph.tree import TreeFormatter

    return {"tree": TreeFormatter}


def extend_backend(backend, config: Config):
    """Wrap backend with dependency tracking if SQLite."""
    from dodo.backends.sqlite import SqliteBackend
    from dodo.plugins.graph.wrapper import GraphWrapper

    # Only wrap SQLite backends
    if isinstance(backend, SqliteBackend):
        return GraphWrapper(backend)
    return backend


def extend_formatter(formatter, config: Config):
    """Wrap formatter to add blocked_by column, or switch to tree view.

    The GraphFormatter wrapper keeps plugin-specific logic out of core formatters.
    """
    from dodo.plugins.graph.formatter import GraphFormatter
    from dodo.plugins.graph.tree import TreeFormatter

    # If user explicitly requested tree format, don't override
    if isinstance(formatter, TreeFormatter):
        return formatter

    # Check if tree view is enabled in config as default (use nested config)
    tree_view = config.get_plugin_config("graph", "tree_view", "false")
    if str(tree_view).lower() in ("true", "1", "yes"):
        return TreeFormatter()

    # Wrap formatter to add blocked_by column when present
    return GraphFormatter(formatter)


def register_hooks() -> dict[str, str]:
    """Register callable hooks for cross-plugin communication."""
    return {
        "add_dependencies": "dodo.plugins.graph.wrapper:add_dependencies_hook",
    }
