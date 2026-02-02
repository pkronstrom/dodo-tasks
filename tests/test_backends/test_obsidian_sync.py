"""Tests for Obsidian sync manager."""

import pytest

from dodo.plugins.obsidian.sync import normalize_text


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
