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

from career_os.ai.base import ProviderQuotaError
from career_os.ai.factory import get_ai_provider
from career_os.ai.openrouter_provider import CreditsExhaustedError
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Application, Profile
from career_os.models.scoring import ScoredJob, ScoringFeedback, ScoringWeights
from career_os.models.skills import Goal, Skill
from career_os.schemas.ai import ScoreResult
from career_os.services.red_flags import detect_data_driven_red_flags, detect_red_flags

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


# ---------------------------------------------------------------------------
# Scoring rubric & calibration (Epic 1 / G-269)
# ---------------------------------------------------------------------------

RUBRIC_VERSION = "v1.0"

SCORING_RUBRIC = """\
## Scoring Rubric

Use these band definitions to anchor your fit_score:

- **9-10 (Dream fit):** Role, skills, seniority, domain, and location all align. \
The candidate would be a top-quartile applicant. Virtually no gaps.
- **7-8 (Strong fit):** Most dimensions match well. Minor gaps exist (e.g. one \
missing tool, slight seniority stretch) but the candidate is clearly competitive.
- **5-6 (Moderate fit):** Partial overlap — some skills transfer, but meaningful \
gaps in domain, seniority, or core requirements. Could succeed with ramp-up.
- **3-4 (Weak fit):** Few dimensions align. Major gaps in multiple areas. \
The candidate would need significant retraining or a career pivot.
- **1-2 (Poor fit):** Near-total mismatch on role type, skills, and domain. \
Applying would waste time for both sides.

### Calibration Examples

**Example 1 — Score: 2.0**
JD: "Senior .NET Developer — build enterprise ERP modules in C#/.NET, Azure DevOps, \
SQL Server. 5+ years .NET required."
Profile: TPM with Python/AI focus, no .NET or ERP experience.
Reasoning: Complete skills mismatch (Python vs .NET), wrong role type (TPM vs SWE), \
unrelated domain. Score: 2.0

**Example 2 — Score: 5.5**
JD: "Product Manager, Growth — own activation funnels, run A/B experiments, SQL \
proficiency, B2C SaaS experience."
Profile: TPM with some PM overlap, strong SQL, but B2B enterprise background.
Reasoning: Transferable analytical skills and SQL, but wrong domain (B2B vs B2C), \
no growth/activation experience. Partial fit. Score: 5.5

**Example 3 — Score: 8.5**
JD: "Technical Program Manager, AI Platform — coordinate ML infrastructure teams, \
drive cross-functional delivery, Python scripting, stakeholder management."
Profile: TPM with strong AI/ML platform experience, Python proficiency, proven \
cross-functional leadership.
Reasoning: Direct role match, strong technical overlap, relevant domain experience. \
Minor gap: specific ML infra tooling. Score: 8.5
"""


def _build_job_family_modifiers(job_family: str | None) -> str:
    """Generate rubric modifiers based on the active job family weights.

    Highlights which dimensions carry more or less weight for the given
    job family so the AI calibrates accordingly.
    """
    if not job_family:
        return ""

    weights = _weights_for_job_family(job_family)
    if weights == DEFAULT_WEIGHTS:
        return ""

    # Identify dimensions that deviate meaningfully from the default
    modifier_lines: list[str] = []
    for dim, weight in weights.items():
        default_w = DEFAULT_WEIGHTS.get(dim, 0.0)
        diff = weight - default_w
        label = dim.replace("_", " ")
        if diff >= 0.05:
            modifier_lines.append(
                f"- For {job_family}: {label} is weighted higher ({weight:.0%} vs "
                f"default {default_w:.0%}) — gaps here are more penalizing."
            )
        elif diff <= -0.05:
            modifier_lines.append(
                f"- For {job_family}: {label} is weighted lower ({weight:.0%} vs "
                f"default {default_w:.0%}) — gaps here matter less."
            )

    if not modifier_lines:
        return ""

    return "\n### Job-Family Weight Modifiers\n" + "\n".join(modifier_lines) + "\n"


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


