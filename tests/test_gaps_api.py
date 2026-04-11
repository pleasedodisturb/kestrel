"""Tests for `career_os.api.gaps` — gap analysis HTTP layer.

Complementary to `tests/test_gap_analysis.py` (which tests the underlying
service functions). These tests target the FastAPI route layer to confirm
status codes, response shapes, and error mappings.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from career_os.models.models import Application, Profile
from career_os.services.gap_analysis import (
    ApplicationNotFoundError,
    MissingRequirementsError,
    ProfileNotFoundError,
)


# Seed a profile + application used by every test in this module. Relies on
# the shared `db_session` fixture from conftest.py (which overrides get_db).
@pytest.fixture(autouse=True)
def _seed_profile_and_app(db_session):
    db_session.add(Profile(id=1, name="P", email="p@p.com"))
    db_session.commit()
    db_session.add(
        Application(
            id=10,
            profile_id=1,
            company="Acme",
            role="Senior PM",
            status="discovered",
        )
    )
    db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# GET /api/applications/{id}/gaps
# ---------------------------------------------------------------------------


def test_get_application_gaps_happy_path(client: TestClient):
    fake = {
        "application_id": 10,
        "company": "Acme",
        "role": "Senior PM",
        "gaps": [
            {
                "skill_name": "Roadmapping",
                "required_level": "advanced",
                "current_level": "beginner",
                "severity": "critical",
                "distance": 2,
            }
        ],
        "readiness_score": 60.0,
        "total_requirements": 3,
        "gaps_count": 1,
    }
    with patch("career_os.api.gaps.analyze_gaps", return_value=fake):
        resp = client.get(
            "/api/applications/10/gaps",
            params={"profile_id": 1},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["application_id"] == 10
    assert body["readiness_score"] == pytest.approx(60.0)
    assert body["gaps"][0]["skill_name"] == "Roadmapping"
    assert body["gaps_count"] == 1


def test_get_application_gaps_application_not_found(client: TestClient):
    with patch(
        "career_os.api.gaps.analyze_gaps",
        side_effect=ApplicationNotFoundError("missing"),
    ):
        resp = client.get(
            "/api/applications/9999/gaps",
            params={"profile_id": 1},
        )
    assert resp.status_code == 404


def test_get_application_gaps_missing_requirements_returns_400(client: TestClient):
    with patch(
        "career_os.api.gaps.analyze_gaps",
        side_effect=MissingRequirementsError("no reqs parsed"),
    ):
        resp = client.get(
            "/api/applications/10/gaps",
            params={"profile_id": 1},
        )
    assert resp.status_code == 400
    assert "no reqs" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/gaps/aggregate
# ---------------------------------------------------------------------------


def test_aggregate_gaps_happy_path(client: TestClient):
    fake = {
        "gaps": [
            {
                "skill_name": "Roadmapping",
                "frequency": 3,
                "application_ids": [1, 2, 3],
                "avg_severity": "critical",
                "avg_distance": 1.7,
            }
        ],
        "total_applications_analyzed": 5,
    }
    with patch("career_os.api.gaps.aggregate_gaps", return_value=fake):
        resp = client.get("/api/gaps/aggregate", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_applications_analyzed"] == 5
    assert body["gaps"][0]["frequency"] == 3
    assert body["gaps"][0]["avg_severity"] == "critical"


def test_aggregate_gaps_empty(client: TestClient):
    with patch(
        "career_os.api.gaps.aggregate_gaps",
        return_value={"gaps": [], "total_applications_analyzed": 0},
    ):
        resp = client.get("/api/gaps/aggregate", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["gaps"] == []


def test_aggregate_gaps_profile_not_found(client: TestClient):
    with patch(
        "career_os.api.gaps.aggregate_gaps",
        side_effect=ProfileNotFoundError("nope"),
    ):
        resp = client.get("/api/gaps/aggregate", params={"profile_id": 999})
    assert resp.status_code == 404
