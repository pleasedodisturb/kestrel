"""Unit + integration tests for relative/percentile batch scoring (G-1338, finding N).

Covers the pure percentile/tier math (toy data, ties, empty, single, boundaries),
the ScoredJob view builder, and the batch_score_discovery wiring — asserting
strict identity when the flag is off and a non-destructive relative view when on.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.config import settings
from career_os.database import Base
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile
from career_os.services.relative_scoring import (
    build_relative_view,
    relative_tier_from_percentile,
    relativize_scores,
)
from career_os.services.scoring import batch_score_discovery

# ---------------------------------------------------------------------------
# relative_tier_from_percentile — boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pct", "tier"),
    [
        (100, "top"),
        (75, "top"),
        (74, "upper"),
        (50, "upper"),
        (49, "lower"),
        (25, "lower"),
        (24, "bottom"),
        (0, "bottom"),
    ],
)
def test_relative_tier_boundaries(pct, tier):
    assert relative_tier_from_percentile(pct) == tier


# ---------------------------------------------------------------------------
# relativize_scores — pure percentile math
# ---------------------------------------------------------------------------


def test_relativize_toy_data():
    out = relativize_scores([2.0, 5.0, 8.0, 9.0])
    # percentile = below/n*100; rank = above+1
    assert [e["batch_percentile"] for e in out] == [0, 25, 50, 75]
    assert [e["relative_rank"] for e in out] == [4, 3, 2, 1]
    assert [e["relative_tier"] for e in out] == ["bottom", "lower", "upper", "top"]
    # raw is preserved, in input order
    assert [e["raw_fit_score"] for e in out] == [2.0, 5.0, 8.0, 9.0]


def test_relativize_ties_share_rank_and_percentile():
    out = relativize_scores([5.0, 5.0, 8.0])
    # both 5s: below=0 → pct 0, above=1 → rank 2
    assert out[0]["batch_percentile"] == 0
    assert out[1]["batch_percentile"] == 0
    assert out[0]["relative_rank"] == 2
    assert out[1]["relative_rank"] == 2
    # 8: below=2 → 66, above=0 → rank 1, top-ish
    assert out[2]["relative_rank"] == 1
    assert out[2]["batch_percentile"] == 66


def test_relativize_all_equal_batch_all_bottom():
    """Documented ordinal artifact: an all-equal batch → every job pct 0, rank 1,
    tier 'bottom' (no separation; 'not above anyone', not 'worst')."""
    out = relativize_scores([5.0, 5.0, 5.0])
    assert [e["batch_percentile"] for e in out] == [0, 0, 0]
    assert [e["relative_rank"] for e in out] == [1, 1, 1]
    assert {e["relative_tier"] for e in out} == {"bottom"}


def test_relativize_empty():
    assert relativize_scores([]) == []


def test_relativize_single_is_degenerate_bottom():
    out = relativize_scores([7.0])
    assert out == [
        {
            "raw_fit_score": 7.0,
            "batch_percentile": 0,
            "relative_rank": 1,
            "relative_tier": "bottom",
        }
    ]


# ---------------------------------------------------------------------------
# build_relative_view — keyed by ScoredJob id, non-destructive
# ---------------------------------------------------------------------------


def test_build_relative_view_keyed_by_id():
    jobs = [
        SimpleNamespace(id=10, fit_score=3.0),
        SimpleNamespace(id=20, fit_score=9.0),
        SimpleNamespace(id=30, fit_score=6.0),
    ]
    view = build_relative_view(jobs)
    assert set(view.keys()) == {10, 20, 30}
    assert view[20]["relative_rank"] == 1  # highest raw score
    assert view[10]["relative_rank"] == 3
    # raw scores unchanged on the source objects
    assert jobs[0].fit_score == 3.0
    assert view[10]["raw_fit_score"] == 3.0


# ---------------------------------------------------------------------------
# batch_score_discovery wiring — identity off, relative view on
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _rec):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    session.add(Profile(id=1, name="U", email="u@example.com", location="Berlin", job_family="TPM"))
    session.commit()
    yield session
    session.close()
    connection.close()
    engine.dispose()


def _seed_jobs(db_session, n=3):
    for i in range(n):
        db_session.add(
            DiscoveredJob(
                profile_id=1,
                title=f"TPM Role {i}",
                company=f"Co{i}",
                location="Berlin",
                url=f"http://e.example.com/{i}",
                description=f"A technical program manager role number {i}.",
                title_normalized=f"tpm role {i}",
                company_normalized=f"co{i}",
                location_normalized="berlin",
            )
        )
    db_session.commit()


@pytest.mark.asyncio
async def test_batch_off_by_default_no_relative_key(db_session, monkeypatch):
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    assert settings.relative_batch_scoring_enabled is False
    _seed_jobs(db_session, 3)

    result = await batch_score_discovery(db_session, 1)
    assert "relative" not in result  # strict identity — default behavior unchanged
    assert result["scored_count"] == 3


@pytest.mark.asyncio
async def test_batch_relative_view_when_enabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    monkeypatch.setattr(settings, "relative_batch_scoring_enabled", True)
    _seed_jobs(db_session, 3)

    result = await batch_score_discovery(db_session, 1)
    assert "relative" in result
    view = result["relative"]
    assert len(view) == result["scored_count"]
    # Non-destructive: each relative entry's raw score matches the persisted score.
    by_id = {s.id: s.fit_score for s in result["scores"]}
    for sid, entry in view.items():
        assert entry["raw_fit_score"] == by_id[sid]
        assert set(entry) == {
            "raw_fit_score",
            "batch_percentile",
            "relative_rank",
            "relative_tier",
        }
