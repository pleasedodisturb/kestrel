"""Rule-based JD red flag detection (#73).

Detects problematic signals in job postings without any AI cost. Each rule
is an independent private function returning zero or one flag dict.

A flag dict has the shape::

    {"flag_type": str, "severity": str, "description": str}

Severity scale (least to most serious)::

    info < caution < warning < dealbreaker

See ``tests/test_red_flags.py`` for per-rule expectations.
See ``tests/test_ghost_jobs.py`` for ghost-job detection expectations.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STALE_POSTING_DAYS = 60

# Mandated salary-transparency jurisdictions (keyword match on location).
_SALARY_MANDATE_KEYWORDS = (
    "colorado",
    " co,",
    " co ",
    "california",
    " ca,",
    " ca ",
    "washington",
    " wa,",
    " wa ",
    "new york",
    " ny,",
    " ny ",
    "connecticut",
    " ct,",
    " ct ",
)

_STAFFING_AGENCY_PATTERNS = (
    "staffing agency",
    "staffing firm",
    "staffing solutions",
    "recruiting agency",
    "on behalf of our client",
    "on behalf of a client",
    "contract-to-hire",
    "contract to hire",
    "zeitarbeit",
    "personalvermittlung",
)

_TURNOVER_PATTERNS = (
    "fast-paced environment",
    "fast paced environment",
    "wear many hats",
    "wears many hats",
    "many hats",
    "hit the ground running",
    "work hard play hard",
    "rockstar",
    "ninja",
)

_WORK_LIFE_PATTERNS = (
    "work-life balance",
    "work life balance",
    "flexible hours",
    "unlimited pto",
    "generous pto",
    "sustainable pace",
)

_VAGUE_BULLET_PATTERNS = (
    "assist with",
    "other duties as assigned",
    "help with",
    "support the team",
    "various tasks",
    "as needed",
)

# Liberal set of tech/skill tokens — used for the "excessive requirements" rule.
_SKILL_TOKEN_PATTERN = re.compile(
    r"""\b(
        python|java|javascript|typescript|ruby|go|golang|rust|scala|kotlin|swift|
        c\+\+|c#|\.net|php|perl|r|matlab|
        react|angular|vue|svelte|next\.?js|nuxt|redux|
        node\.?js|express|django|flask|fastapi|spring|rails|laravel|
        mysql|postgres(?:ql)?|mongodb|redis|elasticsearch|cassandra|dynamodb|sqlite|
        aws|gcp|azure|docker|kubernetes|k8s|terraform|ansible|jenkins|
        graphql|rest|grpc|kafka|rabbitmq|airflow|spark|hadoop|
        git|linux|bash|nginx|apache|
        html|css|sass|tailwind|webpack|vite
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)

_YEARS_REQUIREMENT_PATTERN = re.compile(r"(\d{2})\s*\+?\s*(?:years|yrs)", re.IGNORECASE)

_JUNIOR_TITLE_PATTERNS = (
    "junior",
    "jr.",
    "jr ",
    "associate",
    "entry level",
    "entry-level",
    "mid-level",
    "mid level",
    "intern",
)

# ---------------------------------------------------------------------------
# Ghost job detection constants
# ---------------------------------------------------------------------------

# Seniority/level prefixes and suffixes to strip when normalizing titles.
_TITLE_LEVEL_TOKENS = re.compile(
    r"\b(senior|sr\.?|junior|jr\.?|lead|principal|staff|associate|assoc\.?|"
    r"entry.?level|mid.?level|intern|contract|temp|remote|hybrid)\b",
    re.IGNORECASE,
)

# Legal suffixes to strip when normalizing company names.
_COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b(inc\.?|llc\.?|ltd\.?|gmbh|ag|corp\.?|co\.?|plc|bv|sa|sas|nv|oy|ab|as)\b\.?",
    re.IGNORECASE,
)

# Minimum description prefix length (chars) for multi-city blast comparison.
_DESC_PREFIX_LEN = 200

# Ghost job occurrence thresholds.
_GHOST_CAUTION_THRESHOLD = 3
_GHOST_WARNING_THRESHOLD = 5

