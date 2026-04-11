"""Skills Intelligence API routes."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import (
    DESC_ACTIVE_PROFILE_ID,
    DESC_FILTER_BY_CATEGORY,
    RESP_404,
)
from career_os.database import get_db
from career_os.schemas.skills import (
    IngestRequest,
    IngestResponse,
    SkillCreate,
    SkillHistoryResponse,
    SkillListResponse,
    SkillResponse,
    SkillsEmptyStateResponse,
    SkillUpdate,
)
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

router = APIRouter(prefix="/api/skills", tags=["skills"])

# Default paths for parsing sources
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/../../../
_DEFAULT_CV_PATH = _PROJECT_ROOT / "cv" / "cv.yaml"
_DEFAULT_PROFILE_DIR = _PROJECT_ROOT / "profile"


@router.get("")
async def list_skills_endpoint(
    profile_id: Annotated[int, Query(description="Profile to list skills for")],
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[str | None, Query(description=DESC_FILTER_BY_CATEGORY)] = None,
    source: Annotated[str | None, Query(description="Filter by evidence source")] = None,
    proficiency: Annotated[str | None, Query(description="Filter by proficiency")] = None,
    q: Annotated[str | None, Query(description="Search by name")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Results per page")] = 50,
) -> SkillListResponse | SkillsEmptyStateResponse:
    """List skills with optional filters.

    Returns empty state with CTAs when no skills exist.
    """
    skills, total = list_skills(
        db,
        profile_id=profile_id,
        category=category,
        source=source,
        proficiency=proficiency,
        q=q,
        page=page,
        page_size=page_size,
    )

    # Check if the profile has ANY skills (not just filtered results)
    if total == 0 and not any([category, source, proficiency, q]):
        return SkillsEmptyStateResponse()

    return SkillListResponse(
        skills=[SkillResponse.model_validate(s) for s in skills],
        total=total,
    )


@router.get("/{skill_id}", responses=RESP_404)
async def get_skill_endpoint(
    skill_id: int,
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> SkillResponse:
    """Get a single skill by ID."""
    try:
        skill = get_skill(db, skill_id, profile_id)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillResponse.model_validate(skill)


@router.get("/{skill_id}/history", responses=RESP_404)
async def get_skill_history_endpoint(
    skill_id: int,
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SkillHistoryResponse]:
    """Get proficiency change history for a skill."""
    try:
        history = get_skill_history(db, skill_id, profile_id)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [SkillHistoryResponse.model_validate(h) for h in history]


@router.post("", status_code=201, responses=RESP_404)
async def create_skill_endpoint(
    payload: SkillCreate,
    db: Annotated[Session, Depends(get_db)],
) -> SkillResponse:
    """Create a new skill manually.

    NOTE: evidence_source is always forced to 'manual' regardless of
    client-supplied value, to prevent provenance forgery (e.g., claiming
    cv.yaml or profile as the source for a manually created skill).
    """
    try:
        skill = create_skill(
            db,
            payload.profile_id,
            {
                "name": payload.name,
                "category": payload.category.value,
                "proficiency": payload.proficiency.value,
                "evidence_source": "manual",  # Always force manual - ignore client value
                "evidence_detail": payload.evidence_detail,
            },
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillResponse.model_validate(skill)


@router.put("/{skill_id}", responses=RESP_404)
async def update_skill_endpoint(
    skill_id: int,
    payload: SkillUpdate,
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> SkillResponse:
    """Update a skill. Records history if proficiency changes."""
    # Convert to dict, excluding unset fields (None means "don't change")
    update_data = payload.model_dump(exclude_unset=True)
    # Convert enum values to strings for the service layer
    if "category" in update_data and update_data["category"] is not None:
        update_data["category"] = str(update_data["category"])
    if "proficiency" in update_data and update_data["proficiency"] is not None:
        update_data["proficiency"] = str(update_data["proficiency"])
    try:
        skill = update_skill(db, skill_id, profile_id, update_data)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillResponse.model_validate(skill)


@router.post("/ingest", responses=RESP_404)
async def ingest_skills_endpoint(
    payload: IngestRequest,
    db: Annotated[Session, Depends(get_db)],
) -> IngestResponse:
    """Ingest skills from CV, assessments, and/or profile docs.

    Parses source documents and creates/updates skills in the database.
    """
    cv_path = _DEFAULT_CV_PATH if "cv" in payload.sources else None
    profile_dir = (
        _DEFAULT_PROFILE_DIR
        if any(s in payload.sources for s in ["assessments", "profile"])
        else None
    )

    try:
        result = ingest_skills(
            db,
            payload.profile_id,
            cv_path=cv_path,
            profile_dir=profile_dir,
            sources=payload.sources,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return IngestResponse(
        skills_created=result["skills_created"],
        skills_updated=result["skills_updated"],
        sources_processed=result["sources_processed"],
        errors=result["errors"],
    )
