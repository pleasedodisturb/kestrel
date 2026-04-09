"""Two-profile negative tests for cross-profile isolation.

Creates data for profile A, then verifies that profile B CANNOT:
- Read (GET) profile A's applications
- Update (PATCH) profile A's applications
- Delete (DELETE) profile A's applications
- Create follow-ups for profile A's applications
- Complete follow-ups belonging to profile A

Covers: VAL-CROSS-020 (Multi-user profile isolation)
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

PROFILE_A_ID = 1
PROFILE_B_ID = 2


@pytest.fixture(autouse=True)
def db_session():
    """Create a fresh in-memory database with two profiles for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()

    # Seed TWO profiles
    profile_a = Profile(
        id=PROFILE_A_ID,
        name="Alice",
        email="alice@example.com",
        location="Berlin",
    )
    profile_b = Profile(
        id=PROFILE_B_ID,
        name="Bob",
        email="bob@example.com",
        location="Munich",
    )
    session.add_all([profile_a, profile_b])
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
    """FastAPI test client."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_app_for_profile(
    client: TestClient,
    profile_id: int,
    company: str = "Acme Corp",
    role: str = "Engineer",
    **overrides,
) -> dict:
    """Create an application owned by a specific profile."""
    payload = {
        "company": company,
        "role": role,
        "profile_id": profile_id,
        **overrides,
    }
    resp = client.post("/api/applications", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_follow_up_for_profile(
    client: TestClient,
    application_id: int,
    profile_id: int,
) -> dict:
    """Create a follow-up owned by a specific profile."""
    payload = {
        "application_id": application_id,
        "profile_id": profile_id,
        "due_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "follow_up_type": "email",
        "notes": "Check in",
    }
    resp = client.post("/api/follow-ups", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Application CRUD — cross-profile isolation
# ---------------------------------------------------------------------------


class TestApplicationGetScoping:
    """GET /api/applications/{id} must return 404 for wrong profile."""

    def test_owner_can_read_own_application(self, client: TestClient):
        """Profile A can read its own application."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID, company="AliceCo")
        resp = client.get(f"/api/applications/{app_data['id']}?profile_id={PROFILE_A_ID}")
        assert resp.status_code == 200
        assert resp.json()["company"] == "AliceCo"

    def test_other_profile_cannot_read_application(self, client: TestClient):
        """Profile B cannot read profile A's application (returns 404)."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID, company="AliceCo")
        resp = client.get(f"/api/applications/{app_data['id']}?profile_id={PROFILE_B_ID}")
        assert resp.status_code == 404

    def test_list_excludes_other_profiles_apps(self, client: TestClient):
        """Listing applications for profile B does not show profile A's apps."""
        _create_app_for_profile(client, PROFILE_A_ID, company="AliceCo")
        _create_app_for_profile(client, PROFILE_B_ID, company="BobCo")

        resp_a = client.get(f"/api/applications?profile_id={PROFILE_A_ID}")
        resp_b = client.get(f"/api/applications?profile_id={PROFILE_B_ID}")

        apps_a = resp_a.json()["applications"]
        apps_b = resp_b.json()["applications"]

        assert len(apps_a) == 1
        assert apps_a[0]["company"] == "AliceCo"
        assert len(apps_b) == 1
        assert apps_b[0]["company"] == "BobCo"


