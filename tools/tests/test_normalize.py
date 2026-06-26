"""Tests for tools/normalize.py — shared company/title normalization.

Ported from the Eyas downstream (G-1122). Mirrors the tools-test convention of
adding tools/ to sys.path so the module imports directly (see
test_spike_prefilter.py). tools/tests/ is not currently in the CI testpaths;
run locally with: pytest tools/tests/test_normalize.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add tools/ to path so we can import the normalize module directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from normalize import fuzzy_ratio, job_key, normalize_company, normalize_title


class TestNormalizeCompany:
    def test_lowercase_and_strip(self):
        assert normalize_company("  Acme  ") == "acme"

    def test_strips_legal_suffixes(self):
        assert normalize_company("Acme GmbH") == "acme"
        assert normalize_company("Acme Inc.") == "acme"
        assert normalize_company("Acme Ltd") == "acme"
        assert normalize_company("Acme Technologies") == "acme"

    def test_slug_vs_spaced_match(self):
        # Greenhouse slug-derived "Huggingface" vs tracked "Hugging Face"
        assert normalize_company("Huggingface") == normalize_company("Hugging Face")

    def test_punctuation_collapsed(self):
        assert normalize_company("Cal.com") == normalize_company("cal com")

    def test_empty_and_none(self):
        assert normalize_company("") == ""
        assert normalize_company(None) == ""

    def test_all_suffix_name_not_emptied(self):
        # "The Co" is all suffix-ish; must not collapse to empty (would over-merge)
        assert normalize_company("The Co") != ""


class TestNormalizeTitle:
    def test_strips_gender_tag(self):
        assert normalize_title("Senior PM (m/f/d)") == normalize_title("Senior PM")

    def test_strips_parenthetical_location(self):
        assert normalize_title("Engineer (Berlin)") == normalize_title("Engineer")

    def test_strips_remote_hybrid(self):
        assert normalize_title("Product Manager - Remote") == normalize_title("Product Manager")

    def test_case_insensitive(self):
        assert normalize_title("AI LEAD") == normalize_title("ai lead")

    def test_distinct_titles_stay_distinct(self):
        # must NOT over-merge genuinely different roles
        assert normalize_title("Senior Engineer") != normalize_title("Staff Engineer")


class TestJobKey:
    def test_drift_produces_same_key(self):
        assert job_key("Existing Co GmbH", "Senior PM (m/f/d)") == job_key(
            "Existing Co", "Senior PM"
        )

    def test_different_company_different_key(self):
        assert job_key("Acme", "PM") != job_key("Globex", "PM")


class TestFuzzyRatio:
    def test_identical(self):
        assert fuzzy_ratio("anthropic", "anthropic") == 100.0

    def test_close(self):
        assert fuzzy_ratio("huggingface", "hugging face") > 85.0

    def test_distinct_low(self):
        assert fuzzy_ratio("anthropic", "globex") < 60.0

    def test_empty(self):
        assert fuzzy_ratio("", "x") == 0.0
        assert fuzzy_ratio(None, "x") == 0.0
