"""Real-caller-path integration tests for the occupation signal (G-1351 Phase C).

Covers the second half of Phase C (Task 2):

  * the occupation match tier surfaces in distillation ``extra_signals`` under
    an ``occupation`` key when logging is enabled — through the REAL
    ``score_job`` caller path (not a direct call to ``match_occupation``);
  * running ``score_job`` across >=4 distinct (job_family, JD-title) pairs
    yields >=2 DISTINCT occupation tiers — the "4a inert axis" regression
    guard proving the signal is not constant;
  * an unresolved pair logs ``match="unknown"`` with ``score is None``, never
    the fake ``0.0``;
  * the non-fatal startup populate step swallows a populate failure so the app
    still starts.

All on the mock provider — zero paid LLM calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.config import settings
from career_os.database import Base
from career_os.models.models import Profile
from career_os.models.scoring import DistillationSample
from career_os.schemas.ai import (
    ATSKeyword,
    DimensionalScores,
    ScoreBreakdownFactor,
    ScoreResult,
)
from career_os.services.occupation_taxonomy import populate_occupations
from career_os.services.scoring import score_job

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Session:
    """Fresh in-memory SQLite session, occupations taxonomy populated."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    populate_occupations(session)
    yield session
    session.close()
    connection.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def _distillation_flags(monkeypatch):
    """Enable distillation logging, disable unrelated features (per test_distillation.py)."""
    monkeypatch.setattr(settings, "distillation_logging_enabled", True)
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)


def _make_profile(db: Session, *, profile_id: int, job_family: str) -> Profile:
    profile = Profile(
        id=profile_id,
        name=f"Test User {profile_id}",
        email=f"t{profile_id}@example.com",
        location="Berlin",
        job_family=job_family,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _make_score_result(fit_score: float = 8.0) -> ScoreResult:
    return ScoreResult(
        fit_score=fit_score,
        readiness_score=70.0,
        career_alignment=7.0,
        reasoning="reason",
        estimated_salary="$100k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="notes",
        desire_score=6.0,
        score_breakdown=[
            ScoreBreakdownFactor(factor="a", contribution=1.0, description="x"),
            ScoreBreakdownFactor(factor="b", contribution=1.0, description="y"),
            ScoreBreakdownFactor(factor="c", contribution=1.0, description="z"),
        ],
        dimensional_scores=DimensionalScores(
            technical_fit=8.0,
            seniority_alignment=8.0,
            compensation_fit=7.0,
            location_fit=6.0,
            career_trajectory=8.0,
            company_fit=7.0,
        ),
        ats_keywords=[ATSKeyword(keyword="k", category="technical", matched=True)],
    )


def _patch_provider(fit_score: float = 8.0):
    """Mirrors tests/test_distillation.py's `_patch_provider` (mock AI, no LLM cost)."""
    resp = MagicMock()
    resp.structured = _make_score_result(fit_score=fit_score)
    provider = AsyncMock()
    provider.score.return_value = resp
    provider.name = "mock"
    return provider


# Real overlay job_family codes (career_os.services.occupation_matcher
# FAMILY_OCCUPATION_OVERLAY) paired with JD titles that resolve to distinct
# tiers against the real bundled ESCO occupations fixture — the conftest
# default job_family "Software Engineering" is NOT an overlay key, so these
# are set explicitly per the plan's <interfaces> note.
_FAMILY_TITLE_PAIRS: list[tuple[str, str]] = [
    ("SWE", "Software Developer"),  # -> same_occupation
    ("TPM", "ICT Project Manager"),  # -> same_occupation
    ("Product Manager", "Data Analyst"),  # -> no_match
    ("Data Scientist", "Registered Nurse"),  # -> unknown (title unresolved)
    # G-1351 review F6: a 5th pair that resolves same_isco_group through the
    # REAL score_job path — "data scientist" and "data analyst" are distinct
    # ESCO occupations sharing ISCO unit group 2511 (verified in Phase B's
    # own test_match_occupation_same_isco_group_data_scientist_vs_data_analyst).
    ("Data Scientist", "Data Analyst"),  # -> same_isco_group
]


# ---------------------------------------------------------------------------
# Non-constancy: score_job across >=4 pairs yields >=2 distinct tiers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_occupation_signal_non_inert_across_real_caller_path(db_session):
    """The 4a inert-axis regression guard: occupation must vary, not be constant.

    Scores >=4 distinct (job_family, JD-title) pairs through the REAL
    `score_job` caller path and reads each DistillationSample's
    `signals["occupation"]["match"]` — proving the signal produced by the live
    pipeline (not a direct match_occupation() call) is genuinely non-constant.
    """
    observed_tiers: set[str] = set()

    for i, (family, title) in enumerate(_FAMILY_TITLE_PAIRS, start=1):
        profile = _make_profile(db_session, profile_id=i, job_family=family)
        with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)):
            scored = await score_job(
                db_session,
                profile_id=profile.id,
                job_description=f"{title} role",
                job_title=title,
            )
        sample = db_session.query(DistillationSample).filter_by(scored_job_id=scored.id).one()
        signals = json.loads(sample.signals)
        assert "occupation" in signals
        observed_tiers.add(signals["occupation"]["match"])

    assert len(observed_tiers) >= 2, (
        f"occupation tier was constant across {len(_FAMILY_TITLE_PAIRS)} distinct "
        f"(family, title) pairs: {observed_tiers!r} — signal is inert (4a regression)"
    )