class TestApplicationUpdateScoping:
    """PATCH /api/applications/{id} must return 404 for wrong profile."""

    def test_owner_can_update_own_application(self, client: TestClient):
        """Profile A can update its own application."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        resp = client.patch(
            f"/api/applications/{app_data['id']}?profile_id={PROFILE_A_ID}",
            json={"notes": "Updated by Alice"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated by Alice"

    def test_other_profile_cannot_update_application(self, client: TestClient):
        """Profile B cannot update profile A's application (returns 404)."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        resp = client.patch(
            f"/api/applications/{app_data['id']}?profile_id={PROFILE_B_ID}",
            json={"notes": "Hacked by Bob"},
        )
        assert resp.status_code == 404

    def test_other_profile_cannot_change_status(self, client: TestClient):
        """Profile B cannot change status of profile A's application."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        resp = client.patch(
            f"/api/applications/{app_data['id']}?profile_id={PROFILE_B_ID}",
            json={"status": "interested"},
        )
        assert resp.status_code == 404


class TestApplicationDeleteScoping:
    """DELETE /api/applications/{id} must return 404 for wrong profile."""

    def test_owner_can_delete_own_application(self, client: TestClient):
        """Profile A can archive its own application."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        resp = client.delete(f"/api/applications/{app_data['id']}?profile_id={PROFILE_A_ID}")
        assert resp.status_code == 200

    def test_other_profile_cannot_delete_application(self, client: TestClient):
        """Profile B cannot archive profile A's application (returns 404)."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        resp = client.delete(f"/api/applications/{app_data['id']}?profile_id={PROFILE_B_ID}")
        assert resp.status_code == 404

    def test_application_still_exists_after_failed_delete(self, client: TestClient):
        """Profile A's application persists after profile B's failed delete attempt."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        # Profile B tries to delete — should fail
        client.delete(f"/api/applications/{app_data['id']}?profile_id={PROFILE_B_ID}")
        # Profile A can still see it
        resp = client.get(f"/api/applications/{app_data['id']}?profile_id={PROFILE_A_ID}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Follow-Up CRUD — cross-profile isolation
# ---------------------------------------------------------------------------


class TestFollowUpCreateScoping:
    """POST /api/follow-ups for another profile's application returns 404."""

    def test_owner_can_create_follow_up(self, client: TestClient):
        """Profile A can create follow-ups on its own application."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        fu = _create_follow_up_for_profile(client, app_data["id"], PROFILE_A_ID)
        assert fu["id"] > 0
        assert fu["application_id"] == app_data["id"]

    def test_other_profile_cannot_create_follow_up(self, client: TestClient):
        """Profile B cannot create follow-ups on profile A's application."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        payload = {
            "application_id": app_data["id"],
            "profile_id": PROFILE_B_ID,
            "due_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "follow_up_type": "email",
            "notes": "Sneaky follow-up",
        }
        resp = client.post("/api/follow-ups", json=payload)
        # Application not found because it doesn't belong to profile B
        assert resp.status_code == 404


class TestFollowUpCompleteScoping:
    """PATCH /api/follow-ups/{id}/complete for another profile's follow-up returns 404."""

    def test_owner_can_complete_follow_up(self, client: TestClient):
        """Profile A can complete its own follow-up."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        fu = _create_follow_up_for_profile(client, app_data["id"], PROFILE_A_ID)
        resp = client.patch(
            f"/api/follow-ups/{fu['id']}?profile_id={PROFILE_A_ID}",
            json={"completed": True},
        )
        assert resp.status_code == 200
        assert resp.json()["completed_at"] is not None

    def test_other_profile_cannot_complete_follow_up(self, client: TestClient):
        """Profile B cannot complete profile A's follow-up (returns 404)."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        fu = _create_follow_up_for_profile(client, app_data["id"], PROFILE_A_ID)
        resp = client.patch(
            f"/api/follow-ups/{fu['id']}?profile_id={PROFILE_B_ID}",
            json={"completed": True},
        )
        assert resp.status_code == 404

    def test_follow_up_uncompleted_after_failed_attempt(self, client: TestClient):
        """Profile A's follow-up remains uncompleted after profile B's failed attempt."""
        app_data = _create_app_for_profile(client, PROFILE_A_ID)
        fu = _create_follow_up_for_profile(client, app_data["id"], PROFILE_A_ID)
        # Profile B tries
        client.patch(
            f"/api/follow-ups/{fu['id']}?profile_id={PROFILE_B_ID}",
            json={"completed": True},
        )
        # Profile A sees it is still incomplete
        resp = client.get(f"/api/follow-ups?profile_id={PROFILE_A_ID}")
        follow_ups = resp.json()["follow_ups"]
        matching = [f for f in follow_ups if f["id"] == fu["id"]]
        assert len(matching) == 1
        assert matching[0]["completed_at"] is None


