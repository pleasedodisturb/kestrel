"""Unit tests for the generic 7-way geo-eligibility engine.

Covers, against FRANKFURT_PROFILE (the measured reference preset):

- All geo-classification cases ported from the source engine's geo-gate suite
  (``tools/tests/test_geo_gate.py``), re-expressed as generic-class verdicts.
  The old gate returned ``"de"`` / ``"eligible_remote"`` / ``None``; here each
  case asserts the specific generic class the v2 engine assigns. The source
  suite's 4 URL-parsing cases and the Ashby posting-extraction plumbing have
  no surface in this pure classifier package — the 3 Ashby cases are ported
  as their extracted offices[] lists, the URL cases are N/A (they test ATS
  URL parsing, not geo classification).
- >=3 positive and >=2 negative cases for each of the 7 generic classes.
- Both v2 contract rules, in both directions.
- The 6-input config swing between FRANKFURT_PROFILE and US_REMOTE_PROFILE.
- Edge cases: None/empty locations, offices overriding a lying location
  string, junk offices entries, umlaut variants.
"""

from __future__ import annotations

import pytest

from career_os.services.geo.classifier import (
    ALL_CLASSES,
    ELIGIBLE_CLASSES,
    MAYBE_CLASSES,
    geo_eligibility,
)
from career_os.services.geo.presets import FRANKFURT_PROFILE, US_REMOTE_PROFILE


def fk(
    location: str | None = None,
    *,
    offices: list[str] | None = None,
    remote: bool = False,
    title: str = "",
    description: str = "",
) -> str:
    """Classify under the reference FRANKFURT_PROFILE."""
    return geo_eligibility(
        location,
        offices=offices,
        remote=remote,
        title=title,
        description=description,
        profile=FRANKFURT_PROFILE,
    )


def us(
    location: str | None = None,
    *,
    offices: list[str] | None = None,
    remote: bool = False,
    title: str = "",
    description: str = "",
) -> str:
    """Classify under the contrasting US_REMOTE_PROFILE."""
    return geo_eligibility(
        location,
        offices=offices,
        remote=remote,
        title=title,
        description=description,
        profile=US_REMOTE_PROFILE,
    )


# ---------------------------------------------------------------------------
# Class-name constants
# ---------------------------------------------------------------------------


def test_class_constants():
    assert {"home_local", "home_relocate", "eligible_remote", "unknown"} == ELIGIBLE_CLASSES
    assert {"visa_free_relocate", "visa_required_relocate"} == MAYBE_CLASSES
    assert ELIGIBLE_CLASSES | MAYBE_CLASSES | {"foreign"} == ALL_CLASSES


# ---------------------------------------------------------------------------
# Ported geo-gate cases (tools/tests/test_geo_gate.py), generic verdicts.
# Old "de" -> home_local | home_relocate; old None (drop) -> the specific
# class the v2 engine assigns (foreign, or a MAYBE relocation class).
# ---------------------------------------------------------------------------


def test_munich_onsite_keep():
    # was: geo_classify("Munich, Germany") == "de"
    assert fk("Munich, Germany") == "home_relocate"


def test_frankfurt_keep():
    # was: geo_classify("Frankfurt") == "de" — commute belt, no move.
    assert fk("Frankfurt") == "home_local"


def test_paris_onsite_with_berlin_also_listed_overridden():
    # was: dropped (None). The list string lied "Berlin, Germany; Munich" but
    # the REAL office is Paris; authoritative offices ignore the lying string.
    # v2 keeps a visa-free onsite as a flagged MAYBE class instead of a drop.
    verdict = fk("Berlin, Germany; Munich", offices=["Paris, France"], remote=False)
    assert verdict == "visa_free_relocate"
    assert verdict not in ELIGIBLE_CLASSES


def test_remote_sweden_drop():
    # was: dropped (None) — country-locked remote to Sweden.
    assert fk("Finland; Remote - Denmark; Stockholm, Sweden", offices=["Remote - Sweden"]) == (
        "foreign"
    )


def test_remote_emea_keep():
    assert fk("Remote - EMEA") == "eligible_remote"


