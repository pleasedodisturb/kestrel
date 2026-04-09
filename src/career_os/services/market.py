"""Market Intelligence service — salary trends, skill demand, hiring patterns,
market positioning, and dream company opportunity radar.

All queries are profile-scoped through discovered_jobs.profile_id.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile
from career_os.models.skills import Skill
from career_os.services.salary import parse_salary_range as _shared_parse_salary_range

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _validate_profile(db: Session, profile_id: int) -> Profile:
    """Validate that a profile exists, raising 404-appropriate error if not."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")
    return profile


def _get_last_refreshed_at(profile: Profile) -> str | None:
    """Get the persisted last_refreshed_at timestamp, or None if never refreshed."""
    if profile.last_market_refreshed_at:
        ts = profile.last_market_refreshed_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.isoformat()
    return None


def _get_discovered_jobs(db: Session, profile_id: int) -> list[DiscoveredJob]:
    """Get all discovered jobs for a profile."""
    return db.query(DiscoveredJob).filter(DiscoveredJob.profile_id == profile_id).all()


# ---------------------------------------------------------------------------
# Salary parsing
# ---------------------------------------------------------------------------


def _parse_salary_range(salary_str: str | None) -> tuple[float | None, float | None]:
    """Extract (low, high) salary values from a salary range string.

    Delegates to the shared salary parser in career_os.services.salary.
    """
    return _shared_parse_salary_range(salary_str)


def _midpoint(low: float | None, high: float | None) -> float | None:
    """Compute midpoint of a salary range."""
    if low is None or high is None:
        return None
    return (low + high) / 2


# ---------------------------------------------------------------------------
# Skill extraction from job descriptions
# ---------------------------------------------------------------------------

# Common technical/domain skills to look for in job descriptions
_KNOWN_SKILLS = [
    "Python",
    "TypeScript",
    "JavaScript",
    "React",
    "Node.js",
    "AWS",
    "Kubernetes",
    "Docker",
    "Agile",
    "Scrum",
    "Program Management",
    "Stakeholder Management",
    "System Design",
    "ML",
    "Machine Learning",
    "AI",
    "Artificial Intelligence",
    "SQL",
    "GraphQL",
    "APIs",
    "Technical Writing",
    "Community Management",
    "CUDA",
    "TensorFlow",
    "PyTorch",
    "Java",
    "Go",
    "Rust",
    "C++",
    "DevOps",
    "CI/CD",
    "Terraform",
    "Data Engineering",
    "Data Science",
    "Product Management",
    "Figma",
    "Analytics",
    "Monitoring",
    "Observability",
]


def _extract_skills_from_text(text: str | None) -> list[str]:
    """Extract known skills from job description text (case-insensitive)."""
    if not text:
        return []

    text_lower = text.lower()
    found: list[str] = []
    for skill in _KNOWN_SKILLS:
        # Use word boundary for short terms to avoid false positives
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


# ---------------------------------------------------------------------------
# Role type normalization
# ---------------------------------------------------------------------------


def _normalize_role_type(title: str) -> str:
    """Normalize job title to a role type bucket.

    Groups similar titles: "Senior TPM", "Staff TPM" → "TPM",
    "Product Engineer", "Frontend Engineer" → "Engineer", etc.
    """
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
# VAL-MARKET-001: Salary Trends
# ---------------------------------------------------------------------------


def _filter_jobs_by_role_location(
    jobs: list[DiscoveredJob],
    role: str | None,
    location: str | None,
) -> list[DiscoveredJob]:
    """Filter discovered jobs by optional role and location substrings."""
    if role:
        role_lower = role.lower()
        jobs = [j for j in jobs if role_lower in j.title.lower()]

    if location:
        loc_lower = location.lower()
        jobs = [j for j in jobs if loc_lower in j.location.lower()]

    return jobs


def _group_by_period(
    jobs: list[DiscoveredJob],
) -> dict[tuple[str, str, str], list[float]]:
    """Group jobs by (role_type, normalized_location, period_month) with salary midpoints.

    Uses posted_at if available, otherwise created_at for the period bucket.
    Jobs without a parseable salary range are skipped.
    """
    role_loc_period_salaries: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for job in jobs:
        low, high = _parse_salary_range(job.salary_range)
        mid = _midpoint(low, high)
        if mid is None:
            continue
        role_type = _normalize_role_type(job.title)
        norm_location = (job.location or "").strip() or "Unknown"
        ts = job.posted_at or job.created_at
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        period = ts.strftime("%Y-%m") if ts else datetime.now(UTC).strftime("%Y-%m")
        role_loc_period_salaries[(role_type, norm_location, period)].append(mid)
    return role_loc_period_salaries


