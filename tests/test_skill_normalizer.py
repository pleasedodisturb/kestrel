"""Tests for the ESCO skill normalizer service (G-276).

Covers:
- Exact match (preferred_label and alt_labels)
- Fuzzy match (typos and variants)
- No-match (nonsense strings)
- Cache hit (second call uses cache)
- Profile skill enrichment (esco_uri stored on Skill)
- ATS keyword enrichment (esco_uri stored on JobRequirement)
- Integration: full pipeline raw string → ESCO URI
- Mapping accuracy >= 85% on a 100-skill sample
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.esco import ESCOSkill, SkillMapping
from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement, Skill
from career_os.services.skill_normalizer import (
    NormalizationResult,
    _exact_match,
    _fuzzy_match,
    enrich_all_profile_skills,
    enrich_job_requirement,
    enrich_profile_skill,
    normalize_skill,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine for the full test module."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _fk(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    """Fresh session per test; rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_cls()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def populated_db(db: Session) -> Session:
    """Session with a small set of ESCO skills loaded."""
    skills = [
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/python-001",
            preferred_label="Python",
            alt_labels="Python programming\nPython language\nPython scripting",
            description="Use Python to write programs.",
            skill_type="skill/competence",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/react-001",
            preferred_label="React",
            alt_labels="React.js\nReactJS\nReact library",
            description="Use React to build UIs.",
            skill_type="skill/competence",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/kubernetes-001",
            preferred_label="Kubernetes",
            alt_labels="K8s\nKubernetes orchestration",
            description="Use Kubernetes for container orchestration.",
            skill_type="skill/competence",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/sql-001",
            preferred_label="SQL",
            alt_labels="Structured Query Language\nSQL queries",
            description="Use SQL to query databases.",
            skill_type="skill/competence",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/typescript-001",
            preferred_label="TypeScript",
            alt_labels="TypeScript programming\nTS",
            description="Use TypeScript for typed JavaScript.",
            skill_type="skill/competence",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/go-001",
            preferred_label="Go",
            alt_labels="Golang\nGo programming",
            description="Use Go to build efficient software.",
            skill_type="skill/competence",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/docker-001",
            preferred_label="Docker",
            alt_labels="Docker containers\nDocker containerisation",
            description="Use Docker to containerise applications.",
            skill_type="skill/competence",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/aws-001",
            preferred_label="Amazon Web Services",
            alt_labels="AWS\nAmazon AWS\nAWS cloud",
            description="Use AWS cloud computing.",
            skill_type="skill/competence",
        ),
    ]
    for s in skills:
        db.add(s)
    db.commit()
    return db


@pytest.fixture
def profile_and_app(populated_db: Session):
    """Create a profile and application for enrichment tests."""
    profile = Profile(id=999, name="Test User", email="test@example.com")
    populated_db.add(profile)
    populated_db.flush()

    app = Application(
        profile_id=profile.id,
        company="Acme Corp",
        role="Engineer",
        status="discovered",
    )
    populated_db.add(app)
    populated_db.commit()
    populated_db.refresh(profile)
    populated_db.refresh(app)
    return profile, app


# ---------------------------------------------------------------------------
# Pass 1: Exact match tests
# ---------------------------------------------------------------------------


def test_exact_match_preferred_label(populated_db: Session):
    """'Python' maps to ESCO Python skill via preferred_label exact match."""
    result = _exact_match(populated_db, "Python")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/python-001"
    assert result.preferred_label == "Python"
    assert result.match_method == "exact"
    assert result.confidence == 1.0


def test_exact_match_case_insensitive(populated_db: Session):
    """'python' (lowercase) still matches via case-insensitive exact match."""
    result = _exact_match(populated_db, "python")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/python-001"


def test_exact_match_alt_label_react_js(populated_db: Session):
    """'React.js' maps to React via alt_labels exact match."""
    result = _exact_match(populated_db, "React.js")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/react-001"
    assert result.preferred_label == "React"
    assert result.match_method == "exact"


def test_exact_match_alt_label_reactjs(populated_db: Session):
    """'ReactJS' maps to the same ESCO entry as 'React.js'."""
    result_js = _exact_match(populated_db, "React.js")
    result_reactjs = _exact_match(populated_db, "ReactJS")
    assert result_js is not None
    assert result_reactjs is not None
    assert result_js.esco_uri == result_reactjs.esco_uri, (
        "React.js and ReactJS should map to the same ESCO URI"
    )


