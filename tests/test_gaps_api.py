"""Tests for `career_os.api.gaps` — gap analysis HTTP layer.

Complementary to `tests/test_gap_analysis.py` (which tests the underlying
service functions). These tests target the FastAPI route layer to confirm
status codes, response shapes, and error mappings.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile
from career_os.services.gap_analysis import (
    ApplicationNotFoundError,
    MissingRequirementsError,
    ProfileNotFoundError,
)


@pytest.fixture(autouse=True)
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()

    profile = Profile(id=1, name="P", email="p@p.com")
    session.add(profile)
    session.commit()
    application = Application(
        id=10,
        profile_id=1,
        company="Acme",
        role="Senior PM",
        status="discovered",
    )
    session.add(application)
    session.commit()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


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
    assert body["readiness_score"] == 60.0
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
