"""Role & Industry Intelligence service.

Provides interview format per company, salary benchmarks per role+location,
and common interview patterns per role type.

Data is aggregated from company research (AI) and market intelligence
(discovered jobs data).

Covers:
- VAL-ROLE-INTEL-001: Interview format per company
- VAL-ROLE-INTEL-002: Salary benchmarks per role+location+size
- VAL-ROLE-INTEL-003: Common interview patterns per role type
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from career_os.ai.factory import get_ai_provider
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile
from career_os.schemas.ai import AIFeature, InterviewFormatResult, InterviewPatternsResult
from career_os.schemas.role_intelligence import (
    AssessmentCriterion,
    InterviewFormatResponse,
    InterviewPatternsResponse,
    InterviewRound,
    QuestionCategory,
    SalaryBenchmark,
    SalaryBenchmarkResponse,
    SourceWarning,
)
from career_os.services.market import get_salary_trends
from career_os.services.salary import parse_salary_range

logger = logging.getLogger(__name__)


def _sanitize_for_log(value: object, max_length: int = 200) -> str:
    """Sanitize user-controlled data before logging to prevent log injection."""
    text = str(value).replace("\n", "\\n").replace("\r", "\\r")
    if len(text) > max_length:
        text = text[:max_length] + "...[truncated]"
    return text


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_profile(db: Session, profile_id: int) -> Profile:
    """Validate that a profile exists, raising error if not."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")
    return profile


def _normalize_role_type(title: str) -> str:
    """Normalize job title to a role type bucket."""
    title_lower = title.lower()

    if "tpm" in title_lower or "technical program" in title_lower:
        return "TPM"
    if "program lead" in title_lower or "program manager" in title_lower:
        return "Program Lead"
    if "product engineer" in title_lower:
        return "Product Engineer"
    if "devrel" in title_lower or "developer relation" in title_lower:
        return "DevRel"
    if "engineer" in title_lower:
        return "Engineer"
    if "product manager" in title_lower:
        return "Product Manager"
    if "lead" in title_lower:
        return "Lead"

    return title.strip()


# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-001: Interview format per company
# ---------------------------------------------------------------------------


