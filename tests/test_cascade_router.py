"""Tests for the confidence-routed cascade (G-1338, finding K — Phase 4b).

Covers, with teeth:
  * each signal (embedding / lexical / esco) — value, availability/abstain, vote;
  * the CRITICAL router-safety assertion: SKIP_REJECT requires ALL THREE signals
    available AND voting reject — a job failing only 1 or 2 (or with any
    abstaining signal) must route to SCORE, never skip;
  * shadow logging + full defensiveness on failure;
  * the false-skip comparator on toy data with hand-computed values;
  * strict off-by-default identity through batch_score_discovery (both flags off →
    the pipeline behaves exactly as on main: LLM scores everything, no skips, no
    cascade rows) — even for a job that WOULD be a unanimous reject;
  * live mode persists a skipped job as rejected (not dropped), with no LLM call.

All on the mock provider / deterministic fixtures — zero paid LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.config import settings
from career_os.database import Base
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Application, Profile
from career_os.models.scoring import CascadeDecision as CascadeDecisionRow
from career_os.models.scoring import ScoredJob
from career_os.models.skills import JobRequirement, Skill
from career_os.schemas.ai import (
    ATSKeyword,
    DimensionalScores,
    ScoreBreakdownFactor,
    ScoreResult,
)
from career_os.services.cascade_router import (
    CascadeAction,
    CascadeDecision,
    SignalVote,
    compute_lexical_overlap,
    embedding_signal,
    esco_signal,
    false_skip_rate,
    lexical_signal,
    persist_cascade_reject,
    record_cascade_decision,
    route_job,
    run_false_skip_report,
    safe_route_job,
)

_ESCO_A = "http://data.europa.eu/esco/skill/AAAA"
_ESCO_B = "http://data.europa.eu/esco/skill/BBBB"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Session:
    """Fresh in-memory SQLite session seeded with a scorable profile (id=1)."""
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


def _make_score_result(fit_score: float = 8.0, desire_score: float | None = 6.0) -> ScoreResult:
    return ScoreResult(
        fit_score=fit_score,
        readiness_score=70.0,
        career_alignment=7.0,
        reasoning="reason",
        estimated_salary="$100k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="notes",
        desire_score=desire_score,
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
    resp = MagicMock()
    resp.structured = _make_score_result(fit_score=fit_score)
    provider = AsyncMock()
    provider.score.return_value = resp
    provider.name = "mock"
    return provider


def _vote(available: bool, value: float | None, votes_reject: bool, name: str = "x") -> SignalVote:
    return SignalVote(name=name, available=available, value=value, votes_reject=votes_reject)


def _decision(action: CascadeAction, e: SignalVote, lx: SignalVote, es: SignalVote):
    return CascadeDecision(action=action, embedding=e, lexical=lx, esco=es)


# ---------------------------------------------------------------------------
# SignalVote invariant
# ---------------------------------------------------------------------------


def test_unavailable_signal_can_never_vote_reject():
    """An unavailable signal is forced to votes_reject=False (abstain blocks skip)."""
    v = SignalVote(name="x", available=False, value=None, votes_reject=True)
    assert v.votes_reject is False


# ---------------------------------------------------------------------------
# embedding_signal
# ---------------------------------------------------------------------------


def test_embedding_none_abstains():
    v = embedding_signal(None, reject_threshold=0.35)
    assert v.available is False
    assert v.votes_reject is False


def test_embedding_low_votes_reject():
    v = embedding_signal(0.10, reject_threshold=0.35)
    assert v.available is True
    assert v.votes_reject is True
    assert v.value == 0.10


def test_embedding_high_does_not_reject():
    v = embedding_signal(0.90, reject_threshold=0.35)
    assert v.available is True
    assert v.votes_reject is False


def test_embedding_boundary_is_exclusive():
    # Exactly at threshold is NOT below → not a reject (conservative).
    assert embedding_signal(0.35, reject_threshold=0.35).votes_reject is False


# ---------------------------------------------------------------------------
# compute_lexical_overlap (pure)
# ---------------------------------------------------------------------------


def test_lexical_overlap_exact_and_fuzzy():
    out = compute_lexical_overlap(
        ["Python", "Kubernetes"], ["python programming", "kubernetes (k8s)"]
    )
    assert out["matched"] == 2
    assert out["total"] == 2
    assert out["overlap_score"] == 1.0


def test_lexical_overlap_zero():
    out = compute_lexical_overlap(["Welding", "Forklift"], ["Python", "Kubernetes"])
    assert out["matched"] == 0
    assert out["total"] == 2
    assert out["overlap_score"] == 0.0
    assert out["missing_terms"] == ["Welding", "Forklift"]


def test_lexical_overlap_dedupes_terms():
    out = compute_lexical_overlap(["Python", "python", "PYTHON"], ["Java"])
    assert out["total"] == 1  # deduped


def test_lexical_overlap_no_terms_is_zero_not_crash():
    out = compute_lexical_overlap([], ["Python"])
    assert out["total"] == 0
    assert out["overlap_score"] == 0.0


# ---------------------------------------------------------------------------
# lexical_signal (DB): requirements path, jd_text fallback, abstain
# ---------------------------------------------------------------------------


def _seed_candidate_skills(db, names, *, esco_uris=None):
    esco_uris = esco_uris or [None] * len(names)
    for name, uri in zip(names, esco_uris, strict=True):
        db.add(
            Skill(
                profile_id=1,
                name=name,
                esco_uri=uri,
                category="technical",
                proficiency="advanced",
                evidence_source="manual",
            )
        )
    db.commit()


def _seed_application(db) -> Application:
    app = Application(profile_id=1, company="Acme", role="TPM", status="discovered")
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def _seed_requirements(db, app_id, terms):
    """terms: list of (skill_name, severity, esco_uri)."""
    for name, sev, uri in terms:
        db.add(
            JobRequirement(
                application_id=app_id,
                profile_id=1,
                skill_name=name,
                severity=sev,
                esco_uri=uri,
            )
        )
    db.commit()


def test_lexical_signal_requirements_zero_overlap_votes_reject(db_session):
    _seed_candidate_skills(db_session, ["Python", "Roadmapping"])
    app = _seed_application(db_session)
    _seed_requirements(db_session, app.id, [("Welding", "critical", None)])
    v = lexical_signal(db_session, profile_id=1, application_id=app.id, jd_text="irrelevant")
    assert v.available is True
    assert v.votes_reject is True
    assert v.detail["source"] == "requirements"


def test_lexical_signal_requirements_overlap_does_not_reject(db_session):
    _seed_candidate_skills(db_session, ["Python"])
    app = _seed_application(db_session)
    _seed_requirements(db_session, app.id, [("Python", "critical", None)])
    v = lexical_signal(db_session, profile_id=1, application_id=app.id, jd_text="")
    assert v.available is True
    assert v.votes_reject is False
    assert v.value == 1.0


def test_lexical_signal_jd_text_fallback_when_no_requirements(db_session):
    _seed_candidate_skills(db_session, ["Python", "Roadmapping"])
    # No requirements → fall back to JD text; none of the skills appear → reject.
    v = lexical_signal(
        db_session, profile_id=1, application_id=None, jd_text="We need a welder and a forklift op"
    )
    assert v.available is True
    assert v.votes_reject is True
    assert v.detail["source"] == "jd_text"


def test_lexical_signal_jd_text_present_does_not_reject(db_session):
    _seed_candidate_skills(db_session, ["Python"])
    v = lexical_signal(
        db_session, profile_id=1, application_id=None, jd_text="Strong Python experience required"
    )
    assert v.votes_reject is False


def test_lexical_signal_abstains_without_data(db_session):
    # No candidate skills at all → abstain (no data on either side).
    v = lexical_signal(db_session, profile_id=1, application_id=None, jd_text="anything")
    assert v.available is False
    assert v.votes_reject is False


# ---------------------------------------------------------------------------
# esco_signal (DB)
# ---------------------------------------------------------------------------


def test_esco_signal_zero_coverage_votes_reject(db_session):
    _seed_candidate_skills(db_session, ["Python"], esco_uris=[_ESCO_A])
    app = _seed_application(db_session)
    _seed_requirements(db_session, app.id, [("Welding", "critical", _ESCO_B)])
    v = esco_signal(db_session, profile_id=1, application_id=app.id)
    assert v.available is True
    assert v.votes_reject is True
    assert v.value == 0.0


def test_esco_signal_covered_does_not_reject(db_session):
    _seed_candidate_skills(db_session, ["Python"], esco_uris=[_ESCO_A])
    app = _seed_application(db_session)
    _seed_requirements(db_session, app.id, [("Python", "critical", _ESCO_A)])
    v = esco_signal(db_session, profile_id=1, application_id=app.id)
    assert v.available is True
    assert v.votes_reject is False
    assert v.value == 1.0


def test_esco_signal_abstains_without_requirements(db_session):
    _seed_candidate_skills(db_session, ["Python"], esco_uris=[_ESCO_A])
    app = _seed_application(db_session)  # no requirements
    v = esco_signal(db_session, profile_id=1, application_id=app.id)
    assert v.available is False
    assert v.votes_reject is False


def test_esco_signal_abstains_without_application(db_session):
    v = esco_signal(db_session, profile_id=1, application_id=None)
    assert v.available is False


# ---------------------------------------------------------------------------
# route_job — THE critical safety assertion
# ---------------------------------------------------------------------------


def _seed_unanimous_reject_case(db):
    """Seed DB state where all three signals have data and all vote reject."""
    _seed_candidate_skills(db, ["Python", "Roadmapping"], esco_uris=[_ESCO_A, None])
    app = _seed_application(db)
    _seed_requirements(db, app.id, [("Welding", "critical", _ESCO_B)])
    return app


def test_route_skip_requires_all_three(db_session):
    """All three available + reject → SKIP_REJECT (embedding passed low)."""
    app = _seed_unanimous_reject_case(db_session)
    d = route_job(
        db_session,
        profile_id=1,
        application_id=app.id,
        embedding_similarity=0.10,
        jd_text="welding forklift",
    )
    assert d.action == CascadeAction.SKIP_REJECT
    assert d.would_skip is True
    assert all(s.available and s.votes_reject for s in d.signals)


def test_route_scores_when_embedding_high(db_session):
    """Lexical + ESCO reject, but embedding is high → NOT unanimous → SCORE."""
    app = _seed_unanimous_reject_case(db_session)
    d = route_job(
        db_session,
        profile_id=1,
        application_id=app.id,
        embedding_similarity=0.90,  # only signal that flips
        jd_text="welding forklift",
    )
    assert d.action == CascadeAction.SCORE
    assert d.embedding.votes_reject is False
    assert d.lexical.votes_reject is True
    assert d.esco.votes_reject is True


def test_route_scores_when_embedding_abstains(db_session):
    """Two signals reject but embedding has NO data → abstain blocks skip → SCORE."""
    app = _seed_unanimous_reject_case(db_session)
    d = route_job(
        db_session,
        profile_id=1,
        application_id=app.id,
        embedding_similarity=None,  # abstain
        jd_text="welding forklift",
    )
    assert d.action == CascadeAction.SCORE
    assert d.embedding.available is False


def test_route_scores_when_only_embedding_rejects(db_session):
    """Low embedding but lexical + ESCO both MATCH → one signal is never enough."""
    _seed_candidate_skills(db_session, ["Python"], esco_uris=[_ESCO_A])
    app = _seed_application(db_session)
    _seed_requirements(db_session, app.id, [("Python", "critical", _ESCO_A)])
    d = route_job(
        db_session,
        profile_id=1,
        application_id=app.id,
        embedding_similarity=0.05,
        jd_text="python",
    )
    assert d.action == CascadeAction.SCORE
    assert d.embedding.votes_reject is True
    assert d.lexical.votes_reject is False
    assert d.esco.votes_reject is False


def test_route_scores_when_esco_abstains_even_if_emb_and_lex_reject(db_session):
    """ESCO has no data (no esco_uri on requirement) → abstain → SCORE."""
    _seed_candidate_skills(db_session, ["Python"], esco_uris=[_ESCO_A])
    app = _seed_application(db_session)
    # requirement has NO esco_uri → esco signal abstains (total==0), lexical rejects.
    _seed_requirements(db_session, app.id, [("Welding", "critical", None)])
    d = route_job(
        db_session,
        profile_id=1,
        application_id=app.id,
        embedding_similarity=0.05,
        jd_text="welding",
    )
    assert d.esco.available is False
    assert d.lexical.votes_reject is True
    assert d.embedding.votes_reject is True
    assert d.action == CascadeAction.SCORE  # abstaining ESCO blocks the skip


# ---------------------------------------------------------------------------
# safe_route_job — defensive
# ---------------------------------------------------------------------------


def test_safe_route_job_returns_none_on_failure(db_session):
    with patch("career_os.services.cascade_router.route_job", side_effect=RuntimeError("boom")):
        out = safe_route_job(db_session, profile_id=1, embedding_similarity=0.1)
    assert out is None  # never raises → caller scores normally


# ---------------------------------------------------------------------------
# record_cascade_decision — logging + defensiveness
# ---------------------------------------------------------------------------


def test_record_decision_shadow_logs_llm_score(db_session):
    d = _decision(
        CascadeAction.SKIP_REJECT,
        _vote(True, 0.1, True, "embedding"),
        _vote(True, 0.0, True, "lexical"),
        _vote(True, 0.0, True, "esco"),
    )
    row = record_cascade_decision(
        db_session, profile_id=1, decision=d, mode="shadow", llm_fit_score=8.0, llm_desire_score=6.0
    )
    assert row is not None
    assert row.mode == "shadow"
    assert row.action == "skip_reject"
    assert row.would_skip is True
    assert row.llm_fit_score == 8.0
    assert row.llm_quadrant is not None
    assert row.embedding_votes_reject is True
    assert db_session.query(CascadeDecisionRow).count() == 1


def test_record_decision_defensive_on_bad_fk(db_session):
    """A bad profile FK is swallowed — returns None, session recovers."""
    d = _decision(
        CascadeAction.SCORE,
        _vote(True, 0.9, False, "embedding"),
        _vote(False, None, False, "lexical"),
        _vote(False, None, False, "esco"),
    )
    out = record_cascade_decision(db_session, profile_id=99999, decision=d, mode="shadow")
    assert out is None
    assert db_session.query(CascadeDecisionRow).count() == 0


# ---------------------------------------------------------------------------
# false_skip_rate — toy data, hand-computed
# ---------------------------------------------------------------------------


def test_false_skip_rate_known_values():
    # would_skip / llm_fit_score pairs:
    #   (True, 8.0)  → would skip a genuine fit → FALSE SKIP
    #   (True, 2.0)  → would skip a true reject → correct skip
    #   (True, 5.0)  → 5.0 >= threshold 5.0 → FALSE SKIP
    #   (False, 9.0) → not a skip → ignored in numerator
    #   (True, None) → no LLM score → excluded entirely
    samples = [(True, 8.0), (True, 2.0), (True, 5.0), (False, 9.0), (True, None)]
    out = false_skip_rate(samples, fit_threshold=5.0)
    assert out["n"] == 4  # the None row is excluded
    assert out["would_skip"] == 3
    assert out["false_skips"] == 2  # 8.0 and 5.0
    assert out["false_skip_rate"] == round(2 / 3, 4)
    assert out["skip_rate"] == round(3 / 4, 4)


def test_false_skip_rate_no_skips_is_zero():
    out = false_skip_rate([(False, 8.0), (False, 2.0)], fit_threshold=5.0)
    assert out["would_skip"] == 0
    assert out["false_skips"] == 0
    assert out["false_skip_rate"] == 0.0


def test_run_false_skip_report_reads_shadow_rows(db_session):
    d_skip = _decision(
        CascadeAction.SKIP_REJECT,
        _vote(True, 0.1, True, "embedding"),
        _vote(True, 0.0, True, "lexical"),
        _vote(True, 0.0, True, "esco"),
    )
    d_score = _decision(
        CascadeAction.SCORE,
        _vote(True, 0.9, False, "embedding"),
        _vote(True, 1.0, False, "lexical"),
        _vote(True, 1.0, False, "esco"),
    )
    # A would-skip job the LLM scored 8.0 (a false skip), plus a scored job at 9.0.
    record_cascade_decision(
        db_session, profile_id=1, decision=d_skip, mode="shadow", llm_fit_score=8.0
    )
    record_cascade_decision(
        db_session, profile_id=1, decision=d_score, mode="shadow", llm_fit_score=9.0
    )
    # A live row (llm_fit_score None) must be ignored by the shadow report.
    record_cascade_decision(
        db_session,
        profile_id=1,
        decision=d_skip,
        mode="live",
        llm_fit_score=None,
        reject_fit_score=1.0,
    )
    rep = run_false_skip_report(db_session, profile_id=1, fit_threshold=5.0)
    assert rep["n"] == 2
    assert rep["would_skip"] == 1
    assert rep["false_skips"] == 1
    assert rep["false_skip_rate"] == 1.0


# ---------------------------------------------------------------------------
# persist_cascade_reject — nothing dropped
# ---------------------------------------------------------------------------


def test_persist_cascade_reject_writes_visible_rejected_job(db_session):
    app = _seed_application(db_session)
    dj = DiscoveredJob(
        profile_id=1,
        title="Welder",
        company="Acme",
        title_normalized="welder",
        company_normalized="acme",
        location_normalized="berlin",
        application_id=app.id,
    )
    db_session.add(dj)
    db_session.commit()
    db_session.refresh(dj)

    d = _decision(
        CascadeAction.SKIP_REJECT,
        _vote(True, 0.1, True, "embedding"),
        _vote(True, 0.0, True, "lexical"),
        _vote(True, 0.0, True, "esco"),
    )
    scored = persist_cascade_reject(
        db_session,
        profile_id=1,
        decision=d,
        discovered_job_id=dj.id,
        application_id=app.id,
        reject_fit_score=1.0,
    )
    assert scored.id is not None
    assert scored.fit_score == 1.0
    assert "cascade" in scored.reasoning.lower()
    # Nothing dropped: the job is persisted + fit_score propagated to linked rows.
    assert db_session.query(ScoredJob).count() == 1
    db_session.refresh(dj)
    assert dj.fit_score == 1.0
    app_row = db_session.query(Application).filter(Application.id == app.id).one()
    assert app_row.fit_score == 1.0


# ---------------------------------------------------------------------------
# batch_score_discovery integration — off-by-default identity, shadow, live
# ---------------------------------------------------------------------------


def _seed_scorable_discovered_job(db) -> tuple[Application, DiscoveredJob]:
    """A discovered job whose signals would all vote reject (given a low embed)."""
    _seed_candidate_skills(db, ["Python", "Roadmapping"], esco_uris=[_ESCO_A, None])
    app = _seed_application(db)
    _seed_requirements(db, app.id, [("Welding", "critical", _ESCO_B)])
    dj = DiscoveredJob(
        profile_id=1,
        title="Welder",
        company="Acme",
        location="Berlin",
        description="We need welding and forklift operation.",
        title_normalized="welder",
        company_normalized="acme",
        location_normalized="berlin",
        application_id=app.id,
    )
    db.add(dj)
    db.commit()
    db.refresh(dj)
    return app, dj


async def _run_batch(db, sim_value: float | None):
    """Run batch_score_discovery with a forced embedding similarity + mock provider."""
    from career_os.services import scoring as scoring_mod

    async def fake_sims(_db, _pid, jobs, _provider):
        return {j.id: sim_value for j in jobs} if sim_value is not None else {}

    with (
        patch("career_os.services.scoring.get_ai_provider", return_value=_patch_provider(8.0)),
        patch("career_os.services.embeddings.compute_job_similarities", side_effect=fake_sims),
    ):
        return await scoring_mod.batch_score_discovery(db, profile_id=1)


@pytest.mark.asyncio
async def test_batch_off_by_default_scores_everything_no_cascade_rows(db_session, monkeypatch):
    """Both flags OFF → identity: the would-be-reject job is LLM-scored, no rows."""
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    assert settings.cascade_shadow_enabled is False
    assert settings.cascade_routing_enabled is False

    _app, dj = _seed_scorable_discovered_job(db_session)
    result = await _run_batch(db_session, sim_value=0.05)  # low embed, but flags off

    assert result["scored_count"] == 1
    scored = db_session.query(ScoredJob).one()
    assert scored.discovered_job_id == dj.id
    assert scored.fit_score == 8.0  # real LLM score, NOT the reject score
    assert db_session.query(CascadeDecisionRow).count() == 0  # nothing logged


@pytest.mark.asyncio
async def test_batch_shadow_logs_but_still_scores(db_session, monkeypatch):
    """Shadow ON → LLM still scores everything; the would-skip decision is logged."""
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    monkeypatch.setattr(settings, "cascade_shadow_enabled", True)
    monkeypatch.setattr(settings, "cascade_routing_enabled", False)

    _app, dj = _seed_scorable_discovered_job(db_session)
    result = await _run_batch(db_session, sim_value=0.05)

    # LLM scored it for real (shadow never skips).
    assert result["scored_count"] == 1
    scored = db_session.query(ScoredJob).one()
    assert scored.fit_score == 8.0
    # And the routing decision was logged with the eventual LLM score.
    row = db_session.query(CascadeDecisionRow).one()
    assert row.mode == "shadow"
    assert row.would_skip is True
    assert row.llm_fit_score == 8.0
    assert row.scored_job_id == scored.id


@pytest.mark.asyncio
async def test_batch_live_skips_and_persists_rejected_job(db_session, monkeypatch):
    """Live ON → the unanimous-reject job bypasses the LLM but is persisted."""
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    monkeypatch.setattr(settings, "cascade_routing_enabled", True)
    monkeypatch.setattr(settings, "cascade_shadow_enabled", False)
    monkeypatch.setattr(settings, "cascade_reject_fit_score", 1.0)

    _app, dj = _seed_scorable_discovered_job(db_session)

    provider = _patch_provider(8.0)

    async def fake_sims(_db, _pid, jobs, _provider):
        return {j.id: 0.05 for j in jobs}

    from career_os.services import scoring as scoring_mod

    with (
        patch("career_os.services.scoring.get_ai_provider", return_value=provider),
        patch("career_os.services.embeddings.compute_job_similarities", side_effect=fake_sims),
    ):
        result = await scoring_mod.batch_score_discovery(db_session, profile_id=1)

    # The job was NOT sent to the LLM...
    provider.score.assert_not_called()
    # ...but it is NOT dropped — persisted as a scored-but-rejected job.
    assert result["scored_count"] == 1
    scored = db_session.query(ScoredJob).one()
    assert scored.discovered_job_id == dj.id
    assert scored.fit_score == 1.0
    assert "cascade" in scored.reasoning.lower()
    # A live cascade row was logged with no LLM score + the reject score.
    row = db_session.query(CascadeDecisionRow).one()
    assert row.mode == "live"
    assert row.would_skip is True
    assert row.llm_fit_score is None
    assert row.reject_fit_score == 1.0


@pytest.mark.asyncio
async def test_batch_live_scores_normally_when_not_unanimous(db_session, monkeypatch):
    """Live ON but signals NOT unanimous (high embed) → normal LLM score, no skip."""
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    monkeypatch.setattr(settings, "cascade_routing_enabled", True)

    _app, dj = _seed_scorable_discovered_job(db_session)
    provider = _patch_provider(8.0)

    async def fake_sims(_db, _pid, jobs, _provider):
        return {j.id: 0.95 for j in jobs}  # high embed → not unanimous

    from career_os.services import scoring as scoring_mod

    with (
        patch("career_os.services.scoring.get_ai_provider", return_value=provider),
        patch("career_os.services.embeddings.compute_job_similarities", side_effect=fake_sims),
    ):
        await scoring_mod.batch_score_discovery(db_session, profile_id=1)

    provider.score.assert_called()  # LLM WAS used
    scored = db_session.query(ScoredJob).one()
    assert scored.fit_score == 8.0
    row = db_session.query(CascadeDecisionRow).one()
    assert row.mode == "live"
    assert row.would_skip is False
    assert row.llm_fit_score == 8.0
