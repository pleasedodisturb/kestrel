"""Skills service: CRUD and ingestion for the skills inventory."""

from pathlib import Path

from sqlalchemy.orm import Session

from career_os.models.skills import Skill, SkillHistory
from career_os.services.skills_parsing import (
    IngestionResult,
    ingest_all_skills,
    merge_skills,
)


class SkillNotFoundError(Exception):
    """Raised when a skill is not found."""

    pass


class ProfileNotFoundError(Exception):
    """Raised when the profile doesn't exist."""

    pass


def _verify_profile(db: Session, profile_id: int) -> None:
    """Verify profile exists, raise ProfileNotFoundError if not."""
    from career_os.models.models import Profile

    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")


def list_skills(
    db: Session,
    profile_id: int,
    *,
    category: str | None = None,
    source: str | None = None,
    proficiency: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Skill], int]:
    """List skills with optional filters.

    Args:
        db: Database session.
        profile_id: Profile to list skills for.
        category: Filter by category (technical/domain/soft/tools).
        source: Filter by evidence_source (prefix match).
        proficiency: Filter by proficiency level.
        q: Search query (matches name, case-insensitive).
        page: Page number (1-based).
        page_size: Results per page.

    Returns:
        Tuple of (skills list, total count).
    """
    query = db.query(Skill).filter(Skill.profile_id == profile_id)

    if category:
        query = query.filter(Skill.category == category.lower())
    if source:
        query = query.filter(Skill.evidence_source.like(f"%{source}%"))
    if proficiency:
        query = query.filter(Skill.proficiency == proficiency.lower())
    if q:
        query = query.filter(Skill.name.ilike(f"%{q}%"))

    total = query.count()
    offset = (page - 1) * page_size
    skills = query.order_by(Skill.name).offset(offset).limit(page_size).all()

    return skills, total


def get_skill(db: Session, skill_id: int, profile_id: int) -> Skill:
    """Get a single skill by ID, scoped to profile."""
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.profile_id == profile_id).first()
    if not skill:
        raise SkillNotFoundError(f"Skill {skill_id} not found")
    return skill


def create_skill(db: Session, profile_id: int, data: dict) -> Skill:
    """Create a new skill manually."""
    _verify_profile(db, profile_id)

    skill = Skill(
        profile_id=profile_id,
        name=data["name"],
        category=data["category"],
        proficiency=data.get("proficiency", "beginner"),
        evidence_source=data.get("evidence_source", "manual"),
        evidence_detail=data.get("evidence_detail"),
    )
    db.add(skill)

    # Record initial history
    history = SkillHistory(
        skill_id=0,  # placeholder, set after flush
        profile_id=profile_id,
        previous_proficiency=None,
        new_proficiency=skill.proficiency,
        reason="Initial creation",
    )
    db.flush()  # get the skill ID
    history.skill_id = skill.id
    db.add(history)
    db.commit()
    db.refresh(skill)
    return skill


def update_skill(db: Session, skill_id: int, profile_id: int, data: dict) -> Skill:
    """Update a skill, recording history if proficiency changes.

    Explicit ``None`` values are allowed for nullable fields
    (e.g. ``evidence_detail``) so callers can clear them.
    """
    skill = get_skill(db, skill_id, profile_id)

    old_proficiency = skill.proficiency

    # Nullable columns that may be intentionally cleared
    _nullable_fields = {"evidence_detail"}

    for key, value in data.items():
        if not hasattr(skill, key):
            continue
        # Allow explicit None for nullable fields; skip None for others
        if value is None and key not in _nullable_fields:
            continue
        setattr(skill, key, value)

    # Record proficiency change in history
    if "proficiency" in data and data["proficiency"] != old_proficiency:
        history = SkillHistory(
            skill_id=skill.id,
            profile_id=profile_id,
            previous_proficiency=old_proficiency,
            new_proficiency=data["proficiency"],
            reason=data.get("reason", "Manual update"),
        )
        db.add(history)

    db.commit()
    db.refresh(skill)
    return skill


