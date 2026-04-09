"""Scoring service — AI-powered job scoring engine.

Scores jobs against the user's full profile (target roles, psychometric fit,
culture signals, salary expectations, values). Factors in M2 skills gaps
(readiness_score) and career goals (career_alignment).
"""

from __future__ import annotations

import json
import logging
import time

from sqlalchemy.orm import Session

from career_os.ai.factory import get_ai_provider
from career_os.ai.openrouter_provider import CreditsExhaustedError
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Application, Profile
from career_os.models.scoring import ScoredJob, ScoringWeights
from career_os.models.skills import Goal, Skill
from career_os.schemas.ai import ScoreResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


class JobNotFoundError(Exception):
    """Raised when a discovered job or application is not found."""


class ProfileIncompleteError(Exception):
    """Raised when profile lacks required fields for meaningful scoring."""


class ScoringError(Exception):
    """Raised when scoring fails."""


# ---------------------------------------------------------------------------
# Default weights
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "skills_match": 0.25,
    "career_alignment": 0.20,
    "culture_fit": 0.15,
    "salary_match": 0.15,
    "location_match": 0.10,
    "growth_potential": 0.10,
    "remote_preference": 0.05,
}

# Job-family-specific weight presets (VAL-CROSS-004).
# When a profile's job_family changes, the scoring weights are regenerated
# with the preset for the new family.  Families not listed here fall back to
# DEFAULT_WEIGHTS.
JOB_FAMILY_WEIGHTS: dict[str, dict[str, float]] = {
    "TPM": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "SWE": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Product Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "DevRel": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.10,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "AI Program Lead": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
}


def _weights_for_job_family(job_family: str | None) -> dict[str, float]:
    """Return the default weight preset for a given job family.

    Falls back to DEFAULT_WEIGHTS for unknown or None job families.
    Lookup is case-insensitive with stripped whitespace.
    """
    if not job_family:
        return dict(DEFAULT_WEIGHTS)

    normalized = job_family.strip()
    # Try exact match first
    if normalized in JOB_FAMILY_WEIGHTS:
        return dict(JOB_FAMILY_WEIGHTS[normalized])

    # Try case-insensitive match
    lower = normalized.lower()
    for key, preset in JOB_FAMILY_WEIGHTS.items():
        if key.lower() == lower:
            return dict(preset)

    return dict(DEFAULT_WEIGHTS)


# ---------------------------------------------------------------------------
# Weight management
# ---------------------------------------------------------------------------


