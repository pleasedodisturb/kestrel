"""Profile API routes."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from career_os.api.constants import PROFILE_NOT_FOUND, RESP_404
from career_os.database import get_db
from career_os.models.models import Profile
from career_os.schemas.profiles import (
    ProfileCreate,
    ProfileListResponse,
    ProfileResponse,
    ProfileUpdate,
)
from career_os.services.scoring import flag_stale_scores, regenerate_weights_for_job_family

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("")
async def list_profiles(db: Annotated[Session, Depends(get_db)]) -> ProfileListResponse:
    """List all profiles."""
    profiles = db.query(Profile).all()
    return ProfileListResponse(
        profiles=[ProfileResponse.model_validate(p) for p in profiles],
        count=len(profiles),
    )


@router.get("/{profile_id}", responses=RESP_404)
async def get_profile(profile_id: int, db: Annotated[Session, Depends(get_db)]) -> ProfileResponse:
    """Get a specific profile by ID."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFILE_NOT_FOUND)
    return ProfileResponse.model_validate(profile)


@router.post("", status_code=201)
async def create_profile(
    payload: ProfileCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ProfileResponse:
    """Create a new profile.

    Requires at least a name. Email, location, and job_family are optional.
    """
    profile = Profile(
        name=payload.name,
        email=payload.email,
        location=payload.location,
        job_family=payload.job_family,
        dream_companies=json.dumps(payload.dream_companies) if payload.dream_companies else None,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return ProfileResponse.model_validate(profile)


@router.patch("/{profile_id}", responses=RESP_404)
async def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ProfileResponse:
    """Update a profile's fields (partial update).

    Only supplied fields are updated. Returns 404 if profile doesn't exist.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFILE_NOT_FOUND)

    update_data = payload.model_dump(exclude_unset=True)

    # Track whether job_family changed - triggers stale score invalidation
    # (VAL-CROSS-004)
    old_job_family = profile.job_family
    job_family_changing = (
        "job_family" in update_data and update_data["job_family"] != old_job_family
    )

    for field, value in update_data.items():
        if field == "dream_companies" and value is not None:
            value = json.dumps(value)
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    # Invalidate scores and regenerate weights when job_family changes (VAL-CROSS-004)
    if job_family_changing:
        flag_stale_scores(db, profile_id)
        regenerate_weights_for_job_family(db, profile_id, update_data["job_family"])

    return ProfileResponse.model_validate(profile)


@router.delete(
    "/{profile_id}",
    status_code=204,
    responses={**RESP_404, 409: {"description": "Conflict"}},
)
async def delete_profile(
    profile_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a profile.

    Returns 404 if profile doesn't exist. Cascading deletes remove
    associated applications, activity logs, follow-ups, skills,
    learning resources, goals, job requirements, and coaching suggestions.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFILE_NOT_FOUND)

    try:
        db.delete(profile)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete profile with existing records. "
            "Please remove associated data first.",
        ) from None
