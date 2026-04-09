"""STAR Stories API routes.

Covers:
- VAL-STAR-001: STAR story CRUD (create, list, view, update, delete)
- VAL-STAR-002: Skill-to-company relevance mapping (recommended stories)
- VAL-STAR-003: Story gap identification
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.star_stories import (
    RecommendedStoriesResponse,
    StarStoryCreate,
    StarStoryListResponse,
    StarStoryResponse,
    StarStoryUpdate,
    StoryGapsResponse,
)
from career_os.services.star_stories import (
    ApplicationNotFoundError,
    ProfileNotFoundError,
    StoryNotFoundError,
    create_star_story,
    delete_star_story,
    get_recommended_stories,
    get_star_story,
    get_story_gaps,
    list_star_stories,
    update_star_story,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/star-stories", tags=["star-stories"])


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_star_story_endpoint(
    body: StarStoryCreate,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> StarStoryResponse:
    """Create a new STAR story."""
    try:
        return create_star_story(db=db, profile_id=profile_id, data=body)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
async def list_star_stories_endpoint(
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> StarStoryListResponse:
    """List all STAR stories for a profile."""
    try:
        return list_star_stories(db=db, profile_id=profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{story_id}")
async def get_star_story_endpoint(
    story_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> StarStoryResponse:
    """Get a single STAR story by ID."""
    try:
        return get_star_story(db=db, story_id=story_id, profile_id=profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{story_id}")
async def update_star_story_endpoint(
    story_id: int,
    body: StarStoryUpdate,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> StarStoryResponse:
    """Update an existing STAR story."""
    try:
        return update_star_story(db=db, story_id=story_id, profile_id=profile_id, data=body)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{story_id}", status_code=204)
async def delete_star_story_endpoint(
    story_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> None:
    """Delete a STAR story."""
    try:
        delete_star_story(db=db, story_id=story_id, profile_id=profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Application-scoped endpoints (recommended stories & gaps)
# ---------------------------------------------------------------------------

app_router = APIRouter(prefix="/api/applications", tags=["star-stories"])


@app_router.get(
    "/{application_id}/recommended-stories",
)
async def get_recommended_stories_endpoint(
    application_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> RecommendedStoriesResponse:
    """Get STAR stories recommended for an application.

    Matches story skill tags against application's job requirements.
    """
    try:
        return get_recommended_stories(db=db, application_id=application_id, profile_id=profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app_router.get(
    "/{application_id}/story-gaps",
)
async def get_story_gaps_endpoint(
    application_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> StoryGapsResponse:
    """Identify skills with no corresponding STAR story.

    Skills from job requirements not covered by any story are flagged
    as story gaps with a prompt to create a new story.
    """
    try:
        return get_story_gaps(db=db, application_id=application_id, profile_id=profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
