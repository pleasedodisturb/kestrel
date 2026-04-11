"""Tests for `career_os.api.profiles` — profile CRUD HTTP layer.

Complementary to `tests/test_profiles_crud.py`. Covers edge cases:
- partial PATCH preserves untouched fields
- 404 on unknown profile
- 422 on missing required fields
- dream_companies JSON encode/decode round trip
- delete returns 204 and removes from listing
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app


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
# POST /api/profiles
# ---------------------------------------------------------------------------


def test_create_profile_minimal(client: TestClient):
    resp = client.post("/api/profiles", json={"name": "Solo"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Solo"
    assert body["id"] is not None


def test_create_profile_full(client: TestClient):
    resp = client.post(
        "/api/profiles",
        json={
            "name": "Full",
            "email": "full@example.com",
            "location": "Berlin",
            "job_family": "Product",
            "dream_companies": ["Mistral", "Linear"],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["dream_companies"] == ["Mistral", "Linear"]


def test_create_profile_missing_name_returns_422(client: TestClient):
    resp = client.post("/api/profiles", json={"email": "x@x.com"})
    assert resp.status_code == 422


def test_create_profile_empty_name_returns_422(client: TestClient):
    resp = client.post("/api/profiles", json={"name": ""})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/profiles
# ---------------------------------------------------------------------------


def test_list_profiles_empty(client: TestClient):
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["profiles"] == []


def test_list_profiles_returns_seeded(client: TestClient):
    client.post("/api/profiles", json={"name": "A"})
    client.post("/api/profiles", json={"name": "B"})

    resp = client.get("/api/profiles")
    body = resp.json()
    assert body["count"] == 2
    names = {p["name"] for p in body["profiles"]}
    assert names == {"A", "B"}


# ---------------------------------------------------------------------------
# GET /api/profiles/{id}
# ---------------------------------------------------------------------------


def test_get_profile_200(client: TestClient):
    create = client.post("/api/profiles", json={"name": "X", "email": "x@x.com"})
    pid = create.json()["id"]

    resp = client.get(f"/api/profiles/{pid}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "x@x.com"


def test_get_profile_unknown_id_returns_404(client: TestClient):
    resp = client.get("/api/profiles/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/profiles/{id}
# ---------------------------------------------------------------------------


def test_patch_profile_partial_update_preserves_other_fields(client: TestClient):
    create = client.post(
        "/api/profiles",
        json={
            "name": "Original",
            "email": "o@o.com",
            "location": "Frankfurt",
            "job_family": "Engineering",
        },
    )
    pid = create.json()["id"]

    # Update only the name
    resp = client.patch(f"/api/profiles/{pid}", json={"name": "Renamed"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["email"] == "o@o.com"
    assert body["location"] == "Frankfurt"
    assert body["job_family"] == "Engineering"


def test_patch_profile_dream_companies_round_trip(client: TestClient):
    create = client.post("/api/profiles", json={"name": "X"})
    pid = create.json()["id"]

    resp = client.patch(
        f"/api/profiles/{pid}",
        json={"dream_companies": ["Mistral", "Anthropic"]},
    )
    assert resp.status_code == 200
    assert resp.json()["dream_companies"] == ["Mistral", "Anthropic"]


def test_patch_profile_unknown_id_returns_404(client: TestClient):
    resp = client.patch("/api/profiles/9999", json={"name": "X"})
    assert resp.status_code == 404


def test_patch_profile_empty_payload_is_noop(client: TestClient):
    create = client.post("/api/profiles", json={"name": "Same"})
    pid = create.json()["id"]

    resp = client.patch(f"/api/profiles/{pid}", json={})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Same"


# ---------------------------------------------------------------------------
# DELETE /api/profiles/{id}
# ---------------------------------------------------------------------------


def test_delete_profile_204(client: TestClient):
    create = client.post("/api/profiles", json={"name": "Doomed"})
    pid = create.json()["id"]

    resp = client.delete(f"/api/profiles/{pid}")
    assert resp.status_code == 204

    # No longer in listing
    listing = client.get("/api/profiles").json()
    assert all(p["id"] != pid for p in listing["profiles"])


def test_delete_profile_unknown_id_returns_404(client: TestClient):
    resp = client.delete("/api/profiles/9999")
    assert resp.status_code == 404