def _gather_red_flag_metadata(
    db: Session,
    discovered_job_id: int | None,
    job_title: str | None,
) -> dict:
    """Gather metadata from linked DiscoveredJob for red-flag detection."""
    rf: dict = {"posted_at": None, "title": job_title, "salary": None, "location": None}
    if discovered_job_id is not None:
        dj_meta = db.query(DiscoveredJob).filter(DiscoveredJob.id == discovered_job_id).first()
        if dj_meta is not None:
            rf["posted_at"] = dj_meta.posted_at
            rf["title"] = rf["title"] or dj_meta.title
            rf["salary"] = dj_meta.salary_range
            rf["location"] = dj_meta.location
    return rf


# ---------------------------------------------------------------------------
# Desire Score — Option A (Derived from dimensional scores + goals)
# ---------------------------------------------------------------------------

# Default weights for deriving desire_score from dimensional sub-scores.
# career_trajectory = growth potential, company_fit = culture/reputation,
# compensation_fit = salary attractiveness.
DEFAULT_DESIRE_WEIGHTS: dict[str, float] = {
    "career_trajectory": 0.35,
    "company_fit": 0.35,
    "compensation_fit": 0.30,
}

# Keywords in goal titles/descriptions that shift desire weights.
_GOAL_WEIGHT_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "leadership": {"career_trajectory": 0.50, "company_fit": 0.25, "compensation_fit": 0.25},
    "management": {"career_trajectory": 0.50, "company_fit": 0.25, "compensation_fit": 0.25},
    "compensation": {"career_trajectory": 0.20, "company_fit": 0.25, "compensation_fit": 0.55},
    "salary": {"career_trajectory": 0.20, "company_fit": 0.25, "compensation_fit": 0.55},
    "culture": {"career_trajectory": 0.25, "company_fit": 0.50, "compensation_fit": 0.25},
    "remote": {"career_trajectory": 0.25, "company_fit": 0.50, "compensation_fit": 0.25},
}


def _resolve_desire_weights(goals: list[dict]) -> dict[str, float]:
    """Determine desire weights based on user's active goals.

    If any goal title/description contains keywords like "leadership",
    "compensation", etc., we shift the weights to match user priorities.
    Falls back to DEFAULT_DESIRE_WEIGHTS if no keywords match.
    """
    if not goals:
        return dict(DEFAULT_DESIRE_WEIGHTS)

    all_goal_text = " ".join(
        f"{g.get('title', '')} {g.get('description', '')}".lower() for g in goals
    )

    for keyword, weights in _GOAL_WEIGHT_ADJUSTMENTS.items():
        if keyword in all_goal_text:
            return dict(weights)

    return dict(DEFAULT_DESIRE_WEIGHTS)


def compute_derived_desire_score(
    dimensional_scores: dict[str, float] | None,
    goals: list[dict] | None = None,
) -> float | None:
    """Compute desire_score as a weighted average of dimensional sub-scores.

    Option A: derived from existing dimensions — no additional AI call.

    Args:
        dimensional_scores: Dict with keys career_trajectory, company_fit,
            compensation_fit (each 0-10). None → returns None.
        goals: List of goal dicts with title/description for weight adjustment.

    Returns:
        Float 0-10 rounded to 1 decimal, or None if dimensions unavailable.
    """
    if dimensional_scores is None:
        return None

    # Check that the required dimensions are present
    required = ("career_trajectory", "company_fit", "compensation_fit")
    if not all(dimensional_scores.get(k) is not None for k in required):
        return None

    weights = _resolve_desire_weights(goals or [])

    score = sum(dimensional_scores[dim] * weight for dim, weight in weights.items())

    # Clamp to [0, 10]
    return round(max(0.0, min(10.0, score)), 1)


def _build_dim_columns(dim) -> dict[str, float | None]:
    """Build dimensional score columns dict from AI result."""
    if dim is None:
        return {
            "dim_technical_fit": None,
            "dim_seniority_alignment": None,
            "dim_compensation_fit": None,
            "dim_location_fit": None,
            "dim_career_trajectory": None,
            "dim_company_fit": None,
        }
    return {
        "dim_technical_fit": dim.technical_fit,
        "dim_seniority_alignment": dim.seniority_alignment,
        "dim_compensation_fit": dim.compensation_fit,
        "dim_location_fit": dim.location_fit,
        "dim_career_trajectory": dim.career_trajectory,
        "dim_company_fit": dim.company_fit,
    }


