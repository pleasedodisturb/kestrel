"""Integration tier for the geo-eligibility engine (G-1474 plan 03).

Covers three layers:

1. ``geo_eligibility`` end-to-end on realistic posting dicts (location +
   offices[] + title + description shapes as produced by the Greenhouse and
   Ashby fetchers).
2. The opt-in pre-filter geo gate: inert with ``geo_profile=None``
   (regression guard), drops ``foreign`` with a profile configured, and NEVER
   drops ``unknown`` or a maybe class.
3. The post-AI-cap contract: eligible / maybe / blocked membership for each
   fixture class, so a future reclassification is loud.

NOTE: the home-city literal used here is "Frankfurt am Main" (never the
"<city>, <country>" form) so the personal-geography scrub gate stays empty;
the classes are identical.
"""

import copy

from career_os.discovery.prefilter import (
    PrefilterConfig,
    PrefilterStrategy,
    run_prefilter,
)
from career_os.services.geo.classifier import (
    ALL_CLASSES,
    ELIGIBLE_CLASSES,
    MAYBE_CLASSES,
    geo_eligibility,
)
from career_os.services.geo.presets import FRANKFURT_PROFILE

# ---------------------------------------------------------------------------
# Realistic posting fixtures (Greenhouse / Ashby shapes) + expected classes
# ---------------------------------------------------------------------------

# Each entry: (name, job dict, expected class under FRANKFURT_PROFILE).
POSTING_FIXTURES: list[tuple[str, dict, str]] = [
    (
        "greenhouse_foreign_onsite",
        {
            "title": "Senior Backend Engineer",
            "description": "Join our New York office.",
            "location": "New York, United States",
            "offices": ["New York"],  # Greenhouse offices[].name
            "remote": False,
        },
        "foreign",
    ),
    (
        "ashby_secondary_office_rescue",
        {
            "title": "Product Engineer",
            "description": "Distributed team across the US and Europe.",
            "location": "Austin, Texas",  # primary location is foreign...
            # ...but an Ashby secondaryLocations[].location rescues the role.
            "offices": ["Austin, Texas", "Remote - Germany"],
            "remote": True,
        },
        "home_relocate",
    ),
    (
        "bare_remote_with_us_description",
        {
            "title": "Platform Engineer",
            "description": (
                "We are hiring across our offices in New York, Austin and "
                "Seattle. US work authorization required."
            ),
            "location": "Remote",
            "offices": [],
            "remote": True,
        },
        "foreign",
    ),
    (
        "home_local_onsite",
        {
            "title": "Data Engineer",
            "description": "Onsite role in our head office.",
            "location": "Frankfurt am Main",
            "offices": [],
            "remote": False,
        },
        "home_local",
    ),
    (
        "unknown_no_geo_signal",
        {
            "title": "Software Engineer",
            "description": "A role at a stealth startup.",
            "location": "Somewhereville",
            "offices": [],
            "remote": False,
        },
        "unknown",
    ),
    (
        "visa_required_onsite",
        {
            "title": "Site Reliability Engineer",
            "description": "Onsite in our London office.",
            "location": "London",
            "offices": [],
            "remote": False,
        },
        "visa_required_relocate",
    ),
    (
        "visa_free_onsite",
        {
            "title": "Backend Engineer",
            "description": "Hybrid role.",
            "location": "Amsterdam, Netherlands",
            "offices": [],
            "remote": False,
        },
        "visa_free_relocate",
    ),
]


def _classify(job: dict) -> str:
    return geo_eligibility(
        job.get("location"),
        job.get("offices"),
        bool(job.get("remote")),
        job.get("title", ""),
        job.get("description", ""),
        profile=FRANKFURT_PROFILE,
    )


# ---------------------------------------------------------------------------
# 1. End-to-end classification on realistic posting shapes
# ---------------------------------------------------------------------------


def test_posting_fixtures_classify_as_expected():
    for name, job, expected in POSTING_FIXTURES:
        assert _classify(job) == expected, name


def test_offices_override_the_list_location_string():
    # The Ashby rescue works BECAUSE offices replace the foreign list string.
    _, job, _ = next(f for f in POSTING_FIXTURES if f[0] == "ashby_secondary_office_rescue")
    without_offices = dict(job, offices=[])
    assert _classify(without_offices) == "foreign"
    assert _classify(job) == "home_relocate"


def test_bare_remote_consults_description_before_defaulting_eligible():
    _, job, _ = next(f for f in POSTING_FIXTURES if f[0] == "bare_remote_with_us_description")
    assert _classify(job) == "foreign"
    # Same posting with no description signal is unspecified remote: eligible.
    assert _classify(dict(job, description="")) == "eligible_remote"


