"""Unit tests for scoring shadow-mode (G-1336, finding I).

Covers real variant resolution (distinct provider, model override, self-compare
+ unknown → no-op), the fire-and-forget background worker on its own session,
the score_job wiring, and the comparator.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.ai.base import AIProvider
from career_os.ai.mock_provider import MockProvider
from career_os.config import settings
from career_os.database import Base
from career_os.models.models import Profile
from career_os.models.scoring import ShadowScore
from career_os.services.scoring_shadow import (
    build_shadow_provider,
    compare_primary_vs_shadow,
    record_shadow_score,
    run_shadow_score,
    schedule_shadow_score,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _rec):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    session.add(
        Profile(id=1, name="U", email="u@test.example.com", location="Remote", job_family="TPM")
    )
    session.commit()
    yield session
    session.close()


class _BoomProvider(AIProvider):
    @property
    def name(self):
        return "boom"

    async def complete(self, prompt, **kwargs):  # noqa: ANN001
        raise RuntimeError("nope")

    async def score(self, job_description, profile_data, **kwargs):  # noqa: ANN001
        raise RuntimeError("shadow provider exploded")

    async def embed(self, text, **kwargs):  # noqa: ANN001
        return [0.0] * 768


class _RoleMismatchProvider(AIProvider):
    """Candidate provider that returns a role-mismatched but high fit_score.

    Models a strong-looking holistic score on a job the candidate's role family
    does NOT match — exactly what the G-1335 gate exists to cap.
    """

    @property
    def name(self):
        return "candidate"

    async def complete(self, prompt, **kwargs):  # noqa: ANN001
        raise NotImplementedError

    async def score(self, job_description, profile_data, **kwargs):  # noqa: ANN001
        from career_os.schemas.ai import (
            AIFeature,
            AIResponse,
            RoleMatch,
            ScoreBreakdownFactor,
            ScoreResult,
        )

        return AIResponse(
            content="",
            provider="candidate",
            feature=AIFeature.score,
            structured=ScoreResult(
                role_match=RoleMatch(is_same_role_family=False, evidence="SWE role, not TPM"),
                fit_score=8.0,
                desire_score=7.0,
                reasoning="x" * 120,
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
            ),
        )

    async def embed(self, text, **kwargs):  # noqa: ANN001
        return [0.0] * 768


# ---------------------------------------------------------------------------
# build_shadow_provider — real, distinct variant resolution
# ---------------------------------------------------------------------------


def test_build_shadow_provider_distinct():
    prov = build_shadow_provider("mock", live_provider_name="anthropic")
    assert prov is not None
    assert prov.name == "mock"


def test_build_shadow_provider_self_compare_noops():
    # Same provider, no model override → nothing to learn → None.
    assert build_shadow_provider("mock", live_provider_name="mock") is None


def test_build_shadow_provider_model_override_allows_same_provider():
    # Same provider but a DIFFERENT model is a legit comparison → resolves, and
    # the override is applied to the provider's model (stored as `_model`).
    prov = build_shadow_provider("ollama:llama-custom", live_provider_name="ollama")
    assert prov is not None
    assert prov._model == "llama-custom"


def test_build_shadow_provider_unknown_noops():
    assert build_shadow_provider("nonexistent-provider") is None


def test_build_shadow_provider_empty_noops():
    assert build_shadow_provider("") is None
    assert build_shadow_provider("   ") is None


# ---------------------------------------------------------------------------
# record_shadow_score / run_shadow_score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_shadow_score_persists_fields(db_session):
    row = await record_shadow_score(
        db_session,
        profile_id=1,
        variant="mistral-large",
        prompt="Data Engineer role",
        profile_data={"weights": {}},
        primary_fit_score=4.2,
        provider=MockProvider(),
    )
    assert row.id is not None
    assert row.variant == "mistral-large"
    assert row.primary_fit_score == 4.2
    assert row.reasoning  # MockProvider always returns reasoning


@pytest.mark.asyncio
async def test_record_shadow_score_gates_role_mismatch_candidate(db_session):
    """WR-01: a role-mismatched candidate is stored capped ≤ ROLE_FIT_GATE_CEILING.

    The primary passed in is already post-gate (≤3 for a mismatch). Gating the
    candidate before persisting keeps the shadow comparison apples-to-apples so a
    good candidate model isn't penalized on exactly the jobs the gate exists to fix.
    """
    from career_os.schemas.ai import ROLE_FIT_GATE_CEILING

    row = await record_shadow_score(
        db_session,
        profile_id=1,
        variant="candidate",
        prompt="Senior Software Engineer at Acme",
        profile_data={"weights": {}},
        primary_fit_score=3.0,  # how the live scorer stores this mismatch
        provider=_RoleMismatchProvider(),
    )
    assert row is not None
    # Candidate returned 8.0 but the gate must cap it to match the primary's regime.
    assert row.fit_score <= ROLE_FIT_GATE_CEILING
    assert row.fit_score == ROLE_FIT_GATE_CEILING
    # Desire axis is deliberately left intact by the gate (prestige belongs there).
    assert row.desire_score == 7.0


@pytest.mark.asyncio
async def test_run_shadow_score_uses_own_session(db_session):
    factory = lambda: Session(bind=db_session.get_bind())  # noqa: E731
    row = await run_shadow_score(
        profile_id=1,
        variant="rubric-v2",
        prompt="Senior TPM at Acme",
        profile_data={"weights": {}},
        primary_fit_score=6.5,
        provider=MockProvider(),
        session_factory=factory,
    )
    assert row is not None
    # Written via a separate session, visible from the test session (shared engine).
    persisted = db_session.query(ShadowScore).one()
    assert persisted.variant == "rubric-v2"
    assert persisted.primary_fit_score == 6.5


@pytest.mark.asyncio
async def test_run_shadow_score_is_defensive(db_session):
    factory = lambda: Session(bind=db_session.get_bind())  # noqa: E731
    row = await run_shadow_score(
        profile_id=1,
        variant="bad",
        prompt="p",
        profile_data={"weights": {}},
        primary_fit_score=5.0,
        provider=_BoomProvider(),
        session_factory=factory,
    )
    assert row is None
    assert db_session.query(ShadowScore).count() == 0


# ---------------------------------------------------------------------------
# schedule_shadow_score — fire-and-forget gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_noop_when_unset(db_session, monkeypatch):
    monkeypatch.setattr(settings, "scoring_shadow_variant", "")
    task = schedule_shadow_score(
        profile_id=1, prompt="p", profile_data={"weights": {}}, primary_fit_score=7.0
    )
    assert task is None


@pytest.mark.asyncio
async def test_schedule_noop_when_sample_zero(db_session, monkeypatch):
    monkeypatch.setattr(settings, "scoring_shadow_variant", "mock")
    monkeypatch.setattr(settings, "scoring_shadow_sample", 0.0)
    task = schedule_shadow_score(
        profile_id=1, prompt="p", profile_data={"weights": {}}, primary_fit_score=7.0
    )
    assert task is None


@pytest.mark.asyncio
async def test_schedule_noop_on_self_compare(db_session, monkeypatch):
    monkeypatch.setattr(settings, "scoring_shadow_variant", "mock")
    monkeypatch.setattr(settings, "scoring_shadow_sample", 1.0)
    task = schedule_shadow_score(
        profile_id=1,
        prompt="p",
        profile_data={"weights": {}},
        primary_fit_score=7.0,
        live_provider_name="mock",  # same as variant → self-compare → no-op
    )
    assert task is None


@pytest.mark.asyncio
async def test_schedule_returns_task_and_writes(db_session, monkeypatch):
    monkeypatch.setattr(settings, "scoring_shadow_variant", "mock")
    monkeypatch.setattr(settings, "scoring_shadow_sample", 1.0)
    factory = lambda: Session(bind=db_session.get_bind())  # noqa: E731
    task = schedule_shadow_score(
        profile_id=1,
        prompt="Senior TPM",
        profile_data={"weights": {}},
        primary_fit_score=6.0,
        scored_job_id=None,
        live_provider_name="anthropic",  # distinct from "mock" → runs
        session_factory=factory,
    )
    assert task is not None
    await task  # fire-and-forget task; drive it to completion in the test
    row = db_session.query(ShadowScore).one()
    assert row.variant == "mock"
    assert row.primary_fit_score == 6.0


# ---------------------------------------------------------------------------
# score_job wiring — schedules (does not await) the shadow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_job_schedules_shadow_without_blocking(db_session, monkeypatch):
    from career_os.services import scoring_shadow
    from career_os.services.scoring import score_job

    calls: list[dict] = []

    def _spy(**kwargs):
        calls.append(kwargs)
        return None  # simulate fire-and-forget; return without awaiting anything

    monkeypatch.setattr(settings, "scoring_shadow_variant", "mistral")
    monkeypatch.setattr(scoring_shadow, "schedule_shadow_score", _spy)

    scored = await score_job(
        db_session,
        1,
        "Own cross-functional AI programs. Python, cloud.",
        job_title="Technical Program Manager",
        job_company="Acme",
    )
    assert len(calls) == 1
    assert calls[0]["scored_job_id"] == scored.id
    assert calls[0]["primary_fit_score"] == scored.fit_score
    assert calls[0]["live_provider_name"] == "mock"


@pytest.mark.asyncio
async def test_score_job_does_not_schedule_when_unset(db_session, monkeypatch):
    from career_os.services import scoring_shadow
    from career_os.services.scoring import score_job

    calls: list[dict] = []
    monkeypatch.setattr(settings, "scoring_shadow_variant", "")
    monkeypatch.setattr(scoring_shadow, "schedule_shadow_score", lambda **k: calls.append(k))

    await score_job(db_session, 1, "Some role", job_title="X", job_company="Y")
    assert calls == []


# ---------------------------------------------------------------------------
# comparator
# ---------------------------------------------------------------------------


def test_compare_primary_vs_shadow_bundle():
    labels = ["reject", "mediocre", "strong", "dream"]
    primary = [2.0, 4.5, 6.5, 9.0]  # aligned with labels → strong agreement
    shadow = [9.0, 6.5, 4.5, 2.0]  # inverted → weak agreement
    out = compare_primary_vs_shadow(primary, shadow, labels)
    assert out["n"] == 4
    assert out["primary"]["kappa"] > out["shadow"]["kappa"]
    assert out["delta"]["kappa"] == pytest.approx(out["shadow"]["kappa"] - out["primary"]["kappa"])


def test_compare_primary_vs_shadow_length_mismatch():
    with pytest.raises(ValueError):
        compare_primary_vs_shadow([1.0], [1.0, 2.0], ["reject", "dream"])
