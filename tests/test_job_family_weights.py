"""Tests for job family weight presets (G-301)."""

import pytest

from career_os.services.scoring import (
    DEFAULT_WEIGHTS,
    JOB_FAMILY_WEIGHTS,
    _weights_for_job_family,
)


class TestJobFamilyWeightPresets:
    """Validate the expanded JOB_FAMILY_WEIGHTS dictionary."""

    def test_minimum_preset_count(self):
        """Should have at least 200 job family presets."""
        assert len(JOB_FAMILY_WEIGHTS) >= 200, f"Only {len(JOB_FAMILY_WEIGHTS)} presets, need 200+"

    def test_all_weights_sum_to_one(self):
        """Every preset must sum to exactly 1.0 (within tolerance)."""
        for family, weights in JOB_FAMILY_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, f"{family} sums to {total}"

    def test_all_presets_have_required_keys(self):
        """Every preset must contain exactly the 7 required dimension keys."""
        required = set(DEFAULT_WEIGHTS.keys())
        for family, weights in JOB_FAMILY_WEIGHTS.items():
            assert set(weights.keys()) == required, f"{family} has wrong keys"

    def test_no_negative_weights(self):
        """No weight value should be negative."""
        for family, weights in JOB_FAMILY_WEIGHTS.items():
            for key, val in weights.items():
                assert val >= 0, f"{family}.{key} is negative: {val}"

    def test_no_weight_exceeds_one(self):
        """No single dimension should be weighted above 1.0."""
        for family, weights in JOB_FAMILY_WEIGHTS.items():
            for key, val in weights.items():
                assert val <= 1.0, f"{family}.{key} exceeds 1.0: {val}"

    def test_default_weights_sum_to_one(self):
        """DEFAULT_WEIGHTS itself must sum to 1.0."""
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"DEFAULT_WEIGHTS sums to {total}"


class TestWeightLookup:
    """Test _weights_for_job_family exact, case-insensitive, and fuzzy matching."""

    def test_exact_match(self):
        """Exact name should return the preset, not defaults."""
        result = _weights_for_job_family("Backend Engineer")
        assert result != DEFAULT_WEIGHTS

    def test_case_insensitive_match(self):
        """Case-insensitive lookup should work."""
        result = _weights_for_job_family("backend engineer")
        assert result != DEFAULT_WEIGHTS

    def test_fuzzy_substring_match(self):
        """Substring match should resolve partial queries."""
        # "Backend" is a substring of "Backend Engineer"
        result = _weights_for_job_family("Backend")
        assert result != DEFAULT_WEIGHTS

    def test_fuzzy_superstring_match(self):
        """Query that contains a preset name should match."""
        result = _weights_for_job_family("Senior Backend Engineer at Google")
        assert result != DEFAULT_WEIGHTS

    def test_none_returns_defaults(self):
        """None job_family should return DEFAULT_WEIGHTS."""
        result = _weights_for_job_family(None)
        assert result == DEFAULT_WEIGHTS

    def test_empty_string_returns_defaults(self):
        """Empty string should return DEFAULT_WEIGHTS."""
        result = _weights_for_job_family("")
        assert result == DEFAULT_WEIGHTS

    def test_unknown_family_returns_defaults(self):
        """Completely unknown family should return DEFAULT_WEIGHTS."""
        result = _weights_for_job_family("Underwater Basket Weaving")
        assert result == DEFAULT_WEIGHTS

    def test_returned_dict_is_copy(self):
        """Returned weights should be a copy, not the original dict."""
        result = _weights_for_job_family("SWE")
        result["skills_match"] = 999.0
        # Original should be unchanged
        assert JOB_FAMILY_WEIGHTS["SWE"]["skills_match"] != 999.0

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped."""
        result = _weights_for_job_family("  SWE  ")
        assert result != DEFAULT_WEIGHTS


class TestSectorCoverage:
    """Verify that major sectors have representation."""

    @pytest.mark.parametrize(
        "family",
        [
            "Backend Engineer",
            "Product Manager",
            "Financial Analyst",
            "Corporate Lawyer",
            "Marketing Manager",
            "Account Executive",
            "HR Manager",
            "Operations Manager",
            "Physician (General)",
            "University Professor",
            "Mechanical Engineer",
            "Construction Project Manager",
            "Journalist",
            "Hotel Manager",
            "Policy Analyst",
            "Real Estate Agent",
            "Agricultural Engineer",
        ],
    )
    def test_sector_representative_exists(self, family: str):
        """Each major sector should have at least one representative preset."""
        assert family in JOB_FAMILY_WEIGHTS, f"Missing preset: {family}"
