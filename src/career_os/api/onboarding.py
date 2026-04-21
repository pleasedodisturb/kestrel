"""Onboarding API routes: GET and PATCH /api/onboarding/status."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import PROFILE_NOT_FOUND, RESP_404
from career_os.database import get_db
from career_os.models.models import Profile
from career_os.schemas.onboarding import OnboardingStatusResponse, OnboardingStepUpdate
from career_os.services.onboarding import get_onboarding_status, mark_step_complete, reset_onboarding_flow

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/status", responses=RESP_404)
async def get_onboarding_status_route(
    profile_id: Annotated[int, Query(description="Profile ID to get onboarding status for")],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingStatusResponse:
    """Get current onboarding status for a profile.

    Returns full state including computed next_step, is_complete, and progress_pct.
    If the profile has never started onboarding, returns a synthesized empty state
    (all steps incomplete, progress_pct=0) — does NOT return 404.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFILE_NOT_FOUND)

    return get_onboarding_status(profile_id, db)


@router.patch("/status", responses=RESP_404)
async def patch_onboarding_status_route(
    profile_id: Annotated[int, Query(description="Profile ID to update onboarding status for")],
    payload: OnboardingStepUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingStatusResponse:
    """Mark an onboarding step complete and return updated state.

    Creates the onboarding state row if it does not exist (first call).
    Idempotent: re-patching the same step preserves the original timestamp.
    Step ordering is not enforced — CLI and web can complete steps in different orders.

    OnboardingValidationError (422) is raised for unknown step names and propagates
    to the app-level exception handler registered in main.py (returns
    {"error": user_message, "resolution": resolution}).
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFILE_NOT_FOUND)

    return mark_step_complete(payload.step, payload.via, profile_id, db)


@router.post("/reset", responses=RESP_404)
async def reset_onboarding_route(
    profile_id: Annotated[int, Query(description="Profile ID to reset onboarding for")],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingStatusResponse:
    """Reset the onboarding flow while keeping profile data.

    Clears welcome, tour, feedback, and completed timestamps so the user
    can re-experience the onboarding flow. Profile data is preserved.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFILE_NOT_FOUND)

    return reset_onboarding_flow(profile_id, db)
