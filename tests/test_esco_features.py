"""Unit + integration tests for ESCO skills-overlap features (G-1338, finding L).

Covers the pure weighted skills-overlap math (known values, empty/missing,
all/none matched), the DB wrappers, defensive behavior, and — critically — the
REAL caller path through ``score_job`` so the signal cannot pass while being
inert in production. All deterministic, no LLM calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.config import settings
from career_os.database import Base
from career_os.models.models import Application, Profile
from career_os.models.scoring import DistillationSample
from career_os.models.skills import JobRequirement, Skill
from career_os.schemas.ai import (
    ATSKeyword,
    DimensionalScores,
    ScoreBreakdownFactor,
    ScoreResult,
)
from career_os.services.esco_features import (
    compute_esco_features,
    compute_job_skills_overlap,
    compute_skills_overlap,
    get_candidate_skill_uris,
)
from career_os.services.scoring import score_job


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


def _skill(name, uri):
    return Skill(
        profile_id=1,
        name=name,
        category="technical",
        proficiency="advanced",
        esco_uri=uri,
        evidence_source="manual",
    )


# ---------------------------------------------------------------------------
# compute_skills_overlap — pure, weighted
# ---------------------------------------------------------------------------


def test_overlap_weighted_known_values():
    # critical(1.0) matched, nice-to-have(0.5) missing, bonus(0.25) matched.
    required = [
        ("uri:python", "critical"),
        ("uri:k8s", "nice-to-have"),
        ("uri:docker", "bonus"),
    ]
    candidate = {"uri:python", "uri:docker", "uri:unrelated"}
    out = compute_skills_overlap(required, candidate)

    assert out["matched"] == 2
    assert out["total"] == 3
    assert out["matched_weight"] == 1.25
    assert out["total_weight"] == 1.75
    assert out["overlap_score"] == pytest.approx(0.7143, abs=1e-4)
    assert set(out["matched_uris"]) == {"uri:python", "uri:docker"}
    assert out["missing_uris"] == ["uri:k8s"]


def test_overlap_all_matched_is_one():
    out = compute_skills_overlap([("uri:a", "critical"), ("uri:b", "bonus")], {"uri:a", "uri:b"})
    assert out["overlap_score"] == 1.0
    assert out["matched"] == 2


def test_overlap_none_matched_is_zero_with_total():
    out = compute_skills_overlap([("uri:a", "critical")], {"uri:x"})
    assert out["overlap_score"] == 0.0
    assert out["matched"] == 0
    assert out["total"] == 1  # total>0 disambiguates "matched nothing" from "no data"


def test_overlap_empty_requirements_is_zero_no_data():
    out = compute_skills_overlap([], {"uri:a"})
    assert out["overlap_score"] == 0.0
    assert out["total"] == 0  # total==0 → no ESCO data (vs matched-nothing above)
    assert out["total_weight"] == 0.0


def test_overlap_ignores_unnormalized_requirements():
    required = [("uri:a", "critical"), (None, "critical"), ("", "nice-to-have")]
    out = compute_skills_overlap(required, {"uri:a"})
    assert out["total"] == 1
    assert out["overlap_score"] == 1.0


def test_overlap_unknown_severity_uses_default_weight():
    out = compute_skills_overlap([("uri:a", "weird-label")], set())
    assert out["total_weight"] == 0.5  # default nice-to-have weight


# ---------------------------------------------------------------------------
# DB wrappers
# ---------------------------------------------------------------------------


def test_get_candidate_skill_uris(db_session):
    db_session.add_all(
        [
            _skill("Python", "uri:python"),
            _skill("Docker", "uri:docker"),
            _skill("Unmapped", None),
        ]
    )
    db_session.commit()
    assert get_candidate_skill_uris(db_session, 1) == {"uri:python", "uri:docker"}


def test_compute_job_skills_overlap_db(db_session):
    app = Application(profile_id=1, company="Acme", role="PM", status="discovered")
    db_session.add(app)
    db_session.add(_skill("Python", "uri:python"))
    db_session.commit()
    db_session.add_all(
        [
            JobRequirement(
                application_id=app.id,
                profile_id=1,
                skill_name="Python",
                esco_uri="uri:python",
                severity="critical",
            ),
            JobRequirement(
                application_id=app.id,
                profile_id=1,
                skill_name="Kubernetes",
                esco_uri="uri:k8s",
                severity="critical",
            ),
        ]
    )
    db_session.commit()

    out = compute_job_skills_overlap(db_session, application_id=app.id, profile_id=1)
    assert out["matched"] == 1
    assert out["total"] == 2
    assert out["overlap_score"] == 0.5


# ---------------------------------------------------------------------------
# compute_esco_features bundle
# ---------------------------------------------------------------------------


def test_compute_esco_features_no_application_returns_none(db_session):
    # Skills-overlap is undefined without a job's parsed requirements.
    assert compute_esco_features(db_session, profile_id=1) is None


def test_compute_esco_features_bundle(db_session):
    app = Application(profile_id=1, company="Acme", role="PM", status="discovered")
    db_session.add(app)
    db_session.add(_skill("Python", "uri:python"))
    db_session.commit()
    db_session.add(
        JobRequirement(
            application_id=app.id,
            profile_id=1,
            skill_name="Python",
            esco_uri="uri:python",
            severity="critical",
        )
    )
    db_session.commit()

    out = compute_esco_features(db_session, profile_id=1, application_id=app.id)
    assert out is not None
    assert out["skills_overlap"]["overlap_score"] == 1.0


def test_compute_esco_features_defensive_rolls_back_and_returns_none(db_session, monkeypatch):
    """Any internal failure is swallowed → None, and the session is rolled back."""
    rolled_back = {"count": 0}
    real_rollback = db_session.rollback

    def _spy_rollback():
        rolled_back["count"] += 1
        return real_rollback()

    monkeypatch.setattr(db_session, "rollback", _spy_rollback)
    monkeypatch.setattr(
        "career_os.services.esco_features.compute_job_skills_overlap",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert compute_esco_features(db_session, profile_id=1, application_id=99) is None
    assert rolled_back["count"] == 1


# ---------------------------------------------------------------------------
# REAL caller path — score_job feeds ESCO skills-overlap into the distillation log
# ---------------------------------------------------------------------------


def _mock_provider():
    result = ScoreResult(
        fit_score=8.0,
        readiness_score=70.0,
        career_alignment=7.0,
        reasoning="r",
        estimated_salary="$100k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="p",
        score_breakdown=[
            ScoreBreakdownFactor(factor="a", contribution=1.0, description="d"),
            ScoreBreakdownFactor(factor="b", contribution=1.0, description="d"),
            ScoreBreakdownFactor(factor="c", contribution=1.0, description="d"),
        ],
        dimensional_scores=DimensionalScores(
            technical_fit=8,
            seniority_alignment=8,
            compensation_fit=8,
            location_fit=8,
            career_trajectory=8,
            company_fit=8,
        ),
        ats_keywords=[ATSKeyword(keyword="Python", category="technical", matched=True)],
        desire_score=6.0,
        desire_reasoning="d",
    )
    resp = MagicMock()
    resp.structured = result
    provider = AsyncMock()
    provider.score.return_value = resp
    provider.name = "mock"
    return provider


@pytest.mark.asyncio
async def test_score_job_records_real_esco_overlap(db_session, monkeypatch):
    """The signal must flow through the ACTUAL score_job caller path (application_id),
    not an injected occupation world — so it fails if the feature is inert."""
    monkeypatch.setattr(settings, "feedback_calibration_enabled", False)
    monkeypatch.setattr(settings, "borderline_scoring_enabled", False)
    monkeypatch.setattr(settings, "distillation_logging_enabled", True)

    app = Application(profile_id=1, company="Acme", role="TPM", status="discovered")
    db_session.add(app)
    db_session.add_all([_skill("Python", "uri:python"), _skill("Docker", "uri:docker")])
    db_session.commit()
    db_session.add_all(
        [
            JobRequirement(
                application_id=app.id,
                profile_id=1,
                skill_name="Python",
                esco_uri="uri:python",
                severity="critical",
            ),
            JobRequirement(
                application_id=app.id,
                profile_id=1,
                skill_name="Kubernetes",
                esco_uri="uri:k8s",
                severity="critical",
            ),
        ]
    )
    db_session.commit()

    with patch("career_os.services.scoring.get_ai_provider", return_value=_mock_provider()):
        await score_job(
            db_session,
            profile_id=1,
            job_description="TPM role",
            job_title="TPM",
            application_id=app.id,
        )

    sample = db_session.query(DistillationSample).one()
    signals = json.loads(sample.signals)
    overlap = signals["esco"]["skills_overlap"]
    # Python matched (critical 1.0), Kubernetes missing (critical 1.0) → 1.0 / 2.0
    assert overlap["overlap_score"] == 0.5
    assert overlap["total"] == 2
    assert overlap["matched"] == 1
