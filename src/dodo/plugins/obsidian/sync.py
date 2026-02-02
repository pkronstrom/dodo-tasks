"""Obsidian sync manager for ID mapping and fuzzy matching."""

from __future__ import annotations

import json
import re
import uuid
from difflib import SequenceMatcher
from pathlib import Path


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching.

    - Lowercase
    - Replace punctuation with spaces
    - Collapse multiple whitespace
    - Strip leading/trailing whitespace
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # punctuation -> space
    text = re.sub(r'\s+', ' ', text)       # collapse whitespace
    return text.strip()


def find_best_match(
    text: str,
    candidates: dict[str, str],
    threshold: float = 0.85,
) -> str | None:
    """Find the best matching ID for text using fuzzy matching.

    Args:
        text: Normalized text to match
        candidates: Dict mapping normalized text to ID
        threshold: Minimum similarity ratio (0.0-1.0)

    Returns:
        Best matching ID if similarity >= threshold, else None
    """
    if not candidates:
        return None

    # Try exact match first (fast path)
    if text in candidates:
        return candidates[text]

    best_id = None
    best_ratio = 0.0

    for candidate_text, candidate_id in candidates.items():
        ratio = SequenceMatcher(None, text, candidate_text).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = candidate_id

    return best_id if best_ratio >= threshold else None


class SyncManager:
    """Manages ID mappings and header associations for Obsidian sync.

    Stores data in a JSON sidecar file separate from the Obsidian markdown.
    """

    def __init__(self, sync_file: Path):
        self._sync_file = sync_file
        self.ids: dict[str, str] = {}      # normalized_text -> id
        self.headers: dict[str, str] = {}  # tag -> header_text
        self._load()

    def _load(self) -> None:
        """Load sync data from file."""
        if self._sync_file.exists():
            try:
                data = json.loads(self._sync_file.read_text())
                self.ids = data.get("ids", {})
                self.headers = data.get("headers", {})
            except (json.JSONDecodeError, KeyError):
                pass  # Start fresh on corrupt file

    def save(self) -> None:
        """Save sync data to file."""
        self._sync_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"ids": self.ids, "headers": self.headers}
        self._sync_file.write_text(json.dumps(data, indent=2))

    def get_or_create_id(self, text: str) -> str:
        """Get existing ID or create new one for task text.

        Uses fuzzy matching to find existing IDs for edited text.
        """
        normalized = normalize_text(text)

        # Try exact and fuzzy match
        existing_id = find_best_match(normalized, self.ids)
        if existing_id:
            return existing_id

        # Generate new ID
        new_id = uuid.uuid4().hex[:8]
        self.ids[normalized] = new_id
        return new_id
