"""Bulk input parser for dodo CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum


class BulkInputType(Enum):
    """Type of bulk input detected."""

    JSONL = "jsonl"
    JSON_ARRAY = "json_array"
    PLAIN_IDS = "plain_ids"
    COMMA_SEPARATED = "comma_separated"
    ARGS = "args"
    EMPTY = "empty"


@dataclass
class BulkInput:
    """Parsed bulk input."""

    type: BulkInputType
    items: list  # list of dicts for JSONL, list of strings for IDs


def parse_bulk_input(text: str) -> BulkInput:
    """Parse bulk input, auto-detecting format.

    Supports:
    - JSONL: lines starting with {
    - JSON array: input starts with [
    - Plain IDs: one per line
    - Comma-separated: single line with commas
    """
    text = text.strip()

    if not text:
        return BulkInput(type=BulkInputType.EMPTY, items=[])

    # Try JSON array first
    if text.startswith("["):
        try:
            items = json.loads(text)
            if isinstance(items, list):
                return BulkInput(type=BulkInputType.JSON_ARRAY, items=items)
        except json.JSONDecodeError:
            pass

    # Try JSONL (lines starting with {)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines and lines[0].startswith("{"):
        items = []
        for line in lines:
            if line.startswith("{"):
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Skip invalid lines
        if items:
            return BulkInput(type=BulkInputType.JSONL, items=items)

    # Check for comma-separated (single line with commas)
    if len(lines) == 1 and "," in lines[0]:
        items = [item.strip() for item in lines[0].split(",") if item.strip()]
        return BulkInput(type=BulkInputType.COMMA_SEPARATED, items=items)

    # Plain IDs (one per line)
    items = [line.strip() for line in lines if line.strip()]
    return BulkInput(type=BulkInputType.PLAIN_IDS, items=items)


def parse_bulk_args(args: list[str]) -> BulkInput:
    """Parse bulk input from command line arguments."""
    if not args:
        return BulkInput(type=BulkInputType.EMPTY, items=[])
    return BulkInput(type=BulkInputType.ARGS, items=list(args))
