"""Obsidian sync manager for ID mapping and fuzzy matching."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


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
