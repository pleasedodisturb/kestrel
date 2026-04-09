"""Learning Paths API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.learning import (
    GapRecommendationsResponse,
    LearningResourceCreate,
    LearningResourceResponse,
    LearningStatusUpdate,
    RecommendationsCTA,
    TemplateRecommendation,
)
from career_os.services.learning import (
    GapNotFoundError,
    InvalidStatusTransitionError,
    LearningResourceNotFoundError,
    create_learning_resource,
    get_gap_recommendations,
    update_learning_status,
)

router = APIRouter(tags=["learning"])


@router.get(
    "/api/gaps/{gap_id}/recommendations",
)
async def get_recommendations(
    gap_id: int,
    profile_id: Annotated[int, Query(description="Active profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> GapRecommendationsResponse:
    """Get learning recommendations for a specific gap.

    Returns categorized learning resources (free courses, paid courses,
    hands-on projects) with estimated hours and difficulty.

    When no recommendations exist, returns an empty list with a CTA
    to add custom resources.
    """
    try:
        result = get_gap_recommendations(db, gap_id, profile_id)
    except GapNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    recommendations = [
        LearningResourceResponse.model_validate(r) for r in result["recommendations"]
    ]

    cta = None
    if result.get("cta"):
        cta = RecommendationsCTA(**result["cta"])

    template_recs = [
        TemplateRecommendation(**t) for t in result.get("template_recommendations", [])
    ]

    return GapRecommendationsResponse(
        gap_id=result["gap_id"],
        skill_name=result["skill_name"],
        recommendations=recommendations,
        template_recommendations=template_recs,
        cta=cta,
    )


@router.post(
    "/api/gaps/{gap_id}/recommendations",
    status_code=201,
)
async def add_recommendation(
    gap_id: int,
    payload: LearningResourceCreate,
    db: Annotated[Session, Depends(get_db)],
) -> LearningResourceResponse:
    """Add a learning resource (recommendation) to a gap.

    This is the manual add endpoint that fulfills the "Add your own" CTA
    shown in the empty state.
    """
    try:
        resource = create_learning_resource(
            db,
            gap_id,
            payload.profile_id,
            {
                "title": payload.title,
                "url": payload.url,
                "resource_type": (
                    payload.resource_type.value if payload.resource_type else "free_course"
                ),
                "estimated_hours": payload.estimated_hours,
                "difficulty": payload.difficulty.value if payload.difficulty else None,
                "provider": payload.provider,
            },
        )
    except GapNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return LearningResourceResponse.model_validate(resource)


@router.patch(
    "/api/learning/{resource_id}/status",
)
async def update_status(
    resource_id: int,
    payload: LearningStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> LearningResourceResponse:
    """Update the status of a learning resource.

    Valid transitions:
    - not_started -> in_progress (sets started_at)
    - in_progress -> completed (sets completed_at, triggers skill upgrade)
    - not_started -> completed (sets both timestamps)

    Completing a resource triggers:
    1. Skill creation/upgrade in the skills inventory
    2. Gap distance recalculation (improving readiness score)
    """
    try:
        resource = update_learning_status(
            db,
            resource_id,
            payload.profile_id,
            payload.status.value,
        )
    except LearningResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return LearningResourceResponse.model_validate(resource)
