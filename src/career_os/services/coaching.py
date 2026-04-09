"""Coaching engine service: prioritized suggestions based on skills, gaps, goals, pipeline.

Generates actionable recommendations with effort estimates. Adapts when
learning items are completed — resolved suggestions are removed and new
priorities are surfaced.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from career_os.models.models import Application, Profile
from career_os.models.skills import (
    CoachingSuggestion,
    Goal,
    JobRequirement,
    LearningResource,
    Skill,
)


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


# ---------------------------------------------------------------------------
# Helpers for _build_skill_gap_suggestions
# ---------------------------------------------------------------------------

_PROFICIENCY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2, "expert": 3}
_SEVERITY_WEIGHT = {"critical": 3.0, "nice-to-have": 1.0, "bonus": 0.5}
_DIFFICULTY_LOOKUP = {1: "low", 2: "medium"}


def _calculate_skill_distance(
    required_level: str,
    current_level: str | None,
    proficiency_order: dict[str, int],
) -> int:
    """Return the proficiency gap between required and current level."""
    if current_level is None:
        return 3
    req_idx = proficiency_order.get(required_level.lower(), 1)
    cur_idx = proficiency_order.get(current_level.lower(), 0)
    return max(0, req_idx - cur_idx)


def _get_completed_skills(db: Session, profile_id: int) -> set[str]:
    """Return set of normalised skill names whose learning is completed."""
    completed_resources = (
        db.query(LearningResource)
        .filter(
            LearningResource.profile_id == profile_id,
            LearningResource.status == "completed",
        )
        .all()
    )
    completed: set[str] = set()
    for lr in completed_resources:
        if lr.gap_id is None:
            continue
        gap_req = db.query(JobRequirement).filter(JobRequirement.id == lr.gap_id).first()
        if gap_req:
            completed.add(gap_req.skill_name.lower().strip())
    return completed


def _aggregate_requirement_gaps(requirements, skills_by_name):
    """Aggregate skill gaps from job requirements into gap_data and display_names dicts."""
    gap_data: dict[str, dict] = {}
    display_names: dict[str, str] = {}

    for req in requirements:
        skill_key = req.skill_name.lower().strip()
        current_skill = skills_by_name.get(skill_key)
        current_level = current_skill.proficiency if current_skill else None

        distance = _calculate_skill_distance(req.required_level, current_level, _PROFICIENCY_ORDER)
        if distance <= 0:
            continue

        sw = _SEVERITY_WEIGHT.get(req.severity, 1.0)
        if skill_key not in gap_data:
            gap_data[skill_key] = {
                "frequency": 0,
                "max_severity_weight": 0.0,
                "required_level": req.required_level,
                "current_level": current_level,
                "distance": distance,
            }
            display_names[skill_key] = req.skill_name

        entry = gap_data[skill_key]
        entry["frequency"] += 1
        entry["max_severity_weight"] = max(entry["max_severity_weight"], sw)

        if _PROFICIENCY_ORDER.get(req.required_level.lower(), 0) > _PROFICIENCY_ORDER.get(
            entry["required_level"].lower(), 0
        ):
            entry["required_level"] = req.required_level
            entry["distance"] = distance

    return gap_data, display_names


# ---------------------------------------------------------------------------
# Core suggestion generation
# ---------------------------------------------------------------------------


def _build_skill_gap_suggestions(db: Session, profile_id: int) -> list[dict]:
    """Generate suggestions from skill gaps across applications.

    Looks at job requirements where the user's skill level is below
    what's required. Higher severity and frequency = higher priority.
    """
    # Load skills inventory
    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    skills_by_name: dict[str, Skill] = {s.name.lower().strip(): s for s in skills}

    # Get all job requirements for non-archived applications
    active_apps = (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .all()
    )
    app_ids = [a.id for a in active_apps]

    if not app_ids:
        return []

    requirements = (
        db.query(JobRequirement)
        .filter(
            JobRequirement.application_id.in_(app_ids),
            JobRequirement.profile_id == profile_id,
        )
        .all()
    )

    gap_data, display_names = _aggregate_requirement_gaps(requirements, skills_by_name)

    # Check which gaps already have completed learning
    completed_skills = _get_completed_skills(db, profile_id)

    suggestions = []
    for skill_key, data in gap_data.items():
        if _is_gap_resolved(skill_key, data, completed_skills, skills_by_name):
            continue

        suggestions.append(_make_skill_gap_suggestion(display_names[skill_key], data))

    # Sort by priority score descending
    suggestions.sort(key=lambda s: s["priority_score"], reverse=True)
    return suggestions


def _is_gap_resolved(
    skill_key: str,
    data: dict,
    completed_skills: set[str],
    skills_by_name: dict[str, Skill],
) -> bool:
    """Return True if a skill gap has been resolved via completed learning."""
    if skill_key not in completed_skills:
        return False
    current_skill = skills_by_name.get(skill_key)
    if not current_skill:
        return False
    cur_idx = _PROFICIENCY_ORDER.get(current_skill.proficiency.lower(), 0)
    req_idx = _PROFICIENCY_ORDER.get(data["required_level"].lower(), 1)
    return cur_idx >= req_idx


def _make_skill_gap_suggestion(skill_name: str, data: dict) -> dict:
    """Build a single skill-gap suggestion dict from aggregated data."""
    distance = data["distance"]
    hours = distance * 10.0  # ~10h per proficiency level
    weeks = max(1.0, distance * 1.5)
    difficulty = _DIFFICULTY_LOOKUP.get(distance, "high")

    # Priority score: higher = more important (frequency * severity weight)
    priority_score = data["frequency"] * data["max_severity_weight"]

    current_desc = data["current_level"] or "none"
    return {
        "action": (
            f"Improve {skill_name} from {current_desc} to "
            f"{data['required_level']} — required by {data['frequency']} "
            f"target role{'s' if data['frequency'] > 1 else ''}"
        ),
        "hours": hours,
        "weeks": weeks,
        "difficulty": difficulty,
        "priority_score": priority_score,
    }


# ---------------------------------------------------------------------------
# Helpers for _build_goal_suggestions
# ---------------------------------------------------------------------------


def _goal_application_suggestion(gap_count: int, goal_title: str) -> dict:
    """Build a suggestion for submitting more applications toward a goal."""
    return {
        "action": (
            f"Submit {gap_count} more applications to reach "
            f"your pipeline target for goal: {goal_title}"
        ),
        "hours": gap_count * 2.0,
        "weeks": max(1.0, gap_count * 0.5),
        "difficulty": "medium",
        "priority_score": 2.5,
    }


def _goal_in_progress_suggestion(in_progress_count: int, goal_title: str) -> dict:
    """Build a suggestion for completing in-progress learning resources."""
    return {
        "action": (
            f"Complete {in_progress_count} in-progress learning "
            f"resource{'s' if in_progress_count > 1 else ''} "
            f"to advance toward goal: {goal_title}"
        ),
        "hours": in_progress_count * 5.0,
        "weeks": max(1.0, in_progress_count * 1.0),
        "difficulty": "medium",
        "priority_score": 2.0,
    }


def _goal_unstarted_suggestion(unstarted_count: int) -> dict:
    """Build a suggestion for starting pending learning resources."""
    return {
        "action": (
            f"Start working on {unstarted_count} pending learning "
            f"resource{'s' if unstarted_count > 1 else ''} to close skill gaps"
        ),
        "hours": unstarted_count * 8.0,
        "weeks": max(1.0, unstarted_count * 2.0),
        "difficulty": "medium",
        "priority_score": 1.5,
    }


def _build_goal_suggestions(db: Session, profile_id: int) -> list[dict]:
    """Generate suggestions from career goals.

    Looks at active goals and their progress to identify areas needing attention.
    """
    goals = db.query(Goal).filter(Goal.profile_id == profile_id, Goal.status == "active").all()

    if not goals:
        return []

    # Check pipeline status
    applications = (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .all()
    )
    active_apps = sum(1 for a in applications if a.status in ("applied", "interviewing", "offer"))
    # Check learning progress
    learning_resources = (
        db.query(LearningResource).filter(LearningResource.profile_id == profile_id).all()
    )
    total_learning = len(learning_resources)
    completed_learning = sum(1 for lr in learning_resources if lr.status == "completed")
    in_progress_learning = sum(1 for lr in learning_resources if lr.status == "in_progress")
    unstarted = total_learning - completed_learning - in_progress_learning

    suggestions = []

    for goal in goals:
        target_apps = 10 if goal.goal_type == "aspirational" else 5

        if active_apps < target_apps:
            gap_count = target_apps - active_apps
            suggestions.append(_goal_application_suggestion(gap_count, goal.title))

        if in_progress_learning > 0:
            suggestions.append(_goal_in_progress_suggestion(in_progress_learning, goal.title))

        if unstarted > 0 and in_progress_learning == 0:
            suggestions.append(_goal_unstarted_suggestion(unstarted))

    return suggestions


def _build_pipeline_suggestions(db: Session, profile_id: int) -> list[dict]:
    """Generate suggestions from pipeline state.

    Looks at stale applications, follow-up opportunities, etc.
    """
    applications = (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .all()
    )

    if not applications:
        return [
            {
                "action": "Start your job search pipeline — add at least 5 target companies",
                "hours": 5.0,
                "weeks": 1.0,
                "difficulty": "low",
                "priority_score": 3.0,
            }
        ]

    suggestions = []

    # Check for discovered but not-yet-applied positions
    discovered = [a for a in applications if a.status == "discovered"]
    if len(discovered) >= 3:
        suggestions.append(
            {
                "action": (
                    f"Review and apply to {len(discovered)} discovered positions "
                    f"sitting in your pipeline"
                ),
                "hours": len(discovered) * 1.5,
                "weeks": 1.0,
                "difficulty": "medium",
                "priority_score": 2.0,
            }
        )

    # Check for applications that could use interview prep
    interviewing = [a for a in applications if a.status == "interviewing"]
    if interviewing:
        suggestions.append(
            {
                "action": (
                    f"Prepare for {len(interviewing)} active "
                    f"interview{'s' if len(interviewing) > 1 else ''} — "
                    f"review company research and STAR stories"
                ),
                "hours": len(interviewing) * 3.0,
                "weeks": 1.0,
                "difficulty": "medium",
                "priority_score": 3.5,
            }
        )

    return suggestions


# ---------------------------------------------------------------------------
# Helpers for get_coaching_suggestions
# ---------------------------------------------------------------------------

_FOCUS_AREA_KEYWORDS = [
    (lambda t: "interview" in t.lower(), "Interview Preparation"),
    (lambda t: "application" in t.lower() or "apply" in t.lower(), "Pipeline Growth"),
    (lambda t: "learning" in t.lower(), "Skill Development"),
]


def _determine_focus_area(action_text: str) -> str:
    """Derive focus area string from the top suggestion's action text."""
    if "Improve" in action_text:
        parts = action_text.split("Improve ", 1)
        if len(parts) > 1:
            name_part = parts[1].split(" from ", 1)[0]
            return name_part

    for predicate, area in _FOCUS_AREA_KEYWORDS:
        if predicate(action_text):
            return area

    return "Career Strategy"


