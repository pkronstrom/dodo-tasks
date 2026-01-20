"""Tests for bulk input parser."""

import pytest

from dodo.bulk import parse_bulk_input, BulkInputType


class TestBulkInputParser:
    def test_parse_jsonl(self):
        input_text = '{"id": "abc123"}\n{"id": "def456"}'
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.JSONL
        assert result.items == [{"id": "abc123"}, {"id": "def456"}]

    def test_parse_json_array(self):
        input_text = '["abc123", "def456"]'
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.JSON_ARRAY
        assert result.items == ["abc123", "def456"]

    def test_parse_plain_ids(self):
        input_text = "abc123\ndef456\nghi789"
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.PLAIN_IDS
        assert result.items == ["abc123", "def456", "ghi789"]

    def test_parse_comma_separated(self):
        input_text = "abc123, def456, ghi789"
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.COMMA_SEPARATED
        assert result.items == ["abc123", "def456", "ghi789"]

    def test_parse_empty(self):
        result = parse_bulk_input("")
        assert result.items == []

    def test_parse_whitespace_only(self):
        result = parse_bulk_input("   \n   ")
        assert result.items == []

    def test_parse_jsonl_with_empty_lines(self):
        input_text = '{"id": "abc123"}\n\n{"id": "def456"}\n'
        result = parse_bulk_input(input_text)
        assert result.type == BulkInputType.JSONL
        assert len(result.items) == 2

    def test_parse_ids_strips_whitespace(self):
        input_text = "  abc123  \n  def456  "
        result = parse_bulk_input(input_text)
        assert result.items == ["abc123", "def456"]


class TestBulkInputFromArgs:
    def test_from_args(self):
        from dodo.bulk import parse_bulk_args

        result = parse_bulk_args(["abc123", "def456"])
        assert result.items == ["abc123", "def456"]

    def test_from_args_empty(self):
        from dodo.bulk import parse_bulk_args

        result = parse_bulk_args([])
        assert result.items == []