def test_remote_us_drop():
    # was: dropped (None) — remote must NOT rescue a US-located role.
    assert fk("San Francisco, US", remote=True) == "foreign"
    assert fk("Remote - US", remote=True) == "foreign"


def test_bare_remote_keep():
    assert fk("Remote", remote=True) == "eligible_remote"


def test_remote_germany_keep():
    # was: geo_classify("Germany (Remote)") == "de"
    assert fk("Germany (Remote)") == "home_relocate"


def test_remote_europe_keep():
    assert fk("Remote - Europe") == "eligible_remote"


def test_remote_eu_wide_keep():
    assert fk("Remote (EU)") == "eligible_remote"


def test_global_remote_keep():
    assert fk("Remote - Global") == "eligible_remote"


def test_planetscale_emea_plus_na_keep():
    # "Remote - EMEA, Remote - NA" -> EMEA present => eligible.
    assert fk("Remote - EMEA, Remote - NA") == "eligible_remote"


def test_spain_locked_remote_drop():
    # was: dropped (None) — country-locked remote to Spain.
    assert fk("Madrid; Remotely in Spain", remote=True) == "foreign"


def test_us_not_matching_austria():
    # Word-boundary guard: "Austria" must NOT trigger the \bus\b foreign rule.
    # v2 classifies Austria as a visa-free onsite MAYBE, not foreign.
    verdict = fk("Vienna, Austria")
    assert verdict == "visa_free_relocate"
    assert verdict != "foreign"


def test_home_wins_over_foreign_in_multilist():
    # was: "de" — a Berlin-anchored role that also offers Paris stays eligible.
    assert fk("Berlin", offices=["Berlin, Germany", "Paris, France"]) == "home_relocate"


def test_remote_never_rescues_foreign_office():
    # was: dropped (None) — remote flag never rescues a country-locked office.
    assert fk("Paris", offices=["Paris, France"], remote=True) == "foreign"


def test_eligibility_set_membership():
    # was: geo_ok wrapper — eligibility is now set membership on the verdict.
    assert fk("Munich, Germany") in ELIGIBLE_CLASSES
    assert fk("Remote - Sweden") == "foreign"
    assert fk("Remote - Sweden") not in ELIGIBLE_CLASSES


def test_ashby_secondary_germany_rescues_france_primary():
    # Pennylane rescue: primary "All France (remote)" but a secondary office
    # is "Germany (remote)" => a Germany role (offices[] as extracted).
    verdict = fk(
        "All France (remote)",
        offices=["All France (remote)", "Germany (remote)", "Spain (remote)"],
        remote=True,
    )
    assert verdict == "home_relocate"


def test_ashby_bare_remote_with_no_secondaries_keep():
    # PostHog shape: bare "Remote", no secondary locations. A US HQ address
    # is NOT a candidate, so nothing forecloses the posting.
    assert fk("Remote", offices=[], remote=True) == "eligible_remote"


def test_ashby_berlin_keep():
    assert fk("Berlin", offices=["Berlin"], remote=False) == "home_relocate"


# NOTE: the source suite's remaining 4 cases (test_parse_greenhouse_*,
# test_parse_ashby_url) exercise ATS URL parsing in batch_probe.py — there is
# no equivalent surface in this pure classification package, so they are N/A.


# ---------------------------------------------------------------------------
# Per-class coverage: >=3 positive and >=2 negative cases per generic class.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "location",
    [
        "Frankfurt",
        "Frankfurt am Main, Deutschland",
        "Wiesbaden, Deutschland",
        "Darmstadt, Germany",
    ],
)
def test_home_local_positive(location):
    assert fk(location) == "home_local"


@pytest.mark.parametrize("location", ["Berlin, Deutschland", "Munich, Germany"])
def test_home_local_negative(location):
    assert fk(location) != "home_local"


@pytest.mark.parametrize(
    "location",
    ["Munich, Germany", "Berlin, Deutschland", "Hamburg, Deutschland", "Germany (Remote)"],
)
def test_home_relocate_positive(location):
    assert fk(location) == "home_relocate"