class TestFollowUpListScoping:
    """Follow-up list is scoped to the requesting profile."""

    def test_list_only_own_follow_ups(self, client: TestClient):
        """Each profile only sees their own follow-ups."""
        app_a = _create_app_for_profile(client, PROFILE_A_ID, company="AliceCo")
        app_b = _create_app_for_profile(client, PROFILE_B_ID, company="BobCo")
        _create_follow_up_for_profile(client, app_a["id"], PROFILE_A_ID)
        _create_follow_up_for_profile(client, app_b["id"], PROFILE_B_ID)

        resp_a = client.get(f"/api/follow-ups?profile_id={PROFILE_A_ID}")
        resp_b = client.get(f"/api/follow-ups?profile_id={PROFILE_B_ID}")

        fus_a = resp_a.json()["follow_ups"]
        fus_b = resp_b.json()["follow_ups"]

        assert len(fus_a) == 1
        assert fus_a[0]["application_company"] == "AliceCo"
        assert len(fus_b) == 1
        assert fus_b[0]["application_company"] == "BobCo"

    def test_overdue_count_only_own(self, client: TestClient):
        """Overdue count is scoped per profile."""
        app_a = _create_app_for_profile(client, PROFILE_A_ID)
        app_b = _create_app_for_profile(client, PROFILE_B_ID)

        # Create overdue follow-ups for both
        overdue_date = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        client.post(
            "/api/follow-ups",
            json={
                "application_id": app_a["id"],
                "profile_id": PROFILE_A_ID,
                "due_date": overdue_date,
                "follow_up_type": "email",
            },
        )
        client.post(
            "/api/follow-ups",
            json={
                "application_id": app_b["id"],
                "profile_id": PROFILE_B_ID,
                "due_date": overdue_date,
                "follow_up_type": "phone",
            },
        )

        resp_a = client.get(f"/api/follow-ups/overdue-count?profile_id={PROFILE_A_ID}")
        resp_b = client.get(f"/api/follow-ups/overdue-count?profile_id={PROFILE_B_ID}")

        assert resp_a.json()["count"] == 1
        assert resp_b.json()["count"] == 1


# ---------------------------------------------------------------------------
# Ghost Detection — cross-profile isolation
# ---------------------------------------------------------------------------


class TestGhostDetectionScoping:
    """Ghost detection respects profile scoping."""

    def test_ghosts_scoped_to_profile(self, client: TestClient, db_session: Session):
        """Ghost alerts only surface applications from the requesting profile."""
        # Create ghost for profile A
        ghost_a = Application(
            profile_id=PROFILE_A_ID,
            company="Ghost A Co",
            role="Role A",
            status="applied",
            date_applied=datetime.now(UTC) - timedelta(days=15),
            updated_at=datetime.now(UTC) - timedelta(days=15),
        )
        # Create ghost for profile B
        ghost_b = Application(
            profile_id=PROFILE_B_ID,
            company="Ghost B Co",
            role="Role B",
            status="applied",
            date_applied=datetime.now(UTC) - timedelta(days=15),
            updated_at=datetime.now(UTC) - timedelta(days=15),
        )
        db_session.add_all([ghost_a, ghost_b])
        db_session.commit()

        resp_a = client.get(f"/api/applications?profile_id={PROFILE_A_ID}&ghost_alert=true")
        resp_b = client.get(f"/api/applications?profile_id={PROFILE_B_ID}&ghost_alert=true")

        ghost_companies_a = [a["company"] for a in resp_a.json()["applications"]]
        ghost_companies_b = [a["company"] for a in resp_b.json()["applications"]]

        assert "Ghost A Co" in ghost_companies_a
        assert "Ghost B Co" not in ghost_companies_a
        assert "Ghost B Co" in ghost_companies_b
        assert "Ghost A Co" not in ghost_companies_b


