"""Tests for the per-role Greenhouse qualifying-question overlay.

Covers `_get_gh_fields_for_slug` and the config-driven `GH_FIELDS_BY_SLUG` map
in `tools/batch_apply_browser.py`. The map is seeded from an embedded fictional
floor (and extended by `config/personal.yaml` `role_overlays`), so these tests
run in CI regardless of whether a real config is present — they assert against
the always-present fictional floor slugs.
"""

import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# `tools.batch_apply_browser` loads `config/personal.yaml` eagerly at import
# time. CI (.github/workflows/ci.yml and smoke.yml) copies
# `config/personal.yaml.example -> config/personal.yaml` before running tests.
# We replicate that here so this test module always loads — pure-logic tests
# don't need real PII and shouldn't silently skip on fresh worktrees.
_personal_config = _REPO_ROOT / "config" / "personal.yaml"
_personal_example = _REPO_ROOT / "config" / "personal.yaml.example"
if not _personal_config.exists() and _personal_example.exists():
    shutil.copy(_personal_example, _personal_config)

# If neither file exists, fall back to skip (matches test_batch_apply_browser.py).
if not _personal_config.exists():
    pytest.skip(
        "config/personal.yaml{.example} not found — skipping overlay tests",
        allow_module_level=True,
    )

from tools.batch_apply_browser import (  # noqa: E402
    GH_FIELDS_BY_SLUG,
    _get_gh_fields_for_slug,
)

# Stable baseline used across tests — a minimal stand-in for a company's shared
# Greenhouse baseline. Decoupled from production strings so test breaks signal
# real merge-logic regressions, not copy edits.
BASELINE: list[tuple[str, str, bool]] = [
    ("Country", "United Kingdom", False),
    ("Why Meridian", "baseline-why", False),
    ("Working address", "London", False),
]


# ---------------------------------------------------------------------------
# baseline-only path (no slug match)
# ---------------------------------------------------------------------------


class TestBaselineOnlyPath:
    """When the slug matches no overlay key, baseline is returned unchanged."""

    def test_unknown_slug_returns_baseline_copy(self):
        result = _get_gh_fields_for_slug(BASELINE, "stripe-payments-engineer", overlay={})
        assert result == BASELINE

    def test_empty_slug_returns_baseline_copy(self):
        result = _get_gh_fields_for_slug(BASELINE, "", overlay={})
        assert result == BASELINE

    def test_none_slug_returns_baseline_copy(self):
        # _get_gh_fields_for_slug must tolerate None defensively — app.get("slug")
        # can return None when slug is missing.
        result = _get_gh_fields_for_slug(BASELINE, None, overlay={})  # type: ignore[arg-type]
        assert result == BASELINE

    def test_returns_new_list_not_baseline_reference(self):
        # Caller must not mutate the canonical baseline when iterating results.
        result = _get_gh_fields_for_slug(BASELINE, "no-match", overlay={})
        assert result is not BASELINE
        result.append(("injected", "value", False))
        assert ("injected", "value", False) not in BASELINE

    def test_unmatched_greenhouse_role_unaffected(self):
        # Generic Greenhouse postings that match no overlay key must keep
        # working with baseline only.
        result = _get_gh_fields_for_slug(BASELINE, "orbitalsystems-staff-engineer")
        # Overlay map should not contain this fictional slug.
        assert result == BASELINE


# ---------------------------------------------------------------------------
# overlay-merge for a known slug
# ---------------------------------------------------------------------------


class TestOverlayMerge:
    """When the slug matches an overlay key, extras are appended after baseline."""

    def test_exact_slug_match_appends_extras(self):
        overlay = {
            "meridianlabs-senior-engineer": [
                ("Language C1", "No", False),
                ("e2e delivery", "Yes", False),
            ]
        }
        result = _get_gh_fields_for_slug(BASELINE, "meridianlabs-senior-engineer", overlay=overlay)
        assert result[: len(BASELINE)] == BASELINE
        assert ("Language C1", "No", False) in result
        assert ("e2e delivery", "Yes", False) in result
        assert len(result) == len(BASELINE) + 2

    def test_substring_slug_match_appends_extras(self):
        # Real-world scrapes often append a city/seq suffix to the slug.
        overlay = {"meridianlabs-senior": [("Language C1", "No", False)]}
        result = _get_gh_fields_for_slug(
            BASELINE, "meridianlabs-senior-engineer-2026q2", overlay=overlay
        )
        assert ("Language C1", "No", False) in result

    def test_case_insensitive_slug_match(self):
        overlay = {"meridianlabs-senior": [("Language C1", "No", False)]}
        result = _get_gh_fields_for_slug(BASELINE, "MeridianLabs-Senior-Engineer", overlay=overlay)
        assert ("Language C1", "No", False) in result

    def test_overlay_order_preserved(self):
        overlay = {
            "meridianlabs-engineering-manager": [
                ("managed engineering teams", "Yes", False),
                ("regulated industries", "Yes", False),
                ("forward-deployed", "Yes", False),
            ]
        }
        result = _get_gh_fields_for_slug(
            BASELINE, "meridianlabs-engineering-manager", overlay=overlay
        )
        extras = result[len(BASELINE) :]
        assert [t[0] for t in extras] == [
            "managed engineering teams",
            "regulated industries",
            "forward-deployed",
        ]