# Multi-city blast threshold.
_MULTI_CITY_BLAST_THRESHOLD = 3

# Window for ghost job lookback (days).
_GHOST_LOOKBACK_DAYS = 90


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------


def _flag(flag_type: str, severity: str, description: str) -> dict[str, str]:
    return {"flag_type": flag_type, "severity": severity, "description": description}


def _detect_stale_posting(posted_at: datetime | None) -> dict[str, str] | None:
    if posted_at is None:
        return None
    # Normalize to UTC for the comparison.
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    age = datetime.now(UTC) - posted_at
    if age > timedelta(days=_STALE_POSTING_DAYS):
        days = age.days
        return _flag(
            "stale_posting",
            "warning",
            f"Posting is {days} days old — role may be filled or abandoned.",
        )
    return None


def _detect_unrealistic_requirements(
    description: str,
    title: str | None,
) -> dict[str, str] | None:
    # Rule A: "10+ years" alongside a junior/mid title.
    years_match = _YEARS_REQUIREMENT_PATTERN.search(description)
    high_years = False
    if years_match:
        try:
            if int(years_match.group(1)) >= 10:
                high_years = True
        except ValueError:
            pass

    title_is_junior = False
    if title:
        lowered_title = title.lower()
        if any(p in lowered_title for p in _JUNIOR_TITLE_PATTERNS):
            title_is_junior = True

    if high_years and title_is_junior:
        return _flag(
            "unrealistic_requirements",
            "warning",
            "Junior/mid title paired with 10+ years of experience required.",
        )

    # Rule B: >15 distinct skill tokens in the description.
    distinct_skills = {m.group(0).lower() for m in _SKILL_TOKEN_PATTERN.finditer(description)}
    if len(distinct_skills) > 15:
        return _flag(
            "unrealistic_requirements",
            "warning",
            f"{len(distinct_skills)} distinct technical skills required — "
            "unrealistic expectations.",
        )
    return None


def _detect_turnover_language(description: str) -> dict[str, str] | None:
    lowered = description.lower()
    turnover_hits = sum(1 for p in _TURNOVER_PATTERNS if p in lowered)
    work_life_hits = sum(1 for p in _WORK_LIFE_PATTERNS if p in lowered)
    if turnover_hits >= 2 and work_life_hits == 0:
        return _flag(
            "turnover_language",
            "info",
            "Language suggests high-intensity culture with no work-life mentions.",
        )
    return None


def _detect_missing_salary(
    salary_range: str | None,
    location: str | None,
) -> dict[str, str] | None:
    if salary_range:
        return None
    if not location:
        return None
    lowered_loc = f" {location.lower()} "
    in_mandate_state = any(kw in lowered_loc for kw in _SALARY_MANDATE_KEYWORDS)
    if in_mandate_state:
        return _flag(
            "missing_salary",
            "warning",
            "Salary range missing despite pay-transparency mandate in this location.",
        )
    return None


def _detect_staffing_agency(
    description: str,
    title: str | None,
) -> dict[str, str] | None:
    haystack = description.lower()
    if title:
        haystack = f"{title.lower()} {haystack}"
    for pattern in _STAFFING_AGENCY_PATTERNS:
        if pattern in haystack:
            return _flag(
                "staffing_agency",
                "caution",
                "Role appears to be via a staffing agency or contract-to-hire.",
            )
    return None


def _detect_vague_responsibilities(description: str) -> dict[str, str] | None:
    if len(description) < 200:
        return _flag(
            "vague_responsibilities",
            "info",
            f"Description is only {len(description)} characters — vague role expectations.",
        )
    lowered = description.lower()
    vague_hits = sum(1 for p in _VAGUE_BULLET_PATTERNS if p in lowered)
    # Rough bullet-count via newline/dash boundary detection.
    approximate_bullets = max(
        len(
            [line for line in description.splitlines() if line.strip().startswith(("-", "*", "•"))]
        ),
        1,
    )
    if approximate_bullets >= 4 and vague_hits / approximate_bullets > 0.5:
        return _flag(
            "vague_responsibilities",
            "info",
            "More than half of bullets use generic phrases like 'assist with' or "
            "'other duties as assigned'.",
        )
    return None


