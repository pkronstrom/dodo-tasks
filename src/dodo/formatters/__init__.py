"""Output formatters for dodo list command."""

import json
from pathlib import Path

from .base import FormatterProtocol
from .jsonl import JsonlFormatter
from .table import TableFormatter
from .tsv import TsvFormatter

FORMATTERS: dict[str, type] = {
    "table": TableFormatter,
    "jsonl": JsonlFormatter,
    "tsv": TsvFormatter,
}

DEFAULT_DATETIME_FMT = "%m-%d %H:%M"


def _get_plugin_formatter(name: str) -> type | None:
    """Load formatter from enabled plugin if available."""
    config_dir = Path.home() / ".config" / "dodo"
    registry_path = config_dir / "plugin_registry.json"
    config_path = config_dir / "config.json"

    if not registry_path.exists():
        return None

    try:
        registry = json.loads(registry_path.read_text())
    except json.JSONDecodeError:
        return None

    try:
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
    except json.JSONDecodeError:
        config = {}

    enabled = set(filter(None, config.get("enabled_plugins", "").split(",")))

    for plugin_name, info in registry.items():
        if plugin_name in enabled and name in info.get("formatters", []):
            from dodo.plugins import _import_plugin

            plugin = _import_plugin(plugin_name, None)
            if hasattr(plugin, "register_formatters"):
                formatters = plugin.register_formatters()
                return formatters.get(name)

    return None


def get_formatter(format_str: str) -> FormatterProtocol:
    """Parse format string and return configured formatter.

    Format string syntax: <name>:<datetime_fmt>:<options>

    Examples:
        "table"           -> TableFormatter()
        "table:%Y-%m-%d"  -> TableFormatter(datetime_fmt="%Y-%m-%d")
        "table::id"       -> TableFormatter(show_id=True)
        "table:%m-%d:id"  -> TableFormatter(datetime_fmt="%m-%d", show_id=True)
        "jsonl"           -> JsonlFormatter()
        "tsv"             -> TsvFormatter()
        "tree"            -> TreeFormatter (from graph plugin)
    """
    parts = format_str.split(":")
    name = parts[0]

    # Check built-in formatters first
    if name in FORMATTERS:
        cls = FORMATTERS[name]
    else:
        # Check plugin formatters
        cls = _get_plugin_formatter(name)
        if cls is None:
            available = list(FORMATTERS.keys())
            raise ValueError(f"Unknown format: {name}. Available: {', '.join(available)}")

    if name == "table":
        datetime_fmt = parts[1] if len(parts) > 1 and parts[1] else DEFAULT_DATETIME_FMT
        show_id = len(parts) > 2 and parts[2] == "id"
        return cls(datetime_fmt=datetime_fmt, show_id=show_id)

    return cls()


__all__ = [
    "FormatterProtocol",
    "TableFormatter",
    "JsonlFormatter",
    "TsvFormatter",
    "FORMATTERS",
    "get_formatter",
]
