"""Unit tests for per-provider score calibration (G-1337, finding G).

Covers the isotonic (PAV) fit + apply on synthetic data with known behavior,
identity when the feature is off / unregistered, the sample-count guard, and a
cross-check of the fit against scikit-learn as a dev-only oracle.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob, ScoringFeedback
from career_os.schemas.ai import (
    ATSKeyword,
    DimensionalScores,
    RoleMatch,
    ScoreBreakdownFactor,
    ScoreResult,
)
from career_os.services.scoring import score_job
from career_os.services.scoring_calibration import (
    MIN_CALIBRATION_SAMPLES,
    IsotonicCalibrator,
    apply_calibration_and_gate,
    apply_provider_calibration,
    clear_calibrators,
    fit_from_feedback,
    fit_isotonic,
    get_calibrator,
    register_calibrator,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test starts and ends with an empty calibrator registry."""
    clear_calibrators()
    yield
    clear_calibrators()


# ---------------------------------------------------------------------------
# Isotonic fit
# ---------------------------------------------------------------------------


def test_fit_recovers_monotone_shift():
    """A raw scale that is uniformly 2 points low calibrates up by ~2."""
    raw = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    target = [r + 2.0 if r + 2.0 <= 10 else 10.0 for r in raw]
    cal = fit_isotonic(raw, target)
    assert cal is not None
    # Exactly-fit knots reproduce the targets.
    assert cal.predict(3.0) == pytest.approx(5.0)
    assert cal.predict(6.0) == pytest.approx(8.0)
    # Interpolates between knots.
    assert cal.predict(3.5) == pytest.approx(5.5)


def test_fit_is_monotonic_nondecreasing():
    """The fitted map never decreases as the raw score rises (isotonic constraint)."""
    raw = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    # Deliberately non-monotone targets — PAV must pool the violators.
    target = [2.0, 1.0, 4.0, 3.0, 6.0, 5.0, 9.0, 8.0]
    cal = fit_isotonic(raw, target)
    assert cal is not None
    xs = [i / 2 for i in range(0, 21)]  # 0.0 .. 10.0
    preds = [cal.predict(x) for x in xs]
    for a, b in zip(preds, preds[1:], strict=False):
        assert b >= a - 1e-9, f"map decreased: {a} -> {b}"


def test_fit_clamps_output_to_display_axis():
    """Predictions are clamped to [0, 10] even when targets/inputs exceed it."""
    raw = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    target = [0.0, 1.5, 3.0, 4.5, 6.0, 7.5, 9.0, 11.0]  # last target out of range
    cal = fit_isotonic(raw, target)
    assert cal is not None
    assert cal.predict(7.0) == pytest.approx(10.0)  # clamped from 11
    assert cal.predict(100.0) == 10.0  # clip beyond range + clamp
    assert cal.predict(-5.0) == pytest.approx(0.0)


def test_fit_averages_ties():
    """Duplicate raw values are averaged before the isotonic fit."""
    raw = [5.0, 5.0, 5.0, 1.0, 1.0, 9.0, 9.0, 3.0]
    target = [4.0, 6.0, 5.0, 1.0, 1.0, 9.0, 9.0, 3.0]  # raw=5 → mean target 5.0
    cal = fit_isotonic(raw, target)
    assert cal is not None
    assert cal.predict(5.0) == pytest.approx(5.0)


def test_fit_returns_none_below_min_samples():
    """Too few labels → no calibrator (avoid overfitting noise)."""
    n = MIN_CALIBRATION_SAMPLES - 1
    assert fit_isotonic([float(i) for i in range(n)], [float(i) for i in range(n)]) is None


def test_fit_length_mismatch_raises():
    with pytest.raises(ValueError):
        fit_isotonic([1.0, 2.0], [1.0])


def test_fit_matches_sklearn_oracle():
    sk = pytest.importorskip("sklearn.isotonic")
    raw = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    target = [1.0, 3.0, 2.0, 4.0, 6.0, 5.0, 7.0, 9.0, 8.0, 10.0]
    ours = fit_isotonic(raw, target)
    assert ours is not None
    ir = sk.IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=10.0)
    ir.fit(raw, target)
    for x in [1.0, 2.5, 4.0, 5.5, 7.0, 8.5, 10.0]:
        assert ours.predict(x) == pytest.approx(float(ir.predict([x])[0]), abs=1e-6)


# ---------------------------------------------------------------------------
# Apply + registry + flag gating
# ---------------------------------------------------------------------------


def test_apply_identity_when_disabled():
    """enabled=False → raw score passes through untouched, even with a calibrator."""
    cal = IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(2.0, 8.0))
    register_calibrator("mistral", cal)
    assert apply_provider_calibration("mistral", 5.0, enabled=False) == 5.0


def test_apply_identity_when_provider_unregistered():
    """enabled=True but no calibrator for the provider → identity."""
    assert apply_provider_calibration("openrouter", 7.3, enabled=True) == 7.3


