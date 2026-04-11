"""Unit tests for `career_os.services.skills`.

Direct service-layer tests. The existing `test_skills_api.py` exercises the
HTTP layer; these target the underlying CRUD functions plus their error
paths and side effects (history rows, profile validation).
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.models import Profile
from career_os.models.skills import Skill, SkillHistory
from career_os.services.skills import (
    ProfileNotFoundError,
    SkillNotFoundError,
    create_skill,
    get_skill,
    get_skill_history,
    ingest_skills,
    list_skills,
    update_skill,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()

    session.add(Profile(id=1, name="P", email="p@p.com"))
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# create_skill
# ---------------------------------------------------------------------------


def test_create_skill_persists_and_records_initial_history(db: Session):
    skill = create_skill(
        db,
        profile_id=1,
        data={"name": "Python", "category": "technical", "proficiency": "advanced"},
    )
    assert skill.id is not None
    assert skill.name == "Python"
    assert skill.category == "technical"
    assert skill.proficiency == "advanced"
    assert skill.evidence_source == "manual"

    # initial history record exists
    history = db.query(SkillHistory).filter(SkillHistory.skill_id == skill.id).all()
    assert len(history) == 1
    assert history[0].previous_proficiency is None
    assert history[0].new_proficiency == "advanced"
    assert history[0].reason == "Initial creation"


def test_create_skill_unknown_profile_raises(db: Session):
    with pytest.raises(ProfileNotFoundError):
        create_skill(db, profile_id=999, data={"name": "X", "category": "soft"})


def test_create_skill_default_proficiency(db: Session):
    skill = create_skill(
        db,
        profile_id=1,
        data={"name": "Empathy", "category": "soft"},
    )
    assert skill.proficiency == "beginner"


# ---------------------------------------------------------------------------
# get_skill
# ---------------------------------------------------------------------------


def test_get_skill_returns_skill_for_owning_profile(db: Session):
    skill = create_skill(db, 1, {"name": "Go", "category": "technical"})
    fetched = get_skill(db, skill.id, profile_id=1)
    assert fetched.id == skill.id


def test_get_skill_unknown_id_raises(db: Session):
    with pytest.raises(SkillNotFoundError):
        get_skill(db, skill_id=999, profile_id=1)


def test_get_skill_wrong_profile_raises(db: Session):
    db.add(Profile(id=2, name="Q", email="q@q.com"))
    db.commit()
    skill = create_skill(db, 1, {"name": "Rust", "category": "technical"})

    with pytest.raises(SkillNotFoundError):
        get_skill(db, skill.id, profile_id=2)


# ---------------------------------------------------------------------------
# list_skills
# ---------------------------------------------------------------------------


def test_list_skills_filters_by_category_and_paginates(db: Session):
    create_skill(db, 1, {"name": "Python", "category": "technical"})
    create_skill(db, 1, {"name": "Java", "category": "technical"})
    create_skill(db, 1, {"name": "Negotiation", "category": "soft"})

    techies, total = list_skills(db, 1, category="technical")
    assert total == 2
    assert {s.name for s in techies} == {"Python", "Java"}

    softies, total_soft = list_skills(db, 1, category="soft")
    assert total_soft == 1
    assert softies[0].name == "Negotiation"


def test_list_skills_pagination(db: Session):
    for i in range(5):
        create_skill(db, 1, {"name": f"Skill{i}", "category": "tools"})

    page1, total = list_skills(db, 1, page=1, page_size=2)
    page2, _ = list_skills(db, 1, page=2, page_size=2)
    page3, _ = list_skills(db, 1, page=3, page_size=2)

    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1

    # No overlap
    seen = {s.id for s in page1} | {s.id for s in page2} | {s.id for s in page3}
    assert len(seen) == 5


def test_list_skills_search_query_matches_case_insensitively(db: Session):
    create_skill(db, 1, {"name": "PostgreSQL", "category": "tools"})
    create_skill(db, 1, {"name": "MySQL", "category": "tools"})
    create_skill(db, 1, {"name": "Redis", "category": "tools"})

    matches, total = list_skills(db, 1, q="sql")
    assert total == 2
    assert {s.name for s in matches} == {"PostgreSQL", "MySQL"}


def test_list_skills_filter_by_proficiency(db: Session):
    create_skill(db, 1, {"name": "A", "category": "technical", "proficiency": "expert"})
    create_skill(db, 1, {"name": "B", "category": "technical", "proficiency": "beginner"})

    rows, total = list_skills(db, 1, proficiency="expert")
    assert total == 1
    assert rows[0].name == "A"


# ---------------------------------------------------------------------------
# update_skill
# ---------------------------------------------------------------------------


def test_update_skill_records_history_on_proficiency_change(db: Session):
    skill = create_skill(
        db, 1, {"name": "Kubernetes", "category": "tools", "proficiency": "beginner"}
    )

    update_skill(
        db,
        skill_id=skill.id,
        profile_id=1,
        data={"proficiency": "advanced", "reason": "Built prod cluster"},
    )

    history = (
        db.query(SkillHistory)
        .filter(SkillHistory.skill_id == skill.id)
        .order_by(SkillHistory.id)
        .all()
    )
    # initial + the upgrade
    assert len(history) == 2
    assert history[1].previous_proficiency == "beginner"
    assert history[1].new_proficiency == "advanced"
    assert history[1].reason == "Built prod cluster"


def test_update_skill_no_change_no_history(db: Session):
    skill = create_skill(
        db, 1, {"name": "Docker", "category": "tools", "proficiency": "intermediate"}
    )

    update_skill(
        db,
        skill_id=skill.id,
        profile_id=1,
        data={"proficiency": "intermediate"},  # same value
    )

    history = db.query(SkillHistory).filter(SkillHistory.skill_id == skill.id).all()
    # only the initial creation record
    assert len(history) == 1


def test_update_skill_can_clear_evidence_detail(db: Session):
    skill = create_skill(
        db,
        1,
        {
            "name": "Terraform",
            "category": "tools",
            "evidence_detail": "Used at Acme",
        },
    )
    assert skill.evidence_detail == "Used at Acme"

    update_skill(db, skill.id, 1, {"evidence_detail": None})
    db.refresh(skill)
    assert skill.evidence_detail is None


def test_update_skill_unknown_attribute_silently_skipped(db: Session):
    skill = create_skill(db, 1, {"name": "Bash", "category": "tools"})
    # bogus_field doesn't exist on Skill — should be skipped, not raise
    update_skill(db, skill.id, 1, {"bogus_field": "ignored", "name": "Bash++"})
    db.refresh(skill)
    assert skill.name == "Bash++"


# ---------------------------------------------------------------------------
# get_skill_history
# ---------------------------------------------------------------------------


def test_get_skill_history_returns_descending_order(db: Session):
    skill = create_skill(db, 1, {"name": "SQL", "category": "tools", "proficiency": "beginner"})
    update_skill(db, skill.id, 1, {"proficiency": "intermediate"})
    update_skill(db, skill.id, 1, {"proficiency": "advanced"})

    history = get_skill_history(db, skill.id, profile_id=1)
    # 1 initial + 2 upgrades
    assert len(history) == 3
    # Newest first
    assert history[0].new_proficiency == "advanced"
    assert history[-1].previous_proficiency is None


def test_get_skill_history_unknown_skill_raises(db: Session):
    with pytest.raises(SkillNotFoundError):
        get_skill_history(db, skill_id=999, profile_id=1)


# ---------------------------------------------------------------------------
# ingest_skills
# ---------------------------------------------------------------------------


def test_ingest_skills_unknown_profile_raises(db: Session):
    with pytest.raises(ProfileNotFoundError):
        ingest_skills(db, profile_id=999)


def test_ingest_skills_creates_new_skills(db: Session):
    """ingest_skills() creates new Skill rows from a parsed IngestionResult."""
    from career_os.services.skills_parsing import IngestionResult, ParsedSkill

    parsed = [
        ParsedSkill(
            name="GraphQL",
            category="technical",
            proficiency="intermediate",
            evidence_source="cv.yaml",
        ),
        ParsedSkill(
            name="Mentoring",
            category="soft",
            proficiency="advanced",
            evidence_source="cv.yaml",
        ),
    ]
    fake_result = IngestionResult(skills=parsed, sources_processed=["cv.yaml"], errors=[])

    with patch(
        "career_os.services.skills.ingest_all_skills",
        return_value=fake_result,
    ):
        result = ingest_skills(db, profile_id=1)

    assert result["skills_created"] == 2
    assert result["skills_updated"] == 0
    assert result["sources_processed"] == ["cv.yaml"]
    names = {s.name for s in db.query(Skill).filter(Skill.profile_id == 1).all()}
    assert {"GraphQL", "Mentoring"} <= names


def test_ingest_skills_updates_existing_skill_with_new_source(db: Session):
    """When the same skill is parsed from a new source, evidence merges."""
    from career_os.services.skills_parsing import IngestionResult, ParsedSkill

    create_skill(
        db,
        1,
        {
            "name": "Python",
            "category": "technical",
            "proficiency": "intermediate",
            "evidence_source": "cv.yaml",
        },
    )

    parsed = [
        ParsedSkill(
            name="Python",
            category="technical",
            proficiency="intermediate",
            evidence_source="profile.yaml",
        ),
    ]
    fake_result = IngestionResult(skills=parsed, sources_processed=["profile.yaml"], errors=[])

    with patch(
        "career_os.services.skills.ingest_all_skills",
        return_value=fake_result,
    ):
        result = ingest_skills(db, profile_id=1)

    # Should have updated, not created a duplicate
    assert result["skills_created"] == 0
    rows = db.query(Skill).filter(Skill.name == "Python").all()
    assert len(rows) == 1
    assert "profile.yaml" in rows[0].evidence_source
