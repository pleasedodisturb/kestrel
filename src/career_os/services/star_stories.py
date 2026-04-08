"""STAR stories service.

Manages CRUD, story recommendation by skill matching, and story gap identification.

Covers:
- VAL-STAR-001: STAR story CRUD
- VAL-STAR-002: Skill-to-company relevance mapping
- VAL-STAR-003: Story gap identification
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement
from career_os.models.star_stories import StarStory
from career_os.schemas.star_stories import (
    RecommendedStoriesResponse,
    RecommendedStory,
    StarStoryCreate,
    StarStoryListResponse,
    StarStoryResponse,
    StarStoryUpdate,
    StoryGap,
    StoryGapsResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProfileNotFoundError(Exception):
    """Raised when the profile doesn't exist."""


class StoryNotFoundError(Exception):
    """Raised when a STAR story is not found."""


class ApplicationNotFoundError(Exception):
    """Raised when the application is not found or doesn't belong to profile."""


class MissingRequirementsError(Exception):
    """Raised when an application has no parsed requirements."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_profile(db: Session, profile_id: int) -> Profile:
    """Verify profile exists."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")
    return profile


def _get_application(db: Session, application_id: int, profile_id: int) -> Application:
    """Get application scoped by profile."""
    app_obj = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .first()
    )
    if not app_obj:
        raise ApplicationNotFoundError(f"Application {application_id} not found")
    return app_obj