def get_skill_history(db: Session, skill_id: int, profile_id: int) -> list[SkillHistory]:
    """Get proficiency change history for a skill."""
    # Verify skill exists and belongs to profile
    get_skill(db, skill_id, profile_id)

    return (
        db.query(SkillHistory)
        .filter(SkillHistory.skill_id == skill_id, SkillHistory.profile_id == profile_id)
        .order_by(SkillHistory.created_at.desc())
        .all()
    )


def ingest_skills(
    db: Session,
    profile_id: int,
    *,
    cv_path: Path | None = None,
    profile_dir: Path | None = None,
    sources: list[str] | None = None,
) -> dict:
    """Run skills ingestion and persist to database.

    This is the main entry point for parsing and storing skills from
    CV, assessments, and profile docs.

    Returns:
        Dictionary with skills_created, skills_updated, sources_processed, errors.
    """
    _verify_profile(db, profile_id)

    # Parse all sources
    ingestion: IngestionResult = ingest_all_skills(
        cv_path=cv_path,
        profile_dir=profile_dir,
        sources=sources,
    )

    # Get existing skills for this profile
    existing_skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    existing_by_name: dict[str, Skill] = {s.name.lower().strip(): s for s in existing_skills}

    # Merge parsed skills (dedup and upgrade proficiency)
    merged = merge_skills([], ingestion.skills)

    skills_created = 0
    skills_updated = 0

    for parsed in merged:
        key = parsed.name.lower().strip()
        if key in existing_by_name:
            # Update existing skill — merge evidence sources and upgrade proficiency
            existing = existing_by_name[key]
            from career_os.services.skills_parsing import (
                _evidence_sources_set,
                _higher_proficiency,
                _proficiency_from_source_count,
            )

            # Merge evidence sources (track all distinct sources)
            existing_sources = _evidence_sources_set(existing.evidence_source)
            new_sources = _evidence_sources_set(parsed.evidence_source)
            all_sources = existing_sources | new_sources
            merged_source_str = ", ".join(sorted(all_sources))

            # Compute new proficiency: max of existing, parsed, and source-count-based
            source_prof = _proficiency_from_source_count(len(all_sources))
            new_prof = _higher_proficiency(
                existing.proficiency,
                _higher_proficiency(parsed.proficiency, source_prof),
            )

            changed = False
            if new_prof != existing.proficiency:
                old_prof = existing.proficiency
                existing.proficiency = new_prof
                # Record history
                history = SkillHistory(
                    skill_id=existing.id,
                    profile_id=profile_id,
                    previous_proficiency=old_prof,
                    new_proficiency=new_prof,
                    reason=f"Ingestion from {parsed.evidence_source}",
                )
                db.add(history)
                changed = True

            # Always update evidence source and detail when new sources are added
            if new_sources - existing_sources:
                existing.evidence_source = merged_source_str
                if parsed.evidence_detail:
                    if existing.evidence_detail:
                        existing.evidence_detail += f" | {parsed.evidence_detail}"
                    else:
                        existing.evidence_detail = parsed.evidence_detail
                changed = True

            if changed:
                skills_updated += 1
        else:
            # Create new skill
            skill = Skill(
                profile_id=profile_id,
                name=parsed.name,
                category=parsed.category,
                proficiency=parsed.proficiency,
                evidence_source=parsed.evidence_source,
                evidence_detail=parsed.evidence_detail,
            )
            db.add(skill)
            db.flush()

            # Record initial history
            history = SkillHistory(
                skill_id=skill.id,
                profile_id=profile_id,
                previous_proficiency=None,
                new_proficiency=parsed.proficiency,
                reason=f"Ingested from {parsed.evidence_source}",
            )
            db.add(history)
            skills_created += 1
            existing_by_name[skill.name.lower().strip()] = skill

    db.commit()

    return {
        "skills_created": skills_created,
        "skills_updated": skills_updated,
        "sources_processed": ingestion.sources_processed,
        "errors": ingestion.errors,
    }
