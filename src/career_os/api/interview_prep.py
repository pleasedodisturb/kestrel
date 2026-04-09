"""Interview Preparation API routes.

Covers:
- VAL-PREP-001: Personalized topic list per application
- VAL-PREP-002: Practice question generation (≥5 tailored)
- VAL-PREP-003: Prep checklist with time estimates and total
- VAL-PREP-004: Prep progress tracking (persists on revisit)
- VAL-PREP-005: No-research prompt for un-researched companies
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.interview_prep import (
    InterviewPrepResponse,
    PrepChecklistItem,
    PrepItemUpdate,
)
from career_os.services.interview_prep import (
    ApplicationNotFoundError,
    PrepItemNotFoundError,
    ProfileNotFoundError,
    get_or_create_interview_prep,
    update_prep_item,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/applications", tags=["interview-prep"])


# ---------------------------------------------------------------------------
# GET /api/applications/{application_id}/interview-prep
# ---------------------------------------------------------------------------


@router.get(
    "/{application_id}/interview-prep",
    responses={404: {"description": "Not found"}, 500: {"description": "Internal server error"}},
)
async def get_interview_prep_endpoint(
    application_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> InterviewPrepResponse:
    """Get or generate interview preparation for an application.

    On first call, generates personalized prep using AI (topics, questions,
    checklist). On subsequent calls, returns persisted data with progress.

    If the company hasn't been researched, includes a research_prompt
    suggesting the user research the company first (VAL-PREP-005).
    """
    try:
        return await get_or_create_interview_prep(
            db=db,
            application_id=application_id,
            profile_id=profile_id,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during interview prep generation")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during interview prep: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# PATCH /api/applications/interview-prep/items/{item_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/interview-prep/items/{item_id}",
    responses={404: {"description": "Not found"}, 500: {"description": "Internal server error"}},
)
async def update_prep_item_endpoint(
    item_id: int,
    body: PrepItemUpdate,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> PrepChecklistItem:
    """Update a prep checklist item's completion state.

    Marks an item as completed or uncompleted. Progress persists
    across sessions (VAL-PREP-004).
    """
    try:
        return update_prep_item(
            db=db,
            item_id=item_id,
            profile_id=profile_id,
            completed=body.completed,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PrepItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during prep item update")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during prep item update: {exc}",
        ) from exc