def _story_to_response(story: StarStory) -> StarStoryResponse:
    """Convert a StarStory ORM object to a response schema."""
    return StarStoryResponse(
        id=story.id,
        profile_id=story.profile_id,
        title=story.title,
        situation=story.situation,
        task=story.task,
        action=story.action,
        result=story.result,
        skill_tags=story.get_skill_tags_list(),
        created_at=story.created_at,
        updated_at=story.updated_at,
    )


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def create_star_story(
    db: Session,
    profile_id: int,
    data: StarStoryCreate,
) -> StarStoryResponse:
    """Create a new STAR story.

    Args:
        db: Database session.
        profile_id: Profile ID.
        data: Story creation data.

    Returns:
        Created StarStoryResponse.

    Raises:
        ProfileNotFoundError: If profile doesn't exist.
    """
    _validate_profile(db, profile_id)

    story = StarStory(
        profile_id=profile_id,
        title=data.title,
        situation=data.situation,
        task=data.task,
        action=data.action,
        result=data.result,
        skill_tags=",".join(data.skill_tags) if data.skill_tags else "",
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    return _story_to_response(story)


def list_star_stories(
    db: Session,
    profile_id: int,
) -> StarStoryListResponse:
    """List all STAR stories for a profile.

    Args:
        db: Database session.
        profile_id: Profile ID.

    Returns:
        StarStoryListResponse with all stories.

    Raises:
        ProfileNotFoundError: If profile doesn't exist.
    """
    _validate_profile(db, profile_id)

    stories = (
        db.query(StarStory)
        .filter(StarStory.profile_id == profile_id)
        .order_by(StarStory.created_at.desc())
        .all()
    )

    return StarStoryListResponse(
        stories=[_story_to_response(s) for s in stories],
        total=len(stories),
    )


def get_star_story(
    db: Session,
    story_id: int,
    profile_id: int,
) -> StarStoryResponse:
    """Get a single STAR story by ID, scoped by profile.

    Args:
        db: Database session.
        story_id: Story ID.
        profile_id: Profile ID.

    Returns:
        StarStoryResponse.

    Raises:
        ProfileNotFoundError: If profile doesn't exist.
        StoryNotFoundError: If story not found for profile.
    """
    _validate_profile(db, profile_id)

    story = (
        db.query(StarStory)
        .filter(
            StarStory.id == story_id,
            StarStory.profile_id == profile_id,
        )
        .first()
    )
    if not story:
        raise StoryNotFoundError(f"STAR story {story_id} not found")

    return _story_to_response(story)


def update_star_story(
    db: Session,
    story_id: int,
    profile_id: int,
    data: StarStoryUpdate,
) -> StarStoryResponse:
    """Update an existing STAR story.

    Args:
        db: Database session.
        story_id: Story ID.
        profile_id: Profile ID.
        data: Update data (only non-None fields applied).

    Returns:
        Updated StarStoryResponse.

    Raises:
        ProfileNotFoundError: If profile doesn't exist.
        StoryNotFoundError: If story not found for profile.
    """
    _validate_profile(db, profile_id)

    story = (
        db.query(StarStory)
        .filter(
            StarStory.id == story_id,
            StarStory.profile_id == profile_id,
        )
        .first()
    )
    if not story:
        raise StoryNotFoundError(f"STAR story {story_id} not found")

    if data.title is not None:
        story.title = data.title
    if data.situation is not None:
        story.situation = data.situation
    if data.task is not None:
        story.task = data.task
    if data.action is not None:
        story.action = data.action
    if data.result is not None:
        story.result = data.result
    if data.skill_tags is not None:
        story.skill_tags = ",".join(data.skill_tags)

    db.commit()
    db.refresh(story)

    return _story_to_response(story)


def delete_star_story(
    db: Session,
    story_id: int,
    profile_id: int,
) -> None:
    """Delete a STAR story.

    Args:
        db: Database session.
        story_id: Story ID.
        profile_id: Profile ID.

    Raises:
        ProfileNotFoundError: If profile doesn't exist.
        StoryNotFoundError: If story not found for profile.
    """
    _validate_profile(db, profile_id)

    story = (
        db.query(StarStory)
        .filter(
            StarStory.id == story_id,
            StarStory.profile_id == profile_id,
        )
        .first()
    )
    if not story:
        raise StoryNotFoundError(f"STAR story {story_id} not found")

    db.delete(story)
    db.commit()


# ---------------------------------------------------------------------------
# Story recommendation & gap identification
# ---------------------------------------------------------------------------


def get_recommended_stories(
    db: Session,
    application_id: int,
    profile_id: int,
) -> RecommendedStoriesResponse:
    """Get STAR stories recommended for an application.

    Matches story skill tags against the application's job requirements.
    Stories with overlapping skill tags are recommended, sorted by match count.

    Args:
        db: Database session.
        application_id: Application ID.
        profile_id: Profile ID.

    Returns:
        RecommendedStoriesResponse with matching stories.

    Raises:
        ProfileNotFoundError: If profile doesn't exist.
        ApplicationNotFoundError: If application not found for profile.
    """
    _validate_profile(db, profile_id)
    app_obj = _get_application(db, application_id, profile_id)

    # Get job requirements for this application
    requirements = (
        db.query(JobRequirement)
        .filter(
            JobRequirement.application_id == application_id,
            JobRequirement.profile_id == profile_id,
        )
        .all()
    )

    required_skills = {r.skill_name.lower().strip() for r in requirements}

    # Get all stories for this profile
    stories = db.query(StarStory).filter(StarStory.profile_id == profile_id).all()

    recommended: list[RecommendedStory] = []
    covered_skills: set[str] = set()

    for story in stories:
        story_tags = {t.lower().strip() for t in story.get_skill_tags_list()}
        matching = story_tags & required_skills

        if matching:
            covered_skills.update(matching)
            recommended.append(
                RecommendedStory(
                    story=_story_to_response(story),
                    matching_skills=sorted(matching),
                    match_count=len(matching),
                )
            )

    # Sort by match count descending
    recommended.sort(key=lambda r: r.match_count, reverse=True)

    return RecommendedStoriesResponse(
        application_id=app_obj.id,
        company=app_obj.company,
        role=app_obj.role,
        recommended_stories=recommended,
        total_requirements=len(requirements),
        covered_skills=sorted(covered_skills),
    )


def get_story_gaps(
    db: Session,
    application_id: int,
    profile_id: int,
) -> StoryGapsResponse:
    """Identify skills with no corresponding STAR story.

    Compares application job requirements against the profile's STAR stories.
    Skills not covered by any story are flagged as gaps with a create prompt.

    Args:
        db: Database session.
        application_id: Application ID.
        profile_id: Profile ID.

    Returns:
        StoryGapsResponse with gap information.

    Raises:
        ProfileNotFoundError: If profile doesn't exist.
        ApplicationNotFoundError: If application not found for profile.
    """
    _validate_profile(db, profile_id)
    app_obj = _get_application(db, application_id, profile_id)

    # Get job requirements
    requirements = (
        db.query(JobRequirement)
        .filter(
            JobRequirement.application_id == application_id,
            JobRequirement.profile_id == profile_id,
        )
        .all()
    )

    # Collect all skill tags from stories
    stories = db.query(StarStory).filter(StarStory.profile_id == profile_id).all()
    covered_skills = set()
    for story in stories:
        for tag in story.get_skill_tags_list():
            covered_skills.add(tag.lower().strip())

    # Identify gaps
    story_gaps: list[StoryGap] = []
    covered_count = 0

    for req in requirements:
        skill_key = req.skill_name.lower().strip()
        has_story = skill_key in covered_skills

        if has_story:
            covered_count += 1
        else:
            story_gaps.append(
                StoryGap(
                    skill_name=req.skill_name,
                    severity=req.severity,
                    required_level=req.required_level,
                    has_story=False,
                    create_prompt=(
                        f"Create a STAR story demonstrating your "
                        f"{req.skill_name} skills. "
                        f"This is a {req.severity} requirement for "
                        f"{app_obj.company} - {app_obj.role}."
                    ),
                )
            )

    return StoryGapsResponse(
        application_id=app_obj.id,
        company=app_obj.company,
        role=app_obj.role,
        story_gaps=story_gaps,
        total_requirements=len(requirements),
        covered_count=covered_count,
        gap_count=len(story_gaps),
    )