# ---------------------------------------------------------------------------
# no-collision behaviour when baseline + overlay share a label
# ---------------------------------------------------------------------------


class TestNoCollision:
    """Baseline answers must always win over overlay duplicates."""

    def test_collision_keeps_baseline_value(self):
        overlay = {
            "meridianlabs-senior": [
                ("Country", "France", False),  # collides with baseline
                ("Language C1", "No", False),
            ]
        }
        result = _get_gh_fields_for_slug(BASELINE, "meridianlabs-senior", overlay=overlay)
        # Exactly one Country entry, and it's the baseline value.
        countries = [t for t in result if t[0] == "Country"]
        assert len(countries) == 1
        assert countries[0] == ("Country", "United Kingdom", False)
        # The non-colliding overlay extra still gets appended.
        assert ("Language C1", "No", False) in result

    def test_full_overlap_returns_baseline(self):
        overlay = {
            "meridianlabs-senior": [
                ("Country", "France", False),
                ("Why Meridian", "overlay-why", False),
            ]
        }
        result = _get_gh_fields_for_slug(BASELINE, "meridianlabs-senior", overlay=overlay)
        assert result == BASELINE


# ---------------------------------------------------------------------------
# pre-seeded overlay sanity
# ---------------------------------------------------------------------------


class TestPreSeededOverlay:
    """Smoke-test the three fictional floor roles that ship with the tool."""

    @pytest.mark.parametrize(
        "slug_key",
        [
            "meridianlabs-senior-engineer",
            "meridianlabs-engineering-manager",
            "meridianlabs-solutions-architect",
        ],
    )
    def test_each_pre_seeded_slug_has_non_empty_overlay(self, slug_key):
        assert slug_key in GH_FIELDS_BY_SLUG, f"missing overlay for {slug_key}"
        extras = GH_FIELDS_BY_SLUG[slug_key]
        assert len(extras) >= 3, f"overlay for {slug_key} should have 3+ qualifying questions"
        for entry in extras:
            assert isinstance(entry, tuple) and len(entry) == 3
            label, value, exact = entry
            assert isinstance(label, str) and label
            assert isinstance(value, str) and value
            assert isinstance(exact, bool)

    def test_senior_engineer_includes_language_proficiency(self):
        # A language-proficiency question is the kind of role-specific gating
        # filter the overlay exists to carry.
        extras = GH_FIELDS_BY_SLUG["meridianlabs-senior-engineer"]
        labels = " ".join(label for label, _v, _e in extras).lower()
        assert "language" in labels

    def test_solutions_architect_includes_language_proficiency(self):
        extras = GH_FIELDS_BY_SLUG["meridianlabs-solutions-architect"]
        labels = " ".join(label for label, _v, _e in extras).lower()
        assert "language" in labels

    def test_unknown_role_falls_through_to_baseline(self):
        # A role with no overlay entry returns the baseline unchanged.
        result = _get_gh_fields_for_slug(BASELINE, "meridianlabs-international-readiness")
        assert result == BASELINE

    def test_default_overlay_is_used_when_overlay_arg_omitted(self):
        # When `overlay=` is not passed, the function should consult the
        # module-level GH_FIELDS_BY_SLUG. Patch it to verify the lookup path.
        sentinel = {"meridianlabs-test-slug": [("sentinel-label", "Yes", False)]}
        with patch("tools.batch_apply_browser.GH_FIELDS_BY_SLUG", sentinel):
            result = _get_gh_fields_for_slug(BASELINE, "meridianlabs-test-slug")
        assert ("sentinel-label", "Yes", False) in result