def test_apply_uses_registered_calibrator():
    """enabled=True + registered calibrator → mapped value."""
    cal = IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(0.0, 5.0))  # halve the scale
    register_calibrator("mistral", cal)
    assert get_calibrator("mistral") is cal
    assert apply_provider_calibration("mistral", 8.0, enabled=True) == pytest.approx(4.0)


def test_calibrator_predict_flat_extrapolation():
    """Beyond the fitted range the map holds flat at the end knots."""
    cal = IsotonicCalibrator(knot_x=(2.0, 8.0), knot_y=(3.0, 9.0))
    assert cal.predict(0.0) == pytest.approx(3.0)  # below first knot
    assert cal.predict(10.0) == pytest.approx(9.0)  # above last knot
    assert cal.predict(5.0) == pytest.approx(6.0)  # midpoint interp


def test_empty_calibrator_is_identity_clamped():
    cal = IsotonicCalibrator(knot_x=(), knot_y=())
    assert cal.predict(6.0) == pytest.approx(6.0)
    assert cal.predict(12.0) == 10.0


# ---------------------------------------------------------------------------
# apply_calibration_and_gate — the shared post-processing tail (WR-04)
# ---------------------------------------------------------------------------


def _gate_result(fit_score: float, *, mismatch: bool = False) -> ScoreResult:
    role_match = RoleMatch(is_same_role_family=False, evidence="x") if mismatch else None
    return ScoreResult(
        role_match=role_match,
        fit_score=fit_score,
        reasoning="A" * 120,
        estimated_salary="$150k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="p",
        readiness_score=80.0,
        career_alignment=8.0,
        score_breakdown=[
            ScoreBreakdownFactor(factor="a", contribution=1.0, description="d"),
            ScoreBreakdownFactor(factor="b", contribution=1.0, description="d"),
            ScoreBreakdownFactor(factor="c", contribution=1.0, description="d"),
        ],
    )


def test_helper_calibrates_then_gates():
    """Calibration is applied, then the gate — for a non-mismatch it's just the map."""
    register_calibrator("mock", IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(0.0, 5.0)))
    out = apply_calibration_and_gate(_gate_result(8.0), "mock", calibration_enabled=True)
    assert out.fit_score == pytest.approx(4.0)


def test_helper_disabled_is_identity():
    """Calibration disabled → only the (idempotent) gate runs; fit untouched."""
    register_calibrator("mock", IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(0.0, 5.0)))
    out = apply_calibration_and_gate(_gate_result(8.0), "mock", calibration_enabled=False)
    assert out.fit_score == pytest.approx(8.0)


def test_helper_gate_wins_over_calibration():
    """A calibrator that inflates a role-mismatched score can't beat the gate."""
    register_calibrator("mock", IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(9.0, 10.0)))
    out = apply_calibration_and_gate(
        _gate_result(8.0, mismatch=True), "mock", calibration_enabled=True
    )
    assert out.fit_score == pytest.approx(3.0)


