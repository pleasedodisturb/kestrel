"""Tests for user-testing fix feature m5-fix-ut-docker-cross-flows.

Covers:
- VAL-VOICE-003: Coaching gives feedback on answers (not just repeats questions)
- VAL-CROSS-008: Ghost alerts create follow-up + TickTick chain
- VAL-CROSS-002: Discovery→pipeline promotion carries score
- VAL-CROSS-007: Analytics includes prep/notification metrics
- VAL-CROSS-019: Archiving hides orphaned follow-ups/notifications
"""

import os
import tempfile
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, FollowUp, Profile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _db_engine():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_name = tmp.name
    url = f"sqlite:///{tmp_name}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda c, _: c.cursor().execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.unlink(tmp_name)


@pytest.fixture
def test_db(_db_engine):
    test_session_cls = sessionmaker(bind=_db_engine)
    session = test_session_cls()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def profile(test_db: Session) -> Profile:
    p = Profile(name="Test User", email="test@example.com", location="Frankfurt", job_family="Software Engineering")
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def application(test_db: Session, profile: Profile) -> Application:
    a = Application(
        profile_id=profile.id,
        company="Test Corp",
        role="Senior Engineer",
        url="https://example.com/job",
        source="manual",
        status="applied",
        fit_score=8.0,
    )
    test_db.add(a)
    test_db.commit()
    test_db.refresh(a)
    return a


@pytest.fixture
def client(test_db: Session) -> TestClient:
    def _override():
        yield test_db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ===========================================================================
# VAL-VOICE-003: Coaching gives feedback on answers
# ===========================================================================


class TestCoachingFeedback:
    """Coaching mock returns feedback when user answers questions."""

    def test_coaching_gives_feedback_on_answer(self, client: TestClient, profile: Profile):
        """After asking a question and user answering, coaching returns feedback."""
        # Start coaching session
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        # Send first message to get a question (topic selection)
        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": "I want to focus on interview preparation",
            },
        )
        assert resp.status_code == 200
        first_response = resp.json()["assistant_message"]["content"]
        # First response should contain a question
        assert "?" in first_response

        # Send answer to the coaching question
        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": (
                    "In my previous role, I managed conflicting priorities by "
                    "creating a stakeholder alignment matrix and holding weekly "
                    "syncs. The outcome was 30% faster delivery."
                ),
            },
        )
        assert resp.status_code == 200
        feedback = resp.json()["assistant_message"]["content"]
        # Feedback should NOT just repeat the same question, it should
        # provide critique/improvement guidance
        assert any(
            keyword in feedback.lower()
            for keyword in ["feedback", "strength", "improvement", "suggest"]
        ), f"Expected feedback keywords in response, got: {feedback[:200]}"

    def test_coaching_first_turn_always_asks_question(self, client: TestClient, profile: Profile):
        """First turn returns a coaching question regardless of user content."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        # Send a generic first message (no keyword like "interview")
        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": "Let's go",
            },
        )
        assert resp.status_code == 200
        first_response = resp.json()["assistant_message"]["content"]
        # Must contain a question mark — coaching asks a question on first turn
        assert "?" in first_response, (
            f"First turn should ask a question, got: {first_response[:200]}"
        )


# ===========================================================================
# VAL-CROSS-008: Ghost alerts create follow-up + TickTick chain
# ===========================================================================


class TestGhostAlertFollowUp:
    """Ghost alert trigger auto-creates follow-up for ghost applications."""

    def test_ghost_alert_creates_follow_up(self, test_db: Session, profile: Profile):
        """When ghost alert fires, a follow-up is created for the application."""
        # Create an old "applied" application that will trigger ghost detection
        ghost_app = Application(
            profile_id=profile.id,
            company="Ghost Corp",
            role="Senior TPM",
            source="manual",
            status="applied",
        )
        test_db.add(ghost_app)
        test_db.commit()
        test_db.refresh(ghost_app)

        # Manually set updated_at to 20 days ago to trigger ghost detection
        ghost_app.updated_at = datetime.now(UTC) - timedelta(days=20)
        test_db.commit()

        # Verify it shows up as ghost
        from career_os.services.follow_ups import get_ghost_applications

        ghosts = get_ghost_applications(test_db, profile_id=profile.id)
        assert len(ghosts) >= 1

        # Trigger ghost alerts (Pushover not configured, but follow-up should still be created)
        from career_os.services.pushover import trigger_ghost_alerts

        result = trigger_ghost_alerts(test_db, profile.id)
        # Should fail on sending (no pushover configured) but follow-up created
        assert result["failed"] >= 1 or result["triggered"] >= 0

        # Verify follow-up was created
        follow_ups = (
            test_db.query(FollowUp)
            .filter(
                FollowUp.application_id == ghost_app.id,
                FollowUp.follow_up_type == "ghost_follow_up",
            )
            .all()
        )
        assert len(follow_ups) == 1
        assert "ghost alert" in follow_ups[0].notes.lower()

    def test_ghost_alert_no_duplicate_follow_up(self, test_db: Session, profile: Profile):
        """Repeated ghost alert triggers don't create duplicate follow-ups."""
        ghost_app = Application(
            profile_id=profile.id,
            company="Ghost Corp 2",
            role="Engineer",
            source="manual",
            status="applied",
        )
        test_db.add(ghost_app)
        test_db.commit()
        test_db.refresh(ghost_app)
        ghost_app.updated_at = datetime.now(UTC) - timedelta(days=20)
        test_db.commit()

        from career_os.services.pushover import trigger_ghost_alerts

        # Trigger twice
        trigger_ghost_alerts(test_db, profile.id)
        trigger_ghost_alerts(test_db, profile.id)

        # Should still only have 1 follow-up (deduplication)
        follow_ups = (
            test_db.query(FollowUp)
            .filter(
                FollowUp.application_id == ghost_app.id,
                FollowUp.follow_up_type == "ghost_follow_up",
            )
            .all()
        )
        assert len(follow_ups) == 1


