"""Tests for the Dual-Score Architecture (G-275).

Covers:
- Option A: derived desire_score from dimensional sub-scores + goals
- Option B: AI-generated desire_score via ScoreResult
- Desire score bounds clamping
- Null handling when dimensions are missing
- Goal-based weight adjustment
- desire_score_method tracking on ScoredJob
- classify_quadrant() 2D classification
- Integration: scoring produces both fit_score and desire_score
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob
from career_os.models.skills import Goal
from career_os.schemas.scoring import classify_quadrant
from career_os.services.scoring import (
    DEFAULT_DESIRE_WEIGHTS,
    _resolve_desire_weights,
    compute_derived_desire_score,
)

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    profile = Profile(
        id=1,
        name="Test User",
        email="test@example.com",
        location="Frankfurt",
        job_family="TPM",
    )
    session.add(profile)
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Option A: Derived desire score
# ---------------------------------------------------------------------------


class TestDerivedDesireScore:
    """Tests for compute_derived_desire_score (Option A)."""

    def test_derived_desire_score_calculation(self):
        """Derived score from dimensional scores with default weights."""
        dims = {
            "career_trajectory": 8.0,
            "company_fit": 7.0,
            "compensation_fit": 6.0,
        }
        result = compute_derived_desire_score(dims)
        # 8.0*0.35 + 7.0*0.35 + 6.0*0.30 = 2.8 + 2.45 + 1.8 = 7.05
        # Python's banker's rounding: round(7.05, 1) == 7.0
        assert result == pytest.approx(7.0, abs=0.1)

    def test_derived_desire_score_with_leadership_goals(self):
        """Goals mentioning 'leadership' shift weight to career_trajectory."""
        dims = {
            "career_trajectory": 9.0,
            "company_fit": 5.0,
            "compensation_fit": 5.0,
        }
        goals = [{"title": "Grow into leadership role", "description": ""}]
        result = compute_derived_desire_score(dims, goals)
        # leadership weights: career_trajectory=0.50, company_fit=0.25, compensation_fit=0.25
        # 9.0*0.50 + 5.0*0.25 + 5.0*0.25 = 4.5 + 1.25 + 1.25 = 7.0
        assert result == 7.0

    def test_derived_desire_score_with_compensation_goals(self):
        """Goals mentioning 'salary' shift weight to compensation_fit."""
        dims = {
            "career_trajectory": 5.0,
            "company_fit": 5.0,
            "compensation_fit": 9.0,
        }
        goals = [{"title": "Increase salary", "description": "Target 150k+"}]
        result = compute_derived_desire_score(dims, goals)
        # salary weights: career_trajectory=0.20, company_fit=0.25, compensation_fit=0.55
        # 5.0*0.20 + 5.0*0.25 + 9.0*0.55 = 1.0 + 1.25 + 4.95 = 7.2
        assert result == 7.2

    def test_derived_desire_score_with_culture_goals(self):
        """Goals mentioning 'culture' shift weight to company_fit."""
        dims = {
            "career_trajectory": 5.0,
            "company_fit": 9.0,
            "compensation_fit": 5.0,
        }
        goals = [{"title": "Find great culture fit", "description": ""}]
        result = compute_derived_desire_score(dims, goals)
        # culture weights: career_trajectory=0.25, company_fit=0.50, compensation_fit=0.25
        # 5.0*0.25 + 9.0*0.50 + 5.0*0.25 = 1.25 + 4.5 + 1.25 = 7.0
        assert result == 7.0

    def test_desire_score_bounds_high(self):
        """Desire score is clamped to max 10."""
        dims = {
            "career_trajectory": 10.0,
            "company_fit": 10.0,
            "compensation_fit": 10.0,
        }
        result = compute_derived_desire_score(dims)
        assert result == 10.0

    def test_desire_score_bounds_low(self):
        """Desire score is clamped to min 0."""
        dims = {
            "career_trajectory": 0.0,
            "company_fit": 0.0,
            "compensation_fit": 0.0,
        }
        result = compute_derived_desire_score(dims)
        assert result == 0.0

    def test_desire_score_null_without_dimensions(self):
        """If dimensional_scores is None, desire_score is None."""
        result = compute_derived_desire_score(None)
        assert result is None

    def test_desire_score_null_with_partial_dimensions(self):
        """If required dimensions are missing, desire_score is None."""
        dims = {
            "career_trajectory": 8.0,
            "company_fit": None,
            "compensation_fit": 6.0,
        }
        result = compute_derived_desire_score(dims)
        assert result is None

    def test_default_weights_sum_to_one(self):
        """Default desire weights must sum to 1.0."""
        total = sum(DEFAULT_DESIRE_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_no_matching_goals_uses_defaults(self):
        """Goals with no matching keywords use default weights."""
        goals = [{"title": "Learn Rust", "description": "Systems programming"}]
        weights = _resolve_desire_weights(goals)
        assert weights == DEFAULT_DESIRE_WEIGHTS


# ---------------------------------------------------------------------------
# Option B: AI-generated desire score
# ---------------------------------------------------------------------------


class TestAIGeneratedDesireScore:
    """Tests for AI-generated desire_score via ScoreResult schema."""

    def test_ai_generated_desire_score(self):
        """AI provider returns desire_score in ScoreResult."""
        from career_os.schemas.ai import ScoreBreakdownFactor, ScoreResult

        result = ScoreResult(
            fit_score=7.5,
            reasoning="A" * 100,
            estimated_salary="100k-130k",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Study the product",
            readiness_score=75.0,
            career_alignment=8.0,
            score_breakdown=[
                ScoreBreakdownFactor(factor="Skills", contribution=2.0, description="Good match"),
                ScoreBreakdownFactor(
                    factor="Culture", contribution=1.5, description="Strong culture"
                ),
                ScoreBreakdownFactor(factor="Location", contribution=1.0, description="Remote OK"),
            ],
            desire_score=8.5,
            desire_reasoning="Great company with strong growth trajectory",
        )
        assert result.desire_score == 8.5
        assert result.desire_reasoning == "Great company with strong growth trajectory"

    def test_score_result_without_desire_score(self):
        """ScoreResult without desire_score defaults to None."""
        from career_os.schemas.ai import ScoreBreakdownFactor, ScoreResult

        result = ScoreResult(
            fit_score=7.0,
            reasoning="B" * 100,
            estimated_salary="90k-120k",
            effort_flag="low",
            prep_level="light",
            prep_notes="Quick review",
            readiness_score=80.0,
            career_alignment=7.0,
            score_breakdown=[
                ScoreBreakdownFactor(factor="A", contribution=1.0, description="x"),
                ScoreBreakdownFactor(factor="B", contribution=1.0, description="y"),
                ScoreBreakdownFactor(factor="C", contribution=1.0, description="z"),
            ],
        )
        assert result.desire_score is None
        assert result.desire_reasoning is None


# ---------------------------------------------------------------------------
# Quadrant classification
# ---------------------------------------------------------------------------


class TestQuadrantClassification:
    """Tests for classify_quadrant() 2D classification."""

    def test_dream_job(self):
        assert classify_quadrant(8.0, 8.0) == "dream_job"

    def test_stretch_goal(self):
        assert classify_quadrant(3.0, 7.0) == "stretch_goal"

    def test_safe_bet(self):
        assert classify_quadrant(7.0, 3.0) == "safe_bet"

    def test_skip(self):
        assert classify_quadrant(2.0, 2.0) == "skip"

    def test_threshold_boundary_both_at_5(self):
        """Both scores at threshold = dream_job (>=)."""
        assert classify_quadrant(5.0, 5.0) == "dream_job"

    def test_fit_at_threshold_desire_below(self):
        assert classify_quadrant(5.0, 4.9) == "safe_bet"

    def test_none_fit_score(self):
        assert classify_quadrant(None, 7.0) is None

    def test_none_desire_score(self):
        assert classify_quadrant(7.0, None) is None

    def test_both_none(self):
        assert classify_quadrant(None, None) is None


# ---------------------------------------------------------------------------
# desire_score_method tracking
# ---------------------------------------------------------------------------


class TestDesireScoreMethodTracking:
    """Tests that desire_score_method is correctly set on ScoredJob."""

    def test_desire_score_method_tracked(self, db_session, client):
        """ScoredJob.desire_score_method reflects which option was used."""
        # Create a discovered job
        dj = DiscoveredJob(
            profile_id=1,
            title="AI Product Manager",
            company="TestCo",
            location="Remote",
            sources='["test"]',
            url="https://example.com/job1",
            description="Build AI products",
            title_normalized="ai product manager",
            company_normalized="testco",
            location_normalized="remote",
        )
        db_session.add(dj)
        db_session.commit()
        db_session.refresh(dj)

        # Score via API (mock provider returns desire_score → Option B)
        resp = client.post(
            "/api/score",
            json={
                "profile_id": 1,
                "job_description": "AI Product Manager role at TestCo. Build ML platforms.",
                "job_title": "AI Product Manager",
                "job_company": "TestCo",
                "discovered_job_id": dj.id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()

        # Mock provider returns desire_score → method should be ai_generated
        assert data["desire_score"] is not None
        assert data["desire_score_method"] == "ai_generated"

        # Verify it's persisted in DB
        scored = db_session.query(ScoredJob).first()
        assert scored.desire_score is not None
        assert scored.desire_score_method == "ai_generated"


# ---------------------------------------------------------------------------
# Integration: scoring produces both fit_score and desire_score
# ---------------------------------------------------------------------------


class TestScoringIntegration:
    """Integration tests for the dual-score architecture."""

    def test_score_produces_fit_and_desire(self, db_session, client):
        """Scoring a job produces both fit_score and desire_score."""
        resp = client.post(
            "/api/score",
            json={
                "profile_id": 1,
                "job_description": (
                    "Senior Technical Program Manager at Acme Corp. "
                    "Lead cross-functional teams in AI product delivery."
                ),
                "job_title": "Senior TPM",
                "job_company": "Acme Corp",
            },
        )
        assert resp.status_code == 201
        data = resp.json()

        # Both scores present
        assert "fit_score" in data
        assert data["fit_score"] >= 0
        assert data["fit_score"] <= 10

        assert "desire_score" in data
        assert data["desire_score"] is not None
        assert data["desire_score"] >= 0
        assert data["desire_score"] <= 10

        # Method tracked
        assert data["desire_score_method"] in ("derived", "ai_generated")

    def test_score_with_goals_affects_desire(self, db_session, client):
        """Goals influence the desire_score calculation."""
        # Add a leadership goal
        goal = Goal(
            profile_id=1,
            title="Move into engineering leadership",
            goal_type="career",
            description="Transition to VP of Engineering",
            status="active",
        )
        db_session.add(goal)
        db_session.commit()

        resp = client.post(
            "/api/score",
            json={
                "profile_id": 1,
                "job_description": (
                    "VP of Engineering at ScaleUp Inc. "
                    "Lead 50+ engineers across multiple product lines."
                ),
                "job_title": "VP Engineering",
                "job_company": "ScaleUp Inc",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["desire_score"] is not None

    def test_batch_scoring_includes_desire(self, db_session, client):
        """Batch scoring also produces desire_score for each job."""
        # Seed discovered jobs
        for i in range(3):
            dj = DiscoveredJob(
                profile_id=1,
                title=f"Role {i}",
                company=f"Company {i}",
                location="Remote",
                sources='["test"]',
                url=f"https://example.com/job{i}",
                description=f"Job description for role {i} with AI and ML focus.",
                title_normalized=f"role {i}",
                company_normalized=f"company {i}",
                location_normalized="remote",
            )
            db_session.add(dj)
        db_session.commit()

        resp = client.post(
            "/api/score/batch",
            json={"profile_id": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scored_count"] == 3

        for score in data["scores"]:
            assert "desire_score" in score
            assert score["desire_score"] is not None
            assert score["desire_score_method"] in ("derived", "ai_generated")