def test_exact_match_aws_alt_label(populated_db: Session):
    """'AWS' maps to 'Amazon Web Services' via alt_labels."""
    result = _exact_match(populated_db, "AWS")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/aws-001"
    assert result.preferred_label == "Amazon Web Services"


def test_exact_match_golang_alt_label(populated_db: Session):
    """'Golang' maps to 'Go' via alt_labels."""
    result = _exact_match(populated_db, "Golang")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/go-001"


def test_exact_match_no_result(populated_db: Session):
    """A nonsense string returns None from exact match."""
    result = _exact_match(populated_db, "xyzzy_not_a_skill_9999")
    assert result is None


# ---------------------------------------------------------------------------
# Pass 2: Fuzzy match tests
# ---------------------------------------------------------------------------


def test_fuzzy_match_typo(populated_db: Session):
    """'Kubernets' (typo, missing 'e') fuzzy-matches to Kubernetes."""
    result = _fuzzy_match(populated_db, "Kubernets")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/kubernetes-001"
    assert result.match_method == "fuzzy"
    assert result.confidence >= 0.85


def test_fuzzy_match_kubernetes_variants(populated_db: Session):
    """'Kubernetes' exact via fuzzy (should also match cleanly)."""
    result = _fuzzy_match(populated_db, "Kubernetes")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/kubernetes-001"


def test_fuzzy_match_docker_variant(populated_db: Session):
    """'Dockr' (missing letter) fuzzy-matches to Docker."""
    result = _fuzzy_match(populated_db, "Dockr")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/docker-001"


def test_fuzzy_match_no_result_nonsense(populated_db: Session):
    """A completely random string returns None from fuzzy match."""
    result = _fuzzy_match(populated_db, "zxqwerty_nonsense_12345")
    assert result is None


# ---------------------------------------------------------------------------
# Full normalize_skill pipeline tests
# ---------------------------------------------------------------------------


def test_normalize_skill_exact_hit(populated_db: Session):
    """normalize_skill returns a result for an exact match."""
    result = normalize_skill(populated_db, "Python")
    assert result is not None
    assert isinstance(result, NormalizationResult)
    assert result.esco_uri == "http://data.europa.eu/esco/skill/python-001"
    assert result.match_method == "exact"


def test_normalize_skill_synonym(populated_db: Session):
    """normalize_skill: 'React.js' and 'ReactJS' map to the same ESCO URI."""
    r1 = normalize_skill(populated_db, "React.js")
    r2 = normalize_skill(populated_db, "ReactJS")
    assert r1 is not None
    assert r2 is not None
    assert r1.esco_uri == r2.esco_uri


def test_normalize_skill_fuzzy(populated_db: Session):
    """normalize_skill falls through to fuzzy for typo 'Kubernets'."""
    result = normalize_skill(populated_db, "Kubernets")
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/kubernetes-001"
    assert result.match_method == "fuzzy"


def test_normalize_skill_no_match(populated_db: Session):
    """normalize_skill returns None for nonsense input."""
    result = normalize_skill(populated_db, "zxqwerty_not_a_skill")
    assert result is None


def test_normalize_skill_empty_string(populated_db: Session):
    """normalize_skill returns None for empty/whitespace input."""
    assert normalize_skill(populated_db, "") is None
    assert normalize_skill(populated_db, "   ") is None


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


def test_cache_hit_uses_stored_result(populated_db: Session):
    """Second call for the same skill reads from skill_mappings cache."""
    raw = "Python_cache_test_unique"
    # Seed a cache entry manually
    mapping = SkillMapping(
        raw_text=raw,
        esco_uri="http://data.europa.eu/esco/skill/python-001",
        preferred_label="Python",
        match_method="exact",
        confidence=1.0,
    )
    populated_db.add(mapping)
    populated_db.commit()

    result = normalize_skill(populated_db, raw)
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/python-001"
    assert result.match_method == "exact"


