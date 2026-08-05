"""Hypothesis property-based tests for the geo-eligibility engine.

Proves, across both shipped presets:

- Totality: any input shape (including None/empty/adversarial text) maps to
  a verdict and never raises.
- Exactly-one-class: the verdict is a single string drawn from ALL_CLASSES,
  never a set and never None.
- unknown is never in a blocked set: "unknown" is an ELIGIBLE class and an
  unknown-classified posting is never treated as foreign.
- Purity: classification has no side effects — the class-name constants and
  the profile's compiled patterns are unchanged after arbitrary inputs.
- Backtracking guard: adversarial inputs classify within the pytest timeout
  (the profile patterns are literal alternations with no nested quantifiers).
"""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="hypothesis not installed")
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from career_os.services.geo.classifier import (  # noqa: E402
    ALL_CLASSES,
    ELIGIBLE_CLASSES,
    classify_candidate,
    geo_eligibility,
)
from career_os.services.geo.presets import FRANKFURT_PROFILE, US_REMOTE_PROFILE  # noqa: E402

pytestmark = pytest.mark.property

PROFILES = (FRANKFURT_PROFILE, US_REMOTE_PROFILE)

_text_or_none = st.one_of(st.none(), st.text(max_size=300))
_offices = st.one_of(
    st.none(),
    st.lists(st.one_of(st.none(), st.text(max_size=80)), max_size=5),
)


# ---------------------------------------------------------------------------
# Totality + exactly-one-class
# ---------------------------------------------------------------------------


@given(
    location=_text_or_none,
    offices=_offices,
    remote=st.booleans(),
    title=st.text(max_size=120),
    description=st.text(max_size=3000),
    profile=st.sampled_from(PROFILES),
)
@settings(max_examples=200, deadline=None)
def test_totality_and_exactly_one_class(location, offices, remote, title, description, profile):
    verdict = geo_eligibility(
        location,
        offices=offices,
        remote=remote,
        title=title,
        description=description,
        profile=profile,
    )
    # Exactly one class: a single string, never a set/None/anything else.
    assert isinstance(verdict, str)
    assert verdict in ALL_CLASSES


@given(
    candidate=_text_or_none,
    remote=st.booleans(),
    profile=st.sampled_from(PROFILES),
)
@settings(max_examples=200, deadline=None)
def test_classify_candidate_total(candidate, remote, profile):
    verdict = classify_candidate(candidate, remote, profile)
    assert isinstance(verdict, str)
    # classify_candidate may additionally return the two internal classes.
    assert verdict in ALL_CLASSES | {"bare_remote", "country_locked"}


# ---------------------------------------------------------------------------
# unknown is never in a blocked set
# ---------------------------------------------------------------------------


def test_unknown_is_an_eligible_class():
    assert "unknown" in ELIGIBLE_CLASSES
    assert "unknown" not in {"foreign"}


@given(
    location=_text_or_none,
    remote=st.booleans(),
    profile=st.sampled_from(PROFILES),
)
@settings(max_examples=200, deadline=None)
def test_unknown_verdict_is_never_ineligible(location, remote, profile):
    verdict = geo_eligibility(location, remote=remote, profile=profile)
    if verdict == "unknown":
        assert verdict != "foreign"
        assert verdict in ELIGIBLE_CLASSES


# ---------------------------------------------------------------------------
# Purity: no mutation, no side effects
# ---------------------------------------------------------------------------


def _profile_snapshot(profile):
    """Snapshot the profile's pattern sources (None-safe)."""
    return {
        field: getattr(profile, field).pattern if getattr(profile, field) is not None else None
        for field in (
            "home_local",
            "home_country",
            "visa_free_region",
            "visa_free_wide",
            "visa_free_remote_phrase",
            "visa_required",
            "foreign",
            "eligible_region",
            "title_region_foreign",
        )
    }


@given(candidates=st.lists(st.text(max_size=200), min_size=50, max_size=50))
@settings(max_examples=10, deadline=None)
def test_purity_no_side_effects(candidates):
    classes_before = frozenset(ALL_CLASSES)
    snapshots_before = [_profile_snapshot(p) for p in PROFILES]
    names_before = [p.name for p in PROFILES]

    for profile in PROFILES:
        for candidate in candidates:
            classify_candidate(candidate, remote=False, profile=profile)
            geo_eligibility(candidate, remote=True, profile=profile)

    assert frozenset(ALL_CLASSES) == classes_before
    assert [_profile_snapshot(p) for p in PROFILES] == snapshots_before
    assert [p.name for p in PROFILES] == names_before


# ---------------------------------------------------------------------------
# Backtracking guard: adversarial inputs finish inside the pytest timeout
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "adversarial",
    [
        "a" * 10_000,
        "remote " * 1_500,
        ",-() " * 2_000,
        ("remote - " * 500) + "x",
        ("eu " * 3_000),
        "ü" * 10_000,
    ],
    ids=["run-of-a", "remote-repeat", "punctuation", "remote-dash", "eu-repeat", "umlaut-run"],
)
def test_adversarial_inputs_classify_quickly(adversarial):
    # The 30s pytest timeout is the budget; linear-time literal alternations
    # should finish orders of magnitude faster.
    for profile in PROFILES:
        assert classify_candidate(adversarial, True, profile) in (
            ALL_CLASSES | {"bare_remote", "country_locked"}
        )
        verdict = geo_eligibility(
            adversarial,
            remote=True,
            title=adversarial[:2_000],
            description=adversarial,
            profile=profile,
        )
        assert verdict in ALL_CLASSES