def _compute_period_stats(salaries: list[float]) -> dict:
    """Compute p25, median, and p75 percentiles for a list of salary values.

    Assumes *salaries* is non-empty.
    """
    salaries.sort()
    n = len(salaries)
    p25_idx = max(0, int(n * 0.25) - 1)
    median_idx = n // 2
    p75_idx = min(n - 1, int(n * 0.75))
    return {
        "median": salaries[median_idx],
        "p25": salaries[p25_idx],
        "p75": salaries[p75_idx],
        "sample_size": n,
    }


def get_salary_trends(
    db: Session,
    profile_id: int,
    *,
    role: str | None = None,
    location: str | None = None,
) -> dict:
    """Compute salary trends by role type with month-based bucketing.

    Returns aggregated salary percentiles (p25, median, p75), sample sizes,
    and period (YYYY-MM), grouped by role type and month.
    Optionally filtered by role substring and location.
    """
    profile = _validate_profile(db, profile_id)
    refreshed_at = _get_last_refreshed_at(profile)

    jobs = _get_discovered_jobs(db, profile_id)
    if not jobs:
        return {"trends": [], "last_refreshed_at": refreshed_at}

    jobs = _filter_jobs_by_role_location(jobs, role, location)
    if not jobs:
        return {"trends": [], "last_refreshed_at": refreshed_at}

    role_loc_period_salaries = _group_by_period(jobs)

    trends = []
    for (role_type, norm_loc, period), salaries in sorted(role_loc_period_salaries.items()):
        if not salaries:
            continue
        stats = _compute_period_stats(salaries)
        trends.append(
            {
                "role": role_type,
                "location": norm_loc,
                "period": period,
                **stats,
            }
        )

    return {
        "trends": trends,
        "last_refreshed_at": refreshed_at,
    }


# ---------------------------------------------------------------------------
# VAL-MARKET-002: Skill Demand Trends
# ---------------------------------------------------------------------------


def get_skill_trends(db: Session, profile_id: int) -> dict:
    """Compute skill demand trends from discovered job descriptions.

    Returns skills ranked by mention count with trend direction and
    percentage of postings.
    """
    profile = _validate_profile(db, profile_id)
    refreshed_at = _get_last_refreshed_at(profile)

    jobs = _get_discovered_jobs(db, profile_id)
    if not jobs:
        return {
            "skills": [],
            "total_postings_analyzed": 0,
            "last_refreshed_at": refreshed_at,
        }

    total_postings = len(jobs)
    skill_counts: Counter[str] = Counter()

    for job in jobs:
        found = _extract_skills_from_text(job.description)
        for skill_name in found:
            skill_counts[skill_name] += 1

    # Build ranked list
    skills_list = []
    for skill_name, count in skill_counts.most_common():
        pct = round((count / total_postings) * 100, 1)
        # Simple trend direction: if mentioned in > 50% of postings → "up"
        # In 25-50% → "stable", < 25% → "down"
        if pct >= 50:
            trend = "up"
        elif pct >= 25:
            trend = "stable"
        else:
            trend = "down"

        skills_list.append(
            {
                "skill_name": skill_name,
                "mention_count": count,
                "trend_direction": trend,
                "percentage_of_postings": pct,
            }
        )

    return {
        "skills": skills_list,
        "total_postings_analyzed": total_postings,
        "last_refreshed_at": refreshed_at,
    }


# ---------------------------------------------------------------------------
# VAL-MARKET-003: Company Hiring Patterns
# ---------------------------------------------------------------------------


def get_hiring_patterns(db: Session, profile_id: int) -> dict:
    """Compute company hiring patterns from discovered jobs.

    Returns active companies with posting counts, velocity (per week),
    and trending roles.
    """
    profile = _validate_profile(db, profile_id)
    refreshed_at = _get_last_refreshed_at(profile)

    jobs = _get_discovered_jobs(db, profile_id)
    if not jobs:
        return {
            "companies": [],
            "last_refreshed_at": refreshed_at,
        }

    # Group by company
    company_jobs: dict[str, list[DiscoveredJob]] = defaultdict(list)
    for job in jobs:
        company_jobs[job.company].append(job)

    now = datetime.now(UTC)
    companies_list = []
    for company_name, co_jobs in company_jobs.items():
        # Posting velocity: postings per week over last 30 days
        recent_cutoff = now - timedelta(days=30)
        recent_jobs = [
            j for j in co_jobs if j.posted_at and j.posted_at.replace(tzinfo=UTC) >= recent_cutoff
        ]
        weeks = 4.0  # 30 days ≈ 4 weeks
        if recent_jobs:
            velocity = round(len(recent_jobs) / weeks, 2)
        else:
            velocity = round(len(co_jobs) / weeks, 2)

        # Unique roles
        roles = list({j.title for j in co_jobs})

        companies_list.append(
            {
                "company": company_name,
                "active_postings_count": len(co_jobs),
                "posting_velocity": velocity,
                "roles_trending": roles,
            }
        )

    # Sort by active_postings_count descending
    companies_list.sort(key=lambda c: c["active_postings_count"], reverse=True)

    return {
        "companies": companies_list,
        "last_refreshed_at": refreshed_at,
    }