def _sync_suggestions_to_db(
    db: Session,
    profile_id: int,
    sorted_suggestions: list[dict],
    existing_by_action: dict[str, CoachingSuggestion],
) -> list[CoachingSuggestion]:
    """Persist ranked suggestions to DB, updating existing and creating new ones.

    Returns the list of active CoachingSuggestion ORM objects.
    """
    result_suggestions: list[CoachingSuggestion] = []
    actions_seen: set[str] = set()

    for rank, s in enumerate(sorted_suggestions, start=1):
        action = s["action"]
        if action in actions_seen:
            continue
        actions_seen.add(action)

        if action in existing_by_action:
            cs = existing_by_action[action]
            cs.priority = rank
            cs.hours = s["hours"]
            cs.weeks = s["weeks"]
            cs.difficulty = s["difficulty"]
            cs.updated_at = _utcnow()
        else:
            cs = CoachingSuggestion(
                profile_id=profile_id,
                action=action,
                priority=rank,
                hours=s["hours"],
                weeks=s["weeks"],
                difficulty=s["difficulty"],
                status="active",
            )
            db.add(cs)
        result_suggestions.append(cs)

    # Remove stale suggestions that are no longer relevant
    for action, cs in existing_by_action.items():
        if action not in actions_seen:
            cs.status = "dismissed"
            cs.updated_at = _utcnow()

    db.commit()
    for cs in result_suggestions:
        db.refresh(cs)

    return result_suggestions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_coaching_suggestions(
    db: Session,
    profile_id: int,
) -> dict:
    """Generate prioritized coaching suggestions.

    Combines insights from:
    - Skill gaps across target roles
    - Career goals and progress
    - Pipeline state

    Returns:
        Dict with suggestions list, total count, and focus_area.
    """
    _verify_profile(db, profile_id)

    # Gather suggestions from all sources
    all_suggestions: list[dict] = []
    all_suggestions.extend(_build_skill_gap_suggestions(db, profile_id))
    all_suggestions.extend(_build_goal_suggestions(db, profile_id))
    all_suggestions.extend(_build_pipeline_suggestions(db, profile_id))

    # De-duplicate by action text (keep highest priority_score)
    seen: dict[str, dict] = {}
    for s in all_suggestions:
        key = s["action"]
        if key not in seen or s["priority_score"] > seen[key]["priority_score"]:
            seen[key] = s

    # Sort by priority_score descending
    sorted_suggestions = sorted(seen.values(), key=lambda s: s["priority_score"], reverse=True)

    # Persist to database and build response
    existing = (
        db.query(CoachingSuggestion)
        .filter(
            CoachingSuggestion.profile_id == profile_id,
            CoachingSuggestion.status == "active",
        )
        .all()
    )
    existing_by_action: dict[str, CoachingSuggestion] = {e.action: e for e in existing}

    result_suggestions = _sync_suggestions_to_db(
        db, profile_id, sorted_suggestions, existing_by_action
    )

    # Determine focus area from the top suggestion
    focus_area = None
    if result_suggestions:
        focus_area = _determine_focus_area(result_suggestions[0].action)

    return {
        "suggestions": result_suggestions,
        "total": len(result_suggestions),
        "focus_area": focus_area,
    }
