"""Tests for the additive geo-eligibility + API-submittable helpers in
tools/job_scorer.py (PR A slice).

geo_eligibility delegates to the parameterized batch_probe gate; is_api_submittable
gates on a validated https ATS host. The home region is pinned to a deterministic
set here so the geo assertions don't depend on the shipped config/geo.example.yaml.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import batch_probe  # noqa: E402
import job_scorer  # noqa: E402
from batch_probe import GeoConfig  # noqa: E402


@pytest.fixture(autouse=True)
def _pin_home_region(monkeypatch):
    monkeypatch.setattr(
        batch_probe,
        "_CONFIG",
        GeoConfig(home_tokens=("germany", "berlin", "munich", "frankfurt")),
    )


# --- geo_eligibility (4-way) ----------------------------------------------


def test_geo_eligibility_home():
    assert job_scorer.geo_eligibility("Munich, Germany") == "home"


def test_geo_eligibility_eligible_remote():
    assert job_scorer.geo_eligibility("Remote - EMEA") == "eligible_remote"


def test_geo_eligibility_foreign():
    assert job_scorer.geo_eligibility("Paris, France") == "foreign"


def test_geo_eligibility_unknown():
    assert job_scorer.geo_eligibility("Somewhereville") == "unknown"


def test_geo_eligibility_offices_override_list():
    assert job_scorer.geo_eligibility("Berlin, Germany", offices=["Paris, France"]) == "foreign"


def test_geo_eligibility_remote_flag_only():
    assert job_scorer.geo_eligibility("", remote=True) == "eligible_remote"
    assert job_scorer.geo_eligibility("", remote=False) == "unknown"


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