# ---------------------------------------------------------------------------
# VAL-MARKET-004: Market Positioning
# ---------------------------------------------------------------------------


def _compute_role_match(
    role_jobs: list[DiscoveredJob],
    user_skills: set[str],
) -> float:
    """Compute the skill-match percentage for a set of jobs against user skills.

    *user_skills* should be a set of **lowercased** skill names.
    Returns 0.0 when no skills are required across the jobs.
    """
    total_skills_required = 0
    skills_matched = 0

    for job in role_jobs:
        job_skills = _extract_skills_from_text(job.description)
        total_skills_required += len(job_skills)
        for skill_name in job_skills:
            if skill_name.lower() in user_skills:
                skills_matched += 1

    if total_skills_required == 0:
        return 0.0
    return round((skills_matched / total_skills_required) * 100, 1)


def get_market_positioning(db: Session, profile_id: int) -> dict:
    """Compute profile match percentages by role type.

    Compares user's skills against skills extracted from discovered job
    descriptions, grouped by normalized role type.
    """
    profile = _validate_profile(db, profile_id)
    refreshed_at = _get_last_refreshed_at(profile)

    jobs = _get_discovered_jobs(db, profile_id)
    if not jobs:
        return {
            "positions": [],
            "last_refreshed_at": refreshed_at,
        }

    # Get user's skills
    user_skills_rows = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    user_skill_names = {s.name.lower() for s in user_skills_rows}

    # Group jobs by role type
    role_groups: dict[str, list[DiscoveredJob]] = defaultdict(list)
    for job in jobs:
        role_type = _normalize_role_type(job.title)
        role_groups[role_type].append(job)

    positions = []
    for role_type, role_jobs in sorted(role_groups.items()):
        match_pct = _compute_role_match(role_jobs, user_skill_names)
        positions.append(
            {
                "role_type": role_type,
                "match_percentage": match_pct,
                "total_roles_analyzed": len(role_jobs),
            }
        )

    return {
        "positions": positions,
        "last_refreshed_at": refreshed_at,
    }


# ---------------------------------------------------------------------------
# VAL-MARKET-005: Dream Company Opportunity Radar
# ---------------------------------------------------------------------------


def get_opportunity_radar(
    db: Session,
    profile_id: int,
    *,
    dream_companies: list[str] | None = None,
) -> dict:
    """Find opportunities at dream companies.

    Returns discovered jobs from dream-tier companies, each flagged with
    priority: "dream" and alert: True.
    """
    profile = _validate_profile(db, profile_id)
    refreshed_at = _get_last_refreshed_at(profile)

    if not dream_companies:
        return {
            "opportunities": [],
            "dream_companies": [],
            "last_refreshed_at": refreshed_at,
        }

    # Normalize dream company names for matching
    dream_lower = {name.strip().lower() for name in dream_companies}

    jobs = _get_discovered_jobs(db, profile_id)
    opportunities = []
    for job in jobs:
        if job.company.strip().lower() in dream_lower:
            opportunities.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "url": job.url,
                    "fit_score": job.fit_score,
                    "salary_range": job.salary_range,
                    "priority": "dream",
                    "alert": True,
                    "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                }
            )

    # Sort by fit_score descending (best opportunities first)
    opportunities.sort(key=lambda o: o.get("fit_score") or 0, reverse=True)

    return {
        "opportunities": opportunities,
        "dream_companies": dream_companies,
        "last_refreshed_at": refreshed_at,
    }


# ---------------------------------------------------------------------------
# VAL-MARKET-006: Refresh / auto-update
# ---------------------------------------------------------------------------


def refresh_market_data(db: Session, profile_id: int) -> dict:
    """Trigger a refresh of market intelligence data.

    Persists the last_refreshed_at timestamp on the profile.
    In a production system, this might recompute cached aggregations.
    For now, all our queries are computed live, so this mainly
    serves to update the last_refreshed_at timestamp and could be
    called after each discovery sweep.
    """
    profile = _validate_profile(db, profile_id)

    jobs = _get_discovered_jobs(db, profile_id)

    # Count unique role types with salary data
    salary_count = sum(1 for j in jobs if _parse_salary_range(j.salary_range)[0] is not None)

    # Count unique skills extracted
    all_skills: set[str] = set()
    for job in jobs:
        found = _extract_skills_from_text(job.description)
        all_skills.update(found)

    # Count unique companies
    companies = {j.company for j in jobs}

    # Persist the refresh timestamp on the profile
    now = datetime.now(UTC)
    profile.last_market_refreshed_at = now
    db.commit()

    return {
        "last_refreshed_at": now.isoformat(),
        "salary_trends_count": salary_count,
        "skill_trends_count": len(all_skills),
        "companies_analyzed": len(companies),
    }
