"""Career goals service: CRUD, reality mapping, progress tracking, recalibration, alternatives."""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from career_os.models.models import Application, Profile
from career_os.models.skills import Goal, LearningResource, Skill
from career_os.services.ticktick_sync import try_auto_push_learning_goal

logger = logging.getLogger(__name__)


class GoalNotFoundError(Exception):
    """Raised when a goal is not found."""

    pass


class ProfileNotFoundError(Exception):
    """Raised when the profile doesn't exist."""

    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _verify_profile(db: Session, profile_id: int) -> Profile:
    """Verify profile exists and return it."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")
    return profile


def _get_goal(db: Session, goal_id: int, profile_id: int) -> Goal:
    """Get goal scoped by profile."""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.profile_id == profile_id).first()
    if not goal:
        raise GoalNotFoundError(f"Goal {goal_id} not found")
    return goal


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def create_goal(db: Session, profile_id: int, data: dict) -> Goal:
    """Create a new career goal.

    Args:
        db: Database session.
        profile_id: Profile ID.
        data: Dict with title, goal_type, target_date, status, description.

    Returns:
        Created Goal.
    """
    _verify_profile(db, profile_id)

    goal = Goal(
        profile_id=profile_id,
        title=data["title"],
        goal_type=data["goal_type"],
        target_date=data.get("target_date"),
        status=data.get("status", "active"),
        description=data.get("description"),
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)

    # Auto-push to TickTick (silent no-op if not configured)
    try_auto_push_learning_goal(db, goal)

    return goal


def list_goals(
    db: Session,
    profile_id: int,
    *,
    status: str | None = None,
    goal_type: str | None = None,
) -> tuple[list[Goal], int]:
    """List goals for a profile with optional filters.

    Returns:
        Tuple of (goals list, total count).
    """
    query = db.query(Goal).filter(Goal.profile_id == profile_id)

    if status:
        query = query.filter(Goal.status == status)
    if goal_type:
        query = query.filter(Goal.goal_type == goal_type)

    total = query.count()
    goals = query.order_by(Goal.created_at.desc()).all()
    return goals, total


def get_goal(db: Session, goal_id: int, profile_id: int) -> Goal:
    """Get a single goal by ID, scoped to profile."""
    return _get_goal(db, goal_id, profile_id)


def update_goal(db: Session, goal_id: int, profile_id: int, data: dict) -> Goal:
    """Update a goal's fields.

    Args:
        db: Database session.
        goal_id: Goal ID.
        profile_id: Profile ID.
        data: Dict of fields to update (only non-None keys are applied).

    Returns:
        Updated Goal.
    """
    goal = _get_goal(db, goal_id, profile_id)

    for field in ("title", "goal_type", "target_date", "status", "description"):
        if field in data and data[field] is not None:
            setattr(goal, field, data[field])

    goal.updated_at = _utcnow()
    db.commit()
    db.refresh(goal)

    # Auto-push updated goal to TickTick (silent no-op if not configured)
    try_auto_push_learning_goal(db, goal)

    return goal


def delete_goal(db: Session, goal_id: int, profile_id: int) -> None:
    """Delete a goal.

    Args:
        db: Database session.
        goal_id: Goal ID.
        profile_id: Profile ID.
    """
    goal = _get_goal(db, goal_id, profile_id)
    db.delete(goal)
    db.commit()


# ---------------------------------------------------------------------------
# Reality map
# ---------------------------------------------------------------------------


def get_reality_map(db: Session, goal_id: int, profile_id: int) -> dict:
    """Generate a reality map for a goal.

    Shows current vs required state across dimensions:
    - skills: what skills the user has vs what's needed
    - applications: current pipeline vs target
    - learning: learning progress

    Returns:
        Dict with goal_id, title, goal_type, dimensions, overall_progress.
    """
    goal = _get_goal(db, goal_id, profile_id)

    # Collect skills data
    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    total_skills = len(skills)
    advanced_or_expert = sum(1 for s in skills if s.proficiency in ("advanced", "expert"))

    # Collect applications data
    applications = (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .all()
    )
    active_apps = sum(1 for a in applications if a.status in ("applied", "interviewing", "offer"))
    advanced_apps = sum(1 for a in applications if a.status in ("interviewing", "offer"))

    # Collect learning data
    learning_resources = (
        db.query(LearningResource).filter(LearningResource.profile_id == profile_id).all()
    )
    total_learning = len(learning_resources)
    completed_learning = sum(1 for lr in learning_resources if lr.status == "completed")

    # Skills dimension
    if goal.goal_type == "aspirational":
        skills_required = "Expert-level in ≥5 core areas"
        skills_target = 5
    else:
        skills_required = "Advanced/expert in ≥3 core areas"
        skills_target = 3

    skills_progress = min(100.0, (advanced_or_expert / max(skills_target, 1)) * 100)

    # Applications dimension
    if goal.goal_type == "aspirational":
        apps_required = "≥10 active applications, ≥3 in interview stage"
        apps_target_active = 10
        apps_target_advanced = 3
    else:
        apps_required = "≥5 active applications, ≥1 in interview stage"
        apps_target_active = 5
        apps_target_advanced = 1

    apps_progress_active = min(100.0, (active_apps / max(apps_target_active, 1)) * 100)
    apps_progress_advanced = min(100.0, (advanced_apps / max(apps_target_advanced, 1)) * 100)
    apps_progress = (apps_progress_active + apps_progress_advanced) / 2

    # Learning / portfolio dimension
    learning_progress = (
        min(100.0, (completed_learning / max(total_learning, 1)) * 100)
        if total_learning > 0
        else 0.0
    )

    dimensions = [
        {
            "dimension": "skills",
            "current_state": (
                f"{advanced_or_expert} advanced/expert skills out of {total_skills} total"
            ),
            "required_state": skills_required,
            "delta": (
                f"Need {max(0, skills_target - advanced_or_expert)} more advanced/expert skills"
                if advanced_or_expert < skills_target
                else "Skills target met"
            ),
            "progress_pct": round(skills_progress, 1),
        },
        {
            "dimension": "applications",
            "current_state": (
                f"{active_apps} active applications, {advanced_apps} in interview/offer stage"
            ),
            "required_state": apps_required,
            "delta": (
                f"Need {max(0, apps_target_active - active_apps)} more active "
                f"applications and {max(0, apps_target_advanced - advanced_apps)} "
                f"more in interview stage"
                if active_apps < apps_target_active or advanced_apps < apps_target_advanced
                else "Application pipeline target met"
            ),
            "progress_pct": round(apps_progress, 1),
        },
        {
            "dimension": "portfolio",
            "current_state": (
                f"{completed_learning}/{total_learning} learning resources completed"
                if total_learning > 0
                else "No learning resources tracked"
            ),
            "required_state": "Complete all identified learning resources",
            "delta": (
                f"{total_learning - completed_learning} resources remaining"
                if total_learning > completed_learning
                else "All resources completed"
                if total_learning > 0
                else "Add learning resources to track progress"
            ),
            "progress_pct": round(learning_progress, 1),
        },
    ]

    overall = round(sum(d["progress_pct"] for d in dimensions) / len(dimensions), 1)

    return {
        "goal_id": goal.id,
        "title": goal.title,
        "goal_type": goal.goal_type,
        "dimensions": dimensions,
        "overall_progress": overall,
    }


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------


def get_progress(db: Session, goal_id: int, profile_id: int) -> dict:
    """Get progress tracking across dimensions.

    Tracks progress in:
    - applications: pipeline activity
    - learning: completed learning resources
    - portfolio: skills inventory strength

    Returns:
        Dict with goal_id, title, dimensions, overall_progress.
    """
    goal = _get_goal(db, goal_id, profile_id)

    # Applications dimension
    applications = (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .all()
    )
    total_apps = len(applications)
    active_apps = sum(1 for a in applications if a.status in ("applied", "interviewing", "offer"))
    # Target: at least 5 active apps for realistic, 10 for aspirational
    target_apps = 10 if goal.goal_type == "aspirational" else 5
    apps_pct = min(100.0, (active_apps / max(target_apps, 1)) * 100)

    # Learning dimension
    learning_resources = (
        db.query(LearningResource).filter(LearningResource.profile_id == profile_id).all()
    )
    total_learning = len(learning_resources)
    completed_learning = sum(1 for lr in learning_resources if lr.status == "completed")
    learning_pct = (
        min(100.0, (completed_learning / max(total_learning, 1)) * 100)
        if total_learning > 0
        else 0.0
    )

    # Portfolio dimension (skills strength)
    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    total_skills = len(skills)
    advanced_or_expert = sum(1 for s in skills if s.proficiency in ("advanced", "expert"))
    target_advanced = 5 if goal.goal_type == "aspirational" else 3
    portfolio_pct = min(100.0, (advanced_or_expert / max(target_advanced, 1)) * 100)

    # Market positioning dimension (VAL-CROSS-016)
    #
    # Market positioning progress is a composite of:
    #   1. Discovery coverage: having discovered jobs and analyzed role types
    #      is itself meaningful progress (worth up to 50%).
    #   2. Skills match: the average match percentage across analyzed role
    #      types (worth up to 50%).
    #
    # This ensures market_positioning > 0% as soon as discovery has been run
    # and jobs have been analyzed, even before skills are fully parsed.
    market_pct = 0.0
    market_detail = "No market positioning data available"
    try:
        from career_os.services.market import get_market_positioning

        positioning = get_market_positioning(db, profile_id)
        positions = positioning.get("positions", [])
        if positions:
            total_roles = sum(p["total_roles_analyzed"] for p in positions)
            avg_match = sum(p["match_percentage"] for p in positions) / len(positions)

            # Discovery coverage component: scales 0→50% based on number of
            # role types analyzed (1 type = 20%, 2 = 30%, 3+ = 50%)
            if len(positions) >= 3:
                coverage_component = 50.0
            elif len(positions) == 2:
                coverage_component = 30.0
            else:
                coverage_component = 20.0

            # Skills match component: scales 0→50% based on average match %
            match_component = avg_match * 0.5

            market_pct = min(100.0, round(coverage_component + match_component, 1))
            market_detail = (
                f"{market_pct}% market positioning "
                f"({len(positions)} role types, {total_roles} jobs analyzed, "
                f"{round(avg_match, 1)}% skills match)"
            )
    except Exception:
        logger.debug("Market positioning data unavailable for goal %d progress", goal_id)

    dimensions = [
        {
            "dimension": "applications",
            "percentage": round(apps_pct, 1),
            "detail": f"{active_apps}/{target_apps} active applications ({total_apps} total)",
        },
        {
            "dimension": "learning",
            "percentage": round(learning_pct, 1),
            "detail": (
                f"{completed_learning}/{total_learning} learning resources completed"
                if total_learning > 0
                else "No learning resources tracked yet"
            ),
        },
        {
            "dimension": "portfolio",
            "percentage": round(portfolio_pct, 1),
            "detail": (
                f"{advanced_or_expert}/{target_advanced} advanced/expert skills "
                f"({total_skills} total skills)"
            ),
        },
        {
            "dimension": "market_positioning",
            "percentage": market_pct,
            "detail": market_detail,
        },
    ]

    overall = round(sum(d["percentage"] for d in dimensions) / len(dimensions), 1)

    return {
        "goal_id": goal.id,
        "title": goal.title,
        "dimensions": dimensions,
        "overall_progress": overall,
    }


# ---------------------------------------------------------------------------
# Recalibration (AI-powered)
# ---------------------------------------------------------------------------


async def recalibrate_goal(db: Session, goal_id: int, profile_id: int) -> dict:
    """AI-powered goal recalibration with market suggestions.

    Uses the AI provider to analyze the goal against market data
    and suggest adjustments.

    Returns:
        Dict with goal_id, title, recalibration_notes, suggested_adjustments, market_reality.
    """
    from career_os.ai.factory import get_ai_provider
    from career_os.schemas.ai import AIFeature

    goal = _get_goal(db, goal_id, profile_id)

    provider = get_ai_provider()
    prompt = (
        f"Recalibrate career goal: '{goal.title}' "
        f"(type: {goal.goal_type}, status: {goal.status}). "
        f"Description: {goal.description or 'No description provided.'}. "
        f"Provide market-data-backed suggestions for adjustment."
    )

    response = await provider.complete(
        prompt=prompt,
        feature=AIFeature.goal_recalibration,
        context={
            "goal_id": goal.id,
            "goal_type": goal.goal_type,
            "title": goal.title,
        },
    )

    # Extract structured data from AI response
    if response.structured:
        structured = response.structured
        return {
            "goal_id": goal.id,
            "title": goal.title,
            "recalibration_notes": structured.recalibration_notes,
            "suggested_adjustments": structured.suggested_adjustments,
            "market_reality": structured.market_reality,
        }

    # Fallback if no structured data
    return {
        "goal_id": goal.id,
        "title": goal.title,
        "recalibration_notes": response.content,
        "suggested_adjustments": [],
        "market_reality": "Market data unavailable",
    }


# ---------------------------------------------------------------------------
# Alternative path analysis
# ---------------------------------------------------------------------------


async def get_alternatives(db: Session, goal_id: int, profile_id: int) -> dict:
    """Generate alternative path analysis for a goal.

    Returns employment, freelance, consulting and other paths
    with timelines and projections.

    Returns:
        Dict with goal_id, title, paths.
    """
    goal = _get_goal(db, goal_id, profile_id)

    # Collect context for AI
    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    skill_names = [s.name for s in skills[:20]]  # top 20 for context

    applications = (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .all()
    )

    from career_os.ai.factory import get_ai_provider
    from career_os.schemas.ai import AIFeature

    provider = get_ai_provider()
    prompt = (
        f"Analyze alternative career paths for goal: '{goal.title}' "
        f"(type: {goal.goal_type}). "
        f"Skills: {', '.join(skill_names[:10])}. "
        f"Current pipeline: {len(applications)} applications. "
        f"Provide employment, freelance, and consulting paths with timelines."
    )

    await provider.complete(
        prompt=prompt,
        feature=AIFeature.goal_recalibration,  # reuse recalibration feature
        context={
            "goal_id": goal.id,
            "goal_type": goal.goal_type,
            "skills": skill_names,
            "application_count": len(applications),
        },
    )

    # Build paths from context and AI guidance
    paths = _build_alternative_paths(goal, skills, applications)

    return {
        "goal_id": goal.id,
        "title": goal.title,
        "paths": paths,
    }


def _build_alternative_paths(
    goal: Goal,
    skills: list[Skill],
    applications: list[Application],
) -> list[dict]:
    """Build alternative paths based on current data.

    Always returns at least 3 paths: employment, freelance, consulting.
    """
    total_skills = len(skills)
    advanced_skills = sum(1 for s in skills if s.proficiency in ("advanced", "expert"))
    total_apps = len(applications)
    active_apps = sum(1 for a in applications if a.status in ("applied", "interviewing", "offer"))

    paths = [
        {
            "path_type": "employment",
            "title": "Full-time Employment",
            "description": (
                f"Continue current job search with {total_apps} tracked "
                f"applications ({active_apps} active). Focus on roles "
                f"matching your {advanced_skills} advanced/expert skills."
            ),
            "timeline": ("4-8 weeks" if active_apps >= 3 else "8-12 weeks"),
            "pros": [
                "Stable income and benefits",
                "Career progression path",
                "Team collaboration and mentorship",
            ],
            "cons": [
                "Limited flexibility",
                "Single employer dependency",
                "May require relocation",
            ],
            "estimated_income": "120,000-160,000 EUR/year",
        },
        {
            "path_type": "freelance",
            "title": "Freelance / Contract Work",
            "description": (
                f"Leverage your {total_skills} skills as a freelancer. "
                f"Start with platforms like Toptal, Upwork, or direct "
                f"outreach to companies in your pipeline."
            ),
            "timeline": "2-4 weeks to first engagement",
            "pros": [
                "Higher hourly rate potential",
                "Schedule flexibility",
                "Diverse project experience",
            ],
            "cons": [
                "Income instability",
                "Self-employment tax burden",
                "No benefits (insurance, pension)",
            ],
            "estimated_income": "80-120 EUR/hour (100,000-180,000 EUR/year)",
        },
        {
            "path_type": "consulting",
            "title": "Independent Consulting",
            "description": (
                f"Position as an expert consultant in AI program "
                f"management. Your {advanced_skills} advanced/expert "
                f"skills provide credibility for advisory work."
            ),
            "timeline": "4-6 weeks to establish, 8-12 weeks to first client",
            "pros": [
                "Highest earning potential",
                "Strategic-level impact",
                "Build personal brand",
            ],
            "cons": [
                "Longest ramp-up time",
                "Business development required",
                "Requires strong network",
            ],
            "estimated_income": "150-250 EUR/hour (150,000-250,000 EUR/year)",
        },
    ]

    return paths