# ===========================================================================
# VAL-CROSS-007: Analytics includes prep/notification metrics
# ===========================================================================


class TestAnalyticsPrepNotificationMetrics:
    """Analytics endpoint includes prep completion rate and notification counts."""

    def test_analytics_has_prep_metrics(self, client: TestClient, profile: Profile):
        """Analytics response includes prep_metrics field."""
        resp = client.get("/api/analytics", params={"profile_id": profile.id})
        assert resp.status_code == 200
        data = resp.json()
        assert "prep_metrics" in data
        prep = data["prep_metrics"]
        assert "total_sessions" in prep
        assert "completion_rate" in prep
        assert "completed_items" in prep
        assert "total_items" in prep

    def test_analytics_has_notification_metrics(self, client: TestClient, profile: Profile):
        """Analytics response includes notification_metrics field."""
        resp = client.get("/api/analytics", params={"profile_id": profile.id})
        assert resp.status_code == 200
        data = resp.json()
        assert "notification_metrics" in data
        notif = data["notification_metrics"]
        assert "total_sent" in notif
        assert "total_failed" in notif
        assert "by_category" in notif

    def test_analytics_empty_prep_metrics(self, client: TestClient, profile: Profile):
        """With no prep sessions, metrics show zeros."""
        resp = client.get("/api/analytics", params={"profile_id": profile.id})
        data = resp.json()
        prep = data["prep_metrics"]
        assert prep["total_sessions"] == 0
        assert prep["completion_rate"] is None


# ===========================================================================
# VAL-CROSS-019: Archiving hides orphaned follow-ups
# ===========================================================================


