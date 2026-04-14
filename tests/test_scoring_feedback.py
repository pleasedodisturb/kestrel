"""Tests for Epic 6 — User Feedback Loop (G-274).

Covers:
- POST /api/score/{id}/feedback — submit explicit feedback
- GET /api/score/feedback — list feedback for a profile
- GET /api/score/feedback/stats — summary statistics
- Implicit feedback on application creation
- Implicit feedback when application reaches interview stage
- get_feedback_calibration() — top deviation examples
- Feature flag threshold (< 10 records → empty calibration)
- Feedback references correct original_fit_score snapshot
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile
from career_os.models.scoring import ScoredJob
from career_os.services.scoring import (
    CALIBRATION_MIN_FEEDBACK,
    FeedbackNotFoundError,
    InvalidFeedbackError,
    _build_scoring_prompt,
    _format_calibration_section,
    get_feedback_calibration,
    record_implicit_feedback,
    submit_feedback,
)

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """Fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _record):
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    Session_ = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = Session_()

    profile = Profile(
        id=1, name="Test User", email="test@example.com", location="Berlin", job_family="SWE"
    )
    session.add(profile)
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scored_job(db: Session, *, profile_id: int = 1, fit_score: float = 7.5) -> ScoredJob:
    """Insert a minimal ScoredJob and return it."""
    sj = ScoredJob(
        profile_id=profile_id,
        fit_score=fit_score,
        readiness_score=60.0,
        career_alignment=7.0,
        reasoning="Test reasoning " * 10,
        estimated_salary="$120k–$150k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Prep notes here.",
    )
    db.add(sj)
    db.commit()
    db.refresh(sj)
    return sj


def _make_application(db: Session, *, profile_id: int = 1) -> Application:
    """Insert a minimal Application and return it."""
    app_obj = Application(
        profile_id=profile_id,
        company="Acme Corp",
        role="Backend Engineer",
        status="discovered",
    )
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return app_obj


# ---------------------------------------------------------------------------
# POST /api/score/{id}/feedback
# ---------------------------------------------------------------------------


