"""Unit + integration tests for distillation-label logging (G-1338, finding M).

Covers the pure signal builder (known-value + edge cases), the defensive logger
(off-by-default no-op, records the right tuple, swallows failures), the feedback
backfill, and the score_job / submit_feedback wiring — all on the mock provider,
no paid LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.config import settings
from career_os.database import Base
from career_os.models.models import Profile
from career_os.models.scoring import DistillationSample, ScoredJob
from career_os.schemas.ai import (
    ATSKeyword,
    DimensionalScores,
    RoleMatch,
    ScoreBreakdownFactor,
    ScoreResult,
)
from career_os.services.distillation import (
    build_distillation_signals,
    get_distillation_samples,
    log_distillation_sample,
    record_distillation_feedback,
)
from career_os.services.scoring import score_job, submit_feedback


def _make_score_result(
    fit_score: float = 8.0,
    *,
    desire_score: float | None = 6.0,
    role_match: RoleMatch | None = None,
    disqualifiers: list[str] | None = None,
    dims: bool = True,
) -> ScoreResult:
    """Build a valid ScoreResult with known structured signals."""
    return ScoreResult(
        role_match=role_match,
        disqualifiers=disqualifiers or [],
        fit_score=fit_score,
        readiness_score=72.0,
        career_alignment=7.5,
        reasoning="Test reasoning",
        estimated_salary="$100k-$120k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Prep note",
        score_breakdown=[
            ScoreBreakdownFactor(factor="skills_match", contribution=2.0, description="Good"),
            ScoreBreakdownFactor(
                factor="career_alignment", contribution=1.5, description="Aligned"
            ),
            ScoreBreakdownFactor(factor="culture_fit", contribution=1.0, description="Ok"),
        ],
        dimensional_scores=DimensionalScores(
            technical_fit=9.0,
            seniority_alignment=8.0,
            compensation_fit=7.0,
            location_fit=6.0,
            career_trajectory=8.5,
            company_fit=9.5,
        )
        if dims
        else None,
        ats_keywords=[
            ATSKeyword(keyword="Python", category="technical", matched=True),
            ATSKeyword(keyword="FastAPI", category="tool", matched=True),
        ],
        desire_score=desire_score,
        desire_reasoning="Desirable" if desire_score is not None else None,
    )


@pytest.fixture
def db_session() -> Session:
    """Fresh in-memory SQLite session seeded with a scorable profile."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    session.add(
        Profile(id=1, name="Test User", email="t@example.com", location="Berlin", job_family="TPM")
    )
    session.commit()
    yield session
    session.close()
    connection.close()
    engine.dispose()


@pytest.fixture
def enable_distillation(monkeypatch):
    """Turn the (off-by-default) distillation flag on for a test."""
    monkeypatch.setattr(settings, "distillation_logging_enabled", True)


# ---------------------------------------------------------------------------
# build_distillation_signals — pure, known-value
# ---------------------------------------------------------------------------


def test_build_signals_known_values():
    result = _make_score_result(
        fit_score=8.0, role_match=RoleMatch(is_same_role_family=True, evidence="PM≈PM")
    )
    profile_data = {"job_family": "TPM", "weights": {"skills_match": 0.25}}

    signals = build_distillation_signals(result, profile_data)

    assert signals["dimensional_scores"]["technical_fit"] == 9.0
    assert signals["dimensional_scores"]["company_fit"] == 9.5
    assert signals["role_match"] == {"is_same_role_family": True, "evidence": "PM≈PM"}
    assert signals["role_fit_gate_failed"] is False
    assert signals["disqualifiers"] == []
    assert signals["readiness_score"] == 72.0
    assert signals["career_alignment"] == 7.5
    assert signals["effort_flag"] == "medium"
    assert signals["ats_keyword_count"] == 2
    assert signals["job_family"] == "TPM"
    assert signals["weights"] == {"skills_match": 0.25}


def test_build_signals_gate_failed_flag():
    """A role-family mismatch flips role_fit_gate_failed True."""
    result = _make_score_result(role_match=RoleMatch(is_same_role_family=False, evidence="SWE≠PM"))
    signals = build_distillation_signals(result, {})
    assert signals["role_fit_gate_failed"] is True


def test_build_signals_disqualifiers_flag():
    result = _make_score_result(disqualifiers=["missing clearance"])
    signals = build_distillation_signals(result, {})
    assert signals["role_fit_gate_failed"] is True
    assert signals["disqualifiers"] == ["missing clearance"]


def test_build_signals_handles_missing_dims_and_profile():
    result = _make_score_result(dims=False)
    signals = build_distillation_signals(result, None)
    assert signals["dimensional_scores"] is None
    assert signals["role_match"] is None
    assert signals["job_family"] is None
    assert signals["weights"] is None