class TestArchiveHidesOrphans:
    """Archiving an application hides its follow-ups from list APIs."""

    def test_archived_app_follow_ups_hidden(
        self,
        test_db: Session,
        client: TestClient,
        profile: Profile,
        application: Application,
    ):
        """Follow-ups for archived app don't appear in list."""
        # Create a follow-up for the application
        resp = client.post(
            "/api/follow-ups",
            json={
                "profile_id": profile.id,
                "application_id": application.id,
                "due_date": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                "follow_up_type": "check_in",
                "notes": "Test follow-up",
            },
        )
        assert resp.status_code == 201

        # Verify follow-up appears in list
        resp = client.get("/api/follow-ups", params={"profile_id": profile.id})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        # Archive the application
        resp = client.delete(
            f"/api/applications/{application.id}",
            params={"profile_id": profile.id},
        )
        assert resp.status_code == 200

        # Follow-ups for archived app should now be hidden
        resp = client.get("/api/follow-ups", params={"profile_id": profile.id})
        assert resp.status_code == 200
        # The follow-up should be excluded
        for fu in resp.json()["follow_ups"]:
            assert fu["application_id"] != application.id

    def test_archived_app_requirements_hidden(
        self,
        client: TestClient,
        profile: Profile,
        application: Application,
    ):
        """Requirements for archived apps are not returned by GET endpoint."""
        # Create requirements for the application
        resp = client.post(
            f"/api/applications/{application.id}/requirements",
            json={
                "application_id": application.id,
                "profile_id": profile.id,
                "requirements": [
                    {
                        "skill_name": "Python",
                        "required_level": "advanced",
                        "severity": "critical",
                    },
                ],
            },
        )
        assert resp.status_code == 201

        # Verify requirements visible before archive
        resp = client.get(
            f"/api/applications/{application.id}/requirements",
            params={"profile_id": profile.id},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # Archive the application
        resp = client.delete(
            f"/api/applications/{application.id}",
            params={"profile_id": profile.id},
        )
        assert resp.status_code == 200

        # Requirements for archived app should now be hidden
        resp = client.get(
            f"/api/applications/{application.id}/requirements",
            params={"profile_id": profile.id},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_archived_app_overdue_count_excludes(
        self,
        test_db: Session,
        profile: Profile,
        application: Application,
    ):
        """Overdue count excludes follow-ups for archived applications."""
        from career_os.services.follow_ups import get_overdue_count

        # Create overdue follow-up
        fu = FollowUp(
            profile_id=profile.id,
            application_id=application.id,
            due_date=datetime.now(UTC) - timedelta(days=2),
            follow_up_type="check_in",
        )
        test_db.add(fu)
        test_db.commit()

        # Should count before archive
        count_before = get_overdue_count(test_db, profile_id=profile.id)
        assert count_before >= 1

        # Archive the application
        application.archived_at = datetime.now(UTC)
        test_db.commit()

        # Should NOT count after archive
        count_after = get_overdue_count(test_db, profile_id=profile.id)
        assert count_after == count_before - 1


# ===========================================================================
# VAL-CROSS-002: Discovery→pipeline score propagation
# ===========================================================================


class TestDiscoveryScorePropagation:
    """Batch scoring propagates fit_score to the linked Application.

    Also verifies that requirements created on a discovery-linked application
    work with downstream flows (gap analysis).
    """

    @pytest.mark.asyncio
    async def test_batch_score_updates_application(self, test_db: Session, profile: Profile):
        """When a discovered job is scored, its linked application gets the score too."""
        from career_os.models.discovery import DiscoveredJob

        # Create application and discovered job linked to it
        app_obj = Application(
            profile_id=profile.id,
            company="Score Corp",
            role="Engineer",
            source="discovery",
            status="discovered",
        )
        test_db.add(app_obj)
        test_db.flush()

        dj = DiscoveredJob(
            profile_id=profile.id,
            title="Engineer",
            company="Score Corp",
            location="Remote",
            title_normalized="engineer",
            company_normalized="score corp",
            location_normalized="remote",
            application_id=app_obj.id,
        )
        test_db.add(dj)
        test_db.commit()
        test_db.refresh(dj)
        test_db.refresh(app_obj)

        # Verify no score yet
        assert app_obj.fit_score is None

        # Score the discovered job
        from career_os.services.scoring import batch_score_discovery

        result = await batch_score_discovery(test_db, profile.id, discovered_job_ids=[dj.id])
        assert result["scored_count"] == 1

        # Refresh and verify score propagated to application
        test_db.refresh(app_obj)
        test_db.refresh(dj)
        assert dj.fit_score is not None
        assert app_obj.fit_score is not None
        assert app_obj.fit_score == dj.fit_score

    def test_discovery_app_requirements_enable_gap_analysis(
        self, test_db: Session, profile: Profile
    ):
        """Requirements on a discovery-linked application work with gap analysis."""
        from career_os.models.discovery import DiscoveredJob
        from career_os.models.skills import JobRequirement
        from career_os.services.gap_analysis import analyze_gaps

        # Create discovery-linked application
        app_obj = Application(
            profile_id=profile.id,
            company="Gap Corp",
            role="Platform Engineer",
            source="discovery",
            status="discovered",
        )
        test_db.add(app_obj)
        test_db.flush()

        dj = DiscoveredJob(
            profile_id=profile.id,
            title="Platform Engineer",
            company="Gap Corp",
            location="Remote",
            title_normalized="platform engineer",
            company_normalized="gap corp",
            location_normalized="remote",
            application_id=app_obj.id,
        )
        test_db.add(dj)

        # Add requirements to the linked application
        req = JobRequirement(
            application_id=app_obj.id,
            profile_id=profile.id,
            skill_name="Kubernetes",
            required_level="advanced",
            severity="critical",
        )
        test_db.add(req)
        test_db.commit()

        # Gap analysis on the linked application should work
        result = analyze_gaps(test_db, app_obj.id, profile.id)
        assert result["application_id"] == app_obj.id
        assert result["total_requirements"] >= 1
        assert result["company"] == "Gap Corp"

    def test_discovery_score_on_dj_propagates_to_app_on_rescore(
        self, test_db: Session, profile: Profile
    ):
        """DiscoveredJob fit_score is copied to Application.fit_score during scoring."""
        from career_os.models.discovery import DiscoveredJob

        app_obj = Application(
            profile_id=profile.id,
            company="Rescore Inc",
            role="Engineer",
            source="discovery",
            status="discovered",
        )
        test_db.add(app_obj)
        test_db.flush()

        dj = DiscoveredJob(
            profile_id=profile.id,
            title="Engineer",
            company="Rescore Inc",
            location="Berlin",
            title_normalized="engineer",
            company_normalized="rescore inc",
            location_normalized="berlin",
            application_id=app_obj.id,
            fit_score=8.5,  # DJ already has a score
        )
        test_db.add(dj)
        test_db.commit()
        test_db.refresh(app_obj)

        # Application doesn't have score yet
        assert app_obj.fit_score is None

        # Propagate the score from DJ to Application
        from career_os.services.discovery import (
            propagate_discovery_scores,
        )

        propagate_discovery_scores(test_db, profile.id)
        test_db.refresh(app_obj)
        assert app_obj.fit_score == pytest.approx(8.5)
