"""Obsidian sync manager for ID mapping and fuzzy matching."""

from __future__ import annotations

import re


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
