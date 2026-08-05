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
    assert job_scorer.geo_eligibility("Remote - EMEA") == "eligible_remote"


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