@pytest.mark.parametrize("location", ["Frankfurt", "Amsterdam, Netherlands"])
def test_home_relocate_negative(location):
    assert fk(location) != "home_relocate"


@pytest.mark.parametrize(
    "location",
    ["Remote - EMEA", "Remote - Europe", "Remote - Global", "EMEA"],
)
def test_eligible_remote_positive(location):
    assert fk(location) == "eligible_remote"


@pytest.mark.parametrize("location", ["Remote - US", "Remote - Sweden"])
def test_eligible_remote_negative(location):
    assert fk(location, remote=True) != "eligible_remote"


@pytest.mark.parametrize(
    "location",
    ["Amsterdam, Netherlands", "Vienna, Austria", "Lisbon, Portugal"],
)
def test_visa_free_relocate_positive(location):
    assert fk(location) == "visa_free_relocate"


@pytest.mark.parametrize("location", ["Madrid; Remotely in Spain", "Berlin"])
def test_visa_free_relocate_negative(location):
    assert fk(location) != "visa_free_relocate"


@pytest.mark.parametrize(
    "location",
    ["London, United Kingdom", "Manchester", "Edinburgh, Scotland"],
)
def test_visa_required_relocate_positive(location):
    assert fk(location) == "visa_required_relocate"


@pytest.mark.parametrize("location", ["Remote - UK", "London (Remote)"])
def test_visa_required_relocate_negative(location):
    # A visa-required place that is remote-locked collapses to foreign.
    assert fk(location, remote=True) == "foreign"


@pytest.mark.parametrize(
    "location",
    ["Toronto, Canada", "Bangalore, India", "San Francisco, US", "Tokyo, Japan"],
)
def test_foreign_positive(location):
    assert fk(location) == "foreign"


@pytest.mark.parametrize("location", ["Berlin", "Remote - EMEA, Remote - NA"])
def test_foreign_negative(location):
    assert fk(location) != "foreign"


@pytest.mark.parametrize("location", [None, "", "   ", "Springfield", "Atlantis"])
def test_unknown_positive(location):
    assert fk(location) == "unknown"


@pytest.mark.parametrize(
    ("location", "remote"),
    [("Remote", True), ("Munich, Germany", False)],
)
def test_unknown_negative(location, remote):
    assert fk(location, remote=remote) != "unknown"


def test_unknown_is_eligible_never_buried():
    # Geo-gate rule: absence of geo data must never bury a gem.
    assert "unknown" in ELIGIBLE_CLASSES
    assert fk("Springfield") in ELIGIBLE_CLASSES


# ---------------------------------------------------------------------------
# Contract rule 1: title region-tokens bind first (both directions).
# ---------------------------------------------------------------------------


def test_title_foreign_binds_over_eligible_office():
    # ", Korea" names the served market even with a Berlin office.
    assert fk("Berlin, Germany", title="Account Executive, Korea") == "foreign"


def test_title_amer_alone_forecloses():
    assert fk("Remote", title="Product Manager (AMER)", remote=True) == "foreign"


def test_title_eligible_token_alongside_foreign_rescues():
    # "(EMEA/AMER)" is a multi-region posting open to home.
    verdict = fk("Remote", title="Sales Lead (EMEA/AMER)", remote=True)
    assert verdict == "eligible_remote"
    assert verdict != "foreign"


def test_title_rescue_never_beats_concrete_foreign_office():
    # A concrete office verdict always wins over the title rescue.
    assert fk("San Francisco, US", title="Engineer (EMEA/AMER)") == "foreign"


def test_title_visa_required_token_remote_collapses_to_foreign():
    assert fk("Remote", title="Solutions Engineer, UK", remote=True) == "foreign"


def test_title_visa_required_token_onsite_stays_maybe():
    assert fk("London office", title="Solutions Engineer, UK", remote=False) == (
        "visa_required_relocate"
    )


# ---------------------------------------------------------------------------
# Contract rule 2: bare "Remote" consults the description first (both
# directions).
# ---------------------------------------------------------------------------


def test_bare_remote_with_foreign_description_drops():
    desc = "We are hiring across Austin, Denver and New York City."
    assert fk("Remote", description=desc) == "foreign"


