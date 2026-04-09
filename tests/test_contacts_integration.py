"""Integration tests for Networking CRM (M6) — 6 cross-feature flows per spec §3.6."""

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
# 1. Create contact → link to app → app detail shows contact
# ---------------------------------------------------------------------------


def test_create_link_show_in_app_detail(client: TestClient, sample_app: int):
    """Full flow: create contact, link to application, verify reverse lookup."""
    contact = _create_contact(client, name="Jane Doe", company="Mistral")

    # Link contact to application
    resp = client.post(
        f"/api/contacts/{contact['id']}/applications",
        params={"profile_id": 1},
        json={"application_id": sample_app, "role": "referrer"},
    )
    assert resp.status_code == 201

    # Reverse lookup: application → contacts
    resp = client.get(
        f"/api/applications/{sample_app}/contacts",
        params={"profile_id": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["contact"]["name"] == "Jane Doe"
    assert data[0]["role"] == "referrer"


# ---------------------------------------------------------------------------
# 2. Create contact → log interaction → last_contacted_at updates
# ---------------------------------------------------------------------------


def test_interaction_updates_last_contacted(client: TestClient):
    """Logging an interaction should propagate the timestamp to last_contacted_at."""
    contact = _create_contact(client)
    assert contact.get("last_contacted_at") is None

    # Log interaction
    resp = client.post(
        f"/api/contacts/{contact['id']}/interactions",
        params={"profile_id": 1},
        json={"interaction_type": "email", "direction": "outbound", "notes": "Sent CV"},
    )
    assert resp.status_code == 201

    # Verify last_contacted_at was updated
    resp = client.get(f"/api/contacts/{contact['id']}", params={"profile_id": 1})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["last_contacted_at"] is not None


# ---------------------------------------------------------------------------
# 3. Archive application → linked contacts still exist
# ---------------------------------------------------------------------------


def test_archive_app_contacts_survive(client: TestClient, sample_app: int):
    """Archiving an application should not affect linked contacts."""
    contact = _create_contact(client)

    # Link
    client.post(
        f"/api/contacts/{contact['id']}/applications",
        params={"profile_id": 1},
        json={"application_id": sample_app, "role": "referrer"},
    )

    # Archive the application
    resp = client.delete(
        f"/api/applications/{sample_app}",
        params={"profile_id": 1},
    )
    # Applications endpoint may return 200 or 204 depending on impl
    assert resp.status_code in (200, 204)

    # Contact should still exist and be accessible
    resp = client.get(f"/api/contacts/{contact['id']}", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Jane Doe"


# ---------------------------------------------------------------------------
# 4. Archive contact → excluded from app detail contacts
# ---------------------------------------------------------------------------


def test_archive_contact_excluded_from_app(client: TestClient, sample_app: int):
    """Archived contacts should not appear in application's contact list."""
    contact = _create_contact(client)

    # Link
    client.post(
        f"/api/contacts/{contact['id']}/applications",
        params={"profile_id": 1},
        json={"application_id": sample_app, "role": "referrer"},
    )

    # Archive the contact
    resp = client.delete(f"/api/contacts/{contact['id']}", params={"profile_id": 1})
    assert resp.status_code == 204

    # Reverse lookup should not include archived contact
    resp = client.get(
        f"/api/applications/{sample_app}/contacts",
        params={"profile_id": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


# ---------------------------------------------------------------------------
# 5. Referral contact linked → application shows referral badge data
# ---------------------------------------------------------------------------


def test_referral_badge_data(client: TestClient, sample_app: int):
    """When a referral-type contact is linked, badge data is available."""
    contact = _create_contact(client, name="Referrer Jane", relationship_type="referral")

    client.post(
        f"/api/contacts/{contact['id']}/applications",
        params={"profile_id": 1},
        json={"application_id": sample_app, "role": "referrer"},
    )

    # Check reverse lookup returns referral data
    resp = client.get(
        f"/api/applications/{sample_app}/contacts",
        params={"profile_id": 1},
    )
    data = resp.json()
    assert len(data) == 1
    assert data[0]["contact"]["relationship_type"] == "referral"
    assert data[0]["role"] == "referrer"


# ---------------------------------------------------------------------------
# 6. Contact follow-up overdue → appears in follow-up list
# ---------------------------------------------------------------------------


def test_contact_follow_up_cross_feature(client: TestClient, db_session: Session):
    """Contacts with overdue next_follow_up appear in the filtered list."""
    from career_os.models.contacts import Contact

    past = datetime.now(UTC) - timedelta(days=2)
    future = datetime.now(UTC) + timedelta(days=5)

    # Overdue contact
    c1 = Contact(
        profile_id=1,
        name="Overdue Contact",
        relationship_type="referral",
        warmth="warm",
        next_follow_up=past,
    )
    # Future contact
    c2 = Contact(
        profile_id=1,
        name="Future Contact",
        relationship_type="peer",
        warmth="cold",
        next_follow_up=future,
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    resp = client.get(
        "/api/contacts",
        params={"profile_id": 1, "needs_follow_up": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["contacts"][0]["name"] == "Overdue Contact"
