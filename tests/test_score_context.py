"""Tests for score context / percentile calculation (G-271).

Covers:
- Percentile calculation with known score distributions
- Rank calculation
- Null when < 5 scored jobs exist
- Stale scores excluded from calculation
- Ties handled correctly
- Single score returns None
- API endpoints return score_context on GET
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob
from career_os.services.scoring import compute_score_context

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

MINIMAL_SCORED_JOB_KWARGS = dict(
    reasoning="A" * 100,
    estimated_salary="100k",
    effort_flag="low",
    prep_level="light",
    prep_notes="none",
    readiness_score=80.0,
    career_alignment=7.0,
)


@pytest.fixture()
def db_session():
    """Fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_cls()

    profile = Profile(
        id=1,
        name="Test User",
        email="test@example.com",
        location="Berlin",
        job_family="SWE",
    )
    session.add(profile)
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_scored_jobs(
    session, profile_id: int, scores: list[float], stale: bool = False
) -> list[ScoredJob]:
    """Insert ScoredJob rows with given fit_scores and return them."""
    jobs = []
    for score in scores:
        sj = ScoredJob(
            profile_id=profile_id,
            fit_score=score,
            is_stale=stale,
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        session.add(sj)
        jobs.append(sj)
    session.commit()
    for sj in jobs:
        session.refresh(sj)
    return jobs


# ---------------------------------------------------------------------------
# Unit tests: compute_score_context()
# ---------------------------------------------------------------------------


class TestPercentileCalculation:
    def test_known_distribution(self, db_session):
        """Spec validation: score 6.0 in [2.0, 4.0, 6.0, 8.0, 9.0] → percentile=40, rank=3, total=5."""
        _add_scored_jobs(db_session, profile_id=1, scores=[2.0, 4.0, 6.0, 8.0, 9.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=6.0)
        assert ctx is not None
        assert ctx["percentile"] == 40  # 2 scores below 6.0 out of 5
        assert ctx["rank"] == 3  # 2 scores above 6.0
        assert ctx["total_scored"] == 5

    def test_highest_score(self, db_session):
        """The top-scoring job should have rank=1."""
        _add_scored_jobs(db_session, profile_id=1, scores=[2.0, 4.0, 6.0, 8.0, 9.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=9.0)
        assert ctx is not None
        assert ctx["rank"] == 1
        assert ctx["percentile"] == 80  # 4 scores below 9.0 out of 5

    def test_lowest_score(self, db_session):
        """The bottom-scoring job should have rank=5 and percentile=0."""
        _add_scored_jobs(db_session, profile_id=1, scores=[2.0, 4.0, 6.0, 8.0, 9.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=2.0)
        assert ctx is not None
        assert ctx["rank"] == 5
        assert ctx["percentile"] == 0


class TestRankCalculation:
    def test_rank_third_of_ten(self, db_session):
        """3rd highest of 10 scores → rank=3."""
        scores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        _add_scored_jobs(db_session, profile_id=1, scores=scores)
        ctx = compute_score_context(db_session, profile_id=1, fit_score=8.0)
        assert ctx is not None
        assert ctx["rank"] == 3  # 9.0 and 10.0 are above
        assert ctx["total_scored"] == 10


class TestContextNullBelowThreshold:
    def test_zero_scores_returns_none(self, db_session):
        """With no scored jobs, context is None."""
        ctx = compute_score_context(db_session, profile_id=1, fit_score=7.0)
        assert ctx is None

    def test_four_scores_returns_none(self, db_session):
        """With exactly 4 non-stale scored jobs, context is None (below threshold of 5)."""
        _add_scored_jobs(db_session, profile_id=1, scores=[3.0, 5.0, 7.0, 9.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=7.0)
        assert ctx is None

    def test_five_scores_returns_context(self, db_session):
        """With exactly 5 scores, context is populated."""
        _add_scored_jobs(db_session, profile_id=1, scores=[2.0, 4.0, 6.0, 8.0, 9.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=6.0)
        assert ctx is not None


class TestSingleScore:
    def test_single_score_returns_none(self, db_session):
        """With exactly 1 scored job, context is None."""
        _add_scored_jobs(db_session, profile_id=1, scores=[7.5])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=7.5)
        assert ctx is None


class TestStaleScoresExcluded:
    def test_stale_scores_not_counted(self, db_session):
        """Stale scores don't count toward percentile or total."""
        # 3 fresh + 10 stale = only 3 fresh should be counted → below threshold
        _add_scored_jobs(db_session, profile_id=1, scores=[3.0, 5.0, 7.0])
        _add_scored_jobs(db_session, profile_id=1, scores=[1.0] * 10, stale=True)
        ctx = compute_score_context(db_session, profile_id=1, fit_score=5.0)
        assert ctx is None  # only 3 fresh scores, below threshold of 5

    def test_stale_scores_excluded_from_percentile(self, db_session):
        """Stale scores don't inflate percentile calculation."""
        # 5 fresh scores [2,4,6,8,9], 5 stale at 10.0
        _add_scored_jobs(db_session, profile_id=1, scores=[2.0, 4.0, 6.0, 8.0, 9.0])
        _add_scored_jobs(db_session, profile_id=1, scores=[10.0] * 5, stale=True)
        ctx = compute_score_context(db_session, profile_id=1, fit_score=6.0)
        assert ctx is not None
        assert ctx["total_scored"] == 5  # only fresh scores
        assert ctx["percentile"] == 40  # same as without stale


class TestTiesHandled:
    def test_ties_at_queried_score(self, db_session):
        """Multiple scores at the same value: percentile counts only strictly-below scores."""
        # Scores: [5.0, 5.0, 5.0, 7.0, 8.0] — querying at 5.0
        _add_scored_jobs(db_session, profile_id=1, scores=[5.0, 5.0, 5.0, 7.0, 8.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=5.0)
        assert ctx is not None
        # 0 scores strictly below 5.0 out of 5 → percentile = 0
        assert ctx["percentile"] == 0
        # 2 scores strictly above 5.0 → rank = 3
        assert ctx["rank"] == 3

    def test_all_same_score(self, db_session):
        """All scores equal → percentile=0, rank=1 for any score."""
        _add_scored_jobs(db_session, profile_id=1, scores=[6.0, 6.0, 6.0, 6.0, 6.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=6.0)
        assert ctx is not None
        assert ctx["percentile"] == 0
        assert ctx["rank"] == 1
        assert ctx["total_scored"] == 5


class TestAverageAndBandCount:
    def test_avg_score_calculation(self, db_session):
        """avg_score is the mean of all non-stale fit_scores."""
        _add_scored_jobs(db_session, profile_id=1, scores=[2.0, 4.0, 6.0, 8.0, 10.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=6.0)
        assert ctx is not None
        assert ctx["avg_score"] == 6.0

    def test_score_band_count(self, db_session):
        """score_band_count counts jobs in the same letter grade band."""
        # 6.0, 6.5 are both "B" (6.0-6.9), 8.0 is "A-", 9.0 is "A", 4.0 is "C"
        _add_scored_jobs(db_session, profile_id=1, scores=[4.0, 6.0, 6.5, 8.0, 9.0])
        ctx = compute_score_context(db_session, profile_id=1, fit_score=6.0)
        assert ctx is not None
        assert ctx["score_band_count"] == 2  # 6.0 and 6.5 are both "B"


# ---------------------------------------------------------------------------
# Integration tests: API GET endpoints populate score_context
# ---------------------------------------------------------------------------


class TestAPIScoreContext:
    def test_get_job_score_includes_context_when_enough_data(self, db_session, client):
        """GET /api/score/job/{id} includes score_context when >= 5 scores exist."""
        from career_os.models.discovery import DiscoveredJob

        # Create a discovered job
        dj = DiscoveredJob(
            profile_id=1,
            title="Software Engineer",
            title_normalized="software engineer",
            company="Acme",
            company_normalized="acme",
            location="Berlin",
            location_normalized="berlin",
            remote=False,
        )
        db_session.add(dj)
        db_session.commit()
        db_session.refresh(dj)

        # Score the discovered job + 4 additional standalone scores
        target = ScoredJob(
            profile_id=1,
            discovered_job_id=dj.id,
            fit_score=7.0,
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        db_session.add(target)
        _add_scored_jobs(db_session, profile_id=1, scores=[2.0, 4.0, 5.0, 9.0])
        db_session.commit()
        db_session.refresh(target)

        resp = client.get(f"/api/score/job/{dj.id}?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["score_context"] is not None
        ctx = data["score_context"]
        assert "percentile" in ctx
        assert "rank" in ctx
        assert "total_scored" in ctx
        assert ctx["total_scored"] == 5

    def test_get_job_score_context_null_when_insufficient_data(self, db_session, client):
        """GET /api/score/job/{id} returns score_context=null when < 5 scored jobs."""
        from career_os.models.discovery import DiscoveredJob

        dj = DiscoveredJob(
            profile_id=1,
            title="Data Scientist",
            title_normalized="data scientist",
            company="Corp",
            company_normalized="corp",
            location="Berlin",
            location_normalized="berlin",
            remote=True,
        )
        db_session.add(dj)
        db_session.commit()
        db_session.refresh(dj)

        # Only the target score exists (1 total < 5)
        target = ScoredJob(
            profile_id=1,
            discovered_job_id=dj.id,
            fit_score=8.0,
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        db_session.add(target)
        db_session.commit()

        resp = client.get(f"/api/score/job/{dj.id}?profile_id=1")
        assert resp.status_code == 200
        assert resp.json()["score_context"] is None
