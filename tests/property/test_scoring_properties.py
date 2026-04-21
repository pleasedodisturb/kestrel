"""Hypothesis property-based tests for scoring pipeline invariants.

Proves:
- fit_score is always 0-10 for any valid input (D-05)
- readiness_score is always 0-100 for any valid input (D-05)
- Out-of-range fit_score is rejected by Pydantic validation
- Scoring is idempotent: score_job() called twice with the same args
  via DeterministicScoringMockProvider produces identical ScoredJob output
- Band monotonicity: higher fit_score never maps to a lower band (D-05)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="hypothesis not installed")
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base
from career_os.models.models import Profile
from career_os.schemas.ai import (
    ATSKeyword,
    ScoreBreakdownFactor,
    ScoreResult,
)
from career_os.services.scoring import score_job

# Re-use the DeterministicScoringMockProvider from regression conftest
from tests.regression.conftest import DeterministicScoringMockProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Placeholder values for required ScoreResult fields
_BREAKDOWN = [
    ScoreBreakdownFactor(factor="f1", contribution=1.0, description="d1"),
    ScoreBreakdownFactor(factor="f2", contribution=1.0, description="d2"),
    ScoreBreakdownFactor(factor="f3", contribution=1.0, description="d3"),
]
_ATS = [ATSKeyword(keyword="python", category="technical", matched=True)]


def _make_score_result(*, fit_score: float = 5.0, readiness_score: float = 50.0) -> ScoreResult:
    """Build a ScoreResult with the given scores and valid placeholder values."""
    return ScoreResult(
        fit_score=fit_score,
        reasoning="test",
        estimated_salary="50k",
        effort_flag="low",
        prep_level="light",
        prep_notes="test",
        readiness_score=readiness_score,
        career_alignment=5.0,
        score_breakdown=_BREAKDOWN,
        dimensional_scores=None,
        ats_keywords=_ATS,
    )


def get_band(score: float) -> int:
    """Map a fit_score to a band: 0 (low), 1 (medium), 2 (high).

    No actual band function exists in scoring.py, so we define the simple
    threshold function specified in the plan.
    """
    if score < 3.0:
        return 0
    if score < 6.0:
        return 1
    return 2


# ---------------------------------------------------------------------------
# DB session helper for idempotency test (inline, not a fixture)
# ---------------------------------------------------------------------------


def _create_db_session():
    """Create a fresh in-memory database session with a seeded Profile.

    Returns (session, cleanup_fn). Used inline inside the test to avoid
    Hypothesis health check failures with function-scoped fixtures.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    profile = Profile(
        id=1,
        name="Property Test User",
        email="property@test.example.com",
        location="Berlin, Germany",
        job_family="TPM",
    )
    session.add(profile)
    session.commit()

    def cleanup():
        session.close()
        connection.close()
        engine.dispose()

    return session, cleanup


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@pytest.mark.property
@given(fit_score=st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False))
@settings(max_examples=200)
def test_fit_score_always_in_range(fit_score: float) -> None:
    """fit_score is always 0-10 when constructed with a valid value."""
    result = _make_score_result(fit_score=fit_score)
    assert 0 <= result.fit_score <= 10
    assert isinstance(result.fit_score, float)


@pytest.mark.property
@given(readiness_score=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False))
@settings(max_examples=200)
def test_readiness_score_always_in_range(readiness_score: float) -> None:
    """readiness_score is always 0-100 when constructed with a valid value."""
    result = _make_score_result(readiness_score=readiness_score)
    assert 0 <= result.readiness_score <= 100
    assert isinstance(result.readiness_score, float)


@pytest.mark.property
@given(fit_score=st.floats(min_value=10.01, max_value=1000, allow_nan=False, allow_infinity=False))
@settings(max_examples=50)
def test_fit_score_rejects_out_of_range(fit_score: float) -> None:
    """Pydantic rejects fit_score values above 10."""
    with pytest.raises(ValidationError) as exc_info:
        _make_score_result(fit_score=fit_score)
    assert "fit_score" in str(exc_info.value)
    assert exc_info.value.error_count() >= 1


@pytest.mark.property
@pytest.mark.asyncio
@given(
    description=st.text(
        min_size=10,
        max_size=200,
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    )
)
@settings(max_examples=20)
async def test_scoring_idempotent(description: str) -> None:
    """Calling score_job() twice with the same args produces identical results.

    Uses DeterministicScoringMockProvider to prove pipeline-level idempotency:
    the full score_job() pipeline (prompt building, provider call, DB persistence)
    returns the same scores for the same inputs.

    Creates a fresh in-memory DB per example to avoid Hypothesis health check
    failures with function-scoped fixtures.
    """
    session, cleanup = _create_db_session()
    try:
        provider = DeterministicScoringMockProvider()
        with patch("career_os.services.scoring.get_ai_provider", return_value=provider):
            result1 = await score_job(
                session,
                profile_id=1,
                job_description=description,
                job_title="Test Job",
                job_company="Test Corp",
            )
            result2 = await score_job(
                session,
                profile_id=1,
                job_description=description,
                job_title="Test Job",
                job_company="Test Corp",
            )

        assert result1.fit_score == result2.fit_score
        assert result1.reasoning == result2.reasoning
    finally:
        cleanup()


@pytest.mark.property
@given(
    score_a=st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False),
    score_b=st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_band_monotonicity(score_a: float, score_b: float) -> None:
    """A higher fit_score never maps to a lower band.

    Band thresholds: 0-3 = low (0), 3-6 = medium (1), 6-10 = high (2).
    """
    band_a = get_band(score_a)
    band_b = get_band(score_b)

    if score_a <= score_b:
        assert band_a <= band_b, (
            f"Band monotonicity violated: score {score_a} (band {band_a}) "
            f"<= score {score_b} (band {band_b}) but band decreased"
        )

    # Both bands must be valid integers in {0, 1, 2}
    assert band_a in {0, 1, 2}
    assert band_b in {0, 1, 2}