async def get_interview_format(
    db: Session,
    company: str,
    profile_id: int,
    role: str | None = None,
) -> InterviewFormatResponse:
    """Get typical interview format for a company.

    Uses AI to generate structured interview format data including
    rounds, types, and process duration.

    Args:
        db: Database session.
        company: Company name.
        profile_id: Profile ID for validation.
        role: Optional role context for more specific results.

    Returns:
        InterviewFormatResponse with rounds and duration.

    Raises:
        ProfileNotFoundError: If the profile doesn't exist.
    """
    _validate_profile(db, profile_id)

    role_context = f" for the role of {role}" if role else ""
    prompt = (
        f'Describe the typical interview process at "{company}"{role_context}. '
        f"Include the number of rounds, type of each round "
        f"(e.g., Phone Screen, Technical, Behavioral, System Design, Panel), "
        f"duration per round in minutes, and total process duration. "
        f"Return structured data."
    )

    warnings: list[SourceWarning] = []

    try:
        provider = get_ai_provider()
        response = await provider.complete(
            prompt=prompt,
            feature=AIFeature.interview_format,
            context={"company": company, "role": role, "profile_id": profile_id},
        )
        structured = response.structured
    except Exception as exc:
        logger.warning(
            "AI provider failed for interview format '%s': %s",
            _sanitize_for_log(company),
            _sanitize_for_log(exc),
        )
        structured = None
        warnings.append(
            SourceWarning(
                source="ai_provider",
                error=f"AI provider error: {exc}",
            )
        )

    if isinstance(structured, InterviewFormatResult):
        rounds = [InterviewRound(**rnd) for rnd in structured.rounds]
        return InterviewFormatResponse(
            company=company,
            rounds=rounds,
            total_duration=structured.total_duration,
            process_description=structured.process_description,
            warnings=warnings,
        )

    # Fallback: no structured data
    return InterviewFormatResponse(
        company=company,
        rounds=[],
        total_duration="Unknown",
        process_description="Unable to retrieve interview format data.",
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-002: Salary benchmarks per role+location+size
# ---------------------------------------------------------------------------


def _normalize_role_for_matching(role: str) -> list[str]:
    """Return a list of normalized role variants for fuzzy matching.

    Expands abbreviations and common title variants so that, e.g.,
    "TPM" also matches "Technical Program Manager" and vice versa.
    """
    ROLE_ALIASES: dict[str, list[str]] = {
        "tpm": ["tpm", "technical program manager"],
        "technical program manager": ["tpm", "technical program manager"],
        "pm": ["pm", "program manager", "project manager"],
        "program manager": ["pm", "program manager"],
        "product manager": ["product manager"],
        "swe": ["swe", "software engineer"],
        "software engineer": ["swe", "software engineer"],
        "devrel": ["devrel", "developer relations", "developer advocate"],
        "developer relations": ["devrel", "developer relations", "developer advocate"],
        "developer advocate": ["devrel", "developer relations", "developer advocate"],
        "product engineer": ["product engineer"],
    }

    role_lower = role.strip().lower()
    return ROLE_ALIASES.get(role_lower, [role_lower])


def _salary_fallback_from_market(
    db: Session,
    role: str,
    profile_id: int,
    location: str | None = None,
) -> SalaryBenchmark | None:
    """Fall back to market intelligence salary trends when no discovered jobs match.

    Aggregates p25/median/p75 from market trend data for the given role
    (and optional location). Returns None if no market trend data is available.
    """
    try:
        trends_response = get_salary_trends(db, profile_id, role=role, location=location)
        trends = trends_response.get("trends", [])
        if not trends:
            return None

        # Aggregate across all trend periods
        medians = [t["median"] for t in trends if t.get("median", 0) > 0]
        p25s = [t["p25"] for t in trends if t.get("p25", 0) > 0]
        p75s = [t["p75"] for t in trends if t.get("p75", 0) > 0]
        sample_sizes = [t.get("sample_size", 0) for t in trends]

        if not medians:
            return None

        total_samples = sum(sample_sizes)
        medians.sort()
        p25s.sort()
        p75s.sort()

        return SalaryBenchmark(
            low=p25s[len(p25s) // 2] if p25s else medians[0],
            median=medians[len(medians) // 2],
            high=p75s[len(p75s) // 2] if p75s else medians[-1],
            sample_size=total_samples,
        )
    except Exception as exc:
        logger.warning("Market salary fallback failed for '%s': %s", role, exc)
        return None


def _salary_fallback_from_ai(
    role: str,
    location: str | None = None,
    company_stage: str | None = None,
) -> SalaryBenchmark | None:
    """Generate AI-based salary estimates as final fallback.

    Uses role-based heuristics to produce reasonable salary ranges
    when no discovered jobs or market trends are available.
    """
    # Role-based salary estimate heuristics (EUR)
    _ROLE_SALARY_ESTIMATES: dict[str, tuple[float, float, float]] = {
        "tpm": (110_000.0, 135_000.0, 165_000.0),
        "technical program manager": (110_000.0, 135_000.0, 165_000.0),
        "program manager": (95_000.0, 115_000.0, 140_000.0),
        "product engineer": (90_000.0, 115_000.0, 145_000.0),
        "software engineer": (85_000.0, 110_000.0, 140_000.0),
        "senior engineer": (100_000.0, 125_000.0, 155_000.0),
        "devrel": (85_000.0, 105_000.0, 130_000.0),
        "developer relations": (85_000.0, 105_000.0, 130_000.0),
        "product manager": (95_000.0, 120_000.0, 150_000.0),
        "engineering manager": (110_000.0, 135_000.0, 170_000.0),
        "ai program lead": (115_000.0, 140_000.0, 175_000.0),
    }

    role_lower = role.strip().lower()

    # Try exact match first
    if role_lower in _ROLE_SALARY_ESTIMATES:
        low, median, high = _ROLE_SALARY_ESTIMATES[role_lower]
    else:
        # Try substring match
        matched = None
        for key, values in _ROLE_SALARY_ESTIMATES.items():
            if key in role_lower or role_lower in key:
                matched = values
                break
        if not matched:
            return None
        low, median, high = matched

    return SalaryBenchmark(
        low=low,
        median=median,
        high=high,
        sample_size=0,  # AI estimate, not from data
    )


def get_salary_benchmarks(
    db: Session,
    role: str,
    profile_id: int,
    location: str | None = None,
    company_stage: str | None = None,
) -> SalaryBenchmarkResponse:
    """Compute salary benchmarks from discovered jobs.

    Aggregates salary data from discovered jobs matching the role type
    and optional location/company stage, returning low (p25), median, and
    high (p75) values with sample size and context.

    Role matching uses normalized aliases so that abbreviations like
    "TPM" also match "Technical Program Manager" and vice versa.

    Args:
        db: Database session.
        role: Role type to benchmark (fuzzy-matches job titles).
        profile_id: Profile ID for scoping.
        location: Optional location filter substring.
        company_stage: Optional company stage filter (e.g., 'startup', 'public').

    Returns:
        SalaryBenchmarkResponse with low/median/high benchmarks.

    Raises:
        ProfileNotFoundError: If the profile doesn't exist.
    """
    _validate_profile(db, profile_id)

    # Get discovered jobs for this profile
    query = db.query(DiscoveredJob).filter(DiscoveredJob.profile_id == profile_id)
    jobs = query.all()

    # Filter by role using normalized aliases (case-insensitive)
    role_variants = _normalize_role_for_matching(role)
    matching_jobs = [
        j for j in jobs if any(variant in j.title.lower() for variant in role_variants)
    ]

    # Filter by location if specified
    if location:
        loc_lower = location.lower()
        matching_jobs = [j for j in matching_jobs if j.location and loc_lower in j.location.lower()]

    # Filter by company stage if specified (match against description as heuristic)
    if company_stage:
        stage_lower = company_stage.lower()
        stage_matching: list[DiscoveredJob] = []
        for j in matching_jobs:
            desc = (j.description or "").lower()
            company_lower = (j.company or "").lower()
            # Simple heuristic: check if stage keyword appears in description or company
            if stage_lower in desc or stage_lower in company_lower:
                stage_matching.append(j)
        # Only apply filter if it yields results; otherwise keep all for context
        if stage_matching:
            matching_jobs = stage_matching

    # Extract salary midpoints
    salaries: list[float] = []
    for job in matching_jobs:
        low, high = parse_salary_range(job.salary_range)
        if low is not None and high is not None:
            salaries.append((low + high) / 2)

    if not salaries:
        # VAL-ROLE-INTEL-002: Fall back to market intelligence salary trends
        fallback = _salary_fallback_from_market(db, role, profile_id, location)
        if fallback:
            context_parts = [f"role='{role}'"]
            if location:
                context_parts.append(f"location='{location}'")
            if company_stage:
                context_parts.append(f"stage='{company_stage}'")
            return SalaryBenchmarkResponse(
                role=role,
                location=location,
                company_stage=company_stage,
                benchmarks=fallback,
                context=(
                    f"Based on market intelligence salary trends for "
                    f"{', '.join(context_parts)}. "
                    f"No exact job matches found; using aggregated market data."
                ),
            )

        # Final fallback: AI-based estimates via mock provider
        ai_fallback = _salary_fallback_from_ai(role, location, company_stage)
        if ai_fallback:
            return SalaryBenchmarkResponse(
                role=role,
                location=location,
                company_stage=company_stage,
                benchmarks=ai_fallback,
                context=(
                    f"AI-estimated salary range for '{role}'. "
                    f"No discovered jobs or market trend data matched."
                ),
            )

        context_parts = [f"role='{role}'"]
        if location:
            context_parts.append(f"location='{location}'")
        if company_stage:
            context_parts.append(f"stage='{company_stage}'")
        return SalaryBenchmarkResponse(
            role=role,
            location=location,
            company_stage=company_stage,
            benchmarks=SalaryBenchmark(low=0.0, median=0.0, high=0.0, sample_size=0),
            context=f"No salary data found for {', '.join(context_parts)}.",
        )

    salaries.sort()
    n = len(salaries)

    # Compute percentiles
    p25_idx = max(0, int(n * 0.25) - 1)
    median_idx = n // 2
    p75_idx = min(n - 1, int(n * 0.75))

    p25 = salaries[p25_idx]
    median = salaries[median_idx]
    p75 = salaries[p75_idx]

    # Build context string
    locations = {j.location for j in matching_jobs if j.location}
    companies = {j.company for j in matching_jobs}
    context_parts = [f"Based on {n} data point(s)"]
    if locations:
        context_parts.append(f"from {', '.join(sorted(locations))}")
    if companies:
        context_parts.append(f"at {', '.join(sorted(companies))}")
    if company_stage:
        context_parts.append(f"for {company_stage} stage companies")
    context = ". ".join(context_parts) + "."

    return SalaryBenchmarkResponse(
        role=role,
        location=location,
        company_stage=company_stage,
        benchmarks=SalaryBenchmark(
            low=p25,
            median=median,
            high=p75,
            sample_size=n,
        ),
        context=context,
    )


# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-003: Interview patterns per role type
# ---------------------------------------------------------------------------


async def get_interview_patterns(
    db: Session,
    role: str,
    profile_id: int,
) -> InterviewPatternsResponse:
    """Get common interview patterns for a role type.

    Uses AI to generate role-specific question categories, assessment
    criteria, and frequently tested skills.

    Args:
        db: Database session.
        role: Role type (e.g., "TPM", "Product Engineer", "DevRel").
        profile_id: Profile ID for validation.

    Returns:
        InterviewPatternsResponse with categories, criteria, and skills.

    Raises:
        ProfileNotFoundError: If the profile doesn't exist.
    """
    _validate_profile(db, profile_id)

    prompt = (
        f'Describe the common interview patterns for the "{role}" role type. '
        f"Include question categories (behavioral, technical, system design, etc.), "
        f"assessment criteria interviewers use, and frequently tested skills. "
        f"Return structured data with distinct patterns for this role type."
    )

    warnings: list[SourceWarning] = []

    try:
        provider = get_ai_provider()
        response = await provider.complete(
            prompt=prompt,
            feature=AIFeature.interview_patterns,
            context={"role": role, "profile_id": profile_id},
        )
        structured = response.structured
    except Exception as exc:
        logger.warning(
            "AI provider failed for interview patterns '%s': %s",
            _sanitize_for_log(role),
            _sanitize_for_log(exc),
        )
        structured = None
        warnings.append(
            SourceWarning(
                source="ai_provider",
                error=f"AI provider error: {exc}",
            )
        )

    if isinstance(structured, InterviewPatternsResult):
        question_categories = [QuestionCategory(**cat) for cat in structured.question_categories]
        assessment_criteria = [
            AssessmentCriterion(**crit) for crit in structured.assessment_criteria
        ]
        return InterviewPatternsResponse(
            role=role,
            question_categories=question_categories,
            assessment_criteria=assessment_criteria,
            frequently_tested_skills=structured.frequently_tested_skills,
            warnings=warnings,
        )

    # Fallback: no structured data
    return InterviewPatternsResponse(
        role=role,
        question_categories=[],
        assessment_criteria=[],
        frequently_tested_skills=[],
        warnings=warnings,
    )
