"""Gap analysis service: compare job requirements against skills inventory."""

import re
from collections import Counter

from sqlalchemy.orm import Session

from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement, Skill


class ApplicationNotFoundError(Exception):
    """Raised when an application is not found."""

    pass


class ProfileNotFoundError(Exception):
    """Raised when the profile doesn't exist."""

    pass


class MissingRequirementsError(Exception):
    """Raised when an application has no parsed requirements."""

    pass


# ---------------------------------------------------------------------------
# Severity classification from requirement text
# ---------------------------------------------------------------------------

# Patterns are matched case-insensitively against the requirement text (skill_name).
# Order matters: first match wins. More specific phrases before general ones.
_CRITICAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bmust[\s-]have\b", re.IGNORECASE),
    re.compile(r"\brequired\b", re.IGNORECASE),
    re.compile(r"\bessential\b", re.IGNORECASE),
    re.compile(r"\bmandatory\b", re.IGNORECASE),
]

_NICE_TO_HAVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bnice[\s-]to[\s-]have\b", re.IGNORECASE),
    re.compile(r"\bpreferred\b", re.IGNORECASE),
    re.compile(r"\bideally\b", re.IGNORECASE),
    re.compile(r"\bbonus[\s-]if\b", re.IGNORECASE),
]

_BONUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bgreat[\s-]to[\s-]have\b", re.IGNORECASE),
    re.compile(r"\bbonus\b", re.IGNORECASE),
    re.compile(r"\bplus\b", re.IGNORECASE),
]

_DEFAULT_SEVERITY = "nice-to-have"


def classify_severity(text: str) -> str:
    """Derive requirement severity from its text using rule-based classification.

    Scans *text* for signal phrases and returns the matching severity:
      - ``'critical'``      — "must have", "required", "essential", "mandatory"
      - ``'nice-to-have'``  — "preferred", "nice to have", "ideally", "bonus if"
      - ``'bonus'``         — "bonus", "plus", "great to have"
      - ``'nice-to-have'``  (default when no signal is found)

    The caller-supplied severity, if any, takes precedence over this function
    (handled upstream in :func:`create_job_requirements`).
    """
    for pattern in _CRITICAL_PATTERNS:
        if pattern.search(text):
            return "critical"
    for pattern in _NICE_TO_HAVE_PATTERNS:
        if pattern.search(text):
            return "nice-to-have"
    for pattern in _BONUS_PATTERNS:
        if pattern.search(text):
            return "bonus"
    return _DEFAULT_SEVERITY


# Proficiency level ordering for distance calculation
PROFICIENCY_ORDER = {
    "beginner": 0,
    "intermediate": 1,
    "advanced": 2,
    "expert": 3,
}

# Severity weights for readiness score computation
SEVERITY_WEIGHTS = {
    "critical": 3.0,
    "nice-to-have": 1.0,
    "bonus": 0.5,
}


def _compute_distance(required_level: str, current_level: str | None) -> int:
    """Compute gap distance between required and current proficiency.

    Returns:
        0 if met (current >= required),
        1 if one level below,
        2 if two levels below,
        3 if skill is missing entirely.
    """
    if current_level is None:
        return 3  # skill missing entirely

    req_idx = PROFICIENCY_ORDER.get(required_level.lower(), 1)
    cur_idx = PROFICIENCY_ORDER.get(current_level.lower(), 0)

    if cur_idx >= req_idx:
        return 0  # met or exceeded

    diff = req_idx - cur_idx
    return min(diff, 3)  # cap at 3


def _compute_readiness_score(
    gaps: list[dict],
    total_requirements: int,
) -> float:
    """Compute weighted readiness score (0-100).

    Each requirement contributes its severity weight to the total.
    Gaps reduce the score proportionally to their distance.
    A distance of 0 means the requirement is fully met.
    """
    if total_requirements == 0:
        return 100.0

    total_weight = 0.0
    earned_weight = 0.0

    for gap in gaps:
        severity = gap["severity"]
        distance = gap["distance"]
        weight = SEVERITY_WEIGHTS.get(severity, 1.0)
        total_weight += weight

        # Score contribution: 1.0 if met (distance 0), decreasing for larger gaps
        # distance 0 → 1.0, distance 1 → 0.67, distance 2 → 0.33, distance 3 → 0.0
        score_fraction = max(0.0, 1.0 - distance / 3.0)
        earned_weight += weight * score_fraction

    if total_weight == 0:
        return 100.0

    return round((earned_weight / total_weight) * 100, 1)


