"""Tests for the robust parse_scoring_response() JSON parser."""

import json
import sys
from pathlib import Path

import pytest

# Ensure tools/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from job_scorer import parse_scoring_response

VALID_PAYLOAD = {
    "score": 7,
    "reasoning": "Good match for the role requirements.",
    "estimated_salary": "120k-150k EUR",
    "effort_flag": "medium",
    "prep_level": 2,
    "prep_notes": "Review domain knowledge.",
}


class TestParseValidJSON:
    """Test parsing of well-formed JSON."""

    def test_clean_json(self):
        raw = json.dumps(VALID_PAYLOAD)
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7
        assert result["reasoning"] == "Good match for the role requirements."

    def test_json_with_whitespace(self):
        raw = "  \n" + json.dumps(VALID_PAYLOAD) + "\n  "
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7


class TestCodeFencedJSON:
    """Test parsing of JSON wrapped in markdown code fences."""

    def test_json_code_fence(self):
        raw = "```json\n" + json.dumps(VALID_PAYLOAD) + "\n```"
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7

    def test_plain_code_fence(self):
        raw = "```\n" + json.dumps(VALID_PAYLOAD) + "\n```"
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7

    def test_code_fence_with_trailing_whitespace(self):
        raw = "```json\n" + json.dumps(VALID_PAYLOAD) + "\n```  \n"
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7


class TestTrailingCommas:
    """Test parsing of JSON with trailing commas (common LLM quirk)."""

    def test_trailing_comma_in_object(self):
        raw = '{"score": 7, "reasoning": "Good match",}'
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7

    def test_trailing_comma_in_nested(self):
        raw = '{"score": 7, "tags": ["a", "b",], "reasoning": "OK",}'
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7


class TestSurroundingText:
    """Test extraction of JSON from surrounding explanatory text."""

    def test_text_before_json(self):
        raw = 'Here is my analysis: {"score": 8, "reasoning": "Strong fit"}'
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 8

    def test_text_after_json(self):
        raw = '{"score": 6, "reasoning": "Partial match"} Let me know if you need more.'
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 6

    def test_text_both_sides(self):
        raw = 'Result: {"score": 9, "reasoning": "Excellent"} - done.'
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 9

    def test_nested_object_extraction(self):
        raw = 'Here: {"score": 5, "details": {"note": "nested"}, "reasoning": "OK"} end'
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 5
        assert result["details"]["note"] == "nested"


class TestSingleQuotes:
    """Test parsing of JSON with single quotes instead of double quotes."""

    def test_single_quotes(self):
        raw = "{'score': 7, 'reasoning': 'Good match'}"
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7


class TestEmptyAndNoneInput:
    """Test handling of empty, None, and invalid input."""

    def test_none_input(self):
        assert parse_scoring_response(None) is None

    def test_empty_string(self):
        assert parse_scoring_response("") is None

    def test_whitespace_only(self):
        assert parse_scoring_response("   \n\t  ") is None

    def test_completely_invalid_text(self):
        assert parse_scoring_response("I cannot score this job posting.") is None

    def test_truncated_json(self):
        assert parse_scoring_response('{"score": 7, "reason') is None


class TestEdgeCases:
    """Test edge cases and combined quirks."""

    def test_code_fence_with_trailing_comma(self):
        raw = '```json\n{"score": 7, "reasoning": "OK",}\n```'
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 7

    def test_surrounding_text_with_trailing_comma(self):
        raw = 'Result: {"score": 4, "reasoning": "Weak",} - end'
        result = parse_scoring_response(raw)
        assert result is not None
        assert result["score"] == 4
