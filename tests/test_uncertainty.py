"""Tests for profile completeness and uncertainty ranges (Epic 10 / G-278).

Covers:
- Completeness calculation with full profile (100%)
- Completeness with empty/minimal profile (0% or near-0%)
- Completeness with partial profile
- Confidence interval math (verify formula)
- Confidence range clamped to [0, 10] when fit_score is near boundary
- Missing fields suggestions when completeness < 50%
- Missing fields empty when completeness >= 50%
- apply_confidence_range() helper
- API GET endpoints include profile_completeness
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob
from career_os.models.skills import Goal, Skill
from career_os.services.scoring import apply_confidence_range, compute_profile_completeness

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
    """Fresh in-memory database with FK enforcement for each test."""
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


def _make_profile(
    session: Session,
    *,
    profile_id: int = 1,
    job_family: str | None = None,
    location: str | None = None,
    dream_companies: list[str] | None = None,
    last_market_refreshed_at=None,
) -> Profile:
    """Insert a Profile row with the given fields."""
    dc_json = json.dumps(dream_companies) if dream_companies is not None else None
    p = Profile(
        id=profile_id,
        name="Test User",
        email="test@example.com",
        job_family=job_family,
        location=location,
        dream_companies=dc_json,
        last_market_refreshed_at=last_market_refreshed_at,
    )
    session.add(p)
    session.commit()
    return p


def _add_skills(session: Session, profile_id: int, count: int) -> list[Skill]:
    """Insert `count` Skill rows for the given profile."""
    skills = []
    for i in range(count):
        s = Skill(
            profile_id=profile_id,
            name=f"skill_{i}",
            category="technical",
            proficiency="intermediate",
            evidence_source="resume",
        )
        session.add(s)
        skills.append(s)
    session.commit()
    return skills


def _add_goals(session: Session, profile_id: int, count: int) -> list[Goal]:
    """Insert `count` Goal rows for the given profile."""
    goals = []
    for i in range(count):
        g = Goal(
            profile_id=profile_id,
            title=f"goal_{i}",
            goal_type="realistic",
            status="active",
        )
        session.add(g)
        goals.append(g)
    session.commit()
    return goals


# ---------------------------------------------------------------------------
# Unit tests: compute_profile_completeness()
# ---------------------------------------------------------------------------


class TestCompletenessCalculation:
    def test_empty_profile_zero_completeness(self, db_session):
        """A profile with only name/email has 0% completeness."""
        _make_profile(db_session, profile_id=1)
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 0.0

    def test_full_profile_100_completeness(self, db_session):
        """A profile with all components filled has 100% completeness."""
        from datetime import UTC, datetime

        _make_profile(
            db_session,
            profile_id=1,
            job_family="SWE",
            location="Berlin",
            dream_companies=["Google", "Meta", "Stripe"],
            last_market_refreshed_at=datetime.now(UTC),
        )
        _add_skills(db_session, profile_id=1, count=5)
        _add_goals(db_session, profile_id=1, count=1)

        result = compute_profile_completeness(db_session, profile_id=1)
        # job_family(15) + location(15) + skills(20) + goals(15) + market(10) + dream(10) = 85
        # experiences always 0 until Experiences model exists → max is 85
        assert result["completeness"] == 85.0

    def test_partial_profile_has_location_and_job_family(self, db_session):
        """Profile with only job_family + location = 30% completeness."""
        _make_profile(db_session, profile_id=1, job_family="TPM", location="Frankfurt")
        result = compute_profile_completeness(db_session, profile_id=1)
        # job_family(15) + location(15) = 30
        assert result["completeness"] == 30.0

    def test_skills_threshold_not_met(self, db_session):
        """Only 4 skills (below threshold of 5) → skills component not counted."""
        _make_profile(db_session, profile_id=1, job_family="SWE", location="Berlin")
        _add_skills(db_session, profile_id=1, count=4)
        result = compute_profile_completeness(db_session, profile_id=1)
        # job_family(15) + location(15) = 30 (skills NOT counted, 4 < 5)
        assert result["completeness"] == 30.0

    def test_skills_threshold_met(self, db_session):
        """Exactly 5 skills → skills component counted (+20%)."""
        _make_profile(db_session, profile_id=1, job_family="SWE", location="Berlin")
        _add_skills(db_session, profile_id=1, count=5)
        result = compute_profile_completeness(db_session, profile_id=1)
        # job_family(15) + location(15) + skills(20) = 50
        assert result["completeness"] == 50.0

    def test_goals_counted_with_one_goal(self, db_session):
        """One goal satisfies the goals component (+15%)."""
        _make_profile(db_session, profile_id=1)
        _add_goals(db_session, profile_id=1, count=1)
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 15.0

    def test_dream_companies_json_array(self, db_session):
        """dream_companies as JSON array with values → +10%."""
        _make_profile(db_session, profile_id=1, dream_companies=["Google"])
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 10.0

    def test_dream_companies_empty_array(self, db_session):
        """dream_companies as empty JSON array → not counted."""
        _make_profile(db_session, profile_id=1, dream_companies=[])
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 0.0

    def test_market_positioning_counted(self, db_session):
        """last_market_refreshed_at present → market_positioning component counted (+10%)."""
        from datetime import UTC, datetime

        _make_profile(
            db_session,
            profile_id=1,
            last_market_refreshed_at=datetime.now(UTC),
        )
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 10.0

    def test_nonexistent_profile_returns_zero(self, db_session):
        """Non-existent profile_id returns 0% completeness gracefully."""
        result = compute_profile_completeness(db_session, profile_id=9999)
        assert result["completeness"] == 0.0
        assert result["missing_fields"]  # should list all fields


# ---------------------------------------------------------------------------
# Unit tests: confidence interval formula
# ---------------------------------------------------------------------------


class TestConfidenceIntervalFormula:
    """Verify half_width = 3.0 * (1 - completeness/100) + 0.3."""

    def _expected_half_width(self, completeness: float) -> float:
        return 3.0 * (1.0 - completeness / 100.0) + 0.3

    def test_formula_at_zero_percent(self, db_session):
        """At 0% completeness: half_width = 3.0 * 1.0 + 0.3 = 3.3."""
        _make_profile(db_session, profile_id=1)
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 0.0
        expected = self._expected_half_width(0.0)
        assert abs(result["half_width"] - expected) < 0.001

    def test_formula_at_50_percent(self, db_session):
        """At 50% completeness: half_width = 3.0 * 0.5 + 0.3 = 1.8."""
        _make_profile(db_session, profile_id=1, job_family="SWE", location="Berlin")
        _add_skills(db_session, profile_id=1, count=5)
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 50.0
        expected = self._expected_half_width(50.0)
        assert abs(result["half_width"] - expected) < 0.001

    def test_formula_at_85_percent(self, db_session):
        """At 85% completeness (max without experiences): half_width ≈ 3.0*0.15+0.3=0.75."""
        from datetime import UTC, datetime

        _make_profile(
            db_session,
            profile_id=1,
            job_family="SWE",
            location="Berlin",
            dream_companies=["Google"],
            last_market_refreshed_at=datetime.now(UTC),
        )
        _add_skills(db_session, profile_id=1, count=5)
        _add_goals(db_session, profile_id=1, count=1)
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 85.0
        expected = self._expected_half_width(85.0)
        assert abs(result["half_width"] - expected) < 0.001


# ---------------------------------------------------------------------------
# Unit tests: apply_confidence_range() clamping
# ---------------------------------------------------------------------------


class TestConfidenceRangeClamping:
    def test_low_score_clamps_to_zero(self):
        """Low fit_score with large half_width: lower bound clamped to 0."""
        low, high = apply_confidence_range(fit_score=1.0, half_width=3.3)
        assert low == 0.0
        assert high <= 10.0
        assert high == round(min(10.0, 1.0 + 3.3), 2)

    def test_high_score_clamps_to_ten(self):
        """High fit_score with large half_width: upper bound clamped to 10."""
        low, high = apply_confidence_range(fit_score=9.5, half_width=3.3)
        assert high == 10.0
        assert low >= 0.0

    def test_mid_score_no_clamping_needed(self):
        """Mid-range fit_score with small half_width: no clamping needed."""
        low, high = apply_confidence_range(fit_score=5.0, half_width=0.3)
        assert low == round(5.0 - 0.3, 2)
        assert high == round(5.0 + 0.3, 2)
        assert low >= 0.0
        assert high <= 10.0

    def test_range_is_symmetric_without_clamping(self):
        """Without boundary clamping, range is symmetric around fit_score."""
        fit = 5.0
        hw = 1.5
        low, high = apply_confidence_range(fit_score=fit, half_width=hw)
        assert high - low == pytest.approx(2 * hw, abs=0.01)

    def test_full_range_at_zero_fit_zero_completeness(self):
        """Absolute worst case: score=0, half_width=3.3 → (0.0, 3.3)."""
        low, high = apply_confidence_range(fit_score=0.0, half_width=3.3)
        assert low == 0.0
        assert high == 3.3

    def test_full_range_at_ten_fit_zero_completeness(self):
        """Absolute worst case: score=10, half_width=3.3 → (6.7, 10.0)."""
        low, high = apply_confidence_range(fit_score=10.0, half_width=3.3)
        assert high == 10.0
        assert low == round(10.0 - 3.3, 2)


# ---------------------------------------------------------------------------
# Unit tests: missing_fields suggestions
# ---------------------------------------------------------------------------


class TestMissingFieldsSuggestions:
    def test_missing_fields_populated_below_50_percent(self, db_session):
        """When completeness < 50%, missing_fields should be non-empty."""
        _make_profile(db_session, profile_id=1, job_family="SWE")
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 15.0  # only job_family
        assert len(result["missing_fields"]) > 0

    def test_missing_fields_empty_at_50_percent(self, db_session):
        """When completeness >= 50%, missing_fields should be empty."""
        _make_profile(db_session, profile_id=1, job_family="SWE", location="Berlin")
        _add_skills(db_session, profile_id=1, count=5)
        result = compute_profile_completeness(db_session, profile_id=1)
        assert result["completeness"] == 50.0
        assert result["missing_fields"] == []

    def test_missing_fields_contain_specific_suggestions(self, db_session):
        """Missing fields should include human-readable labels, not raw keys."""
        _make_profile(db_session, profile_id=1)  # completely empty
        result = compute_profile_completeness(db_session, profile_id=1)
        # Should mention skills/goals/etc. — check for known labels
        joined = " ".join(result["missing_fields"])
        assert "skills" in joined
        assert "goal" in joined

    def test_location_missing_when_not_set(self, db_session):
        """If location is not set, it appears in missing_fields."""
        _make_profile(db_session, profile_id=1, job_family="SWE")
        result = compute_profile_completeness(db_session, profile_id=1)
        joined = " ".join(result["missing_fields"])
        assert "location" in joined

    def test_location_not_missing_when_set(self, db_session):
        """If location is set, it should not appear in missing_fields."""
        _make_profile(db_session, profile_id=1, location="Berlin")
        result = compute_profile_completeness(db_session, profile_id=1)
        joined = " ".join(result["missing_fields"])
        assert "location preference" not in joined


# ---------------------------------------------------------------------------
# Integration tests: API endpoints include profile_completeness
# ---------------------------------------------------------------------------


class TestAPIProfileCompleteness:
    def _make_discovered_job(self, db_session):
        """Create a minimal DiscoveredJob and return it."""
        from career_os.models.discovery import DiscoveredJob

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
        return dj

    def test_get_job_score_includes_profile_completeness(self, db_session, client):
        """GET /api/score/job/{id} always includes profile_completeness."""
        _make_profile(db_session, profile_id=1, job_family="SWE", location="Berlin")
        dj = self._make_discovered_job(db_session)

        sj = ScoredJob(
            profile_id=1,
            discovered_job_id=dj.id,
            fit_score=7.0,
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        db_session.add(sj)
        db_session.commit()

        resp = client.get(f"/api/score/job/{dj.id}?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile_completeness"] is not None
        pc = data["profile_completeness"]
        assert "completeness" in pc
        assert "confidence_range" in pc
        assert "missing_fields" in pc
        assert isinstance(pc["confidence_range"], list)
        assert len(pc["confidence_range"]) == 2

    def test_confidence_range_centered_on_fit_score(self, db_session, client):
        """The confidence_range should be centered around the actual fit_score."""
        _make_profile(db_session, profile_id=1)  # 0% completeness → wide range
        dj = self._make_discovered_job(db_session)

        sj = ScoredJob(
            profile_id=1,
            discovered_job_id=dj.id,
            fit_score=5.0,
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        db_session.add(sj)
        db_session.commit()

        resp = client.get(f"/api/score/job/{dj.id}?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        pc = data["profile_completeness"]
        low, high = pc["confidence_range"]

        # At 0% completeness, half_width = 3.3, centered at 5.0 → (1.7, 8.3)
        assert low == pytest.approx(5.0 - 3.3, abs=0.01)
        assert high == pytest.approx(5.0 + 3.3, abs=0.01)

    def test_improvement_hint_present_for_sparse_profile(self, db_session, client):
        """improvement_hint is populated when completeness < 50%."""
        _make_profile(db_session, profile_id=1)  # 0% completeness
        dj = self._make_discovered_job(db_session)

        sj = ScoredJob(
            profile_id=1,
            discovered_job_id=dj.id,
            fit_score=6.0,
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        db_session.add(sj)
        db_session.commit()

        resp = client.get(f"/api/score/job/{dj.id}?profile_id=1")
        assert resp.status_code == 200
        pc = resp.json()["profile_completeness"]
        assert pc["improvement_hint"] is not None
        assert "uncertainty" in pc["improvement_hint"].lower()

    def test_improvement_hint_absent_for_rich_profile(self, db_session, client):
        """improvement_hint is None when completeness >= 50%."""
        _make_profile(db_session, profile_id=1, job_family="SWE", location="Berlin")
        _add_skills(db_session, profile_id=1, count=5)
        dj = self._make_discovered_job(db_session)

        sj = ScoredJob(
            profile_id=1,
            discovered_job_id=dj.id,
            fit_score=6.0,
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        db_session.add(sj)
        db_session.commit()

        resp = client.get(f"/api/score/job/{dj.id}?profile_id=1")
        assert resp.status_code == 200
        pc = resp.json()["profile_completeness"]
        assert pc["completeness"] == 50.0
        assert pc["improvement_hint"] is None

    def test_get_application_score_includes_profile_completeness(self, db_session, client):
        """GET /api/score/application/{id} also includes profile_completeness."""
        from career_os.models.models import Application

        _make_profile(db_session, profile_id=1, job_family="SWE", location="Berlin")

        app_row = Application(
            profile_id=1,
            company="Acme",
            role="Engineer",
            status="applied",
        )
        db_session.add(app_row)
        db_session.commit()
        db_session.refresh(app_row)

        sj = ScoredJob(
            profile_id=1,
            application_id=app_row.id,
            fit_score=7.5,
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        db_session.add(sj)
        db_session.commit()

        resp = client.get(f"/api/score/application/{app_row.id}?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile_completeness"] is not None
        assert "completeness" in data["profile_completeness"]

    def test_confidence_range_bounds_within_0_10(self, db_session, client):
        """confidence_range values must always be within [0, 10]."""
        _make_profile(db_session, profile_id=1)  # 0% completeness, wide range
        dj = self._make_discovered_job(db_session)

        # Test with extreme fit_score (very low)
        sj = ScoredJob(
            profile_id=1,
            discovered_job_id=dj.id,
            fit_score=0.5,  # near 0, lower bound should clamp
            **MINIMAL_SCORED_JOB_KWARGS,
        )
        db_session.add(sj)
        db_session.commit()

        resp = client.get(f"/api/score/job/{dj.id}?profile_id=1")
        assert resp.status_code == 200
        low, high = resp.json()["profile_completeness"]["confidence_range"]
        assert low >= 0.0
        assert high <= 10.0