def _verify_profile(db: Session, profile_id: int) -> None:
    """Verify profile exists."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")


def _get_application(
    db: Session, application_id: int, profile_id: int
) -> Application:
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


def analyze_gaps(
    db: Session,
    application_id: int,
    profile_id: int,
) -> dict:
    """Perform gap analysis for a single application.

    Compares job requirements against the profile's skills inventory.

    Returns:
        Dict with gaps, readiness_score, total_requirements, gaps_count.

    Raises:
        ApplicationNotFoundError: If the application doesn't exist or belongs to another profile.
        MissingRequirementsError: If no requirements are parsed for the application.
    """
    app_obj = _get_application(db, application_id, profile_id)

    # Load requirements for this application
    requirements = (
        db.query(JobRequirement)
        .filter(
            JobRequirement.application_id == application_id,
            JobRequirement.profile_id == profile_id,
        )
        .all()
    )

    if not requirements:
        raise MissingRequirementsError(
            f"Job requirements not yet parsed for application {application_id}. "
            "Run requirement extraction first."
        )

    # Load all skills for this profile (indexed by lowercase name)
    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    skills_by_name: dict[str, Skill] = {
        s.name.lower().strip(): s for s in skills
    }

    gaps = []
    for req in requirements:
        skill_key = req.skill_name.lower().strip()
        current_skill = skills_by_name.get(skill_key)

        current_level = current_skill.proficiency if current_skill else None
        distance = _compute_distance(req.required_level, current_level)

        gaps.append({
            "skill_name": req.skill_name,
            "required_level": req.required_level,
            "current_level": current_level,
            "severity": req.severity,
            "distance": distance,
        })

    readiness_score = _compute_readiness_score(gaps, len(requirements))

    return {
        "application_id": application_id,
        "company": app_obj.company,
        "role": app_obj.role,
        "gaps": gaps,
        "readiness_score": readiness_score,
        "total_requirements": len(requirements),
        "gaps_count": sum(1 for g in gaps if g["distance"] > 0),
    }


def get_readiness_score(
    db: Session,
    application_id: int,
    profile_id: int,
) -> float | None:
    """Get the readiness score for an application.

    Returns None if no requirements are parsed (instead of raising).
    """
    requirements = (
        db.query(JobRequirement)
        .filter(
            JobRequirement.application_id == application_id,
            JobRequirement.profile_id == profile_id,
        )
        .all()
    )

    if not requirements:
        return None

    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    skills_by_name: dict[str, Skill] = {
        s.name.lower().strip(): s for s in skills
    }

    gaps = []
    for req in requirements:
        skill_key = req.skill_name.lower().strip()
        current_skill = skills_by_name.get(skill_key)
        current_level = current_skill.proficiency if current_skill else None
        distance = _compute_distance(req.required_level, current_level)
        gaps.append({
            "severity": req.severity,
            "distance": distance,
        })

    return _compute_readiness_score(gaps, len(requirements))


def aggregate_gaps(
    db: Session,
    profile_id: int,
) -> dict:
    """Aggregate gaps across all applications for a profile.

    Returns skills that appear as gaps across multiple applications,
    ranked by frequency.
    """
    _verify_profile(db, profile_id)

    # Get all non-archived applications for this profile
    applications = (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .all()
    )

    if not applications:
        return {
            "gaps": [],
            "total_applications_analyzed": 0,
        }

    # Load skills inventory
    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    skills_by_name: dict[str, Skill] = {
        s.name.lower().strip(): s for s in skills
    }

    # Collect gaps across all applications
    # gap_data: normalized_key → list of (app_id, severity, distance)
    # display_names: normalized_key → first-seen display name
    gap_data: dict[str, list[tuple[int, str, int]]] = {}
    display_names: dict[str, str] = {}
    apps_with_requirements = 0

    for app_obj in applications:
        requirements = (
            db.query(JobRequirement)
            .filter(
                JobRequirement.application_id == app_obj.id,
                JobRequirement.profile_id == profile_id,
            )
            .all()
        )

        if not requirements:
            continue

        apps_with_requirements += 1

        for req in requirements:
            skill_key = req.skill_name.lower().strip()
            current_skill = skills_by_name.get(skill_key)
            current_level = current_skill.proficiency if current_skill else None
            distance = _compute_distance(req.required_level, current_level)

            if distance > 0:  # only include actual gaps
                if skill_key not in gap_data:
                    gap_data[skill_key] = []
                    display_names[skill_key] = req.skill_name
                gap_data[skill_key].append(
                    (app_obj.id, req.severity, distance)
                )

    # Build aggregate response sorted by frequency
    aggregate_gaps = []
    for skill_key, entries in gap_data.items():
        app_ids = list({e[0] for e in entries})
        severities = [e[1] for e in entries]
        distances = [e[2] for e in entries]

        # Determine the most common severity
        severity_counts = Counter(severities)
        avg_severity = severity_counts.most_common(1)[0][0]

        avg_distance = round(sum(distances) / len(distances), 1)

        aggregate_gaps.append({
            "skill_name": display_names[skill_key],
            "frequency": len(app_ids),
            "application_ids": app_ids,
            "avg_severity": avg_severity,
            "avg_distance": avg_distance,
        })

    # Sort by frequency descending
    aggregate_gaps.sort(key=lambda x: x["frequency"], reverse=True)

    return {
        "gaps": aggregate_gaps,
        "total_applications_analyzed": apps_with_requirements,
    }


def create_job_requirements(
    db: Session,
    application_id: int,
    profile_id: int,
    requirements: list[dict],
) -> list[JobRequirement]:
    """Create job requirements for an application.

    Args:
        db: Database session.
        application_id: Application ID.
        profile_id: Profile ID.
        requirements: List of dicts with skill_name, required_level, and
            optionally severity.  When *severity* is ``None`` or missing the
            value is derived from the requirement's ``skill_name`` text via
            :func:`classify_severity`.

    Returns:
        List of created JobRequirement objects.
    """
    _verify_profile(db, profile_id)
    _get_application(db, application_id, profile_id)

    created = []
    for req_data in requirements:
        # If caller supplies severity, use it as override; otherwise classify
        severity = req_data.get("severity") or classify_severity(
            req_data["skill_name"]
        )

        req = JobRequirement(
            application_id=application_id,
            profile_id=profile_id,
            skill_name=req_data["skill_name"],
            required_level=req_data.get("required_level", "intermediate"),
            severity=severity,
        )
        db.add(req)
        created.append(req)

    db.commit()
    for r in created:
        db.refresh(r)

    return created
