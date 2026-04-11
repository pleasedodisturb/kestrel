"""Tests for `career_os.api.applications` — application CRUD HTTP layer.

These exercise the FastAPI router directly with a real in-memory database.
The Service layer is well-covered elsewhere; this file targets HTTP-level
behavior: status codes, request/response shape, status transition 422s.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Profile


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

    session.add(Profile(id=1, name="P", email="p@p.com"))
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


def _create(client: TestClient, **overrides) -> dict:
    payload = {
        "profile_id": 1,
        "company": "Acme",
        "role": "Senior PM",
    }
    payload.update(overrides)
    resp = client.post("/api/applications", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/applications
# ---------------------------------------------------------------------------


def test_create_application_201(client: TestClient):
    body = _create(client)
    assert body["id"] is not None
    assert body["company"] == "Acme"
    assert body["role"] == "Senior PM"
    assert body["status"] == "discovered"


def test_create_application_unknown_profile_returns_404(client: TestClient):
    resp = client.post(
        "/api/applications",
        json={"profile_id": 999, "company": "X", "role": "Y"},
    )
    assert resp.status_code == 404


def test_create_application_missing_required_fields_returns_422(client: TestClient):
    resp = client.post(
        "/api/applications",
        json={"profile_id": 1},  # missing company and role
    )
    assert resp.status_code == 422


def test_create_application_with_optional_fields(client: TestClient):
    body = _create(
        client,
        url="https://acme.example/jobs/1",
        salary_range="100k-120k EUR",
        notes="initial",
        fit_score=8.5,
    )
    assert body["url"] == "https://acme.example/jobs/1"
    assert body["salary_range"] == "100k-120k EUR"
    assert body["notes"] == "initial"
    assert body["fit_score"] == 8.5


# ---------------------------------------------------------------------------
# GET /api/applications
# ---------------------------------------------------------------------------


def test_list_applications_empty(client: TestClient):
    resp = client.get("/api/applications", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["applications"] == []


def test_list_applications_returns_seeded_apps(client: TestClient):
    _create(client, company="A")
    _create(client, company="B")
    _create(client, company="C")

    resp = client.get("/api/applications", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert {a["company"] for a in body["applications"]} == {"A", "B", "C"}


def test_list_applications_status_filter(client: TestClient):
    _create(client, company="A")
    b = _create(client, company="B")
    # Move B to interested
    client.patch(
        f"/api/applications/{b['id']}",
        params={"profile_id": 1},
        json={"status": "interested"},
    )

    resp = client.get(
        "/api/applications",
        params={"profile_id": 1, "status": "interested"},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["applications"][0]["company"] == "B"


# ---------------------------------------------------------------------------
# GET /api/applications/{id}
# ---------------------------------------------------------------------------


def test_get_application_detail_200(client: TestClient):
    created = _create(client, company="Mistral")
    resp = client.get(
        f"/api/applications/{created['id']}",
        params={"profile_id": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["company"] == "Mistral"
    assert "activity_log" in body
    assert "follow_ups" in body


def test_get_application_detail_unknown_id_404(client: TestClient):
    resp = client.get("/api/applications/9999", params={"profile_id": 1})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/applications/{id}
# ---------------------------------------------------------------------------


def test_patch_application_valid_status_transition(client: TestClient):
    created = _create(client)
    resp = client.patch(
        f"/api/applications/{created['id']}",
        params={"profile_id": 1},
        json={"status": "interested"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "interested"


def test_patch_application_invalid_status_transition_returns_422(client: TestClient):
    """discovered → offer is not a valid forward transition."""
    created = _create(client)
    resp = client.patch(
        f"/api/applications/{created['id']}",
        params={"profile_id": 1},
        json={"status": "offer"},
    )
    assert resp.status_code == 422
    assert "Invalid status transition" in resp.json()["detail"]


def test_patch_application_unknown_id_returns_404(client: TestClient):
    resp = client.patch(
        "/api/applications/9999",
        params={"profile_id": 1},
        json={"notes": "x"},
    )
    assert resp.status_code == 404


def test_patch_application_partial_update_preserves_other_fields(client: TestClient):
    created = _create(client, notes="original")
    resp = client.patch(
        f"/api/applications/{created['id']}",
        params={"profile_id": 1},
        json={"contact": "Jane Doe"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["contact"] == "Jane Doe"
    assert body["notes"] == "original"


# ---------------------------------------------------------------------------
# DELETE /api/applications/{id}
# ---------------------------------------------------------------------------


def test_delete_application_archives(client: TestClient):
    created = _create(client)
    resp = client.delete(
        f"/api/applications/{created['id']}",
        params={"profile_id": 1},
    )
    assert resp.status_code == 200

    # No longer listed (excluded by archived_at)
    listing = client.get("/api/applications", params={"profile_id": 1})
    assert listing.json()["total"] == 0


def test_delete_application_unknown_id_returns_404(client: TestClient):
    resp = client.delete("/api/applications/9999", params={"profile_id": 1})
    assert resp.status_code == 404
