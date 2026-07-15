"""Unit tests for scoring shadow-mode (G-1336, finding I)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.ai.base import AIProvider
from career_os.ai.mock_provider import MockProvider
from career_os.config import settings
from career_os.database import Base
from career_os.models.models import Profile
from career_os.models.scoring import ShadowScore
from career_os.services.scoring_shadow import (
    compare_primary_vs_shadow,
    maybe_record_shadow_score,
    record_shadow_score,
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


@pytest.mark.asyncio
async def test_maybe_shadow_noop_when_unset(db_session, monkeypatch):
    monkeypatch.setattr(settings, "scoring_shadow_variant", "")
    result = await maybe_record_shadow_score(
        db_session, profile_id=1, prompt="p", profile_data={"weights": {}}, primary_fit_score=7.0
    )
    assert result is None
    assert db_session.query(ShadowScore).count() == 0


@pytest.mark.asyncio
async def test_maybe_shadow_logs_when_set(db_session, monkeypatch):
    monkeypatch.setattr(settings, "scoring_shadow_variant", "rubric-v2")
    result = await maybe_record_shadow_score(
        db_session,
        profile_id=1,
        prompt="Senior TPM at Acme",
        profile_data={"weights": {}},
        primary_fit_score=6.5,
        provider=MockProvider(),
    )
    assert result is not None
    row = db_session.query(ShadowScore).one()
    assert row.variant == "rubric-v2"
    assert row.primary_fit_score == 6.5
    assert 0.0 <= row.fit_score <= 10.0


@pytest.mark.asyncio
async def test_shadow_is_defensive_on_provider_failure(db_session, monkeypatch):
    monkeypatch.setattr(settings, "scoring_shadow_variant", "bad")
    # Must not raise, must not persist a partial row.
    result = await maybe_record_shadow_score(
        db_session,
        profile_id=1,
        prompt="p",
        profile_data={"weights": {}},
        primary_fit_score=5.0,
        provider=_BoomProvider(),
    )
    assert result is None
    assert db_session.query(ShadowScore).count() == 0


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
    assert row.reasoning  # MockProvider always returns reasoning


@pytest.mark.asyncio
async def test_shadow_hook_fires_inside_score_job(db_session, monkeypatch):
    """score_job logs a shadow row linked to the persisted primary score."""
    from career_os.services.scoring import score_job

    monkeypatch.setattr(settings, "scoring_shadow_variant", "0to5-scale")
    scored = await score_job(
        db_session,
        1,
        "Own cross-functional AI programs. Python, cloud.",
        job_title="Technical Program Manager",
        job_company="Acme",
    )
    shadow = db_session.query(ShadowScore).one()
    assert shadow.variant == "0to5-scale"
    assert shadow.scored_job_id == scored.id
    assert shadow.primary_fit_score == scored.fit_score


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