def _update_linked_scores(
    db: Session,
    fit_score: float,
    discovered_job_id: int | None,
    application_id: int | None,
) -> None:
    """Propagate fit_score to linked DiscoveredJob and/or Application."""
    if discovered_job_id is not None:
        dj = db.query(DiscoveredJob).filter(DiscoveredJob.id == discovered_job_id).first()
        if dj:
            dj.fit_score = fit_score
    if application_id is not None:
        app_record = db.query(Application).filter(Application.id == application_id).first()
        if app_record:
            app_record.fit_score = fit_score


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

    # Fetch calibration examples when feature flag is enabled
    calibration_examples: list[dict] = []
    from career_os.config import settings

    if settings.feedback_calibration_enabled:
        calibration_examples = get_feedback_calibration(db, profile_id)

    # Build scoring prompt with job context
    prompt = _build_scoring_prompt(
        job_description=job_description,
        job_title=job_title,
        job_company=job_company,
        job_url=job_url,
        profile_data=profile_data,
        calibration_examples=calibration_examples,
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

    # Rule-based red flags (zero AI cost)
    rf = _gather_red_flag_metadata(db, discovered_job_id, job_title)
    red_flags = detect_red_flags(
        job_description,
        posted_at=rf["posted_at"],
        title=rf["title"],
        salary_range=rf["salary"],
        location=rf["location"],
    )

    # Data-driven red flags: ghost job and multi-city blast detection (G-270)
    # Only runs when we have company and title context from a discovered job.
    effective_title = rf["title"] or job_title
    if job_company and effective_title:
        ghost_flags = detect_data_driven_red_flags(
            db,
            company=job_company,
            title=effective_title,
            description=job_description,
            profile_id=profile_id,
        )
        red_flags = red_flags + ghost_flags

    red_flags_json = json.dumps(red_flags) if red_flags else None

    # Dimensional sub-scores
    dim_columns = _build_dim_columns(score_data.dimensional_scores)

    # ATS keywords: serialize the list of {keyword, category, matched} to JSON
    # text. Empty list → NULL so legacy rows remain unchanged.
    ats_keywords_json = (
        json.dumps([kw.model_dump() for kw in score_data.ats_keywords])
        if score_data.ats_keywords
        else None
    )

    # Desire score computation (dual-score architecture, G-275)
    desire_score = None
    desire_score_method = None
    desire_reasoning = None

    # Option B: AI-generated desire_score (if the provider returned one)
    if score_data.desire_score is not None:
        desire_score = score_data.desire_score
        desire_score_method = "ai_generated"
        desire_reasoning = score_data.desire_reasoning

    # Option A fallback: derive from dimensional scores + goals
    if desire_score is None and score_data.dimensional_scores is not None:
        dim_dict = {
            "career_trajectory": score_data.dimensional_scores.career_trajectory,
            "company_fit": score_data.dimensional_scores.company_fit,
            "compensation_fit": score_data.dimensional_scores.compensation_fit,
        }
        desire_score = compute_derived_desire_score(dim_dict, profile_data.get("goals"))
        if desire_score is not None:
            desire_score_method = "derived"

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
        red_flags=red_flags_json,
        ats_keywords=ats_keywords_json,
        is_stale=False,
        weights_snapshot=json.dumps({**profile_data["weights"], "rubric_version": RUBRIC_VERSION}),
        desire_score=desire_score,
        desire_score_method=desire_score_method,
        desire_reasoning=desire_reasoning,
        **dim_columns,
    )
    db.add(scored_job)

    # Propagate fit_score to linked records
    _update_linked_scores(db, score_data.fit_score, discovered_job_id, application_id)

    db.commit()
    db.refresh(scored_job)

    return scored_job


