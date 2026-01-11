"""Graph plugin for todo dependency tracking.

This plugin adds dependency management between todos:
- `dodo graph ready` - list todos with no blocking dependencies
- `dodo graph blocked` - list blocked todos
- `dodo dep add/rm/list` - manage dependencies
- `dodo list -f tree` - show todos as dependency tree

Also available under `dodo plugins graph` for discoverability.

Only works with SQLite adapter (requires database for dependency storage).
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
    """Configuration variable declaration."""

    name: str
    default: str


def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin."""
    return [
        ConfigVar("graph_tree_view", "false"),  # Show deps as tree in `dodo ls`
    ]


def register_commands(app: typer.Typer, config: Config) -> None:
    """Add dependency tracking CLI commands under 'dodo plugins graph'."""
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

    app.add_typer(graph_app, name="graph")


def register_root_commands(app: typer.Typer, config: Config) -> None:
    """Register root-level commands (dodo graph, dodo dep)."""
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

    app.add_typer(graph_app, name="graph")
    app.add_typer(dep_app, name="dep")


def register_formatters() -> dict[str, type]:
    """Return formatter classes for registration."""
    from dodo.plugins.graph.tree import TreeFormatter

    return {"tree": TreeFormatter}


def extend_adapter(adapter, config: Config):
    """Wrap adapter with dependency tracking if SQLite."""
    from dodo.plugins.graph.wrapper import GraphWrapper

    # Only wrap SQLite adapters (they have _path attribute)
    if hasattr(adapter, "_path") and str(adapter._path).endswith(".db"):
        return GraphWrapper(adapter)
    return adapter


def extend_formatter(formatter, config: Config):
    """Extend formatter to show blocked_by column or tree view."""
    from dodo.plugins.graph.tree import TreeFormatter

    # If user explicitly requested tree format, don't override
    if isinstance(formatter, TreeFormatter):
        return formatter

    # Check if tree view is enabled in config as default
    tree_view = getattr(config, "graph_tree_view", "false")
    if str(tree_view).lower() in ("true", "1", "yes"):
        return TreeFormatter()

    # Only wrap table formatter - other formats (jsonl, tsv) should pass through unchanged
    from dodo.formatters.table import TableFormatter

    if not isinstance(formatter, TableFormatter):
        return formatter

    from dodo.plugins.graph.formatter import GraphFormatter

    return GraphFormatter(formatter)