def test_helper_defaults_enabled_from_settings(monkeypatch):
    """calibration_enabled defaults to settings.scoring_calibration_enabled."""
    from career_os.config import settings

    register_calibrator("mock", IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(0.0, 5.0)))
    monkeypatch.setattr(settings, "scoring_calibration_enabled", True)
    out = apply_calibration_and_gate(_gate_result(8.0), "mock")
    assert out.fit_score == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Fit from stored feedback (DB path, no paid ops)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Session:
    """Fresh in-memory SQLite session with a seeded TPM profile."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    session.add(Profile(id=1, name="T", email="t@example.com", location="Berlin", job_family="TPM"))
    session.commit()
    yield session
    session.close()
    connection.close()
    engine.dispose()


def _seed_feedback(db: Session, pairs: list[tuple[float, float]]) -> None:
    """Seed ScoredJob + ScoringFeedback rows: (original_fit_score, user_score)."""
    for raw, user in pairs:
        sj = ScoredJob(profile_id=1, fit_score=raw, reasoning="seed")
        db.add(sj)
        db.flush()
        db.add(
            ScoringFeedback(
                scored_job_id=sj.id,
                profile_id=1,
                direction="too_low" if user > raw else "too_high",
                user_score=user,
                original_fit_score=raw,
            )
        )
    db.commit()


def test_fit_from_feedback_builds_calibrator(db_session):
    """Enough labeled corrections → a fitted calibrator from stored data (no LLM)."""
    # AI consistently scores ~2 low; user corrects up.
    pairs = [(float(r), min(r + 2.0, 10.0)) for r in range(1, 10)]
    _seed_feedback(db_session, pairs)
    cal = fit_from_feedback(db_session, profile_id=1)
    assert cal is not None
    assert cal.predict(5.0) == pytest.approx(7.0, abs=1e-6)


def test_fit_from_feedback_none_when_too_few(db_session):
    """Below MIN_CALIBRATION_SAMPLES corrections → None (fall back to identity)."""
    _seed_feedback(db_session, [(float(r), float(r)) for r in range(MIN_CALIBRATION_SAMPLES - 1)])
    assert fit_from_feedback(db_session, profile_id=1) is None


def test_fit_from_feedback_ignores_null_user_score(db_session):
    """Corrections without a user_score are not usable labels and are skipped."""
    # Only 3 with user_score, rest null → below threshold → None.
    _seed_feedback(db_session, [(5.0, 7.0), (6.0, 8.0), (4.0, 6.0)])
    for _ in range(MIN_CALIBRATION_SAMPLES):
        sj = ScoredJob(profile_id=1, fit_score=5.0, reasoning="seed")
        db_session.add(sj)
        db_session.flush()
        db_session.add(
            ScoringFeedback(
                scored_job_id=sj.id,
                profile_id=1,
                direction="correct",
                user_score=None,
                original_fit_score=5.0,
            )
        )
    db_session.commit()
    assert fit_from_feedback(db_session, profile_id=1) is None


# ---------------------------------------------------------------------------
# score_job integration — flag gating + gate precedence
# ---------------------------------------------------------------------------


def _score_result(fit_score: float, *, role_match: RoleMatch | None = None) -> ScoreResult:
    return ScoreResult(
        role_match=role_match,
        fit_score=fit_score,
        readiness_score=80.0,
        career_alignment=8.0,
        reasoning="A" * 120,
        estimated_salary="$150k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="p",
        score_breakdown=[
            ScoreBreakdownFactor(factor="a", contribution=1.0, description="d"),
            ScoreBreakdownFactor(factor="b", contribution=1.0, description="d"),
            ScoreBreakdownFactor(factor="c", contribution=1.0, description="d"),
        ],
        dimensional_scores=DimensionalScores(
            technical_fit=8.0,
            seniority_alignment=8.0,
            compensation_fit=8.0,
            location_fit=8.0,
            career_trajectory=8.0,
            company_fit=8.0,
        ),
        ats_keywords=[ATSKeyword(keyword="Python", category="technical", matched=True)],
        desire_score=8.0,
        desire_reasoning="d",
    )


def _mock_settings(*, calibration_enabled: bool) -> MagicMock:
    s = MagicMock()
    s.feedback_calibration_enabled = False
    s.borderline_scoring_enabled = False
    s.borderline_low_threshold = 4.0
    s.borderline_high_threshold = 6.5
    s.scoring_calibration_enabled = calibration_enabled
    s.scoring_shadow_variant = ""
    return s


async def _run_score_job(db, provider, settings_mock):
    with (
        patch("career_os.services.scoring.get_ai_provider", return_value=provider),
        patch("career_os.services.scoring.settings", settings_mock),
    ):
        return await score_job(
            db, profile_id=1, job_description="TPM role", job_title="TPM", job_company="Acme"
        )


@pytest.mark.asyncio
async def test_score_job_calibration_off_is_noop(db_session):
    """Flag off → raw fit_score persists untouched even with a registered calibrator."""
    register_calibrator("mock-x", IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(0.0, 5.0)))
    provider = AsyncMock()
    provider.name = "mock-x"
    provider.score.return_value = MagicMock(structured=_score_result(8.0))
    scored = await _run_score_job(db_session, provider, _mock_settings(calibration_enabled=False))
    assert scored.fit_score == pytest.approx(8.0)


@pytest.mark.asyncio
async def test_score_job_calibration_on_applies_map(db_session):
    """Flag on + registered calibrator → persisted fit_score is the calibrated value."""
    register_calibrator("mock-x", IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(0.0, 5.0)))
    provider = AsyncMock()
    provider.name = "mock-x"
    provider.score.return_value = MagicMock(structured=_score_result(8.0))
    scored = await _run_score_job(db_session, provider, _mock_settings(calibration_enabled=True))
    # Map halves the axis: 8.0 → 4.0.
    assert scored.fit_score == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_score_job_calibration_on_but_unregistered_is_noop(db_session):
    """Flag on but no calibrator for this provider → identity."""
    provider = AsyncMock()
    provider.name = "unregistered-provider"
    provider.score.return_value = MagicMock(structured=_score_result(7.0))
    scored = await _run_score_job(db_session, provider, _mock_settings(calibration_enabled=True))
    assert scored.fit_score == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_role_fit_gate_wins_over_calibration(db_session):
    """A calibrator that would RAISE a role-mismatched score cannot beat the gate."""
    # Map lifts everything toward 9-10; the gate must still cap at 3.0.
    register_calibrator("mock-x", IsotonicCalibrator(knot_x=(0.0, 10.0), knot_y=(9.0, 10.0)))
    provider = AsyncMock()
    provider.name = "mock-x"
    provider.score.return_value = MagicMock(
        structured=_score_result(8.0, role_match=RoleMatch(is_same_role_family=False, evidence="x"))
    )
    scored = await _run_score_job(db_session, provider, _mock_settings(calibration_enabled=True))
    assert scored.fit_score == pytest.approx(3.0)
