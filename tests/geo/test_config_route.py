"""Regression tests for the CONFIG route (``GeoProfile.from_home_tokens``).

``tests/geo/test_classifier.py`` covers the PRESET route (curated pattern
strings). This module covers the route the shipped ``config/geo.yaml`` actually
drives — user home tokens in, compiled profile out — which is the path
``tools/job_scorer.geo_eligibility`` uses in production.

The distinction matters: the two routes build their vocabularies completely
differently, so a preset-only suite can be green while the config route admits
ineligible roles or buries the user's home market. Every case below pins a
verdict that regressed once and must not regress again (G-1474 review
BL-01/BL-02/BL-04, WR-06).
"""

from __future__ import annotations

import pytest

from career_os.services.geo.classifier import geo_eligibility
from career_os.services.geo.profile import GeoProfile

# Country-level home configs — the likeliest thing a user writes, and the shape
# that broke: a country token with no city list.
DE = GeoProfile.from_home_tokens("de", ["germany"])
PL = GeoProfile.from_home_tokens("pl", ["poland", "polska", "warszawa", "krakow"])
IE = GeoProfile.from_home_tokens("ie", ["ireland", "dublin", "cork", "galway", "limerick"])
IE_NO_PAN = GeoProfile.from_home_tokens(
    "ie-strict",
    ["ireland", "dublin", "cork"],
    allow_pan_region_remote=False,
)


# ---------------------------------------------------------------------------
# BL-01: a home token ALWAYS wins (the documented config contract)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "location",
    [
        "Berlin, Germany",
        "Munich, Germany",
        "Hamburg, Germany",
        "Frankfurt am Main, Germany",
        # Not in the public geography list — was already correct, pinned so the
        # fix cannot regress into "only listed cities work".
        "Leipzig, Germany",
    ],
)
def test_home_country_cities_are_home_under_a_country_level_config(location):
    # Every one of these also carries a PUBLIC_GEOGRAPHY_TOKENS entry. Token
    # subtraction alone cannot know Berlin is IN Germany, so without home_wins
    # the user's entire home market classifies foreign.
    assert geo_eligibility(location, profile=DE) == "home_local"


def test_english_vs_local_spelling_still_resolves_home():
    # The user wrote "warszawa"; the public list carries "warsaw". Both must be
    # home — an inconsistent split (Krakow kept, Warsaw dropped) looks like
    # noise rather than a bug.
    assert geo_eligibility("Warsaw, Poland", profile=PL) == "home_local"
    assert geo_eligibility("Krakow, Poland", profile=PL) == "home_local"


def test_home_wins_is_the_config_route_only():
    # Presets keep home_wins False: their vocabularies are curated and
    # non-overlapping, so a foreign token there is a deliberate veto.
    from career_os.services.geo.presets import FRANKFURT_PROFILE

    assert FRANKFURT_PROFILE.home_wins is False
    assert DE.home_wins is True


def test_foreign_country_is_still_foreign_under_a_home_config():
    # home_wins must not make everything home.
    assert geo_eligibility("Paris, France", profile=DE) == "foreign"
    assert geo_eligibility("Tokyo, Japan", profile=IE) == "foreign"


# ---------------------------------------------------------------------------
# BL-02: short foreign signals the plain token list cannot express
# ---------------------------------------------------------------------------

# The nine strings the config route admitted after the port. "Remote - US" is
# one of the most common location strings on Greenhouse/Ashby.
REGRESSED_FOREIGN = [
    "Remote - US",
    "Remote, US",
    "Remote (US)",
    "Remote - UK",
    "Remote - NA",
    "Miami, FL",
    "Dallas, TX",
    "Los Angeles, CA",
    "San Diego",
]


@pytest.mark.parametrize("location", REGRESSED_FOREIGN)
def test_short_and_city_foreign_signals_are_blocked_on_the_config_route(location):
    assert geo_eligibility(location, profile=IE) == "foreign"


def test_location_only_vocabulary_is_never_applied_to_the_description():
    # "us" in prose means "join us". Applying the location-only vocabulary to
    # the 2500-char description window would drop every remote posting whose
    # blurb happens to use the word.
    jd = "We are a fast-growing startup. Join us in building the future of tooling."
    assert geo_eligibility("Remote", description=jd, profile=IE) == "eligible_remote"


def test_location_only_vocabulary_yields_to_the_home_region():
    # A UK-based user must not have their own country made foreign by \buk\b.
    uk = GeoProfile.from_home_tokens("uk", ["uk", "united kingdom", "london"])
    assert uk.foreign_location_only is None or not uk.foreign_location_only.search("uk")
    assert geo_eligibility("Remote - UK", profile=uk) == "home_local"
    assert geo_eligibility("London", profile=uk) == "home_local"


def test_title_binds_the_location_only_vocabulary_too():
    assert geo_eligibility("Remote", title="Account Executive (US)", profile=IE) == "foreign"