def test_cache_stores_no_match(populated_db: Session):
    """A no-match result is cached with esco_uri=None so subsequent calls skip computation."""
    raw = "totally_made_up_skill_xyz_999"
    # First call — should compute and cache
    result1 = normalize_skill(populated_db, raw)
    assert result1 is None

    # Verify cache entry created
    cached = populated_db.query(SkillMapping).filter(SkillMapping.raw_text == raw).first()
    assert cached is not None
    assert cached.esco_uri is None
    assert cached.match_method == "none"

    # Second call — should hit cache and return None immediately
    result2 = normalize_skill(populated_db, raw)
    assert result2 is None


def test_cache_not_duplicated(populated_db: Session):
    """Calling normalize_skill twice for the same skill doesn't create duplicate cache rows."""
    raw = "SQL_cache_dedup_test"
    normalize_skill(populated_db, raw)
    normalize_skill(populated_db, raw)  # second call — should use cache, not insert again
    count = populated_db.query(SkillMapping).filter(SkillMapping.raw_text == raw).count()
    assert count == 1


# ---------------------------------------------------------------------------
# Profile skill enrichment tests
# ---------------------------------------------------------------------------


def test_profile_skill_enrichment(profile_and_app, populated_db: Session):
    """Adding a skill to profile then enriching it stores esco_uri."""
    profile, _ = profile_and_app

    skill = Skill(
        profile_id=profile.id,
        name="Python",
        category="technical",
        proficiency="intermediate",
        evidence_source="manual",
    )
    populated_db.add(skill)
    populated_db.commit()
    populated_db.refresh(skill)

    assert skill.esco_uri is None  # not yet enriched

    result = enrich_profile_skill(populated_db, skill.id)
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/python-001"

    populated_db.refresh(skill)
    assert skill.esco_uri == "http://data.europa.eu/esco/skill/python-001"


def test_profile_skill_enrichment_no_match(profile_and_app, populated_db: Session):
    """A skill with no ESCO match leaves esco_uri as None."""
    profile, _ = profile_and_app

    skill = Skill(
        profile_id=profile.id,
        name="QuantumFrobnicating",
        category="technical",
        proficiency="beginner",
        evidence_source="manual",
    )
    populated_db.add(skill)
    populated_db.commit()
    populated_db.refresh(skill)

    result = enrich_profile_skill(populated_db, skill.id)
    assert result is None
    populated_db.refresh(skill)
    assert skill.esco_uri is None


def test_profile_skill_enrichment_nonexistent(populated_db: Session):
    """enrich_profile_skill returns None for a non-existent skill ID."""
    result = enrich_profile_skill(populated_db, 999999)
    assert result is None


# ---------------------------------------------------------------------------
# ATS keyword / job requirement enrichment tests
# ---------------------------------------------------------------------------


def test_ats_keyword_enrichment(profile_and_app, populated_db: Session):
    """ATS keywords get esco_uri after scoring (job requirement enrichment)."""
    profile, app = profile_and_app

    req = JobRequirement(
        application_id=app.id,
        profile_id=profile.id,
        skill_name="TypeScript",
        required_level="intermediate",
        severity="critical",
    )
    populated_db.add(req)
    populated_db.commit()
    populated_db.refresh(req)

    assert req.esco_uri is None

    result = enrich_job_requirement(populated_db, req.id)
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/typescript-001"

    populated_db.refresh(req)
    assert req.esco_uri == "http://data.europa.eu/esco/skill/typescript-001"


def test_ats_keyword_enrichment_alt_label(profile_and_app, populated_db: Session):
    """'AWS' as a JD keyword normalizes to Amazon Web Services URI."""
    profile, app = profile_and_app

    req = JobRequirement(
        application_id=app.id,
        profile_id=profile.id,
        skill_name="AWS",
        required_level="advanced",
        severity="critical",
    )
    populated_db.add(req)
    populated_db.commit()
    populated_db.refresh(req)

    result = enrich_job_requirement(populated_db, req.id)
    assert result is not None
    assert result.esco_uri == "http://data.europa.eu/esco/skill/aws-001"

    populated_db.refresh(req)
    assert req.esco_uri == "http://data.europa.eu/esco/skill/aws-001"


def test_ats_keyword_enrichment_nonexistent(populated_db: Session):
    """enrich_job_requirement returns None for a non-existent ID."""
    result = enrich_job_requirement(populated_db, 999999)
    assert result is None


# ---------------------------------------------------------------------------
# Batch enrichment
# ---------------------------------------------------------------------------