def test_bare_remote_with_foreign_description_ignores_remote_flag():
    # The remote flag must not skip the description consult.
    desc = "Our teams sit in Texas and Florida."
    assert fk("Remote", remote=True, description=desc) == "foreign"


def test_bare_remote_with_home_description_keeps():
    assert fk("Remote", description="Join our Berlin engineering hub.") == "home_relocate"


def test_bare_remote_with_commute_belt_description_is_local():
    assert fk("Remote", description="Our office is in Frankfurt.") == "home_local"


def test_bare_remote_with_mixed_description_keeps_home():
    # Foreign AND home tokens in the description: home wins.
    desc = "Offices in New York and Berlin."
    assert fk("Remote", description=desc) == "home_relocate"


def test_bare_remote_with_no_description_defaults_eligible():
    assert fk("Remote", remote=True, description="") == "eligible_remote"
    assert fk("Remote", remote=False, description="") == "eligible_remote"


def test_bare_remote_with_geo_free_description_defaults_eligible():
    desc = "We build collaborative software for distributed teams."
    assert fk("Remote", remote=True, description=desc) == "eligible_remote"


def test_description_truncated_at_2500_chars():
    # A foreign token past the 2500-char consult window is not seen.
    desc = ("word " * 600) + "texas"
    assert len(desc) > 2500
    assert fk("Remote", description=desc) == "eligible_remote"


# ---------------------------------------------------------------------------
# Config swing: same input, different profile, different (correct) class.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("location", "frankfurt_verdict", "us_verdict"),
    [
        # NOTE: "Frankfurt am Main, Germany" (not the bare city-comma-country
        # form) to keep the AC7 pre-push scrub literal clean; same classes.
        ("Frankfurt am Main, Germany", "home_local", "foreign"),
        ("San Francisco, CA", "foreign", "home_local"),
        ("Berlin, Deutschland", "home_relocate", "foreign"),
        ("Remote - EMEA", "eligible_remote", "foreign"),
        ("Remote - Americas", "foreign", "eligible_remote"),
        ("Toronto, Canada", "foreign", "visa_free_relocate"),
    ],
)
def test_config_swing(location, frankfurt_verdict, us_verdict):
    assert fk(location) == frankfurt_verdict
    assert us(location) == us_verdict
    assert fk(location) != us(location)


def test_no_home_region_hardcoded_in_engine():
    # The same posting yields different, correct classes under each profile —
    # proof no home region is baked into the engine itself.
    assert fk("San Francisco, CA") == "foreign"
    assert us("San Francisco, CA") == "home_local"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_none_location_no_signal():
    assert fk(None) == "unknown"
    assert fk(None, remote=True) == "eligible_remote"


def test_empty_location_no_signal():
    assert fk("") == "unknown"
    assert fk("", remote=True) == "eligible_remote"


def test_offices_override_lying_location():
    # The Pennylane rescue: authoritative offices beat the location string.
    assert fk("All France (remote)", offices=["Germany (remote)"], remote=True) == ("home_relocate")


def test_offices_with_junk_entries_are_skipped():
    verdict = fk("Paris, France", offices=[None, "", "   ", "Berlin, Deutschland"])
    assert verdict == "home_relocate"


def test_all_junk_offices_fall_back_to_location():
    assert fk("Berlin", offices=[None, "", "   "]) == "home_relocate"


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("München", "home_relocate"),
        ("Munchen", "home_relocate"),
        ("Düsseldorf", "home_relocate"),
        ("Dusseldorf", "home_relocate"),
        ("Würzburg, Deutschland", "home_local"),
        ("Wurzburg, Deutschland", "home_local"),
        ("Gießen, Deutschland", "home_local"),
        ("Giessen, Deutschland", "home_local"),
        # ASCII transliteration "ue" is OUTSIDE the measured vocabulary:
        # "Muenchen" alone carries no recognized token (documented boundary).
        ("Muenchen", "unknown"),
        # ...but a country token still rescues the transliterated city.
        ("Muenchen, Deutschland", "home_relocate"),
    ],
)
def test_umlaut_variants(location, expected):
    assert fk(location) == expected
