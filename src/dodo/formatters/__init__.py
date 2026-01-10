"""Output formatters for dodo list command."""

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
    """
    parts = format_str.split(":")
    name = parts[0]

    if name not in FORMATTERS:
        raise ValueError(f"Unknown format: {name}. Available: {', '.join(FORMATTERS.keys())}")

    cls = FORMATTERS[name]

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
