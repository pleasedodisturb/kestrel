"""Gap Analysis API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import DESC_ACTIVE_PROFILE_ID, RESP_404
from career_os.database import get_db
from career_os.models.models import Application
from career_os.models.skills import JobRequirement
from career_os.schemas.gaps import (
    AggregateGapItem,
    AggregateGapResponse,
    GapAnalysisResponse,
    GapItem,
    JobRequirementBulkCreate,
    JobRequirementResponse,
)
from career_os.services.gap_analysis import (
    ApplicationNotFoundError,
    MissingRequirementsError,
    ProfileNotFoundError,
    aggregate_gaps,
    analyze_gaps,
    create_job_requirements,
)

router = APIRouter(tags=["gaps"])


@router.get(
    "/api/applications/{application_id}/gaps",
    responses={**RESP_404, 400: {"description": "Bad request"}},
)
async def get_application_gaps(
    application_id: int,
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> GapAnalysisResponse:
    """Perform gap analysis for a specific application.

    Compares the application's job requirements against the profile's
    skills inventory. Returns gaps with severity, distance, and a
    weighted readiness score (0-100).

    Returns 400 if no requirements are parsed for the application.
    Returns 404 if the application doesn't exist or belongs to another profile.
    """
    try:
        result = analyze_gaps(db, application_id, profile_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MissingRequirementsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GapAnalysisResponse(
        application_id=result["application_id"],
        company=result["company"],
        role=result["role"],
        gaps=[GapItem(**g) for g in result["gaps"]],
        readiness_score=result["readiness_score"],
        total_requirements=result["total_requirements"],
        gaps_count=result["gaps_count"],
    )


@router.get(
    "/api/gaps/aggregate",
    responses=RESP_404,
)
async def get_aggregate_gaps(
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> AggregateGapResponse:
    """Get aggregate gap analysis across all applications.

    Returns skills that are gaps across multiple applications,
    ranked by frequency. Useful for identifying the most impactful
    skills to learn.
    """
    try:
        result = aggregate_gaps(db, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AggregateGapResponse(
        gaps=[AggregateGapItem(**g) for g in result["gaps"]],
        total_applications_analyzed=result["total_applications_analyzed"],
    )


@router.get(
    "/api/applications/{application_id}/requirements",
)
async def get_requirements(
    application_id: int,
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> list[JobRequirementResponse]:
    """Get job requirements for an application.

    Returns the list of parsed requirements (useful for linking
    gap analysis to learning recommendations).
    Requirements for archived applications are hidden (VAL-CROSS-019).
    """
    reqs = (
        db.query(JobRequirement)
        .join(Application, JobRequirement.application_id == Application.id)
        .filter(
            JobRequirement.application_id == application_id,
            JobRequirement.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .all()
    )
    return [JobRequirementResponse.model_validate(r) for r in reqs]


@router.post(
    "/api/applications/{application_id}/requirements",
    status_code=201,
    responses=RESP_404,
)
async def create_requirements(
    application_id: int,
    payload: JobRequirementBulkCreate,
    db: Annotated[Session, Depends(get_db)],
) -> list[JobRequirementResponse]:
    """Create job requirements for an application.

    This endpoint allows adding parsed requirements from a job posting
    to enable gap analysis.
    """
    try:
        reqs = create_job_requirements(
            db,
            application_id,
            payload.profile_id,
            [
                {
                    "skill_name": r.skill_name,
                    "required_level": r.required_level.value,
                    "severity": r.severity.value if r.severity is not None else None,
                }
                for r in payload.requirements
            ],
        )
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [JobRequirementResponse.model_validate(r) for r in reqs]
