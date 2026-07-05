"""Tests for the geo-eligibility gate in tools/batch_probe.py.

Encodes the eligibility rule for a HOME-based applicant:
  eligible <=> onsite/hybrid in the home region OR remote open to the home region
  drop      <=> foreign onsite OR country-locked foreign remote

The home region is parameterized (loaded from config). These tests pin an
explicit home region (a set of home cities) via an autouse fixture so the
classification logic is verified independently of whatever the shipped
config/geo.example.yaml happens to contain.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import batch_probe  # noqa: E402
from batch_probe import (  # noqa: E402
    GeoConfig,
    _ashby_candidates_from_posting,
    _classify_token,
    geo_classify,
    geo_ok,
    parse_ashby_url,
    parse_greenhouse_url,
)

# Explicit test home region: a set of home cities + the country name.
_TEST_HOME = GeoConfig(
    home_tokens=(
        "germany",
        "deutschland",
        "frankfurt",
        "berlin",
        "munich",
        "münchen",
        "muenchen",
        "hamburg",
        "cologne",
        "köln",
        "stuttgart",
        "düsseldorf",
        "dusseldorf",
    ),
    allow_pan_region_remote=True,
    extra_foreign_tokens=(),
)


@pytest.fixture(autouse=True)
def _pin_home_region(monkeypatch):
    """Pin a deterministic home region for every test in this module."""
    monkeypatch.setattr(batch_probe, "_CONFIG", _TEST_HOME)


# --- verdict token is "home" (renamed from the old "de") -------------------


def test_classify_token_home_verdict():
    assert _classify_token("Munich, Germany") == "home"
    assert _classify_token("Remote - EMEA") == "eu_remote"
    assert _classify_token("Paris, France") == "foreign"
    assert _classify_token("Somewhereville") == "unknown"


# --- core eligibility rule (required by task) ------------------------------


def test_munich_onsite_keep():
    assert geo_classify("Munich, Germany") == "home"


def test_frankfurt_keep():
    assert geo_classify("Frankfurt") == "home"


def test_foreign_office_overrides_home_list_drop():
    # Failure #2a: list string lied "Berlin, Germany; Munich" but the REAL
    # office is Paris. With authoritative offices the home string is ignored.
    assert (
        geo_classify("Berlin, Germany; Munich", offices=["Paris, France"], is_remote=False) is None
    )


def test_remote_sweden_drop():
    # Failure #2b: country-locked remote to a foreign country.
    assert (
        geo_classify(
            "Finland; Remote - Denmark; Stockholm, Sweden",
            offices=["Remote - Sweden"],
        )
        is None
    )


def test_remote_emea_keep():
    assert geo_classify("Remote - EMEA") == "eligible_remote"


def test_remote_us_drop():
    # Failure #1: is_remote must NOT rescue a foreign-located role.
    assert geo_classify("San Francisco, US", is_remote=True) is None
    assert geo_classify("Remote - US", is_remote=True) is None


def test_bare_remote_keep():
    assert geo_classify("Remote", is_remote=True) == "eligible_remote"


# --- additional rule coverage ----------------------------------------------


def test_remote_home_country_keep():
    assert geo_classify("Germany (Remote)") == "home"


def test_remote_europe_keep():
    assert geo_classify("Remote - Europe") == "eligible_remote"


def test_remote_eu_wide_keep():
    assert geo_classify("Remote (EU)") == "eligible_remote"


def test_global_remote_keep():
    assert geo_classify("Remote - Global") == "eligible_remote"


def test_emea_plus_na_keep():
    # "Remote - EMEA, Remote - NA" -> EMEA present => eligible.
    assert geo_classify("Remote - EMEA, Remote - NA") == "eligible_remote"


def test_foreign_locked_remote_drop():
    assert geo_classify("Madrid; Remotely in Spain", is_remote=True) is None


def test_us_not_matching_austria():
    # Word-boundary guard: "Austria" must NOT trigger the \bus\b foreign rule
    # (Austria is foreign anyway, but for the right reason).
    assert geo_classify("Vienna, Austria") is None  # foreign, not via \bus\b


def test_home_wins_over_foreign_in_multilist():
    # A home-anchored role that also offers a foreign office is still eligible.
    assert geo_classify("Berlin", offices=["Berlin, Germany", "Paris, France"]) == "home"


def test_is_remote_never_rescues_foreign_office():
    assert geo_classify("Paris", offices=["Paris, France"], is_remote=True) is None


def test_pan_region_remote_can_be_disabled():
    # With allow_pan_region_remote=False an EMEA-only role is no longer eligible.
    strict = GeoConfig(home_tokens=_TEST_HOME.home_tokens, allow_pan_region_remote=False)
    original = batch_probe._CONFIG
    batch_probe._CONFIG = strict
    try:
        assert geo_classify("Remote - EMEA") is None
        assert geo_classify("Munich, Germany") == "home"
    finally:
        batch_probe._CONFIG = original


def test_extra_foreign_tokens_drop():
    # A home token still wins, but an extra_foreign_tokens entry drops.
    cfg = GeoConfig(
        home_tokens=_TEST_HOME.home_tokens,
        extra_foreign_tokens=("atlantis",),
    )
    original = batch_probe._CONFIG
    batch_probe._CONFIG = cfg
    try:
        assert geo_classify("Atlantis City") is None
    finally:
        batch_probe._CONFIG = original


def test_geo_ok_wrapper():
    assert geo_ok("Munich, Germany") is True
    assert geo_ok("Remote - Sweden") is False


# --- Ashby candidate extraction (secondaryLocations rescue, bare-remote) ----


def test_ashby_secondary_home_rescues_foreign_primary():
    # primary "All France (remote)" but a secondary is a home-region remote
    # => eligible.
    posting = {
        "location": "All France (remote)",
        "address": {"postalAddress": {"addressCountry": "France", "addressLocality": "Paris"}},
        "secondaryLocations": [
            {
                "location": "Germany (remote)",
                "address": {"postalAddress": {"addressCountry": "Germany"}},
            },
            {
                "location": "Spain (remote)",
                "address": {"postalAddress": {"addressCountry": "Spain"}},
            },
        ],
        "isRemote": True,
    }
    candidates, primary, is_remote = _ashby_candidates_from_posting(posting)
    assert geo_classify(primary, offices=candidates, is_remote=is_remote) == "home"


def test_ashby_bare_remote_with_foreign_hq_keep():
    # Bare "Remote", HQ address country foreign, no secondaries. The foreign HQ
    # address must NOT be treated as a restriction.
    posting = {
        "location": "Remote",
        "address": {"postalAddress": {"addressCountry": "USA"}},
        "secondaryLocations": [],
        "isRemote": True,
    }
    candidates, primary, is_remote = _ashby_candidates_from_posting(posting)
    assert geo_classify(primary, offices=candidates, is_remote=is_remote) == "eligible_remote"


def test_ashby_home_city_keep():
    posting = {
        "location": "Berlin",
        "address": {"postalAddress": {"addressCountry": "Germany", "addressLocality": "Berlin"}},
        "secondaryLocations": [],
    }
    candidates, primary, is_remote = _ashby_candidates_from_posting(posting)
    assert geo_classify(primary, offices=candidates, is_remote=is_remote) == "home"


# --- URL parsing ------------------------------------------------------------


def test_parse_greenhouse_standard_url():
    assert parse_greenhouse_url("https://job-boards.greenhouse.io/exampleco/jobs/5135407007") == (
        "exampleco",
        "5135407007",
    )


def test_parse_greenhouse_eu_url():
    assert parse_greenhouse_url(
        "https://job-boards.eu.greenhouse.io/sampleboard/jobs/4905260101"
    ) == ("sampleboard", "4905260101")


def test_parse_greenhouse_vendor_url():
    # Uses the fictional vendor slug shipped in _GH_VENDOR_SLUGS.
    assert parse_greenhouse_url(
        "https://example-vendor.com/careers/open-positions/job?gh_jid=8611600002"
    ) == ("examplevendor", "8611600002")


def test_parse_ashby_url():
    assert parse_ashby_url(
        "https://jobs.ashbyhq.com/exampleco/11d442eb-444f-4c63-bbaf-ef76660ca28e/application"
    ) == ("exampleco", "11d442eb-444f-4c63-bbaf-ef76660ca28e")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
