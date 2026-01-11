"""Graph plugin for todo dependency tracking.

This plugin adds dependency management between todos:
- `dodo plugins graph ready` - list todos with no blocking dependencies
- `dodo plugins graph blocked` - list blocked todos
- `dodo plugins graph dep add/rm/list` - manage dependencies

Only works with SQLite adapter (requires database for dependency storage).
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


def extend_adapter(adapter, config: Config):
    """Wrap adapter with dependency tracking if SQLite."""
    from dodo.plugins.graph.wrapper import GraphWrapper

    # Only wrap SQLite adapters (they have _path attribute)
    if hasattr(adapter, "_path") and str(adapter._path).endswith(".db"):
        return GraphWrapper(adapter)
    return adapter


def extend_formatter(formatter, config: Config):
    """Extend formatter to show blocked_by column or tree view."""
    # Check if tree view is enabled in config
    tree_view = getattr(config, "graph_tree_view", "false")
    if str(tree_view).lower() in ("true", "1", "yes"):
        from dodo.plugins.graph.tree import TreeFormatter

        return TreeFormatter()

    from dodo.plugins.graph.formatter import GraphFormatter

    return GraphFormatter(formatter)
