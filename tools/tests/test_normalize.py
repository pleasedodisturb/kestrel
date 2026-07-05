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

    def test_accents_folded_to_ascii(self):
        # NFKD transliteration: combining-accent variants dedup against their
        # base form and aren't mangled (the old code turned "Café" into "caf").
        # Note: distinct letters that don't decompose (ø, ß, ł) are dropped, not
        # transliterated — accepted limitation.
        assert normalize_company("Café") == normalize_company("Cafe")
        assert normalize_company("Müller") == normalize_company("Muller")
        assert normalize_company("Zürich Labs") == normalize_company("Zurich")
        assert normalize_title("Señor Engineer") == normalize_title("Senor Engineer")

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
        # Dublin is a home-region city in the shipped config/geo.example.yaml; a
        # recognized location parenthetical is noise and must collapse.
        assert normalize_title("Engineer (Dublin)") == normalize_title("Engineer")
        assert normalize_title("Engineer (New York)") == normalize_title("Engineer")

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


class TestParentheticalSpecialization:
    """Specialization parens must NOT collapse; noise parens still do."""

    def test_distinct_specializations_not_merged(self):
        assert normalize_title("PM (Growth)") != normalize_title("PM (Platform)")
        assert normalize_title("Engineer (Backend)") != normalize_title("Engineer (Frontend)")

    def test_specialization_preserved_in_key(self):
        assert job_key("Acme", "PM (Growth)") != job_key("Acme", "PM (Platform)")

    def test_gender_paren_still_merged(self):
        assert normalize_title("Senior PM (m/f/d)") == normalize_title("Senior PM")
        assert normalize_title("Senior PM (w/m/d)") == normalize_title("Senior PM")

    def test_location_paren_still_merged(self):
        # Dublin = home-region city, New York = foreign, Remote/EU = remote noise —
        # all are recognized location noise and collapse.
        assert normalize_title("Engineer (Dublin)") == normalize_title("Engineer")
        assert normalize_title("Engineer (New York)") == normalize_title("Engineer")
        assert normalize_title("Engineer (Remote)") == normalize_title("Engineer")
        assert normalize_title("Engineer (EU)") == normalize_title("Engineer")

    def test_specialization_distinct_from_bare(self):
        assert normalize_title("PM (Growth)") != normalize_title("PM")


class TestMixedParenSpecialization:
    """A paren mixing location/remote + specialization must keep the specialization,
    not drop the whole paren."""

    def test_remote_plus_specialization_kept_distinct(self):
        assert normalize_title("Eng (Remote, Growth)") != normalize_title("Eng (Remote, Platform)")
        assert "growth" in normalize_title("Eng (Remote, Growth)")

    def test_pure_location_paren_still_dropped(self):
        assert normalize_title("Engineer (New York)") == normalize_title("Engineer")
        assert normalize_title("Engineer (Remote, EU)") == normalize_title("Engineer")


class TestHomeTokenLocationNoise:
    """The renamed 'home' geo verdict token drives location-noise detection.

    _segment_is_noise checks _classify_token(segment) in ("home", "eu_remote",
    "foreign"). A home-region city (Dublin in the shipped example config) must be
    filtered as noise through the "home" verdict specifically.
    """

    def test_home_city_paren_dropped_via_home_token(self):
        # "(Dublin)" is a home-region city -> _classify_token == "home" -> noise.
        # The title normalizes identically to the same title without the paren.
        assert normalize_title("Product Manager (Dublin)") == normalize_title("Product Manager")

    def test_home_city_does_not_shadow_specialization(self):
        # A home city mixed with a specialization keeps the specialization.
        assert "growth" in normalize_title("Product Manager (Dublin, Growth)")
        assert normalize_title("Product Manager (Dublin, Growth)") != normalize_title(
            "Product Manager (Dublin, Platform)"
        )