def _format_skills_section(skills: list[dict]) -> list[str]:
    """Format skills into prompt lines."""
    if not skills:
        return []
    lines = ["\nSkills:"]
    for skill in skills[:20]:  # Limit to avoid huge prompts
        lines.append(f"  - {skill['name']} ({skill['category']}, {skill['proficiency']})")
    return lines


def _format_goals_section(goals: list[dict]) -> list[str]:
    """Format goals into prompt lines."""
    if not goals:
        return []
    lines = ["\nCareer Goals:"]
    for goal in goals[:5]:
        lines.append(f"  - {goal['title']} ({goal['type']})")
    return lines


def _format_market_section(market: dict) -> list[str]:
    """Format market positioning into prompt lines (VAL-CROSS-010)."""
    positions = market.get("positions", [])
    if not positions:
        return []
    lines = ["\nMarket Positioning:"]
    for pos in positions[:5]:
        lines.append(
            f"  - {pos['role_type']}: {pos['match_percentage']}% match "
            f"({pos['total_roles_analyzed']} roles analyzed)"
        )
    return lines


def _format_calibration_section(calibration_examples: list[dict]) -> list[str]:
    """Format feedback calibration examples into prompt lines.

    Tells the AI how the user previously corrected scores so it can adjust
    its scoring tendencies for this profile.
    """
    if not calibration_examples:
        return []
    lines = ["\nScoring Calibration (user corrections on past scores — adjust accordingly):"]
    for ex in calibration_examples:
        title = ex.get("job_title") or "Unknown role"
        company = ex.get("company") or "Unknown company"
        ai = ex.get("ai_score", "?")
        user = ex.get("user_score", "?")
        reason = ex.get("reason")
        line = f"  - {title} @ {company}: AI scored {ai}, user corrected to {user}"
        if reason:
            line += f" (reason: {reason})"
        lines.append(line)
    return lines