# ---------------------------------------------------------------------------
# 2. Pre-filter wiring (opt-in geo gate)
# ---------------------------------------------------------------------------


def _prefilter_jobs() -> list[dict]:
    # All titles match the keyword so ONLY the geo gate can differ between
    # the with-profile and without-profile runs.
    return [dict(job, title="Product Manager") for _, job, _ in POSTING_FIXTURES]


def _config(**kwargs) -> PrefilterConfig:
    kwargs.setdefault("strategy", PrefilterStrategy.MODERATE)
    return PrefilterConfig(title_keywords=["Product Manager"], **kwargs)


def test_prefilter_without_profile_is_byte_identical_regression_guard():
    jobs = _prefilter_jobs()
    snapshot = copy.deepcopy(jobs)

    passed, metrics = run_prefilter(jobs, _config())

    # Inert: nothing filtered, no geo metric, and the job dicts are untouched
    # (no geo_class key injected).
    assert passed == snapshot
    assert jobs == snapshot
    assert metrics.geo_rejections == 0
    assert metrics.filtered == 0
    assert all("geo_class" not in job for job in passed)


def test_prefilter_with_profile_drops_only_foreign():
    jobs = _prefilter_jobs()
    passed, metrics = run_prefilter(jobs, _config(geo_profile=FRANKFURT_PROFILE))

    kept_locations = [job["location"] for job in passed]
    # Both foreign fixtures are dropped and counted.
    assert "New York, United States" not in kept_locations
    assert metrics.geo_rejections == 2
    assert metrics.filtered == 2

    # NEVER dropped: unknown and the maybe classes.
    assert "Somewhereville" in kept_locations
    assert "London" in kept_locations
    assert "Amsterdam, Netherlands" in kept_locations
    # And the eligible ones obviously survive.
    assert "Frankfurt am Main" in kept_locations
    assert "Austin, Texas" in kept_locations  # the office-rescued role

    # Survivors carry the verdict for downstream consumers (t3 lane, ranking).
    assert all(job.get("geo_class") in ALL_CLASSES for job in passed)
    assert all(job["geo_class"] != "foreign" for job in passed)


def test_prefilter_off_strategy_bypasses_the_geo_gate():
    jobs = _prefilter_jobs()
    passed, metrics = run_prefilter(
        jobs,
        _config(geo_profile=FRANKFURT_PROFILE, strategy=PrefilterStrategy.OFF),
    )
    # OFF is a full bypass: everything passes, no geo classification happens.
    assert len(passed) == len(jobs)
    assert metrics.geo_rejections == 0
    assert all("geo_class" not in job for job in passed)


def test_prefilter_strict_strategy_also_applies_the_geo_gate():
    jobs = _prefilter_jobs()
    passed, metrics = run_prefilter(
        jobs,
        _config(geo_profile=FRANKFURT_PROFILE, strategy=PrefilterStrategy.STRICT),
    )
    assert metrics.geo_rejections == 2
    assert all(job["geo_class"] != "foreign" for job in passed)


# ---------------------------------------------------------------------------
# 3. Post-AI-cap contract: eligible / maybe / blocked membership
# ---------------------------------------------------------------------------

# Cap treatment expected for each fixture class. A reclassification between
# eligible / maybe / blocked changes scoring-cap behaviour downstream and
# must be a loud, deliberate change.
_EXPECTED_CAP_TREATMENT = {
    "greenhouse_foreign_onsite": "blocked",
    "ashby_secondary_office_rescue": "eligible",
    "bare_remote_with_us_description": "blocked",
    "home_local_onsite": "eligible",
    "unknown_no_geo_signal": "eligible",
    "visa_required_onsite": "maybe",
    "visa_free_onsite": "maybe",
}


def test_cap_treatment_contract_per_fixture():
    for name, job, _ in POSTING_FIXTURES:
        cls = _classify(job)
        if cls in ELIGIBLE_CLASSES:
            treatment = "eligible"
        elif cls in MAYBE_CLASSES:
            treatment = "maybe"
        else:
            treatment = "blocked"
        assert treatment == _EXPECTED_CAP_TREATMENT[name], (name, cls)


def test_unknown_is_deliberately_eligible():
    # Absence of geo signal must never bury a role.
    assert "unknown" in ELIGIBLE_CLASSES
    assert "unknown" not in MAYBE_CLASSES


def test_class_sets_partition_all_classes():
    assert ELIGIBLE_CLASSES | MAYBE_CLASSES | {"foreign"} == ALL_CLASSES
    assert ELIGIBLE_CLASSES.isdisjoint(MAYBE_CLASSES)
    assert "foreign" not in ELIGIBLE_CLASSES | MAYBE_CLASSES
