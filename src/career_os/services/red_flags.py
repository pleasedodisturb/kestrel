"""Rule-based JD red flag detection (#73).

Detects problematic signals in job postings without any AI cost. Each rule
is an independent private function returning zero or one flag dict.

A flag dict has the shape::

    {"flag_type": str, "severity": str, "description": str}

Severity scale (least to most serious)::

    info < caution < warning < dealbreaker

See ``tests/test_red_flags.py`` for per-rule expectations.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

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
    """Run all red-flag rules and return any flags found.

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