def _build_scoring_prompt(
    *,
    job_description: str,
    job_title: str | None = None,
    job_company: str | None = None,
    job_url: str | None = None,
    profile_data: dict,
    calibration_examples: list[dict] | None = None,
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

    parts.extend(_format_skills_section(profile_data.get("skills", [])))
    parts.extend(_format_goals_section(profile_data.get("goals", [])))
    parts.extend(_format_market_section(profile_data.get("market_positioning", {})))

    # Scoring rubric with calibration examples (G-269)
    parts.append(f"\n{SCORING_RUBRIC}")
    job_family = profile_data.get("job_family")
    family_modifiers = _build_job_family_modifiers(job_family)
    if family_modifiers:
        parts.append(family_modifiers)

    if profile_data.get("weights"):
        parts.append(f"\nScoring Weights: {json.dumps(profile_data['weights'])}")

    parts.extend(_format_calibration_section(calibration_examples or []))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Batch Scoring
# ---------------------------------------------------------------------------


def _query_jobs_to_score(
    db: Session,
    profile_id: int,
    discovered_job_ids: list[int] | None,
    rescore_stale: bool,
) -> list:
    """Return the list of DiscoveredJob rows to score."""
    if discovered_job_ids:
        return (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.profile_id == profile_id,
                DiscoveredJob.id.in_(discovered_job_ids),
            )
            .all()
        )
    if rescore_stale:
        fresh_scored_ids = db.query(ScoredJob.discovered_job_id).filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.discovered_job_id.isnot(None),
            ScoredJob.is_stale.is_(False),
        )
        return (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.profile_id == profile_id,
                DiscoveredJob.id.notin_(fresh_scored_ids),
            )
            .all()
        )
    any_scored_ids = db.query(ScoredJob.discovered_job_id).filter(
        ScoredJob.profile_id == profile_id,
        ScoredJob.discovered_job_id.isnot(None),
    )
    return (
        db.query(DiscoveredJob)
        .filter(
            DiscoveredJob.profile_id == profile_id,
            DiscoveredJob.id.notin_(any_scored_ids),
        )
        .all()
    )


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

    jobs = _query_jobs_to_score(db, profile_id, discovered_job_ids, rescore_stale)

    # --- Embedding pre-filter (Epic 4 / G-272) ---
    # Compute cosine similarity between profile and each job embedding.
    # In shadow mode (default): log similarities but score all jobs.
    # When enabled: skip jobs below threshold to save LLM costs.
    from career_os.config import settings as _settings
    from career_os.services.embeddings import compute_job_similarities

    provider = get_ai_provider()
    prefilter_enabled = _settings.embedding_prefilter_enabled
    threshold = _settings.embedding_prefilter_threshold

    try:
        similarities = await compute_job_similarities(db, profile_id, jobs, provider)
    except Exception:
        logger.warning(
            "Embedding pre-filter failed — skipping, all %d jobs will be fully scored",
            len(jobs),
            exc_info=True,
        )
        similarities = {}

    if similarities:
        below = sum(1 for s in similarities.values() if s < threshold)
        above = len(similarities) - below
        no_embed = len(jobs) - len(similarities)

        if prefilter_enabled:
            # Actually filter: keep jobs above threshold + jobs without embeddings
            jobs = [j for j in jobs if similarities.get(j.id, threshold) >= threshold]
            logger.info(
                "Pre-filtered %d of %d jobs (threshold %.2f), sending %d to full scoring "
                "(%d without embeddings passed through)",
                below,
                below + above + no_embed,
                threshold,
                len(jobs),
                no_embed,
            )
        else:
            # Shadow mode: log but don't filter
            logger.info(
                "Shadow pre-filter: %d/%d jobs below threshold %.2f "
                "(would be filtered if enabled), %d without embeddings",
                below,
                below + above + no_embed,
                threshold,
                no_embed,
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
        except (CreditsExhaustedError, ProviderQuotaError):
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
# Score Context (Percentile / Rank)
# ---------------------------------------------------------------------------

_SCORE_CONTEXT_MIN_SCORES = 5  # minimum non-stale scores required for meaningful context


def compute_score_context(db: Session, profile_id: int, fit_score: float) -> dict | None:
    """Return percentile context for a score relative to the user's scoring history.

    Only computed when the profile has >= 5 non-stale scored jobs.  Returns
    ``None`` when there is insufficient data.

    The returned dict matches the ``ScoreContextResponse`` Pydantic schema:
        {
            "percentile": 82,       # score is higher than 82% of scored jobs
            "rank": 3,              # 3rd highest score
            "total_scored": 47,     # total non-stale scored jobs
            "avg_score": 5.3,       # average fit_score
            "score_band_count": 8,  # jobs in the same letter grade band
        }
    """
    from career_os.schemas.scoring import score_to_letter_grade

    # Count total non-stale scored jobs for this profile
    total_scored: int = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .count()
    )

    if total_scored < _SCORE_CONTEXT_MIN_SCORES:
        return None

    # Count how many scores are strictly below this score (for percentile)
    below_count: int = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
            ScoredJob.fit_score < fit_score,
        )
        .count()
    )

    percentile = int(below_count / total_scored * 100)

    # Rank: count scores strictly above this score + 1
    above_count: int = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
            ScoredJob.fit_score > fit_score,
        )
        .count()
    )
    rank = above_count + 1

    # Average score across all non-stale jobs
    from sqlalchemy import func as sa_func

    avg_result = (
        db.query(sa_func.avg(ScoredJob.fit_score))
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .scalar()
    )
    avg_score = round(float(avg_result), 2) if avg_result is not None else 0.0

    # Jobs in the same letter grade band as fit_score
    target_grade = score_to_letter_grade(fit_score)
    all_scores = (
        db.query(ScoredJob.fit_score)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .all()
    )
    score_band_count = sum(1 for (s,) in all_scores if score_to_letter_grade(s) == target_grade)

    return {
        "percentile": percentile,
        "rank": rank,
        "total_scored": total_scored,
        "avg_score": avg_score,
        "score_band_count": score_band_count,
    }


# ---------------------------------------------------------------------------
# Profile Completeness (Epic 10 / G-278)
# ---------------------------------------------------------------------------

