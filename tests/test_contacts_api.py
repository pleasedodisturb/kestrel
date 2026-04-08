"""API tests for Networking CRM (M6) — 15 tests per spec §3.6."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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

    session.add(Profile(id=1, name="Test User", email="test@example.com"))
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session):
    return TestClient(app)


@pytest.fixture
def sample_app(db_session) -> int:
    a = Application(profile_id=1, company="Mistral", role="TPM", status="applied")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a.id


def _create_contact(client: TestClient, **overrides) -> dict:
    payload = {
        "profile_id": 1,
        "name": "Jane Doe",
        "company": "Mistral",
        "relationship_type": "referral",
        "warmth": "hot",
        **overrides,
    }
    resp = client.post("/api/contacts", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# 1. POST /api/contacts — valid
# ---------------------------------------------------------------------------


def test_create_contact_valid(client: TestClient):
    data = _create_contact(client)
    assert data["id"]
    assert data["name"] == "Jane Doe"
    assert data["relationship_type"] == "referral"


# ---------------------------------------------------------------------------
# 2. POST /api/contacts — missing name → 422
# ---------------------------------------------------------------------------


def test_create_contact_missing_name(client: TestClient):
    resp = client.post("/api/contacts", json={"profile_id": 1})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. GET /api/contacts — empty
# ---------------------------------------------------------------------------


def test_list_contacts_empty(client: TestClient):
    resp = client.get("/api/contacts", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["contacts"] == []
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# 4. GET /api/contacts — with data
# ---------------------------------------------------------------------------


def test_list_contacts_with_data(client: TestClient):
    _create_contact(client, name="A")
    _create_contact(client, name="B")

    resp = client.get("/api/contacts", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


# ---------------------------------------------------------------------------
# 5. GET /api/contacts?company=X — filtered
# ---------------------------------------------------------------------------


def test_list_contacts_filter_company(client: TestClient):
    _create_contact(client, name="A", company="Mistral")
    _create_contact(client, name="B", company="Linear")

    resp = client.get("/api/contacts", params={"profile_id": 1, "company": "mistral"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["contacts"][0]["company"] == "Mistral"


# ---------------------------------------------------------------------------
# 6. GET /api/contacts/{id} — exists
# ---------------------------------------------------------------------------


def test_get_contact_exists(client: TestClient):
    created = _create_contact(client)
    resp = client.get(f"/api/contacts/{created['id']}", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Jane Doe"


# ---------------------------------------------------------------------------
# 7. GET /api/contacts/{id} — not found → 404
# ---------------------------------------------------------------------------


def test_get_contact_not_found(client: TestClient):
    resp = client.get("/api/contacts/999", params={"profile_id": 1})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 8. PATCH /api/contacts/{id} — updated
# ---------------------------------------------------------------------------


def test_update_contact(client: TestClient):
    created = _create_contact(client)
    resp = client.patch(
        f"/api/contacts/{created['id']}",
        json={"warmth": "cold"},
        params={"profile_id": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["warmth"] == "cold"


# ---------------------------------------------------------------------------
# 9. DELETE /api/contacts/{id} → 204
# ---------------------------------------------------------------------------


def test_delete_contact(client: TestClient):
    created = _create_contact(client)
    resp = client.delete(f"/api/contacts/{created['id']}", params={"profile_id": 1})
    assert resp.status_code == 204

    # Verify archived
    resp = client.get(f"/api/contacts/{created['id']}", params={"profile_id": 1})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 10. POST /api/contacts/{id}/interactions → 201
# ---------------------------------------------------------------------------


def test_create_interaction(client: TestClient):
    created = _create_contact(client)
    resp = client.post(
        f"/api/contacts/{created['id']}/interactions",
        params={"profile_id": 1},
        json={
            "interaction_type": "email",
            "direction": "outbound",
            "notes": "Sent CV",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["interaction_type"] == "email"
    assert data["direction"] == "outbound"


# ---------------------------------------------------------------------------
# 11. GET /api/contacts/{id}/interactions → ordered
# ---------------------------------------------------------------------------


def test_list_interactions(client: TestClient):
    created = _create_contact(client)
    client.post(
        f"/api/contacts/{created['id']}/interactions",
        params={"profile_id": 1},
        json={"interaction_type": "email", "direction": "outbound"},
    )
    client.post(
        f"/api/contacts/{created['id']}/interactions",
        params={"profile_id": 1},
        json={"interaction_type": "call", "direction": "inbound"},
    )

    resp = client.get(
        f"/api/contacts/{created['id']}/interactions",
        params={"profile_id": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


# ---------------------------------------------------------------------------
# 12. POST /api/contacts/{id}/applications → link created
# ---------------------------------------------------------------------------


def test_link_contact_to_application(client: TestClient, sample_app: int):
    created = _create_contact(client)
    resp = client.post(
        f"/api/contacts/{created['id']}/applications",
        params={"profile_id": 1},
        json={"application_id": sample_app, "role": "referrer"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "referrer"
    assert data["application_id"] == sample_app


# ---------------------------------------------------------------------------
# 13. GET /api/applications/{id}/contacts → reverse lookup
# ---------------------------------------------------------------------------


def test_application_contacts_reverse_lookup(client: TestClient, sample_app: int):
    c = _create_contact(client)
    client.post(
        f"/api/contacts/{c['id']}/applications",
        params={"profile_id": 1},
        json={"application_id": sample_app, "role": "referrer"},
    )

    resp = client.get(
        f"/api/applications/{sample_app}/contacts",
        params={"profile_id": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["role"] == "referrer"


# ---------------------------------------------------------------------------
# 14. GET /api/contacts/by-company/Mistral → company lookup
# ---------------------------------------------------------------------------


def test_contacts_by_company(client: TestClient):
    _create_contact(client, name="A", company="Mistral AI")
    _create_contact(client, name="B", company="Mistral AI")
    _create_contact(client, name="C", company="Linear")

    resp = client.get("/api/contacts/by-company/Mistral", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


# ---------------------------------------------------------------------------
# 15. GET /api/contacts?needs_follow_up=true → overdue contacts
# ---------------------------------------------------------------------------


def test_contacts_needs_follow_up(client: TestClient, db_session: Session):
    # Create a contact with overdue follow-up directly in DB
    from career_os.models.contacts import Contact

    past = datetime.now(UTC) - timedelta(days=1)
    contact = Contact(
        profile_id=1,
        name="Overdue",
        relationship_type="referral",
        warmth="warm",
        next_follow_up=past,
    )
    db_session.add(contact)
    db_session.commit()

    resp = client.get(
        "/api/contacts",
        params={"profile_id": 1, "needs_follow_up": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["contacts"][0]["name"] == "Overdue"