def get_or_create_weights(db: Session, profile_id: int) -> ScoringWeights:
    """Get scoring weights for a profile, creating defaults if none exist.

    When creating new weights, uses job-family-specific defaults based on
    the profile's current job_family setting.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    weights = db.query(ScoringWeights).filter(ScoringWeights.profile_id == profile_id).first()
    if not weights:
        preset = _weights_for_job_family(profile.job_family)
        weights = ScoringWeights(profile_id=profile_id, **preset)
        db.add(weights)
        db.commit()
        db.refresh(weights)

    return weights


def update_weights(db: Session, profile_id: int, data: dict[str, float]) -> ScoringWeights:
    """Update scoring weights for a profile. Marks existing scores as stale."""
    weights = get_or_create_weights(db, profile_id)

    for field_name, value in data.items():
        if hasattr(weights, field_name) and value is not None:
            setattr(weights, field_name, value)

    # Mark all existing scores as stale and null out cached fit_scores
    flag_stale_scores(db, profile_id)

    db.refresh(weights)
    return weights


def regenerate_weights_for_job_family(
    db: Session, profile_id: int, job_family: str | None
) -> ScoringWeights:
    """Delete existing scoring weights and recreate with job-family defaults.

    Called when a profile's job_family changes (VAL-CROSS-004) so that
    GET /api/scoring-weights returns job-family-appropriate values.
    """
    # Delete existing weights row if any
    db.query(ScoringWeights).filter(ScoringWeights.profile_id == profile_id).delete()
    db.flush()

    # Create fresh weights using the new job_family preset
    preset = _weights_for_job_family(job_family)
    weights = ScoringWeights(profile_id=profile_id, **preset)
    db.add(weights)
    db.commit()
    db.refresh(weights)
    return weights


# ---------------------------------------------------------------------------
# Profile data gathering (for scoring context)
# ---------------------------------------------------------------------------


def _gather_profile_data(db: Session, profile: Profile) -> dict:
    """Gather all profile data relevant for scoring.

    Includes skills, goals, and market positioning data (VAL-CROSS-010).
    """
    # Skills
    skills = db.query(Skill).filter(Skill.profile_id == profile.id).all()
    skills_data = [
        {
            "name": s.name,
            "category": s.category,
            "proficiency": s.proficiency,
        }
        for s in skills
    ]

    # Goals
    goals = db.query(Goal).filter(Goal.profile_id == profile.id, Goal.status == "active").all()
    goals_data = [
        {
            "title": g.title,
            "type": g.goal_type,
            "description": g.description,
        }
        for g in goals
    ]

    # Market positioning data (VAL-CROSS-010)
    market_data: dict = {}
    try:
        from career_os.services.market import get_market_positioning

        positioning = get_market_positioning(db, profile.id)
        market_data = {
            "positions": positioning.get("positions", []),
            "last_refreshed_at": positioning.get("last_refreshed_at"),
        }
    except Exception:
        # Market data is supplementary — scoring must not fail if unavailable
        logger.debug("Market positioning data unavailable for profile %d", profile.id)

    return {
        "name": profile.name,
        "location": profile.location,
        "job_family": profile.job_family,
        "email": profile.email,
        "skills": skills_data,
        "goals": goals_data,
        "market_positioning": market_data,
    }


# ---------------------------------------------------------------------------
# Single Job Scoring
# ---------------------------------------------------------------------------


def _validate_scoring_inputs(
    db: Session,
    profile_id: int,
    application_id: int | None,
    discovered_job_id: int | None,
) -> Profile:
    """Validate profile, discovered job, and application exist for scoring.

    Returns the Profile on success.
    Raises ProfileNotFoundError or JobNotFoundError on failure.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    if discovered_job_id is not None:
        dj = (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.id == discovered_job_id,
                DiscoveredJob.profile_id == profile_id,
            )
            .first()
        )
        if not dj:
            raise JobNotFoundError(
                f"Discovered job {discovered_job_id} not found for profile {profile_id}"
            )

    if application_id is not None:
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.profile_id == profile_id,
            )
            .first()
        )
        if not app:
            raise JobNotFoundError(
                f"Application {application_id} not found for profile {profile_id}"
            )

    return profile


def _gather_scoring_context(db: Session, profile: Profile, profile_id: int) -> dict:
    """Gather profile data and scoring weights into a single context dict."""
    weights = get_or_create_weights(db, profile_id)
    profile_data = _gather_profile_data(db, profile)
    profile_data["weights"] = weights.to_dict()
    return profile_data


async def score_job(
    db: Session,
    profile_id: int,
    job_description: str,
    *,
    job_url: str | None = None,
    job_title: str | None = None,
    job_company: str | None = None,
    discovered_job_id: int | None = None,
    application_id: int | None = None,
) -> ScoredJob:
    """Score a single job against a profile.

    Returns a ScoredJob record persisted in the database.
    """
    profile = _validate_scoring_inputs(db, profile_id, application_id, discovered_job_id)

    # Guard: profile must have target roles and location for meaningful scores
    if not profile.job_family or not profile.location:
        missing = []
        if not profile.job_family:
            missing.append("target roles")
        if not profile.location:
            missing.append("location")
        raise ProfileIncompleteError(
            f"Fill in your profile ({', '.join(missing)}) for personalized scores"
        )

    # Gather profile data and weights for scoring
    profile_data = _gather_scoring_context(db, profile, profile_id)

    # Build scoring prompt with job context
    prompt = _build_scoring_prompt(
        job_description=job_description,
        job_title=job_title,
        job_company=job_company,
        job_url=job_url,
        profile_data=profile_data,
    )

    # Score via AI provider
    provider = get_ai_provider()
    response = await provider.score(
        job_description=prompt,
        profile_data=profile_data,
    )

    # Extract structured score result
    if response.structured and isinstance(response.structured, ScoreResult):
        score_data = response.structured
    else:
        raise ScoringError("AI provider did not return a valid ScoreResult")

    # Serialize score_breakdown to JSON for storage
    breakdown_json = (
        json.dumps([f.model_dump() for f in score_data.score_breakdown])
        if score_data.score_breakdown
        else None
    )

    # Persist the score
    scored_job = ScoredJob(
        profile_id=profile_id,
        discovered_job_id=discovered_job_id,
        application_id=application_id,
        fit_score=score_data.fit_score,
        readiness_score=score_data.readiness_score,
        career_alignment=score_data.career_alignment,
        reasoning=score_data.reasoning,
        estimated_salary=score_data.estimated_salary,
        effort_flag=score_data.effort_flag,
        prep_level=score_data.prep_level,
        prep_notes=score_data.prep_notes,
        score_breakdown=breakdown_json,
        is_stale=False,
        weights_snapshot=json.dumps(profile_data["weights"]),
    )
    db.add(scored_job)

    # Also update fit_score on the discovered job and/or application
    if discovered_job_id is not None:
        dj = db.query(DiscoveredJob).filter(DiscoveredJob.id == discovered_job_id).first()
        if dj:
            dj.fit_score = score_data.fit_score

    if application_id is not None:
        app_record = db.query(Application).filter(Application.id == application_id).first()
        if app_record:
            app_record.fit_score = score_data.fit_score

    db.commit()
    db.refresh(scored_job)

    return scored_job