def test_submit_feedback(client, db_session):
    """Submit feedback with direction and reason — stored correctly."""
    sj = _make_scored_job(db_session, fit_score=8.0)

    resp = client.post(
        f"/api/score/{sj.id}/feedback",
        params={"profile_id": 1},
        json={"direction": "too_high", "reason": "Role is too senior for my experience"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["direction"] == "too_high"
    assert data["reason"] == "Role is too senior for my experience"
    assert data["user_score"] is None
    assert data["original_fit_score"] == 8.0
    assert data["scored_job_id"] == sj.id
    assert data["profile_id"] == 1


def test_submit_feedback_with_user_score(client, db_session):
    """Feedback with explicit user_score is stored correctly."""
    sj = _make_scored_job(db_session, fit_score=9.0)

    resp = client.post(
        f"/api/score/{sj.id}/feedback",
        params={"profile_id": 1},
        json={"direction": "too_high", "user_score": 6.5, "reason": "Skills mismatch"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_score"] == 6.5
    assert data["original_fit_score"] == 9.0


def test_submit_feedback_invalid_direction(client, db_session):
    """Invalid direction returns 400."""
    sj = _make_scored_job(db_session)

    resp = client.post(
        f"/api/score/{sj.id}/feedback",
        params={"profile_id": 1},
        json={"direction": "completely_wrong"},
    )
    assert resp.status_code == 422  # Pydantic rejects the enum value


def test_submit_feedback_user_score_out_of_range(client, db_session):
    """user_score outside 0–10 returns validation error."""
    sj = _make_scored_job(db_session)

    resp = client.post(
        f"/api/score/{sj.id}/feedback",
        params={"profile_id": 1},
        json={"direction": "too_low", "user_score": 15.0},
    )
    assert resp.status_code == 422


def test_submit_feedback_scored_job_not_found(client, db_session):
    """404 when scored_job_id does not exist."""
    resp = client.post(
        "/api/score/9999/feedback",
        params={"profile_id": 1},
        json={"direction": "correct"},
    )
    assert resp.status_code == 404


def test_submit_feedback_wrong_profile(client, db_session):
    """404 when scored_job belongs to a different profile."""
    # Create second profile
    p2 = Profile(
        id=2, name="Other User", email="other@example.com", location="Munich", job_family="TPM"
    )
    db_session.add(p2)
    db_session.commit()

    sj = _make_scored_job(db_session, profile_id=2, fit_score=7.0)

    resp = client.post(
        f"/api/score/{sj.id}/feedback",
        params={"profile_id": 1},  # wrong profile
        json={"direction": "too_low"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/score/feedback
# ---------------------------------------------------------------------------


def test_list_feedback_for_profile(client, db_session):
    """GET feedback returns all entries for the profile, newest first."""
    sj = _make_scored_job(db_session)
    submit_feedback(db_session, scored_job_id=sj.id, profile_id=1, direction="too_high")
    submit_feedback(db_session, scored_job_id=sj.id, profile_id=1, direction="correct")

    resp = client.get("/api/score/feedback", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Most recent first
    assert data[0]["direction"] == "correct"
    assert data[1]["direction"] == "too_high"


def test_list_feedback_empty(client, db_session):
    """GET feedback returns empty list when no feedback submitted."""
    resp = client.get("/api/score/feedback", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/score/feedback/stats
# ---------------------------------------------------------------------------


def test_feedback_stats(client, db_session):
    """Stats endpoint returns count, avg deviation, most common direction."""
    sj = _make_scored_job(db_session, fit_score=8.0)
    submit_feedback(
        db_session, scored_job_id=sj.id, profile_id=1, direction="too_high", user_score=6.0
    )
    submit_feedback(
        db_session, scored_job_id=sj.id, profile_id=1, direction="too_low", user_score=9.0
    )
    submit_feedback(db_session, scored_job_id=sj.id, profile_id=1, direction="correct")

    resp = client.get("/api/score/feedback/stats", params={"profile_id": 1})
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_count"] == 3
    assert stats["explicit_count"] == 3
    assert stats["implicit_count"] == 0
    # avg deviation: |6.0-8.0|=2.0, |9.0-8.0|=1.0 → avg=1.5
    assert stats["avg_deviation"] == pytest.approx(1.5)
    assert stats["direction_counts"]["too_high"] == 1
    assert stats["direction_counts"]["too_low"] == 1
    assert stats["direction_counts"]["correct"] == 1


def test_feedback_stats_empty(client, db_session):
    """Stats with no feedback records returns zeros."""
    resp = client.get("/api/score/feedback/stats", params={"profile_id": 1})
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_count"] == 0
    assert stats["avg_deviation"] is None


# ---------------------------------------------------------------------------
# Implicit feedback — service layer
# ---------------------------------------------------------------------------


def test_implicit_positive_on_application_create(db_session):
    """Creating an application linked to a ScoredJob records implicit_positive feedback."""
    app_obj = _make_application(db_session)
    sj = ScoredJob(
        profile_id=1,
        application_id=app_obj.id,
        fit_score=7.0,
        readiness_score=55.0,
        career_alignment=6.5,
        reasoning="Test reasoning " * 10,
        estimated_salary="$100k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Notes here.",
    )
    db_session.add(sj)
    db_session.commit()

    # Simulate what ApplicationService.create does post-commit
    result = record_implicit_feedback(
        db_session,
        profile_id=1,
        direction="implicit_positive",
        application_id=app_obj.id,
    )

    assert result is not None
    assert result.direction == "implicit_positive"
    assert result.original_fit_score == 7.0
    assert result.user_score is None


def test_implicit_strong_positive_on_interview(db_session):
    """Application reaching 'interview' status triggers implicit_strong_positive."""
    app_obj = _make_application(db_session)
    sj = ScoredJob(
        profile_id=1,
        application_id=app_obj.id,
        fit_score=8.5,
        readiness_score=70.0,
        career_alignment=8.0,
        reasoning="Test reasoning " * 10,
        estimated_salary="$130k",
        effort_flag="high",
        prep_level="intensive",
        prep_notes="Prepare STAR stories.",
    )
    db_session.add(sj)
    db_session.commit()

    result = record_implicit_feedback(
        db_session,
        profile_id=1,
        direction="implicit_strong_positive",
        application_id=app_obj.id,
    )

    assert result is not None
    assert result.direction == "implicit_strong_positive"
    assert result.original_fit_score == 8.5


def test_implicit_feedback_no_scored_job_returns_none(db_session):
    """record_implicit_feedback returns None when no ScoredJob exists."""
    result = record_implicit_feedback(
        db_session,
        profile_id=1,
        direction="implicit_positive",
        application_id=9999,  # doesn't exist
    )
    assert result is None


def test_implicit_feedback_invalid_direction_returns_none(db_session):
    """record_implicit_feedback with an explicit direction returns None (logged, not raised)."""
    sj = _make_scored_job(db_session)
    result = record_implicit_feedback(
        db_session,
        profile_id=1,
        direction="too_high",  # explicit direction not allowed for implicit hook
        scored_job_id=sj.id,
    )
    assert result is None


# ---------------------------------------------------------------------------
# Calibration summary
# ---------------------------------------------------------------------------


def test_calibration_summary_minimum_threshold(db_session):
    """With fewer than CALIBRATION_MIN_FEEDBACK records, returns empty list."""
    sj = _make_scored_job(db_session, fit_score=8.0)
    # Submit 9 feedback records (below threshold of 10)
    for i in range(CALIBRATION_MIN_FEEDBACK - 1):
        submit_feedback(
            db_session,
            scored_job_id=sj.id,
            profile_id=1,
            direction="too_high",
            user_score=float(i),
        )

    result = get_feedback_calibration(db_session, profile_id=1)
    assert result == []


def test_calibration_summary_top_deviations(db_session):
    """Summary returns the highest-deviation examples when ≥ threshold exist."""
    sj = _make_scored_job(db_session, fit_score=8.0)

    # Submit enough records to exceed threshold, with varying deviations
    # Record with biggest deviation: user says 1.0 → deviation = 7.0
    for _ in range(CALIBRATION_MIN_FEEDBACK):
        submit_feedback(
            db_session,
            scored_job_id=sj.id,
            profile_id=1,
            direction="too_high",
            user_score=1.0,
        )

    result = get_feedback_calibration(db_session, profile_id=1)
    # Should return up to 5 examples
    assert 1 <= len(result) <= 5
    # All returned examples should have the correct ai_score snapshot
    for example in result:
        assert example["ai_score"] == 8.0
        assert example["user_score"] == 1.0
        assert example["deviation"] == pytest.approx(7.0)


def test_calibration_summary_sorted_by_deviation(db_session):
    """Calibration examples are sorted highest deviation first."""
    sj_high = _make_scored_job(db_session, fit_score=9.0)
    sj_low = _make_scored_job(db_session, fit_score=5.0)

    # For sj_high: user says 2.0 → deviation 7.0
    # For sj_low: user says 4.0 → deviation 1.0
    # Submit enough records to exceed the threshold
    for _ in range(CALIBRATION_MIN_FEEDBACK):
        submit_feedback(
            db_session,
            scored_job_id=sj_high.id,
            profile_id=1,
            direction="too_high",
            user_score=2.0,
        )
    submit_feedback(
        db_session,
        scored_job_id=sj_low.id,
        profile_id=1,
        direction="too_low",
        user_score=4.0,
    )

    result = get_feedback_calibration(db_session, profile_id=1)
    assert len(result) >= 1
    # First example should have the highest deviation
    assert result[0]["deviation"] >= result[-1]["deviation"]


# ---------------------------------------------------------------------------
# Feedback references correct original score
# ---------------------------------------------------------------------------


def test_feedback_references_correct_score(db_session):
    """original_fit_score matches the scored_job's actual fit_score at submission time."""
    sj = _make_scored_job(db_session, fit_score=6.3)

    fb = submit_feedback(
        db_session,
        scored_job_id=sj.id,
        profile_id=1,
        direction="too_low",
        user_score=8.0,
    )

    assert fb.original_fit_score == pytest.approx(6.3)
    assert fb.user_score == 8.0


def test_submit_feedback_correct_direction_no_user_score(db_session):
    """'correct' direction can be submitted without a user_score."""
    sj = _make_scored_job(db_session, fit_score=7.0)

    fb = submit_feedback(
        db_session,
        scored_job_id=sj.id,
        profile_id=1,
        direction="correct",
    )

    assert fb.direction == "correct"
    assert fb.user_score is None
    assert fb.original_fit_score == 7.0


# ---------------------------------------------------------------------------
# Service-layer validation
# ---------------------------------------------------------------------------


def test_submit_feedback_invalid_direction_raises(db_session):
    """submit_feedback raises InvalidFeedbackError for unknown direction."""
    sj = _make_scored_job(db_session)

    with pytest.raises(InvalidFeedbackError, match="Invalid direction"):
        submit_feedback(
            db_session,
            scored_job_id=sj.id,
            profile_id=1,
            direction="nonsense",
        )


def test_submit_feedback_bad_user_score_raises(db_session):
    """submit_feedback raises InvalidFeedbackError when user_score is out of range."""
    sj = _make_scored_job(db_session)

    with pytest.raises(InvalidFeedbackError, match="user_score"):
        submit_feedback(
            db_session,
            scored_job_id=sj.id,
            profile_id=1,
            direction="too_high",
            user_score=11.0,
        )


def test_submit_feedback_not_found_raises(db_session):
    """submit_feedback raises FeedbackNotFoundError for unknown scored_job_id."""
    with pytest.raises(FeedbackNotFoundError):
        submit_feedback(
            db_session,
            scored_job_id=9999,
            profile_id=1,
            direction="correct",
        )


# ---------------------------------------------------------------------------
# Integration: submit → retrieve → verify stats
# ---------------------------------------------------------------------------


def test_integration_submit_retrieve_stats(client, db_session):
    """Full flow: submit feedback → retrieve list → verify stats match."""
    sj = _make_scored_job(db_session, fit_score=7.0)

    # Submit three explicit feedbacks
    client.post(
        f"/api/score/{sj.id}/feedback",
        params={"profile_id": 1},
        json={"direction": "too_high", "user_score": 5.0, "reason": "Overvalued"},
    )
    client.post(
        f"/api/score/{sj.id}/feedback",
        params={"profile_id": 1},
        json={"direction": "too_low", "user_score": 9.0},
    )
    client.post(
        f"/api/score/{sj.id}/feedback",
        params={"profile_id": 1},
        json={"direction": "correct"},
    )

    # Retrieve list
    list_resp = client.get("/api/score/feedback", params={"profile_id": 1})
    assert list_resp.status_code == 200
    records = list_resp.json()
    assert len(records) == 3

    # Verify stats
    stats_resp = client.get("/api/score/feedback/stats", params={"profile_id": 1})
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_count"] == 3
    assert stats["explicit_count"] == 3
    assert stats["implicit_count"] == 0
    # Deviations: |5.0-7.0|=2.0, |9.0-7.0|=2.0 → avg=2.0
    assert stats["avg_deviation"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Calibration prompt injection (G-274 fix)
# ---------------------------------------------------------------------------


class TestCalibrationFormatting:
    """Tests for _format_calibration_section and prompt injection."""

    def test_empty_calibration_returns_empty(self):
        """No calibration examples → no lines added."""
        assert _format_calibration_section([]) == []

    def test_calibration_section_includes_header(self):
        """Calibration section starts with an explanatory header."""
        examples = [
            {
                "job_title": "SWE",
                "company": "Acme",
                "ai_score": 8.0,
                "user_score": 5.0,
                "reason": None,
                "deviation": 3.0,
            }
        ]
        lines = _format_calibration_section(examples)
        assert any("Scoring Calibration" in line for line in lines)

    def test_calibration_section_formats_example(self):
        """Each example shows job, company, AI score, user score."""
        examples = [
            {
                "job_title": "Backend Engineer",
                "company": "BigCo",
                "ai_score": 9.0,
                "user_score": 6.0,
                "reason": "Too senior",
                "deviation": 3.0,
            }
        ]
        lines = _format_calibration_section(examples)
        detail_line = lines[1]
        assert "Backend Engineer" in detail_line
        assert "BigCo" in detail_line
        assert "9.0" in detail_line
        assert "6.0" in detail_line
        assert "Too senior" in detail_line

    def test_calibration_section_handles_missing_metadata(self):
        """None job_title/company gracefully becomes 'Unknown'."""
        examples = [
            {
                "job_title": None,
                "company": None,
                "ai_score": 7.0,
                "user_score": 4.0,
                "reason": None,
                "deviation": 3.0,
            }
        ]
        lines = _format_calibration_section(examples)
        detail_line = lines[1]
        assert "Unknown role" in detail_line
        assert "Unknown company" in detail_line

    def test_build_prompt_includes_calibration(self):
        """When calibration_examples are passed, they appear in the prompt."""
        examples = [
            {
                "job_title": "SRE",
                "company": "CloudCo",
                "ai_score": 8.5,
                "user_score": 5.5,
                "reason": None,
                "deviation": 3.0,
            }
        ]
        prompt = _build_scoring_prompt(
            job_description="Test JD",
            profile_data={"name": "Test", "location": "Berlin", "job_family": "SWE"},
            calibration_examples=examples,
        )
        assert "Scoring Calibration" in prompt
        assert "SRE @ CloudCo" in prompt

    def test_build_prompt_without_calibration(self):
        """When no calibration_examples, section is absent from prompt."""
        prompt = _build_scoring_prompt(
            job_description="Test JD",
            profile_data={"name": "Test", "location": "Berlin", "job_family": "SWE"},
        )
        assert "Scoring Calibration" not in prompt
