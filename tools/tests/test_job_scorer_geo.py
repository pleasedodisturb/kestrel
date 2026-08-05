"""Tests for the geo-eligibility + API-submittable helpers in
tools/job_scorer.py.

geo_eligibility delegates to the single geo authority
(career_os.services.geo.classifier) with a profile derived from the
batch_probe geo config; is_api_submittable gates on a validated https ATS
host. The home region is pinned to a deterministic set here (and the memoized
profile cleared) so the geo assertions don't depend on the shipped
config/geo.example.yaml.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import batch_probe  # noqa: E402
import job_scorer  # noqa: E402
from batch_probe import GeoConfig  # noqa: E402

from career_os.services.geo.classifier import ALL_CLASSES  # noqa: E402


@pytest.fixture(autouse=True)
def _pin_home_region(monkeypatch):
    monkeypatch.setattr(
        batch_probe,
        "_CONFIG",
        GeoConfig(home_tokens=("ireland", "dublin", "cork", "galway")),
    )
    # Clear the memoized profile so the delegation rebuilds it from the
    # pinned config above (and never leaks between tests).
    monkeypatch.setattr(job_scorer, "_GEO_PROFILE", None)


# --- geo_eligibility (7-way, delegated to the package engine) --------------


def test_geo_eligibility_home_local():
    # Single flat home vocabulary, no local/country split configured:
    # every home hit counts as local.
    assert job_scorer.geo_eligibility("Cork, Ireland") == "home_local"


def test_geo_eligibility_eligible_remote():
    # Assert the DISCRIMINATING case: bare "EMEA" carries no "remote" token, so
    # it can only pass by being recognized as a multi-country region. Testing
    # "Remote - EMEA" alone proves nothing — it passed identically as
    # "Remote - Antarctica" via the bare-remote fallback.
    assert job_scorer.geo_eligibility("EMEA") == "eligible_remote"
    assert job_scorer.geo_eligibility("Remote - EMEA") == "eligible_remote"
    # ...and the counter-case that shares the "Remote - X" shape.
    assert job_scorer.geo_eligibility("Remote - US") == "foreign"


def test_geo_eligibility_eu_onsite_is_foreign_under_flat_config():
    # The flat token config cannot express a visa-free region, so an EU
    # onsite posting outside the home country lands in the shared foreign
    # vocabulary. The code route (build_profile) can express it.
    assert job_scorer.geo_eligibility("Paris, France") == "foreign"


def test_geo_eligibility_unknown():
    assert job_scorer.geo_eligibility("Somewhereville") == "unknown"


def test_geo_eligibility_offices_override_list():
    assert job_scorer.geo_eligibility("Dublin, Ireland", offices=["Paris, France"]) == "foreign"


def test_geo_eligibility_remote_flag_only():
    assert job_scorer.geo_eligibility("", remote=True) == "eligible_remote"
    assert job_scorer.geo_eligibility("", remote=False) == "unknown"


def test_geo_eligibility_returns_a_public_class():
    for loc in ("Cork, Ireland", "Remote - EMEA", "Paris, France", "Somewhereville", ""):
        assert job_scorer.geo_eligibility(loc) in ALL_CLASSES


def test_geo_eligibility_explicit_profile_bypasses_config():
    from career_os.services.geo.presets import US_REMOTE_PROFILE

    # Under a US profile the same Irish posting needs a work visa.
    verdict = job_scorer.geo_eligibility("Cork, Ireland", profile=US_REMOTE_PROFILE)
    assert verdict == "visa_required_relocate"


def test_geo_profile_is_memoized():
    first = job_scorer._default_geo_profile()
    assert job_scorer._default_geo_profile() is first


def test_profile_is_keyword_only():
    # A positionally-bound profile would be str()-lowered into a no-op match:
    # a silently wrong verdict. Keyword-only turns that into a loud TypeError,
    # and matches the engine's own signature.
    import inspect

    from career_os.services.geo.presets import US_REMOTE_PROFILE

    with pytest.raises(TypeError):
        job_scorer.geo_eligibility("Cork, Ireland", None, False, "", "", US_REMOTE_PROFILE)

    params = inspect.signature(job_scorer.geo_eligibility).parameters
    assert params["profile"].kind is inspect.Parameter.KEYWORD_ONLY


# --- differential vs the gate this replaced (batch_probe.geo_classify) ------
#
# The config route is the PRODUCTION path, and it is the one that regressed
# while the preset-only suite stayed green. This pins it against the behaviour
# it replaced over a fixed corpus: batch_probe returns None to DROP, the engine
# returns "foreign", and the two must agree on every string except the
# divergences enumerated below.

_DIFFERENTIAL_CORPUS = (
    # home
    "Cork, Ireland",
    "Dublin",
    "Dublin, Ireland",
    "Remote - Ireland",
    "Galway",
    # short foreign signals (the BL-02 regression)
    "Remote - US",
    "Remote, US",
    "Remote (US)",
    "Remote - UK",
    "Remote - NA",
    # US cities missing from the ported token list (the BL-02 regression)
    "Miami, FL",
    "Dallas, TX",
    "Los Angeles, CA",
    "San Diego",
    "Houston, TX",
    "Phoenix, AZ",
    "San Jose, CA",
    # foreign, already correct
    "New York, United States",
    "San Francisco, CA",
    "Seattle, WA",
    "Austin, Texas",
    "Paris, France",
    "Madrid, Spain",
    "Tokyo, Japan",
    "Singapore",
    "Tel Aviv, Israel",
    # pan-region (the BL-04 vocabulary)
    "Remote - EMEA",
    "EMEA",
    "Europe",
    "DACH",
    "Benelux",
    "Nordics",
    "EU-wide",
    "Remote - Worldwide",
    "Global",
    "Anywhere",
    "Work from anywhere",
    # unspecified remote
    "Remote",
    "Fully remote",
    # no signal
    "",
    "Somewhereville",
)

# Divergences we intend to keep: (location, remote_flag) -> why.
# Anything NOT listed here must match the old gate exactly; anything listed
# must still diverge, so silently "fixing" one of these also fails the test.
_INTENDED_DIVERGENCES = {
    # The engine's public geography list is far broader than batch_probe's
    # ~30 hand-picked foreign tokens, which carried no European or Latin
    # American entries at all. A remote posting anchored in a named foreign
    # country is now correctly blocked instead of admitted.
    ("Berlin, Germany", True): "broader public geography list",
    ("Mexico City, Mexico", True): "broader public geography list",
    # Core 7-way contract: absence of geo signal must NEVER bury a role.
    # The old gate dropped it; "unknown" is deliberately an eligible class.
    ("", False): "unknown is deliberately not buried",
    ("Somewhereville", False): "unknown is deliberately not buried",
    ("Unknown City", False): "unknown is deliberately not buried",
}


@pytest.mark.parametrize("location", _DIFFERENTIAL_CORPUS)
@pytest.mark.parametrize("remote", [False, True], ids=["onsite", "remote"])
def test_config_route_matches_the_gate_it_replaced(location, remote):
    old_drops = batch_probe.geo_classify(location, None, remote) is None
    new_drops = job_scorer.geo_eligibility(location, None, remote) == "foreign"

    if (location, remote) in _INTENDED_DIVERGENCES:
        assert old_drops != new_drops, (
            f"{location!r} (remote={remote}) no longer diverges — remove it from "
            f"_INTENDED_DIVERGENCES: {_INTENDED_DIVERGENCES[location, remote]}"
        )
    else:
        assert old_drops == new_drops, (
            f"{location!r} (remote={remote}): old gate "
            f"{'DROPPED' if old_drops else 'KEPT'}, engine "
            f"{'DROPPED' if new_drops else 'KEPT'} — an unintended behaviour change"
        )


def test_differential_corpus_covers_the_regressed_strings():
    # Guards the guard: the nine strings that regressed must stay in the corpus.
    regressed = {
        "Remote - US",
        "Remote, US",
        "Remote (US)",
        "Remote - UK",
        "Remote - NA",
        "Miami, FL",
        "Dallas, TX",
        "Los Angeles, CA",
        "San Diego",
    }
    assert regressed <= set(_DIFFERENTIAL_CORPUS)


# --- is_api_submittable ----------------------------------------------------


def test_api_submittable_greenhouse_host():
    job = {"source": "greenhouse", "url": "https://job-boards.greenhouse.io/exampleco/jobs/123"}
    assert job_scorer.is_api_submittable(job) is True


def test_api_submittable_ashby_host_no_source():
    job = {"url": "https://jobs.ashbyhq.com/exampleco/uuid"}
    assert job_scorer.is_api_submittable(job) is True


def test_not_submittable_non_ats_host():
    job = {"source": "greenhouse", "url": "https://careers.example.com/job/123"}
    assert job_scorer.is_api_submittable(job) is False


def test_not_submittable_http_scheme():
    # Non-https must not qualify even on an ATS host.
    job = {"source": "lever", "url": "http://jobs.lever.co/exampleco/123"}
    assert job_scorer.is_api_submittable(job) is False


def test_not_submittable_missing_url():
    assert job_scorer.is_api_submittable({"source": "greenhouse"}) is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
