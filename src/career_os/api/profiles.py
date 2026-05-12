"""Profile API routes."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
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

# Child tables owned by a profile, in (table, label) form. Counted in one
# round-trip SQL statement to decide whether DELETE /api/profiles/{id} should
# refuse with 409 (safe default) or proceed (force=true).
_PROFILE_CHILD_TABLES: tuple[tuple[str, str], ...] = (
    ("applications", "applications"),
    ("application_packages", "application_packages"),
    ("activity_log", "activity_logs"),
    ("follow_ups", "follow_ups"),
    ("skills", "skills"),
    ("learning_resources", "learning_resources"),
    ("goals", "goals"),
    ("coaching_suggestions", "coaching_suggestions"),
    ("job_requirements", "job_requirements"),
)


def _count_profile_children(db: Session, profile_id: int) -> dict[str, int]:
    """Return a row-count for every child table that references profile_id.

    Single SQL round-trip; relies on (profile_id) indexes for sub-millisecond cost.
    """
    selects = ", ".join(
        f"(SELECT COUNT(*) FROM {table} WHERE profile_id = :pid) AS {label}"
        for table, label in _PROFILE_CHILD_TABLES
    )
    row = db.execute(text(f"SELECT {selects}"), {"pid": profile_id}).mappings().one()
    return dict(row)


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
    responses={
        **RESP_404,
        409: {
            "description": "Conflict — profile has child rows; pass ?force=true to cascade-delete"
        },
    },
)
async def delete_profile(
    profile_id: int,
    db: Annotated[Session, Depends(get_db)],
    force: bool = False,
) -> None:
    """Delete a profile.

    By default, refuses with HTTP 409 if the profile owns any rows in
    applications, application_packages, activity_log, follow_ups, skills,
    learning_resources, goals, coaching_suggestions, or job_requirements.

    Pass ?force=true to cascade-delete the profile and every child row.

    The previous behavior of this endpoint (cascade on plain DELETE) is what
    wiped a downstream user's full dataset on 2026-05-11 with one stray API
    call; the same DELETE on every Kestrel install would have done the same.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFILE_NOT_FOUND)

    if not force:
        counts = _count_profile_children(db, profile_id)
        non_empty = {k: v for k, v in counts.items() if v > 0}
        if non_empty:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Profile has child rows; refusing to cascade-delete",
                    "child_counts": non_empty,
                    "hint": "Pass ?force=true to delete the profile and all child rows.",
                },
            )

    db.delete(profile)
    db.commit()