def test_build_signals_merges_extra():
    """extra signals (e.g. ESCO overlap from finding L) merge in."""
    result = _make_score_result()
    signals = build_distillation_signals(result, {}, extra={"esco_skills_overlap": 0.75})
    assert signals["esco_skills_overlap"] == 0.75


# ---------------------------------------------------------------------------
# log_distillation_sample — flag gating, tuple contents, defensiveness
# ---------------------------------------------------------------------------


def test_log_off_by_default_is_noop(db_session):
    """Flag defaults off → no row written, returns None."""
    assert settings.distillation_logging_enabled is False
    out = log_distillation_sample(
        db_session, profile_id=1, score_result=_make_score_result(), profile_data={}
    )
    assert out is None
    assert db_session.query(DistillationSample).count() == 0


def test_log_records_the_right_tuple(db_session, enable_distillation):
    result = _make_score_result(fit_score=8.0, desire_score=6.0)
    sample = log_distillation_sample(
        db_session,
        profile_id=1,
        score_result=result,
        profile_data={"job_family": "TPM", "weights": {}},
        rubric_version="v1.1",
    )
    assert sample is not None
    assert sample.fit_score == 8.0
    assert sample.desire_score == 6.0
    # fit 8 + desire 6 → both high → "dream_job" quadrant (threshold 5.0)
    assert sample.quadrant is not None
    assert sample.rubric_version == "v1.1"
    assert '"technical_fit": 9.0' in sample.signals
    assert sample.feedback_direction is None

    assert db_session.query(DistillationSample).count() == 1


def test_log_prefers_persisted_desire_over_result(db_session, enable_distillation):
    """WR-02: when the model omits desire_score, the derived value persisted to
    ScoredJob is what gets logged (and drives the quadrant), not None."""
    from career_os.schemas.scoring import classify_quadrant

    result = _make_score_result(fit_score=8.0, desire_score=None)  # model omitted desire
    assert result.desire_score is None

    sample = log_distillation_sample(
        db_session,
        profile_id=1,
        score_result=result,
        profile_data={},
        persisted_desire_score=6.5,  # the value derived + persisted to ScoredJob
    )
    assert sample is not None
    assert sample.desire_score == 6.5  # persisted value, not the result's None
    # Quadrant reflects the persisted desire (fit 8 + desire 6.5), not None.
    assert sample.quadrant == classify_quadrant(8.0, 6.5)
    assert sample.quadrant is not None


def test_log_falls_back_to_result_desire_when_no_override(db_session, enable_distillation):
    """Back-compat: absent an override, the result's own desire_score is used."""
    result = _make_score_result(fit_score=8.0, desire_score=6.0)
    sample = log_distillation_sample(db_session, profile_id=1, score_result=result, profile_data={})
    assert sample is not None
    assert sample.desire_score == 6.0


def test_log_defensive_on_failure_returns_none(db_session, enable_distillation):
    """A DB failure (bad FK) is swallowed — returns None, never raises."""
    # profile_id 99999 does not exist → FK violation on commit (PRAGMA FK=ON).
    out = log_distillation_sample(
        db_session, profile_id=99999, score_result=_make_score_result(), profile_data={}
    )
    assert out is None
    # Session recovered (rolled back) — still usable.
    assert db_session.query(DistillationSample).count() == 0


# ---------------------------------------------------------------------------
# record_distillation_feedback — backfill
# ---------------------------------------------------------------------------


def test_feedback_backfill_off_is_noop(db_session):
    assert (
        record_distillation_feedback(
            db_session, scored_job_id=1, profile_id=1, direction="too_high"
        )
        == 0
    )


def test_feedback_backfill_updates_sample(db_session, enable_distillation):
    scored = ScoredJob(profile_id=1, fit_score=8.0, reasoning="r")
    db_session.add(scored)
    db_session.commit()
    log_distillation_sample(
        db_session,
        profile_id=1,
        score_result=_make_score_result(),
        profile_data={},
        scored_job_id=scored.id,
    )
    sample = db_session.query(DistillationSample).one()

    updated = record_distillation_feedback(
        db_session, scored_job_id=scored.id, profile_id=1, direction="too_low", user_score=4.0
    )
    assert updated == 1
    db_session.refresh(sample)
    assert sample.feedback_direction == "too_low"
    assert sample.feedback_user_score == 4.0


def test_feedback_backfill_scoped_by_profile(db_session, enable_distillation):
    """A mismatched profile_id must not touch another profile's sample."""
    db_session.add(Profile(id=2, name="V", email="v@example.com", location="X", job_family="TPM"))
    scored = ScoredJob(profile_id=1, fit_score=8.0, reasoning="r")
    db_session.add(scored)
    db_session.commit()
    log_distillation_sample(
        db_session,
        profile_id=1,
        score_result=_make_score_result(),
        profile_data={},
        scored_job_id=scored.id,
    )
    # Wrong profile → no rows match → 0 updated, sample untouched.
    updated = record_distillation_feedback(
        db_session, scored_job_id=scored.id, profile_id=2, direction="too_low"
    )
    assert updated == 0
    sample = db_session.query(DistillationSample).one()
    assert sample.feedback_direction is None


