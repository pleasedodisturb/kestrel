"""Tests for the per-role Greenhouse qualifying-question overlay (G-627 / issue #347).

Covers `_get_gh_fields_for_slug` and the pre-seeded `GH_FIELDS_BY_SLUG` map
in `tools/batch_apply_browser.py`. These tests are intentionally pure-Python
(no Playwright, no network, no config files) so they run in CI regardless of
whether `config/personal.yaml` is present.
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

# Stable baseline used across tests — a minimal stand-in for the real
# Anthropic Greenhouse baseline. Decoupled from production strings so test
# breaks signal real merge-logic regressions, not copy edits.
BASELINE: list[tuple[str, str, bool]] = [
    ("Country", "United Kingdom", False),
    ("Why Anthropic", "baseline-why", False),
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

    def test_non_anthropic_greenhouse_role_unaffected(self):
        # Regression guard for issue #347 acceptance criteria — generic
        # Greenhouse postings must keep working with baseline only.
        result = _get_gh_fields_for_slug(BASELINE, "vercel-staff-engineer")
        # Real overlay map should not contain Vercel.
        assert result == BASELINE


# ---------------------------------------------------------------------------
# overlay-merge for a known slug
# ---------------------------------------------------------------------------


class TestOverlayMerge:
    """When the slug matches an overlay key, extras are appended after baseline."""

    def test_exact_slug_match_appends_extras(self):
        overlay = {
            "anthropic-tdl-paris": [
                ("French C1", "No", False),
                ("e2e delivery", "Yes", False),
            ]
        }
        result = _get_gh_fields_for_slug(BASELINE, "anthropic-tdl-paris", overlay=overlay)
        assert result[: len(BASELINE)] == BASELINE
        assert ("French C1", "No", False) in result
        assert ("e2e delivery", "Yes", False) in result
        assert len(result) == len(BASELINE) + 2

    def test_substring_slug_match_appends_extras(self):
        # Real-world scrapes often append a city/seq suffix to the slug.
        overlay = {"anthropic-tdl": [("French C1", "No", False)]}
        result = _get_gh_fields_for_slug(BASELINE, "anthropic-tdl-paris-2026q2", overlay=overlay)
        assert ("French C1", "No", False) in result

    def test_case_insensitive_slug_match(self):
        overlay = {"anthropic-tdl": [("French C1", "No", False)]}
        result = _get_gh_fields_for_slug(BASELINE, "Anthropic-TDL-Paris", overlay=overlay)
        assert ("French C1", "No", False) in result

    def test_overlay_order_preserved(self):
        overlay = {
            "anthropic-mgr-fde": [
                ("managed engineering teams", "Yes", False),
                ("regulated industries", "Yes", False),
                ("forward-deployed", "Yes", False),
            ]
        }
        result = _get_gh_fields_for_slug(BASELINE, "anthropic-mgr-fde", overlay=overlay)
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
            "anthropic-tdl": [
                ("Country", "France", False),  # collides with baseline
                ("French C1", "No", False),
            ]
        }
        result = _get_gh_fields_for_slug(BASELINE, "anthropic-tdl", overlay=overlay)
        # Exactly one Country entry, and it's the baseline value.
        countries = [t for t in result if t[0] == "Country"]
        assert len(countries) == 1
        assert countries[0] == ("Country", "United Kingdom", False)
        # The non-colliding overlay extra still gets appended.
        assert ("French C1", "No", False) in result

    def test_full_overlap_returns_baseline(self):
        overlay = {
            "anthropic-tdl": [
                ("Country", "France", False),
                ("Why Anthropic", "overlay-why", False),
            ]
        }
        result = _get_gh_fields_for_slug(BASELINE, "anthropic-tdl", overlay=overlay)
        assert result == BASELINE


# ---------------------------------------------------------------------------
# pre-seeded overlay sanity
# ---------------------------------------------------------------------------


class TestPreSeededOverlay:
    """Smoke-test the three roles called out in issue #347."""

    @pytest.mark.parametrize(
        "slug_key",
        [
            "anthropic-technical-deployment-lead",
            "anthropic-manager-fde-applied-ai",
            "anthropic-solutions-architect",
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

    def test_tdl_paris_includes_french_proficiency(self):
        # The actual gating filter for TDL Paris per issue #347.
        extras = GH_FIELDS_BY_SLUG["anthropic-technical-deployment-lead"]
        labels = " ".join(label for label, _v, _e in extras).lower()
        assert "french" in labels

    def test_architect_munich_includes_german_proficiency(self):
        extras = GH_FIELDS_BY_SLUG["anthropic-solutions-architect"]
        labels = " ".join(label for label, _v, _e in extras).lower()
        assert "german" in labels

    def test_anthropic_irl_falls_through_to_baseline(self):
        # IRL has no role-specific qualifying questions in the current scrape
        # (acceptance criterion 4 in issue #347).
        result = _get_gh_fields_for_slug(BASELINE, "anthropic-international-readiness")
        assert result == BASELINE

    def test_default_overlay_is_used_when_overlay_arg_omitted(self):
        # When `overlay=` is not passed, the function should consult the
        # module-level GH_FIELDS_BY_SLUG. Patch it to verify the lookup path.
        sentinel = {"anthropic-test-slug": [("sentinel-label", "Yes", False)]}
        with patch("tools.batch_apply_browser.GH_FIELDS_BY_SLUG", sentinel):
            result = _get_gh_fields_for_slug(BASELINE, "anthropic-test-slug")
        assert ("sentinel-label", "Yes", False) in result