# ---------------------------------------------------------------------------
# unknown surfaces as match=unknown / score=None — never omitted or coerced
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unresolved_pair_logs_unknown_with_none_score(db_session):
    profile = _make_profile(db_session, profile_id=1, job_family="Data Scientist")
    with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)):
        scored = await score_job(
            db_session,
            profile_id=profile.id,
            job_description="Registered Nurse role",
            job_title="Registered Nurse",
        )
    sample = db_session.query(DistillationSample).filter_by(scored_job_id=scored.id).one()
    signals = json.loads(sample.signals)
    assert signals["occupation"]["match"] == "unknown"
    assert signals["occupation"]["score"] is None


@pytest.mark.asyncio
async def test_resolved_pair_logs_real_tier_and_score(db_session):
    profile = _make_profile(db_session, profile_id=1, job_family="SWE")
    with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)):
        scored = await score_job(
            db_session,
            profile_id=profile.id,
            job_description="Software Developer role",
            job_title="Software Developer",
        )
    sample = db_session.query(DistillationSample).filter_by(scored_job_id=scored.id).one()
    signals = json.loads(sample.signals)
    assert signals["occupation"]["match"] == "same_occupation"
    assert signals["occupation"]["score"] == 1.0


@pytest.mark.asyncio
async def test_same_isco_group_pair_logs_that_tier_through_real_caller_path(db_session):
    """G-1351 review F6: the same_isco_group tier must be reachable through
    the REAL score_job path, not just via a direct match_occupation() call
    (which Phase B's own tests already cover). "Data Scientist" family vs a
    "Data Analyst" title share ISCO unit group 2511 but are distinct
    occupations, so this must persist same_isco_group at 0.5 — never
    same_occupation (1.0) and never a fake no_match (0.0)."""
    profile = _make_profile(db_session, profile_id=1, job_family="Data Scientist")
    with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)):
        scored = await score_job(
            db_session,
            profile_id=profile.id,
            job_description="Data Analyst role",
            job_title="Data Analyst",
        )
    sample = db_session.query(DistillationSample).filter_by(scored_job_id=scored.id).one()
    signals = json.loads(sample.signals)
    assert signals["occupation"]["match"] == "same_isco_group"
    assert signals["occupation"]["score"] == 0.5


@pytest.mark.asyncio
async def test_occupation_present_alongside_esco_when_both_available(db_session):
    """occupation is always included, additively alongside `esco` (never replaces it)."""
    profile = _make_profile(db_session, profile_id=1, job_family="SWE")
    with patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)):
        scored = await score_job(
            db_session,
            profile_id=profile.id,
            job_description="Software Developer role",
            job_title="Software Developer",
        )
    sample = db_session.query(DistillationSample).filter_by(scored_job_id=scored.id).one()
    signals = json.loads(sample.signals)
    assert "occupation" in signals
    # No parsed requirements/application in this path -> esco is None and thus
    # never added to `extra` (mirrors the existing esco behavior) — occupation
    # must still be present regardless.
    assert "esco" not in signals


# ---------------------------------------------------------------------------
# Startup populate resilience — non-fatal on failure
# ---------------------------------------------------------------------------


def test_startup_populate_occupations_is_non_fatal_on_failure(monkeypatch):
    """The extracted lifespan step (`main._startup_populate_occupations`)
    swallows a `populate_occupations` failure and does not propagate.

    Exercises the REAL function main.py's `lifespan` calls at startup — not a
    re-implementation of its try/except — proving app boot is never blocked by
    a broken/locked occupation taxonomy populate (G-1351 Phase C, T-p2l-04).
    """
    import career_os.main as main_module

    monkeypatch.setattr(
        main_module,
        "populate_occupations",
        MagicMock(side_effect=RuntimeError("boom - simulated populate failure")),
    )

    try:
        main_module._startup_populate_occupations()
    except RuntimeError:
        pytest.fail("populate_occupations failure must be caught, not propagate")


def test_startup_populate_occupations_succeeds_normally(monkeypatch):
    """Sanity check: the extracted step actually calls populate_occupations
    (not just swallowing everything and doing nothing)."""
    import career_os.main as main_module

    mock_populate = MagicMock()
    monkeypatch.setattr(main_module, "populate_occupations", mock_populate)

    main_module._startup_populate_occupations()

    mock_populate.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_invokes_startup_populate_occupations(tmp_path, monkeypatch):
    """G-1351 review F3: drives the REAL `main.lifespan` async context manager
    (not a direct call to the extracted `_startup_populate_occupations`
    helper) and asserts the ESCO occupations taxonomy is actually populated
    by the time startup completes.

    Deleting `_startup_populate_occupations()` from `lifespan` would leave
    `test_startup_populate_occupations_succeeds_normally` above green (it
    only exercises the extracted helper in isolation) — this test closes
    that gap by exercising the wiring between `lifespan` and the helper.

    Heavy/unrelated startup side effects (real Alembic migration, background
    schedulers) are monkeypatched out; `SessionLocal` is redirected to a real
    temp-file SQLite DB with the ORM schema created directly (equivalent to
    what a completed migration would produce), so `_startup_populate_occupations`
    (and the seeding/status-normalization steps around it) run for real
    against a real, if minimal, database.
    """
    import career_os.main as main_module

    db_path = tmp_path / "lifespan_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(main_module, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(main_module, "_auto_migrate", lambda: None)
    monkeypatch.setattr(main_module, "start_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "stop_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "start_ticktick_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "stop_ticktick_scheduler", lambda: None)

    async with main_module.lifespan(main_module.app):
        pass

    from sqlalchemy import text

    check_session = TestSessionLocal()
    try:
        count = check_session.execute(text("SELECT COUNT(*) FROM esco_occupations")).scalar()
    finally:
        check_session.close()
    engine.dispose()

    assert count is not None and count > 0, (
        "esco_occupations is empty after running the REAL lifespan — "
        "_startup_populate_occupations() is not actually wired into lifespan"
    )