# ---------------------------------------------------------------------------
# Profiles API — basic sanity
# ---------------------------------------------------------------------------


class TestProfilesAPI:
    """Verify /api/profiles returns both profiles."""

    def test_list_profiles_returns_both(self, client: TestClient):
        """Both seeded profiles are returned."""
        resp = client.get("/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()["profiles"]
        ids = {p["id"] for p in profiles}
        assert PROFILE_A_ID in ids
        assert PROFILE_B_ID in ids

    def test_get_profile_a(self, client: TestClient):
        resp = client.get(f"/api/profiles/{PROFILE_A_ID}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice"

    def test_get_profile_b(self, client: TestClient):
        resp = client.get(f"/api/profiles/{PROFILE_B_ID}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bob"


# ---------------------------------------------------------------------------
# Regression: legacy follow-up with mismatched profile_id
# ---------------------------------------------------------------------------


class TestFollowUpLegacyProfileMismatch:
    """Regression test for follow-up completion when follow_up.profile_id
    does not match application.profile_id (legacy/migrated data).

    The complete_follow_up service now authorizes by joining through the
    owning application rather than relying on follow_ups.profile_id.
    """

    def test_complete_follow_up_with_mismatched_profile_id(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Follow-up whose profile_id differs from its application's profile_id
        can still be completed by the application's owner.

        Simulates legacy/migrated data where follow_up.profile_id was set
        to a different profile than the owning application.
        """
        from career_os.models.models import FollowUp

        # Create application owned by profile A
        app_data = _create_app_for_profile(client, PROFILE_A_ID, company="LegacyCo")

        # Manually insert a follow-up with WRONG profile_id (legacy data)
        # Use PROFILE_B_ID which is a valid FK but doesn't match the app's owner
        legacy_fu = FollowUp(
            profile_id=PROFILE_B_ID,  # mismatched — app belongs to PROFILE_A
            application_id=app_data["id"],
            due_date=datetime.now(UTC) + timedelta(days=1),
            follow_up_type="email",
            notes="Legacy migrated follow-up",
        )
        db_session.add(legacy_fu)
        db_session.commit()
        db_session.refresh(legacy_fu)

        # Profile A (the application owner) should be able to complete it
        resp = client.patch(
            f"/api/follow-ups/{legacy_fu.id}?profile_id={PROFILE_A_ID}",
            json={"completed": True},
        )
        assert resp.status_code == 200
        assert resp.json()["completed_at"] is not None

    def test_non_owner_cannot_complete_legacy_follow_up(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Profile B cannot complete a legacy follow-up on profile A's application,
        even if the follow-up's profile_id happens to match profile B.
        """
        from career_os.models.models import FollowUp

        # Create application owned by profile A
        app_data = _create_app_for_profile(client, PROFILE_A_ID, company="LegacyCo")

        # Insert follow-up with profile_id = PROFILE_B_ID (but app belongs to A)
        legacy_fu = FollowUp(
            profile_id=PROFILE_B_ID,  # matches B but app is A's
            application_id=app_data["id"],
            due_date=datetime.now(UTC) + timedelta(days=1),
            follow_up_type="phone",
            notes="Follow-up with B's profile_id",
        )
        db_session.add(legacy_fu)
        db_session.commit()
        db_session.refresh(legacy_fu)

        # Profile B should NOT be able to complete it (app belongs to A)
        resp = client.patch(
            f"/api/follow-ups/{legacy_fu.id}?profile_id={PROFILE_B_ID}",
            json={"completed": True},
        )
        assert resp.status_code == 404
