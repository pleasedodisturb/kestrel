"""Follow-up engine API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.follow_ups import (
    FollowUpComplete,
    FollowUpCreate,
    FollowUpListResponse,
    FollowUpResponse,
    OverdueCountResponse,
)
from career_os.services.follow_ups import (
    ApplicationNotFoundError,
    FollowUpNotFoundError,
    ProfileNotFoundError,
    complete_follow_up,
    create_follow_up,
    get_overdue_count,
    list_follow_ups,
)

router = APIRouter(prefix="/api/follow-ups", tags=["follow-ups"])


@router.post("", status_code=201)
async def create(
    payload: FollowUpCreate,
    db: Annotated[Session, Depends(get_db)],
) -> FollowUpResponse:
    """Create a new follow-up for an application.

    Requires application_id, profile_id, due_date, and follow_up_type.
    """
    try:
        follow_up = create_follow_up(db, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Attach application context
    return FollowUpResponse(
        id=follow_up.id,
        application_id=follow_up.application_id,
        profile_id=follow_up.profile_id,
        due_date=follow_up.due_date,
        follow_up_type=follow_up.follow_up_type,
        notes=follow_up.notes,
        completed_at=follow_up.completed_at,
        created_at=follow_up.created_at,
        application_company=follow_up.application.company if follow_up.application else None,
        application_role=follow_up.application.role if follow_up.application else None,
    )


@router.get("/overdue-count")
async def overdue_count(
    profile_id: Annotated[int, Query(description="Profile to check overdue count for")],
    db: Annotated[Session, Depends(get_db)],
) -> OverdueCountResponse:
    """Get the count of overdue, incomplete follow-ups."""
    count = get_overdue_count(db, profile_id=profile_id)
    return OverdueCountResponse(count=count)


@router.get("")
async def list_all(
    profile_id: Annotated[int, Query(description="Profile to list follow-ups for")],
    db: Annotated[Session, Depends(get_db)],
    overdue: Annotated[bool, Query(description="Only show overdue follow-ups")] = False,
) -> FollowUpListResponse:
    """List follow-ups with optional overdue filter."""
    follow_ups, total = list_follow_ups(db, profile_id=profile_id, overdue=overdue)
    return FollowUpListResponse(
        follow_ups=[
            FollowUpResponse(
                id=fu.id,
                application_id=fu.application_id,
                profile_id=fu.profile_id,
                due_date=fu.due_date,
                follow_up_type=fu.follow_up_type,
                notes=fu.notes,
                completed_at=fu.completed_at,
                created_at=fu.created_at,
                application_company=fu.application.company if fu.application else None,
                application_role=fu.application.role if fu.application else None,
            )
            for fu in follow_ups
        ],
        total=total,
    )


@router.patch("/{follow_up_id}")
async def complete(
    follow_up_id: int,
    payload: FollowUpComplete,
    profile_id: Annotated[int, Query(description="Active profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> FollowUpResponse:
    """Complete a follow-up (set completed_at).

    Returns 404 if the follow-up does not belong to the given profile.
    """
    try:
        follow_up = complete_follow_up(db, follow_up_id, profile_id=profile_id)
    except FollowUpNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FollowUpResponse(
        id=follow_up.id,
        application_id=follow_up.application_id,
        profile_id=follow_up.profile_id,
        due_date=follow_up.due_date,
        follow_up_type=follow_up.follow_up_type,
        notes=follow_up.notes,
        completed_at=follow_up.completed_at,
        created_at=follow_up.created_at,
        application_company=follow_up.application.company if follow_up.application else None,
        application_role=follow_up.application.role if follow_up.application else None,
    )