# Weights for each completeness component (sum = 100)
_COMPLETENESS_WEIGHTS: dict[str, int] = {
    "job_family": 15,
    "location": 15,
    "skills": 20,
    "goals": 15,
    "market_positioning": 10,
    "experiences": 15,
    "dream_companies": 10,
}

_MIN_SKILLS = 5
_MIN_GOALS = 1
_MIN_EXPERIENCES = 3  # proxy: Applications with status != 'discovered'
_HIGH_UNCERTAINTY_THRESHOLD = 50  # below this, show the improvement hint


def compute_profile_completeness(db: Session, profile_id: int) -> dict:
    """Compute profile richness and return a completeness dict.

    Returns a dict with:
        - ``completeness``: 0-100 float representing profile richness
        - ``confidence_range``: (low_bound, high_bound) tuple clamped to [0, 10]
        - ``missing_fields``: list of field suggestions (only when completeness < 50)

    Completeness components and their weights:
        job_family (+15%), location (+15%), >=5 skills (+20%),
        >=1 goal (+15%), market_positioning (+10%), >=3 experiences (+15%),
        dream_companies (+10%).

    Confidence interval formula:
        half_width = 3.0 * (1 - completeness / 100) + 0.3
    so at 100% -> ±0.3, at 50% -> ±1.8 (effective), at 25% -> ±3.075.

    Since there is no Experiences model yet, that component is always 0.
    """
    import json as _json

    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        return {
            "completeness": 0.0,
            "confidence_range": (0.0, 10.0),
            "missing_fields": list(_COMPLETENESS_WEIGHTS.keys()),
        }

    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    goals = db.query(Goal).filter(Goal.profile_id == profile_id).all()

    # Evaluate each component
    has_job_family = bool(profile.job_family)
    has_location = bool(profile.location)
    has_enough_skills = len(skills) >= _MIN_SKILLS
    has_goals = len(goals) >= _MIN_GOALS
    has_market_data = profile.last_market_refreshed_at is not None
    # No Experiences model yet — proxy via applied/interviewing/offer/accepted applications
    # We conservatively treat this as 0 until the model exists.
    has_experiences = False  # always False until Experiences model is introduced

    # dream_companies is a JSON array stored as text
    has_dream_companies = False
    if profile.dream_companies:
        try:
            dc = _json.loads(profile.dream_companies)
            has_dream_companies = isinstance(dc, list) and len(dc) > 0
        except (ValueError, TypeError):
            has_dream_companies = bool(profile.dream_companies.strip())

    component_flags = {
        "job_family": has_job_family,
        "location": has_location,
        "skills": has_enough_skills,
        "goals": has_goals,
        "market_positioning": has_market_data,
        "experiences": has_experiences,
        "dream_companies": has_dream_companies,
    }

    completeness = float(
        sum(
            _COMPLETENESS_WEIGHTS[component]
            for component, present in component_flags.items()
            if present
        )
    )

    # half_width = 3.0 * (1 - completeness/100) + 0.3
    half_width = 3.0 * (1.0 - completeness / 100.0) + 0.3

    # We need a fit_score to center the range, but completeness is profile-level
    # (not score-specific), so we express it as a symmetric expansion around
    # the score midpoint.  Callers apply this to the actual fit_score.
    # Return raw half_width here; the API layer applies it to each score.
    low_bound = round(max(0.0, 5.0 - half_width), 2)
    high_bound = round(min(10.0, 5.0 + half_width), 2)

    missing_fields: list[str] = []
    if completeness < _HIGH_UNCERTAINTY_THRESHOLD:
        field_labels: dict[str, str] = {
            "job_family": "target job family",
            "location": "location preference",
            "skills": f"at least {_MIN_SKILLS} skills",
            "goals": "at least one career goal",
            "market_positioning": "market positioning data (refresh market)",
            "experiences": "past work experiences",
            "dream_companies": "dream companies list",
        }
        missing_fields = [
            field_labels[component] for component, present in component_flags.items() if not present
        ]

    return {
        "completeness": completeness,
        "confidence_range": (low_bound, high_bound),
        "missing_fields": missing_fields,
        "half_width": half_width,
    }