def _build_scoring_prompt(
    *,
    job_description: str,
    job_title: str | None = None,
    job_company: str | None = None,
    job_url: str | None = None,
    profile_data: dict,
) -> str:
    """Build a scoring prompt combining job info and profile context."""
    parts = ["Score this job against the candidate profile.\n"]

    if job_title:
        parts.append(f"Job Title: {job_title}")
    if job_company:
        parts.append(f"Company: {job_company}")
    if job_url:
        parts.append(f"URL: {job_url}")
    parts.append(f"\nJob Description:\n{job_description}\n")

    parts.append("\nCandidate Profile:")
    parts.append(f"Name: {profile_data.get('name', 'Unknown')}")
    parts.append(f"Location: {profile_data.get('location', 'Unknown')}")
    parts.append(f"Job Family: {profile_data.get('job_family', 'Unknown')}")

    if profile_data.get("skills"):
        parts.append("\nSkills:")
        for skill in profile_data["skills"][:20]:  # Limit to avoid huge prompts
            parts.append(f"  - {skill['name']} ({skill['category']}, {skill['proficiency']})")

    if profile_data.get("goals"):
        parts.append("\nCareer Goals:")
        for goal in profile_data["goals"][:5]:
            parts.append(f"  - {goal['title']} ({goal['type']})")

    # Include market positioning data (VAL-CROSS-010)
    market = profile_data.get("market_positioning", {})
    positions = market.get("positions", [])
    if positions:
        parts.append("\nMarket Positioning:")
        for pos in positions[:5]:
            parts.append(
                f"  - {pos['role_type']}: {pos['match_percentage']}% match "
                f"({pos['total_roles_analyzed']} roles analyzed)"
            )

    if profile_data.get("weights"):
        parts.append(f"\nScoring Weights: {json.dumps(profile_data['weights'])}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Batch Scoring
# ---------------------------------------------------------------------------


async def batch_score_discovery(
    db: Session,
    profile_id: int,
    *,
    discovered_job_ids: list[int] | None = None,
    rescore_stale: bool = False,
) -> dict:
    """Score multiple discovered jobs in batch.

    If discovered_job_ids is empty/None, scores all unscored jobs for the profile.
    Returns dict with scored_count, total_time_seconds, scores, errors.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    # Guard: profile must have target roles and location for meaningful scores
    if not profile.job_family or not profile.location:
        missing = []
        if not profile.job_family:
            missing.append("target roles")
        if not profile.location:
            missing.append("location")
        raise ProfileIncompleteError(
            f"Fill in your profile ({', '.join(missing)}) for personalized scores"
        )

    start_time = time.monotonic()

    # Determine which jobs to score
    if discovered_job_ids:
        jobs = (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.profile_id == profile_id,
                DiscoveredJob.id.in_(discovered_job_ids),
            )
            .all()
        )
    else:
        if rescore_stale:
            # Score jobs with no non-stale score (includes never-scored + stale-only)
            fresh_scored_ids = db.query(ScoredJob.discovered_job_id).filter(
                ScoredJob.profile_id == profile_id,
                ScoredJob.discovered_job_id.isnot(None),
                ScoredJob.is_stale.is_(False),
            )
            jobs = (
                db.query(DiscoveredJob)
                .filter(
                    DiscoveredJob.profile_id == profile_id,
                    DiscoveredJob.id.notin_(fresh_scored_ids),
                )
                .all()
            )
        else:
            # Score only never-scored jobs (no ScoredJob record at all)
            any_scored_ids = db.query(ScoredJob.discovered_job_id).filter(
                ScoredJob.profile_id == profile_id,
                ScoredJob.discovered_job_id.isnot(None),
            )
            jobs = (
                db.query(DiscoveredJob)
                .filter(
                    DiscoveredJob.profile_id == profile_id,
                    DiscoveredJob.id.notin_(any_scored_ids),
                )
                .all()
            )

    scores: list[ScoredJob] = []
    errors: list[dict[str, str]] = []
    credits_exhausted = False

    for job in jobs:
        try:
            description = job.description or f"{job.title} at {job.company} in {job.location}"
            scored = await score_job(
                db,
                profile_id,
                description,
                job_title=job.title,
                job_company=job.company,
                job_url=job.url,
                discovered_job_id=job.id,
                application_id=job.application_id,
            )
            scores.append(scored)
        except CreditsExhaustedError:
            logger.warning(
                "AI credits exhausted after scoring %d/%d jobs — stopping batch",
                len(scores),
                len(jobs),
            )
            credits_exhausted = True
            break
        except Exception as exc:
            logger.warning("Failed to score job %d: %s", job.id, exc)
            errors.append(
                {
                    "discovered_job_id": str(job.id),
                    "error": str(exc),
                }
            )

    total_time = time.monotonic() - start_time

    return {
        "scored_count": len(scores),
        "total_time_seconds": round(total_time, 2),
        "scores": scores,
        "errors": errors,
        "credits_exhausted": credits_exhausted,
    }


# ---------------------------------------------------------------------------
# Profile Switch — Flag Stale Scores
# ---------------------------------------------------------------------------


def flag_stale_scores(db: Session, profile_id: int) -> int:
    """Mark all scores for a profile as stale.

    Called when scoring weights change or profile is switched/updated.
    Also nulls out cached fit_score on DiscoveredJob and Application rows
    so stale scores don't render in the frontend.
    Returns the number of scores flagged as stale.
    """
    # Get IDs of affected discovered jobs and applications before marking stale
    stale_scores = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .all()
    )

    discovered_job_ids = {
        s.discovered_job_id for s in stale_scores if s.discovered_job_id is not None
    }
    application_ids = {s.application_id for s in stale_scores if s.application_id is not None}

    count = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .update({"is_stale": True})
    )

    # Null out cached fit_score on DiscoveredJob rows
    if discovered_job_ids:
        db.query(DiscoveredJob).filter(
            DiscoveredJob.id.in_(discovered_job_ids),
            DiscoveredJob.profile_id == profile_id,
        ).update({"fit_score": None}, synchronize_session="fetch")

    # Null out cached fit_score on Application rows
    if application_ids:
        db.query(Application).filter(
            Application.id.in_(application_ids),
            Application.profile_id == profile_id,
        ).update({"fit_score": None}, synchronize_session="fetch")

    db.commit()
    return count


# ---------------------------------------------------------------------------
# Score Retrieval
# ---------------------------------------------------------------------------


def get_score_for_job(db: Session, profile_id: int, discovered_job_id: int) -> ScoredJob | None:
    """Get the latest non-stale score for a discovered job."""
    return (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.discovered_job_id == discovered_job_id,
            ScoredJob.is_stale.is_(False),
        )
        .order_by(ScoredJob.created_at.desc())
        .first()
    )


def get_score_for_application(
    db: Session, profile_id: int, application_id: int
) -> ScoredJob | None:
    """Get the latest non-stale score for an application."""
    return (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.application_id == application_id,
            ScoredJob.is_stale.is_(False),
        )
        .order_by(ScoredJob.created_at.desc())
        .first()
    )