# ---------------------------------------------------------------------------
# BL-04: allow_pan_region_remote actually tightens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("location", ["Remote", "Remote - Worldwide", "Fully remote"])
def test_unanchored_remote_is_unknown_when_pan_region_is_off(location):
    # The user set the flag specifically to require a home-region anchor.
    assert geo_eligibility(location, profile=IE_NO_PAN) == "unknown"


def test_remote_flag_alone_is_unknown_when_pan_region_is_off():
    assert geo_eligibility("", remote=True, profile=IE_NO_PAN) == "unknown"


def test_unanchored_remote_is_eligible_when_pan_region_is_on():
    assert geo_eligibility("Remote", profile=IE) == "eligible_remote"
    assert geo_eligibility("", remote=True, profile=IE) == "eligible_remote"


def test_pan_region_off_never_buries_an_explicit_home_anchor():
    # Tightening the remote default must not touch home classification.
    assert geo_eligibility("Remote - Dublin", profile=IE_NO_PAN) == "home_local"


@pytest.mark.parametrize(
    "location",
    ["EMEA", "Europe", "European", "DACH", "Benelux", "Nordics", "EU-wide", "EU wide"],
)
def test_multi_country_region_tokens_are_eligible_remote(location):
    # Bare region names, no "remote" anywhere in the string: these must be
    # positively recognized, not fall through to the bare-remote default.
    assert geo_eligibility(location, profile=IE) == "eligible_remote"


@pytest.mark.parametrize("location", ["EMEA", "DACH", "Nordics"])
def test_multi_country_region_tokens_are_suppressed_when_pan_region_is_off(location):
    assert geo_eligibility(location, profile=IE_NO_PAN) == "unknown"


@pytest.mark.parametrize(
    "location",
    [
        "Remote EMEA/US",
        "Remote (EMEA, US)",
        "Remote - EMEA or US",
        "Europe or US",
        "Remote, EMEA/AMER",
        "EMEA / North America",
        "Remote - Europe, US & Canada",
    ],
)
def test_multi_region_rescue_survives_a_foreign_token(location):
    # BL-05 regression (contract rule 1): a posting that names an eligible
    # region alongside a foreign one is rescued, not buried. Requires
    # from_home_tokens to wire eligible_region to the pan-region vocabulary —
    # with eligible_region=None the foreign token alone decided the verdict.
    assert geo_eligibility(location, profile=IE) == "eligible_remote"


def test_multi_region_rescue_is_off_with_pan_region_disabled():
    # With the pan-region vocabulary disabled there is nothing eligible to
    # rescue on: the explicit foreign token dominates.
    assert geo_eligibility("Remote EMEA/US", profile=IE_NO_PAN) == "foreign"


def test_presets_keep_unspecified_remote_eligible():
    from career_os.services.geo.presets import FRANKFURT_PROFILE, US_REMOTE_PROFILE

    assert FRANKFURT_PROFILE.allow_unspecified_remote is True
    assert US_REMOTE_PROFILE.allow_unspecified_remote is True


# ---------------------------------------------------------------------------
# WR-06 / NT-05: token boundary handling
# ---------------------------------------------------------------------------


def test_extra_foreign_token_ending_in_punctuation_matches():
    # A trailing \b after "." demands a word character follow, so "u.s." could
    # never match at end-of-string. The user's explicit "always drop this
    # place" instruction was silently discarded.
    p = GeoProfile.from_home_tokens("t", ["ireland"], extra_foreign_tokens=["u.s."])
    assert geo_eligibility("Based in u.s.", profile=p) == "foreign"
    assert geo_eligibility("u.s. remote", profile=p) == "foreign"


def test_extra_foreign_token_still_respects_word_boundaries():
    p = GeoProfile.from_home_tokens("t", ["ireland"], extra_foreign_tokens=["ing"])
    # "ing" must not match inside "Consulting".
    assert geo_eligibility("Consulting GmbH", profile=p) == "unknown"
    assert geo_eligibility("ing, somewhere", profile=p) == "foreign"


def test_punctuation_only_tokens_are_dropped_not_matched():
    # Unfenced, "-" would match every hyphen and classify the whole corpus
    # foreign off one stray config entry.
    p = GeoProfile.from_home_tokens("t", ["ireland"], extra_foreign_tokens=["-", "  ", "!"])
    assert geo_eligibility("Somewhere-ville", profile=p) == "unknown"


def test_hostile_tokens_cannot_inject_regex():
    p = GeoProfile.from_home_tokens("t", ["ireland"], extra_foreign_tokens=["a(b", "x[y"])
    # Compiles at all (re.escape) and matches literally, not as a group.
    assert geo_eligibility("team a(b office", profile=p) == "foreign"
    assert geo_eligibility("team ab office", profile=p) == "unknown"


# ---------------------------------------------------------------------------
# NT-06: offices type handling
# ---------------------------------------------------------------------------


def test_offices_passed_as_a_bare_string_is_one_office():
    # Iterating a str yields single characters, silently losing the signal.
    assert geo_eligibility("Dublin", offices="Paris, France", profile=IE) == "foreign"


def test_offices_list_still_wins_over_location():
    assert geo_eligibility("Paris, France", offices=["Dublin, Ireland"], profile=IE) == "home_local"
