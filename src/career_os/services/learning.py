"""Learning paths service: recommendations, progress tracking, readiness recalculation."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from career_os.models.skills import JobRequirement, LearningResource, Skill, SkillHistory


class GapNotFoundError(Exception):
    """Raised when a gap (job requirement) is not found."""

    pass


class LearningResourceNotFoundError(Exception):
    """Raised when a learning resource is not found."""

    pass


class InvalidStatusTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""

    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _verify_gap_ownership(
    db: Session, gap_id: int, profile_id: int
) -> JobRequirement:
    """Verify the gap (job requirement) exists and belongs to the profile.

    Returns the JobRequirement if valid.
    """
    gap = (
        db.query(JobRequirement)
        .filter(
            JobRequirement.id == gap_id,
            JobRequirement.profile_id == profile_id,
        )
        .first()
    )
    if not gap:
        raise GapNotFoundError(f"Gap {gap_id} not found")
    return gap


def _generate_template_recommendations(
    skill_name: str, required_level: str
) -> list[dict]:
    """Generate template-based recommendations for a fresh gap.

    Returns 3 suggestions: free_course, paid_course, hands_on_project.
    Hours and difficulty scale with the required proficiency level.
    """
    level_hours = {
        "beginner": (5.0, 10.0, 4.0),
        "intermediate": (15.0, 25.0, 10.0),
        "advanced": (30.0, 40.0, 20.0),
        "expert": (50.0, 60.0, 30.0),
    }
    free_h, paid_h, project_h = level_hours.get(
        required_level, level_hours["intermediate"]
    )
    difficulty = required_level if required_level in level_hours else "intermediate"

    return [
        {
            "title": f"{skill_name} — Free Course ({required_level})",
            "url": (
                f"https://www.youtube.com/results"
                f"?search_query={skill_name.replace(' ', '+')}+tutorial"
            ),
            "provider": "YouTube / Coursera",
            "resource_type": "free_course",
            "estimated_hours": free_h,
            "difficulty": difficulty,
        },
        {
            "title": f"{skill_name} — Paid Course ({required_level})",
            "url": f"https://www.udemy.com/courses/search/?q={skill_name.replace(' ', '+')}",
            "provider": "Udemy / O'Reilly",
            "resource_type": "paid_course",
            "estimated_hours": paid_h,
            "difficulty": difficulty,
        },
        {
            "title": f"{skill_name} — Hands-on Project ({required_level})",
            "url": f"https://github.com/topics/{skill_name.lower().replace(' ', '-')}",
            "provider": "GitHub",
            "resource_type": "hands_on_project",
            "estimated_hours": project_h,
            "difficulty": difficulty,
        },
    ]


def get_gap_recommendations(
    db: Session, gap_id: int, profile_id: int
) -> dict:
    """Get learning recommendations for a specific gap.

    Returns dict with gap_id, skill_name, recommendations list.
    When no user-created resources exist, generates template-based
    suggestions (free_course, paid_course, hands_on_project) using
    the gap's skill name and required level.
    If user-created resources exist, returns those (no CTA).
    """
    gap = _verify_gap_ownership(db, gap_id, profile_id)

    resources = (
        db.query(LearningResource)
        .filter(
            LearningResource.gap_id == gap_id,
            LearningResource.profile_id == profile_id,
        )
        .order_by(LearningResource.created_at.desc())
        .all()
    )

    result: dict = {
        "gap_id": gap_id,
        "skill_name": gap.skill_name,
        "recommendations": resources,
    }

    if not resources:
        # Generate template-based suggestions for fresh gaps
        result["template_recommendations"] = _generate_template_recommendations(
            gap.skill_name, gap.required_level
        )
        result["cta"] = {
            "label": "Add your own",
            "action": "add_recommendation",
        }

    return result


def create_learning_resource(
    db: Session,
    gap_id: int,
    profile_id: int,
    data: dict,
) -> LearningResource:
    """Create a learning resource linked to a gap.

    Args:
        db: Database session.
        gap_id: Job requirement (gap) ID.
        profile_id: Profile ID.
        data: Dict with title, url, resource_type, estimated_hours, difficulty, provider.

    Returns:
        Created LearningResource.
    """
    gap = _verify_gap_ownership(db, gap_id, profile_id)

    # Look up the skill_id if the skill exists in the inventory
    skill = (
        db.query(Skill)
        .filter(
            Skill.profile_id == profile_id,
            Skill.name.ilike(gap.skill_name),
        )
        .first()
    )

    resource = LearningResource(
        profile_id=profile_id,
        gap_id=gap_id,
        skill_id=skill.id if skill else None,
        title=data["title"],
        url=data.get("url"),
        provider=data.get("provider"),
        resource_type=data.get("resource_type", "free_course"),
        estimated_hours=data.get("estimated_hours"),
        difficulty=data.get("difficulty"),
        status="not_started",
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


"""Allowed transitions: from_status → set of valid to_statuses."""
VALID_TRANSITIONS: dict[str, set[str]] = {
    "not_started": {"in_progress"},
    "in_progress": {"completed", "not_started"},
    # no outward transitions; completed→completed is idempotent
    "completed": set(),
}


def update_learning_status(
    db: Session,
    resource_id: int,
    profile_id: int,
    new_status: str,
) -> LearningResource:
    """Update the status of a learning resource.

    Enforces a strict transition map:
    - not_started → in_progress: sets started_at
    - in_progress → completed: sets completed_at, triggers skill upgrade
    - in_progress → not_started: clears started_at and completed_at
    - completed → completed: idempotent, skips skill upgrade

    Invalid transitions (e.g. not_started → completed) raise InvalidStatusTransitionError.

    Returns:
        Updated LearningResource.

    Raises:
        LearningResourceNotFoundError: If resource not found for profile.
        InvalidStatusTransitionError: If transition is not allowed.
    """
    resource = (
        db.query(LearningResource)
        .filter(
            LearningResource.id == resource_id,
            LearningResource.profile_id == profile_id,
        )
        .first()
    )
    if not resource:
        raise LearningResourceNotFoundError(
            f"Learning resource {resource_id} not found"
        )

    current_status = resource.status

    # Idempotent: completed → completed is a no-op (skip upgrade)
    if current_status == new_status == "completed":
        return resource

    # Validate transition
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise InvalidStatusTransitionError(
            f"Cannot transition from '{current_status}' to '{new_status}'"
        )

    now = _utcnow()

    if new_status == "in_progress":
        resource.status = "in_progress"
        if resource.started_at is None:
            resource.started_at = now

    elif new_status == "completed":
        resource.status = "completed"
        if resource.started_at is None:
            resource.started_at = now
        resource.completed_at = now

        # Trigger skill upgrade when completing learning
        _upgrade_skill_on_completion(db, resource)

    elif new_status == "not_started":
        resource.status = "not_started"
        resource.started_at = None
        resource.completed_at = None

    resource.updated_at = now
    db.commit()
    db.refresh(resource)
    return resource


def _upgrade_skill_on_completion(
    db: Session, resource: LearningResource
) -> None:
    """When learning is completed, create or upgrade the associated skill.

    If the gap's skill doesn't exist in inventory, create it at beginner level.
    If it exists, upgrade proficiency one level if below the required level.
    """
    if resource.gap_id is None:
        return

    gap = db.query(JobRequirement).filter(JobRequirement.id == resource.gap_id).first()
    if not gap:
        return

    # Look up existing skill
    skill = (
        db.query(Skill)
        .filter(
            Skill.profile_id == resource.profile_id,
            Skill.name.ilike(gap.skill_name),
        )
        .first()
    )

    proficiency_order = ["beginner", "intermediate", "advanced", "expert"]

    if skill is None:
        # Create new skill at beginner level (learning started from zero)
        # Use the difficulty of the resource to determine starting level
        new_level = "beginner"
        if resource.difficulty in proficiency_order:
            idx = proficiency_order.index(resource.difficulty)
            # Cap at intermediate for first learning completion
            new_level = proficiency_order[min(idx, 1)]

        skill = Skill(
            profile_id=resource.profile_id,
            name=gap.skill_name,
            category="technical",  # Default; can be refined later
            proficiency=new_level,
            evidence_source="learning",
            evidence_detail=f"Completed: {resource.title}",
        )
        db.add(skill)
        db.flush()

        # Record history
        history = SkillHistory(
            skill_id=skill.id,
            profile_id=resource.profile_id,
            previous_proficiency=None,
            new_proficiency=new_level,
            reason=f"Completed learning: {resource.title}",
        )
        db.add(history)
    else:
        # Upgrade existing skill by one level if below required
        current_idx = (
            proficiency_order.index(skill.proficiency)
            if skill.proficiency in proficiency_order
            else 0
        )
        required_idx = (
            proficiency_order.index(gap.required_level)
            if gap.required_level in proficiency_order
            else 1
        )

        if current_idx < required_idx:
            new_idx = min(current_idx + 1, len(proficiency_order) - 1)
            old_proficiency = skill.proficiency
            skill.proficiency = proficiency_order[new_idx]
            skill.evidence_detail = (
                f"{skill.evidence_detail or ''}\nCompleted: {resource.title}"
            ).strip()
            skill.updated_at = _utcnow()

            # Record history
            history = SkillHistory(
                skill_id=skill.id,
                profile_id=resource.profile_id,
                previous_proficiency=old_proficiency,
                new_proficiency=skill.proficiency,
                reason=f"Completed learning: {resource.title}",
            )
            db.add(history)

    # Link the resource to the skill if not already linked
    if resource.skill_id is None:
        resource.skill_id = skill.id