def apply_confidence_range(fit_score: float, half_width: float) -> tuple[float, float]:
    """Apply a half-width to a specific fit_score, clamped to [0, 10].

    Returns (low_bound, high_bound).
    """
    return (
        round(max(0.0, fit_score - half_width), 2),
        round(min(10.0, fit_score + half_width), 2),
    )


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


# ---------------------------------------------------------------------------
# Feedback CRUD
# ---------------------------------------------------------------------------

#: Directions considered explicit user corrections
EXPLICIT_DIRECTIONS = {"too_high", "too_low", "correct"}

#: Directions considered implicit signals
IMPLICIT_DIRECTIONS = {"implicit_positive", "implicit_negative", "implicit_strong_positive"}

#: All valid feedback directions
VALID_DIRECTIONS = EXPLICIT_DIRECTIONS | IMPLICIT_DIRECTIONS


class FeedbackNotFoundError(Exception):
    """Raised when a scored_job is not found when submitting feedback."""


class InvalidFeedbackError(Exception):
    """Raised when feedback data is invalid."""


def submit_feedback(
    db: Session,
    *,
    scored_job_id: int,
    profile_id: int,
    direction: str,
    user_score: float | None = None,
    reason: str | None = None,
) -> ScoringFeedback:
    """Submit feedback on an AI-generated score.

    Validates that the scored_job exists and belongs to the profile, then
    creates a ScoringFeedback record snapshotting the original fit_score.

    Raises FeedbackNotFoundError if the scored_job does not exist.
    Raises InvalidFeedbackError if direction or user_score are invalid.
    """
    if direction not in VALID_DIRECTIONS:
        raise InvalidFeedbackError(
            f"Invalid direction '{direction}'. Must be one of: {sorted(VALID_DIRECTIONS)}"
        )
    if user_score is not None and not (0.0 <= user_score <= 10.0):
        raise InvalidFeedbackError("user_score must be between 0 and 10")

    scored_job = (
        db.query(ScoredJob)
        .filter(ScoredJob.id == scored_job_id, ScoredJob.profile_id == profile_id)
        .first()
    )
    if scored_job is None:
        raise FeedbackNotFoundError(f"ScoredJob {scored_job_id} not found for profile {profile_id}")

    feedback = ScoringFeedback(
        scored_job_id=scored_job_id,
        profile_id=profile_id,
        direction=direction,
        user_score=user_score,
        reason=reason,
        original_fit_score=scored_job.fit_score,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def record_implicit_feedback(
    db: Session,
    *,
    profile_id: int,
    direction: str,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
    application_id: int | None = None,
) -> ScoringFeedback | None:
    """Record an implicit feedback signal.

    Looks up the most recent ScoredJob linked to the given discovered_job_id
    or application_id, then creates a ScoringFeedback record. Returns None
    if no ScoredJob can be found (gracefully skipped).

    Called from service hooks — never fails loudly.
    """
    if direction not in IMPLICIT_DIRECTIONS:
        logger.warning("record_implicit_feedback: invalid direction '%s', skipping", direction)
        return None

    # Resolve scored_job_id from the linked entity if not supplied directly
    if scored_job_id is None:
        query = db.query(ScoredJob).filter(ScoredJob.profile_id == profile_id)
        if discovered_job_id is not None:
            query = query.filter(ScoredJob.discovered_job_id == discovered_job_id)
        elif application_id is not None:
            query = query.filter(ScoredJob.application_id == application_id)
        else:
            return None
        scored_job = query.order_by(ScoredJob.created_at.desc()).first()
        if scored_job is None:
            return None
        scored_job_id = scored_job.id
    else:
        scored_job = db.query(ScoredJob).filter(ScoredJob.id == scored_job_id).first()
        if scored_job is None:
            return None

    try:
        feedback = ScoringFeedback(
            scored_job_id=scored_job_id,
            profile_id=profile_id,
            direction=direction,
            user_score=None,
            reason=None,
            original_fit_score=scored_job.fit_score,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback
    except Exception:
        logger.warning(
            "record_implicit_feedback: failed to record signal '%s' for scored_job %d",
            direction,
            scored_job_id,
            exc_info=True,
        )
        db.rollback()
        return None


def list_feedback(db: Session, profile_id: int) -> list[ScoringFeedback]:
    """List all feedback records for a profile, newest first."""
    return (
        db.query(ScoringFeedback)
        .filter(ScoringFeedback.profile_id == profile_id)
        .order_by(ScoringFeedback.created_at.desc())
        .all()
    )


def get_feedback_stats(db: Session, profile_id: int) -> dict:
    """Return summary statistics for feedback submitted by a profile.

    Returns:
        total_count, explicit_count, implicit_count,
        avg_deviation (or None), direction_counts.
    """
    records = list_feedback(db, profile_id)

    direction_counts: dict[str, int] = {}
    explicit_count = 0
    implicit_count = 0
    deviations: list[float] = []

    for r in records:
        direction_counts[r.direction] = direction_counts.get(r.direction, 0) + 1
        if r.direction in EXPLICIT_DIRECTIONS:
            explicit_count += 1
        else:
            implicit_count += 1
        if r.user_score is not None:
            deviations.append(abs(r.user_score - r.original_fit_score))

    avg_deviation = sum(deviations) / len(deviations) if deviations else None

    return {
        "total_count": len(records),
        "explicit_count": explicit_count,
        "implicit_count": implicit_count,
        "avg_deviation": avg_deviation,
        "direction_counts": direction_counts,
    }


# ---------------------------------------------------------------------------
# Calibration Summary (foundation for Epic 11 / Bayesian Learning)
# ---------------------------------------------------------------------------

#: Minimum number of explicit feedback records required before calibration is
#: returned. Below this threshold the data is too sparse to be meaningful.
CALIBRATION_MIN_FEEDBACK = 10

#: Maximum number of calibration examples injected into the scoring prompt.
CALIBRATION_MAX_EXAMPLES = 5


def get_feedback_calibration(db: Session, profile_id: int) -> list[dict]:
    """Return the most informative calibration examples for the scoring prompt.

    "Most informative" = largest absolute deviation between the user's score
    and the AI's original score. Only explicit corrections (too_high / too_low)
    with a user_score are considered.

    Returns an empty list when fewer than CALIBRATION_MIN_FEEDBACK explicit
    feedback records exist (data too sparse to calibrate).

    Each returned dict has keys:
        job_title, company, ai_score, user_score, reason, deviation
    """
    explicit_records = (
        db.query(ScoringFeedback)
        .filter(
            ScoringFeedback.profile_id == profile_id,
            ScoringFeedback.direction.in_(["too_high", "too_low"]),
            ScoringFeedback.user_score.isnot(None),
        )
        .all()
    )

    if len(explicit_records) < CALIBRATION_MIN_FEEDBACK:
        return []

    # Enrich with job metadata from the linked ScoredJob → DiscoveredJob/Application
    enriched: list[dict] = []
    for record in explicit_records:
        scored_job = db.query(ScoredJob).filter(ScoredJob.id == record.scored_job_id).first()
        job_title: str | None = None
        company: str | None = None
        if scored_job is not None:
            if scored_job.discovered_job_id is not None:
                dj = (
                    db.query(DiscoveredJob)
                    .filter(DiscoveredJob.id == scored_job.discovered_job_id)
                    .first()
                )
                if dj:
                    job_title = dj.title
                    company = dj.company
            elif scored_job.application_id is not None:
                app_rec = (
                    db.query(Application)
                    .filter(Application.id == scored_job.application_id)
                    .first()
                )
                if app_rec:
                    job_title = app_rec.role
                    company = app_rec.company

        deviation = abs(record.user_score - record.original_fit_score)  # type: ignore[operator]
        enriched.append(
            {
                "job_title": job_title,
                "company": company,
                "ai_score": record.original_fit_score,
                "user_score": record.user_score,
                "reason": record.reason,
                "deviation": deviation,
            }
        )

    # Sort by deviation descending, take top N
    enriched.sort(key=lambda x: x["deviation"], reverse=True)
    return enriched[:CALIBRATION_MAX_EXAMPLES]