def _detect_excessive_requirements(description: str) -> dict[str, str] | None:
    distinct_skills = {m.group(0).lower() for m in _SKILL_TOKEN_PATTERN.finditer(description)}
    if len(distinct_skills) > 15:
        return _flag(
            "excessive_requirements",
            "warning",
            f"Lists {len(distinct_skills)} distinct technologies/skills as required.",
        )
    return None


# ---------------------------------------------------------------------------
# Ghost job detection helpers
# ---------------------------------------------------------------------------


def normalize_job_title(title: str) -> str:
    """Strip seniority tokens and normalize whitespace/case for title matching.

    Examples:
        "Senior Software Engineer" -> "software engineer"
        "Sr. Software Engineer" -> "software engineer"
        "Software Engineer (Senior)" -> "software engineer"
        "Lead Backend Developer" -> "backend developer"
    """
    # Remove parenthesized qualifiers like "(Senior)" or "(Contract)"
    cleaned = re.sub(r"\([^)]*\)", " ", title)
    # Strip seniority/level tokens (including optional trailing period for abbreviations)
    cleaned = _TITLE_LEVEL_TOKENS.sub(" ", cleaned)
    # Remove stray punctuation left behind by abbreviation stripping (e.g. "Sr." -> ".")
    cleaned = re.sub(r"[.\-/]", " ", cleaned)
    # Collapse whitespace and lowercase
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def normalize_company_name(company: str) -> str:
    """Strip common legal suffixes and normalize case/punctuation for company matching.

    Examples:
        "Google LLC" -> "google"
        "Alphabet Inc." -> "alphabet"
        "ACME Corp" -> "acme"
    """
    # Remove legal suffixes
    cleaned = _COMPANY_SUFFIX_PATTERN.sub(" ", company)
    # Strip trailing punctuation (commas, periods)
    cleaned = re.sub(r"[,.]", " ", cleaned)
    # Collapse whitespace and lowercase
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _count_company_title_occurrences(
    db: Session,
    company: str,
    title: str,
    profile_id: int,
    days: int = _GHOST_LOOKBACK_DAYS,
) -> int:
    """Count how many times a normalized company+title pair appears in discovered_jobs.

    Uses indexed columns (company_normalized, title_normalized, profile_id) for
    performance. The window is ``days`` days looking back from now.
    """
    from career_os.models.discovery import DiscoveredJob

    norm_company = normalize_company_name(company)
    norm_title = normalize_job_title(title)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    return (
        db.query(DiscoveredJob)
        .filter(
            DiscoveredJob.profile_id == profile_id,
            DiscoveredJob.company_normalized == norm_company,
            DiscoveredJob.title_normalized == norm_title,
            DiscoveredJob.created_at >= cutoff,
        )
        .count()
    )


def _detect_ghost_job_signals(
    db: Session,
    company: str,
    title: str,
    profile_id: int,
) -> dict[str, str] | None:
    """Detect ghost job patterns by counting repeated company+title occurrences.

    A job is considered a ghost posting signal when the same normalized
    company+title pair appears multiple times in the discovery history within
    the past 90 days -- indicating the role is never filled or is used for
    talent pipeline / make-employees-nervous purposes.

    Thresholds:
        >=3 occurrences -> "caution"
        >=5 occurrences -> "warning"
    """
    count = _count_company_title_occurrences(db, company, title, profile_id)

    if count >= _GHOST_WARNING_THRESHOLD:
        return _flag(
            "ghost_job",
            "warning",
            f"This {company} role has appeared {count} times in the last "
            f"{_GHOST_LOOKBACK_DAYS} days -- strong ghost job signal.",
        )
    if count >= _GHOST_CAUTION_THRESHOLD:
        return _flag(
            "ghost_job",
            "caution",
            f"This {company} role has appeared {count} times in the last "
            f"{_GHOST_LOOKBACK_DAYS} days -- may be a ghost posting.",
        )
    return None


