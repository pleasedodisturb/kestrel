"""Coaching Engine API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.coaching import (
    CoachingSuggestionResponse,
    CoachingSuggestionsResponse,
    EffortEstimate,
)
from career_os.services.coaching import (
    ProfileNotFoundError,
    get_coaching_suggestions,
)

router = APIRouter(prefix="/api/coaching", tags=["coaching"])


@router.get("/suggestions", response_model=CoachingSuggestionsResponse)
async def get_suggestions(
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> CoachingSuggestionsResponse:
    """Get prioritized coaching suggestions.

    Returns actionable recommendations based on skills inventory,
    gaps, career goals, and pipeline state. Each suggestion includes
    effort estimates (hours, weeks, difficulty).

    Coaching adapts when learning items are completed — resolved
    suggestions are removed and new priorities surfaced.
    """
    try:
        result = get_coaching_suggestions(db, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    suggestions = [
        CoachingSuggestionResponse(
            id=cs.id,
            profile_id=cs.profile_id,
            action=cs.action,
            priority=cs.priority,
            effort_estimate=EffortEstimate(
                hours=cs.hours,
                weeks=cs.weeks,
                difficulty=cs.difficulty,
            ),
            status=cs.status,
            created_at=cs.created_at,
            updated_at=cs.updated_at,
        )
        for cs in result["suggestions"]
    ]

    return CoachingSuggestionsResponse(
        suggestions=suggestions,
        total=result["total"],
        focus_area=result["focus_area"],
    )
