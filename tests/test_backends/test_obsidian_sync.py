"""Tests for Obsidian sync manager."""

import pytest

from dodo.plugins.obsidian.sync import find_best_match, normalize_text


class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("Ship The Feature") == "ship the feature"

    def test_strip_whitespace(self):
        assert normalize_text("  task  ") == "task"

    def test_collapse_multiple_spaces(self):
        assert normalize_text("ship  the   feature") == "ship the feature"

    def test_punctuation_to_space(self):
        assert normalize_text("ship-the-feature") == "ship the feature"

    def test_complex_normalization(self):
        assert normalize_text("Ship, the Feature!!!") == "ship the feature"

    def test_apostrophe(self):
        assert normalize_text("don't forget") == "don t forget"


class TestFindBestMatch:
    def test_exact_match(self):
        candidates = {"ship the feature": "abc12345", "buy groceries": "def67890"}
        match = find_best_match("ship the feature", candidates)
        assert match == "abc12345"

    def test_fuzzy_match_above_threshold(self):
        candidates = {"ship the feature": "abc12345"}
        # "ship feature" is ~88% similar to "ship the feature"
        match = find_best_match("ship feature", candidates, threshold=0.85)
        assert match == "abc12345"

    def test_no_match_below_threshold(self):
        candidates = {"ship the feature": "abc12345"}
        match = find_best_match("buy groceries", candidates, threshold=0.85)
        assert match is None

    def test_empty_candidates(self):
        match = find_best_match("anything", {})
        assert match is None

    def test_best_match_selected(self):
        candidates = {
            "ship feature": "abc12345",  # 75% similar
            "ship the features now": "def67890",  # 97.6% similar
        }
        match = find_best_match("ship the feature now", candidates)
        # "ship the features now" is closer match (97.6% vs 75%)
        assert match == "def67890"