# ---------------------------------------------------------------------------
# score_job wiring — off-by-default identity + on-writes-one
# ---------------------------------------------------------------------------


def _patch_provider(fit_score: float = 8.0):
    result = _make_score_result(fit_score=fit_score)
    resp = MagicMock()
    resp.structured = result
    provider = AsyncMock()
    provider.score.return_value = resp
    provider.name = "mock"
    return provider


@pytest.mark.asyncio
async def test_score_job_off_by_default_writes_no_sample(db_session, monkeypatch):
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    assert settings.distillation_logging_enabled is False
    with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider()):
        await score_job(db_session, profile_id=1, job_description="TPM role", job_title="TPM")
    assert db_session.query(DistillationSample).count() == 0


@pytest.mark.asyncio
async def test_score_job_logs_sample_when_enabled(db_session, monkeypatch, enable_distillation):
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)):
        scored = await score_job(
            db_session, profile_id=1, job_description="TPM role", job_title="TPM"
        )
    samples = db_session.query(DistillationSample).all()
    assert len(samples) == 1
    assert samples[0].scored_job_id == scored.id
    assert samples[0].fit_score == scored.fit_score
    assert samples[0].rubric_version == "v1.1"


@pytest.mark.asyncio
async def test_score_job_logs_derived_desire_matching_persisted(
    db_session, monkeypatch, enable_distillation
):
    """WR-02 end-to-end: when the model OMITS desire_score, score_job derives it,
    persists it to ScoredJob, and the distillation tuple logs that SAME non-None
    desire + quadrant — not None."""
    from career_os.schemas.scoring import classify_quadrant

    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)

    # Provider returns a result with desire_score=None but dims present → derived.
    result = _make_score_result(fit_score=8.0, desire_score=None, dims=True)
    assert result.desire_score is None
    resp = MagicMock()
    resp.structured = result
    provider = AsyncMock()
    provider.score.return_value = resp
    provider.name = "mock"

    with patch("career_os.services.scoring.get_ai_provider", return_value=provider):
        scored = await score_job(
            db_session, profile_id=1, job_description="TPM role", job_title="TPM"
        )

    # Desire was derived + persisted (non-None) on the ScoredJob.
    assert scored.desire_score is not None
    assert scored.desire_score_method == "derived"

    sample = db_session.query(DistillationSample).filter_by(scored_job_id=scored.id).one()
    # The training tuple must reflect the PERSISTED derived desire, not None.
    assert sample.desire_score == scored.desire_score
    assert sample.desire_score is not None
    assert sample.quadrant == classify_quadrant(scored.fit_score, scored.desire_score)


@pytest.mark.asyncio
async def test_score_job_survives_mid_path_logging_failure(
    db_session, monkeypatch, enable_distillation
):
    """With logging ENABLED, if the sample write FAILS during score_job, the
    returned + persisted ScoredJob score must be intact (in-path guarantee)."""
    from sqlalchemy import text

    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    # Break the distillation write mid-path: drop the table so the INSERT fails.
    db_session.execute(text("DROP TABLE distillation_samples"))
    db_session.commit()

    with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)):
        scored = await score_job(
            db_session, profile_id=1, job_description="TPM role", job_title="TPM"
        )

    # Score returned intact despite the logging failure...
    assert scored.fit_score == 8.0
    # ...and it is actually persisted (survives the defensive rollback).
    persisted = db_session.query(ScoredJob).filter_by(id=scored.id).one()
    assert persisted.fit_score == 8.0


@pytest.mark.asyncio
async def test_submit_feedback_backfills_sample(db_session, monkeypatch, enable_distillation):
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)):
        scored = await score_job(
            db_session, profile_id=1, job_description="TPM role", job_title="TPM"
        )

    submit_feedback(
        db_session, scored_job_id=scored.id, profile_id=1, direction="too_high", user_score=5.0
    )
    sample = db_session.query(DistillationSample).filter_by(scored_job_id=scored.id).one()
    assert sample.feedback_direction == "too_high"
    assert sample.feedback_user_score == 5.0


def test_get_distillation_samples_reads_newest_first(db_session, enable_distillation):
    for fs in (3.0, 9.0):
        log_distillation_sample(
            db_session, profile_id=1, score_result=_make_score_result(fit_score=fs), profile_data={}
        )
    out = get_distillation_samples(db_session, 1)
    assert len(out) == 2