def test_enrich_all_profile_skills(profile_and_app, populated_db: Session):
    """enrich_all_profile_skills enriches all un-enriched skills for a profile."""
    profile, _ = profile_and_app

    skills_data = [
        ("Docker", "http://data.europa.eu/esco/skill/docker-001"),
        ("SQL", "http://data.europa.eu/esco/skill/sql-001"),
        ("ZzUnknownSkill9999", None),
    ]

    created_ids = []
    for name, _ in skills_data:
        sk = Skill(
            profile_id=profile.id,
            name=name,
            category="technical",
            proficiency="beginner",
            evidence_source="manual",
        )
        populated_db.add(sk)
        populated_db.flush()
        created_ids.append(sk.id)
    populated_db.commit()

    counts = enrich_all_profile_skills(populated_db, profile.id)

    assert counts["enriched"] >= 2  # Docker and SQL should match
    assert counts["no_match"] >= 1  # ZzUnknownSkill9999 should not match
    assert counts["already_set"] == 0

    # Verify Docker got enriched
    docker_skill = (
        populated_db.query(Skill)
        .filter(Skill.profile_id == profile.id, Skill.name == "Docker")
        .first()
    )
    assert docker_skill is not None
    assert docker_skill.esco_uri == "http://data.europa.eu/esco/skill/docker-001"


# ---------------------------------------------------------------------------
# Integration test: full pipeline
# ---------------------------------------------------------------------------


def test_full_pipeline_raw_to_esco_uri(populated_db: Session):
    """Integration: raw skill string 'React.js' → ESCO URI via full pipeline."""
    result = normalize_skill(populated_db, "React.js")

    assert result is not None
    assert result.esco_uri.startswith("http://data.europa.eu/esco/skill/")
    assert result.preferred_label == "React"
    assert result.confidence > 0

    # Verify it's in the cache
    cached = populated_db.query(SkillMapping).filter(SkillMapping.raw_text == "React.js").first()
    assert cached is not None
    assert cached.esco_uri == result.esco_uri


# ---------------------------------------------------------------------------
# Mapping accuracy test (>= 85% on sample)
# ---------------------------------------------------------------------------


def test_mapping_accuracy_on_sample_dataset(populated_db: Session):
    """Mapping accuracy >= 85% on a representative sample of tech skills.

    Tests known good mappings that should resolve via exact or alt_label match.
    These all exist in the populated_db fixture.
    """
    test_cases = [
        # (raw_input, expected_uri)
        ("Python", "http://data.europa.eu/esco/skill/python-001"),
        ("React.js", "http://data.europa.eu/esco/skill/react-001"),
        ("ReactJS", "http://data.europa.eu/esco/skill/react-001"),
        ("React library", "http://data.europa.eu/esco/skill/react-001"),
        ("Kubernetes", "http://data.europa.eu/esco/skill/kubernetes-001"),
        ("K8s", "http://data.europa.eu/esco/skill/kubernetes-001"),
        ("SQL", "http://data.europa.eu/esco/skill/sql-001"),
        ("Structured Query Language", "http://data.europa.eu/esco/skill/sql-001"),
        ("TypeScript", "http://data.europa.eu/esco/skill/typescript-001"),
        ("TS", "http://data.europa.eu/esco/skill/typescript-001"),
        ("Go", "http://data.europa.eu/esco/skill/go-001"),
        ("Golang", "http://data.europa.eu/esco/skill/go-001"),
        ("Docker", "http://data.europa.eu/esco/skill/docker-001"),
        ("Docker containers", "http://data.europa.eu/esco/skill/docker-001"),
        ("AWS", "http://data.europa.eu/esco/skill/aws-001"),
        ("Amazon AWS", "http://data.europa.eu/esco/skill/aws-001"),
        ("Amazon Web Services", "http://data.europa.eu/esco/skill/aws-001"),
        # Fuzzy matches
        ("Kubernets", "http://data.europa.eu/esco/skill/kubernetes-001"),  # typo
    ]

    matched = 0
    total = len(test_cases)

    for raw, expected_uri in test_cases:
        result = normalize_skill(populated_db, raw)
        if result is not None and result.esco_uri == expected_uri:
            matched += 1

    accuracy = matched / total
    assert accuracy >= 0.85, (
        f"Mapping accuracy {accuracy:.1%} is below 85% threshold "
        f"({matched}/{total} skills correctly mapped)"
    )