def _detect_multi_city_blast(
    db: Session,
    company: str,
    description: str,
    profile_id: int,
) -> dict[str, str] | None:
    """Detect 'spray and pray' postings: same company+description across 3+ locations.

    Uses the first 200 characters of the stripped description as a fingerprint.
    This catches copy-pasted JDs posted to many cities simultaneously without
    requiring expensive similarity calculations.

    Severity: "info" -- it is not necessarily bad, but worth noting.
    """
    from career_os.models.discovery import DiscoveredJob

    norm_company = normalize_company_name(company)
    desc_prefix = description.strip()[:_DESC_PREFIX_LEN]
    if not desc_prefix:
        return None

    cutoff = datetime.now(UTC) - timedelta(days=_GHOST_LOOKBACK_DAYS)

    # Fetch all jobs for this company within the window
    candidates = (
        db.query(DiscoveredJob.location, DiscoveredJob.description)
        .filter(
            DiscoveredJob.profile_id == profile_id,
            DiscoveredJob.company_normalized == norm_company,
            DiscoveredJob.created_at >= cutoff,
            DiscoveredJob.description.isnot(None),
        )
        .all()
    )

    # Find distinct locations where the description prefix matches
    matching_locations: set[str] = set()
    for loc, desc in candidates:
        if desc and desc.strip()[:_DESC_PREFIX_LEN] == desc_prefix:
            matching_locations.add(loc)

    if len(matching_locations) >= _MULTI_CITY_BLAST_THRESHOLD:
        return _flag(
            "multi_city_blast",
            "info",
            f"{company} posted this same role across {len(matching_locations)} locations "
            f"-- may indicate a spray-and-pray hiring pattern.",
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_red_flags(
    job_description: str | None,
    *,
    posted_at: datetime | None = None,
    title: str | None = None,
    salary_range: str | None = None,
    location: str | None = None,
) -> list[dict[str, str]]:
    """Run all rule-based red-flag rules and return any flags found.

    Stateless rules only -- no DB access. For data-driven ghost job detection,
    call ``detect_data_driven_red_flags()`` separately and merge the results.

    Returns an empty list when ``job_description`` is ``None`` or empty.
    Each rule is independent and failures in one never affect the others.
    """
    if not job_description:
        return []

    flags: list[dict[str, str]] = []

    stale = _detect_stale_posting(posted_at)
    if stale:
        flags.append(stale)

    unrealistic = _detect_unrealistic_requirements(job_description, title)
    if unrealistic:
        flags.append(unrealistic)

    turnover = _detect_turnover_language(job_description)
    if turnover:
        flags.append(turnover)

    salary = _detect_missing_salary(salary_range, location)
    if salary:
        flags.append(salary)

    staffing = _detect_staffing_agency(job_description, title)
    if staffing:
        flags.append(staffing)

    vague = _detect_vague_responsibilities(job_description)
    if vague:
        flags.append(vague)

    # Only emit excessive_requirements if unrealistic_requirements didn't
    # already capture the same "too many skills" signal.
    if not unrealistic or unrealistic.get("flag_type") != "unrealistic_requirements":
        excessive = _detect_excessive_requirements(job_description)
        if excessive:
            flags.append(excessive)

    return flags


def detect_data_driven_red_flags(
    db: Session,
    company: str,
    title: str,
    description: str,
    profile_id: int,
) -> list[dict[str, str]]:
    """Run data-driven red-flag rules that require DB access.

    Complements the stateless ``detect_red_flags()`` function with rules that
    query historical discovery data to detect ghost jobs and spray-and-pray
    posting patterns.

    Callers should merge the results with those from ``detect_red_flags()``.
    """
    flags: list[dict[str, str]] = []

    ghost = _detect_ghost_job_signals(db, company, title, profile_id)
    if ghost:
        flags.append(ghost)

    blast = _detect_multi_city_blast(db, company, description, profile_id)
    if blast:
        flags.append(blast)

    return flags
