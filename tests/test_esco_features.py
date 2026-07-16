"""Unit tests for ESCO quantitative scoring features (G-1338, finding L).

Covers the pure weighted skills-overlap math (known values, empty/missing,
all/none matched), the DB wrappers, and the title→occupation axis (same URI,
same ISCO group, no match, empty titles) — all deterministic, no LLM calls.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.esco import ESCOSkill
from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement, Skill
from career_os.services.esco_features import (
    compute_esco_features,
    compute_job_skills_overlap,
    compute_skills_overlap,
    get_candidate_skill_uris,
    title_occupation_axis,
)


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
    session.add(
        Profile(
            id=1, name="U", email="u@example.com", location="Berlin", job_family="Product Manager"
        )
    )
    session.commit()
    yield session
    session.close()
    connection.close()
    engine.dispose()


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
    # 1.25 / 1.75 = 0.7143
    assert out["overlap_score"] == pytest.approx(0.7143, abs=1e-4)
    assert set(out["matched_uris"]) == {"uri:python", "uri:docker"}
    assert out["missing_uris"] == ["uri:k8s"]


def test_overlap_all_matched_is_one():
    required = [("uri:a", "critical"), ("uri:b", "bonus")]
    out = compute_skills_overlap(required, {"uri:a", "uri:b"})
    assert out["overlap_score"] == 1.0
    assert out["matched"] == 2


def test_overlap_none_matched_is_zero():
    required = [("uri:a", "critical")]
    out = compute_skills_overlap(required, {"uri:x"})
    assert out["overlap_score"] == 0.0
    assert out["matched"] == 0
    assert out["total"] == 1


def test_overlap_empty_requirements_is_zero_not_error():
    out = compute_skills_overlap([], {"uri:a"})
    assert out["overlap_score"] == 0.0
    assert out["total"] == 0
    assert out["total_weight"] == 0.0


def test_overlap_ignores_unnormalized_requirements():
    # Requirements without an esco_uri are not counted.
    required = [("uri:a", "critical"), (None, "critical"), ("", "nice-to-have")]
    out = compute_skills_overlap(required, {"uri:a"})
    assert out["total"] == 1
    assert out["overlap_score"] == 1.0


def test_overlap_unknown_severity_uses_default_weight():
    required = [("uri:a", "weird-label")]
    out = compute_skills_overlap(required, set())
    assert out["total_weight"] == 0.5  # default nice-to-have weight


# ---------------------------------------------------------------------------
# DB wrappers
# ---------------------------------------------------------------------------


def test_get_candidate_skill_uris(db_session):
    db_session.add_all(
        [
            Skill(
                profile_id=1,
                name="Python",
                category="technical",
                proficiency="advanced",
                esco_uri="uri:python",
                evidence_source="manual",
            ),
            Skill(
                profile_id=1,
                name="Docker",
                category="technical",
                proficiency="intermediate",
                esco_uri="uri:docker",
                evidence_source="manual",
            ),
            Skill(
                profile_id=1,
                name="Unmapped",
                category="technical",
                proficiency="beginner",
                esco_uri=None,
                evidence_source="manual",
            ),
        ]
    )
    db_session.commit()
    assert get_candidate_skill_uris(db_session, 1) == {"uri:python", "uri:docker"}


def test_compute_job_skills_overlap_db(db_session):
    app = Application(profile_id=1, company="Acme", role="PM", status="discovered")
    db_session.add(app)
    db_session.add(
        Skill(
            profile_id=1,
            name="Python",
            category="technical",
            proficiency="advanced",
            esco_uri="uri:python",
            evidence_source="manual",
        )
    )
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
    assert out["overlap_score"] == 0.5  # 1.0 / 2.0


# ---------------------------------------------------------------------------
# title_occupation_axis
# ---------------------------------------------------------------------------


def _seed_occupations(db_session):
    db_session.add_all(
        [
            ESCOSkill(concept_uri="uri:pm", preferred_label="Product Manager", isco_group="1213"),
            ESCOSkill(concept_uri="uri:pgm", preferred_label="Program Manager", isco_group="1213"),
            ESCOSkill(
                concept_uri="uri:swe", preferred_label="Software Engineer", isco_group="2512"
            ),
        ]
    )
    db_session.commit()


def test_title_axis_same_occupation(db_session):
    _seed_occupations(db_session)
    out = title_occupation_axis(db_session, "Product Manager", "Product Manager")
    assert out["match_score"] == 1.0
    assert out["same_occupation"] is True
    assert out["same_isco_group"] is True


def test_title_axis_same_isco_group_different_role(db_session):
    _seed_occupations(db_session)
    out = title_occupation_axis(db_session, "Program Manager", "Product Manager")
    assert out["match_score"] == 0.7
    assert out["same_occupation"] is False
    assert out["same_isco_group"] is True
    assert out["jd_occupation"]["isco_group"] == "1213"


def test_title_axis_no_match_different_family(db_session):
    _seed_occupations(db_session)
    out = title_occupation_axis(db_session, "Software Engineer", "Product Manager")
    assert out["match_score"] == 0.0
    assert out["same_occupation"] is False
    assert out["same_isco_group"] is False


def test_title_axis_empty_titles(db_session):
    _seed_occupations(db_session)
    out = title_occupation_axis(db_session, "", None)
    assert out["match_score"] == 0.0
    assert out["jd_occupation"] is None
    assert out["candidate_occupation"] is None


# ---------------------------------------------------------------------------
# compute_esco_features bundle
# ---------------------------------------------------------------------------


def test_compute_esco_features_bundle(db_session):
    _seed_occupations(db_session)
    app = Application(profile_id=1, company="Acme", role="PM", status="discovered")
    db_session.add(app)
    db_session.add(
        Skill(
            profile_id=1,
            name="Python",
            category="technical",
            proficiency="advanced",
            esco_uri="uri:python",
            evidence_source="manual",
        )
    )
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

    out = compute_esco_features(
        db_session,
        profile_id=1,
        application_id=app.id,
        jd_title="Product Manager",
        candidate_role="Product Manager",
    )
    assert out is not None
    assert out["skills_overlap"]["overlap_score"] == 1.0
    assert out["title_occupation"]["match_score"] == 1.0


def test_compute_esco_features_no_application_skips_overlap(db_session):
    _seed_occupations(db_session)
    out = compute_esco_features(
        db_session, profile_id=1, jd_title="Product Manager", candidate_role="Product Manager"
    )
    assert out is not None
    assert "skills_overlap" not in out
    assert out["title_occupation"]["match_score"] == 1.0


def test_compute_esco_features_defensive_returns_none(db_session, monkeypatch):
    """Any internal failure is swallowed → None (best-effort signal)."""
    monkeypatch.setattr(
        "career_os.services.esco_features.title_occupation_axis",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert compute_esco_features(db_session, profile_id=1, jd_title="X", candidate_role="Y") is None
