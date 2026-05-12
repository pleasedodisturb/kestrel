"""Tests for the safety guard on DELETE /api/profiles/{id}.

Before this guard, calling DELETE silently cascaded every child row (applications,
packages, activity_log, follow-ups, skills, goals, coaching suggestions, learning
resources, job_requirements) thanks to SQLAlchemy `cascade="all, delete-orphan"`.
A single stray API call wiped a downstream user's full job-search dataset on
2026-05-11.

The guard:
- Plain DELETE refuses with 409 if any child rows exist; reports counts per table.
- ?force=true bypasses the guard (preserves the old behavior, now opt-in).
- 404 still wins over 409 when the profile id doesn't exist.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import (
    ActivityLog,
    Application,
    ApplicationPackage,
    FollowUp,
    Profile,
)
from career_os.models.skills import (
    CoachingSuggestion,
    Goal,
    JobRequirement,
    LearningResource,
    Skill,
)


@pytest.fixture(autouse=True)
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()

    session.add(Profile(id=1, name="Owner", email="owner@example.com"))
    session.commit()

    def override_get_db():
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


def _seed_application(session: Session, profile_id: int) -> int:
    app_row = Application(profile_id=profile_id, company="Acme", role="PM", status="applied")
    session.add(app_row)
    session.commit()
    return app_row.id


class TestRefusesDefaultDelete:
    """Plain DELETE must refuse with 409 if any child rows exist."""

    def test_refuses_when_application_exists(self, client: TestClient, db_session: Session):
        _seed_application(db_session, 1)
        resp = client.delete("/api/profiles/1")
        assert resp.status_code == 409
        body = resp.json()["detail"]
        assert body["child_counts"]["applications"] == 1
        # Profile and child row both still present.
        assert db_session.query(Profile).count() == 1
        assert db_session.query(Application).count() == 1

    def test_refuses_when_skill_exists(self, client: TestClient, db_session: Session):
        db_session.add(
            Skill(
                profile_id=1,
                name="Python",
                category="technical",
                proficiency="advanced",
                evidence_source="manual",
            )
        )
        db_session.commit()
        resp = client.delete("/api/profiles/1")
        assert resp.status_code == 409
        assert resp.json()["detail"]["child_counts"]["skills"] == 1

    def test_refuses_when_goal_exists(self, client: TestClient, db_session: Session):
        db_session.add(Goal(profile_id=1, title="Land Senior TPM", goal_type="realistic"))
        db_session.commit()
        resp = client.delete("/api/profiles/1")
        assert resp.status_code == 409
        assert resp.json()["detail"]["child_counts"]["goals"] == 1

    def test_409_lists_only_non_empty_tables(self, client: TestClient, db_session: Session):
        """child_counts must omit zero-count tables (signal-to-noise)."""
        _seed_application(db_session, 1)
        resp = client.delete("/api/profiles/1")
        body = resp.json()["detail"]
        assert "applications" in body["child_counts"]
        assert "skills" not in body["child_counts"]
        assert "follow_ups" not in body["child_counts"]


class TestForceTrueCascades:
    """?force=true preserves the old cascade behavior, now opt-in."""

    def test_force_true_returns_204_and_cascades(self, client: TestClient, db_session: Session):
        app_id = _seed_application(db_session, 1)
        db_session.add(
            ApplicationPackage(
                profile_id=1,
                application_id=app_id,
                package_dir="/tmp/pkg",
                cover_letter_path="/tmp/cl.pdf",
            )
        )
        db_session.commit()

        resp = client.delete("/api/profiles/1?force=true")
        assert resp.status_code == 204
        assert db_session.query(Profile).count() == 0
        assert db_session.query(Application).count() == 0
        assert db_session.query(ApplicationPackage).count() == 0

    def test_force_false_explicit_still_refuses(self, client: TestClient, db_session: Session):
        _seed_application(db_session, 1)
        resp = client.delete("/api/profiles/1?force=false")
        assert resp.status_code == 409


class TestEdgeCases:
    """Things that must keep working alongside the guard."""

    def test_empty_profile_deletes_without_force(self, client: TestClient, db_session: Session):
        """Profile with zero child rows: plain DELETE returns 204."""
        create = client.post("/api/profiles", json={"name": "Lonely"})
        pid = create.json()["id"]
        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204

    def test_nonexistent_returns_404_not_409(self, client: TestClient):
        """404 wins over 409 when the profile does not exist."""
        resp = client.delete("/api/profiles/9999")
        assert resp.status_code == 404

    def test_409_does_not_partially_delete(self, client: TestClient, db_session: Session):
        """If we refuse, no row anywhere may be touched."""
        app_id = _seed_application(db_session, 1)
        db_session.add(
            FollowUp(
                profile_id=1,
                application_id=app_id,
                follow_up_type="thanks",
                due_date=datetime(2026, 6, 1, tzinfo=UTC),
                notes="x",
            )
        )
        db_session.add(ActivityLog(profile_id=1, action="note", details="x"))
        db_session.add(LearningResource(profile_id=1, title="x", resource_type="free_course"))
        db_session.add(
            JobRequirement(
                application_id=app_id,
                profile_id=1,
                skill_name="Python",
                required_level="advanced",
                severity="critical",
            )
        )
        db_session.add(CoachingSuggestion(profile_id=1, action="x", priority=1))
        db_session.commit()
        before = {
            "profile": db_session.query(Profile).count(),
            "application": db_session.query(Application).count(),
            "follow_up": db_session.query(FollowUp).count(),
            "activity_log": db_session.query(ActivityLog).count(),
            "learning_resource": db_session.query(LearningResource).count(),
            "job_requirement": db_session.query(JobRequirement).count(),
            "coaching_suggestion": db_session.query(CoachingSuggestion).count(),
        }
        resp = client.delete("/api/profiles/1")
        assert resp.status_code == 409
        after = {
            "profile": db_session.query(Profile).count(),
            "application": db_session.query(Application).count(),
            "follow_up": db_session.query(FollowUp).count(),
            "activity_log": db_session.query(ActivityLog).count(),
            "learning_resource": db_session.query(LearningResource).count(),
            "job_requirement": db_session.query(JobRequirement).count(),
            "coaching_suggestion": db_session.query(CoachingSuggestion).count(),
        }
        assert before == after


class TestRealWorldReproduction:
    """The exact incident from the 2026-05-11 downstream wipe."""

    def test_one_delete_call_does_not_lose_full_dataset(
        self, client: TestClient, db_session: Session
    ):
        # Seed something representative: 3 applications + 1 package + 1 follow-up.
        for company in ("Anthropic", "DeepMind", "Linear"):
            db_session.add(
                Application(
                    profile_id=1,
                    company=company,
                    role="TPM",
                    status="applied",
                )
            )
        db_session.commit()
        app_one = db_session.query(Application).first().id
        db_session.add(
            ApplicationPackage(
                profile_id=1,
                application_id=app_one,
                package_dir="/tmp/pkg",
                cv_path="/tmp/cv.pdf",
            )
        )
        db_session.add(
            FollowUp(
                profile_id=1,
                application_id=app_one,
                follow_up_type="thanks",
                due_date=datetime(2026, 6, 1, tzinfo=UTC),
            )
        )
        db_session.commit()

        # The exact call shape that triggered the production wipe.
        resp = client.delete("/api/profiles/1")
        assert resp.status_code == 409, "guard must refuse — this was the wipe path"
        # Nothing lost.
        assert db_session.query(Application).count() == 3
        assert db_session.query(ApplicationPackage).count() == 1
        assert db_session.query(FollowUp).count() == 1
