"""
Score scraped job listings against profile criteria using OpenAI.

Usage:
    export OPENAI_API_KEY=your_key
    python tools/job_scorer.py tracking/scraped_jobs_2026-02-22.csv

Reads scraped jobs CSV, scores each against the ideal role profile,
and writes results with fit_score and fit_reasoning columns.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import yaml

from career_os.services.geo.classifier import geo_eligibility as _geo_eligibility_engine
from career_os.services.geo.profile import GeoProfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# Profile loading -- reads from config/personal.yaml with generic defaults
# --------------------------------------------------------------------------

_DEFAULT_PROFILE = {
    "background_summary": "Senior engineer with 8+ years in tech",
    "target_roles": ["Senior Software Engineer", "Staff Engineer", "Engineering Manager"],
    "location": "Berlin, Germany",
    "salary_range": {"min": 80000, "max": 140000, "currency": "EUR"},
    "languages": "English (fluent)",
    "values": ["builder culture", "shipping over process"],
}


def _load_profile():
    """Load candidate profile from config/personal.yaml, falling back to defaults."""
    config_path = PROJECT_ROOT / "config" / "personal.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}
    return {
        "background_summary": cfg.get("background_summary", _DEFAULT_PROFILE["background_summary"]),
        "target_roles": cfg.get("target_roles", _DEFAULT_PROFILE["target_roles"]),
        "location": cfg.get("location", _DEFAULT_PROFILE["location"]),
        "salary_min": cfg.get("salary_range", _DEFAULT_PROFILE["salary_range"]).get("min", 80000),
        "salary_max": cfg.get("salary_range", _DEFAULT_PROFILE["salary_range"]).get("max", 140000),
        "salary_currency": cfg.get("salary_range", _DEFAULT_PROFILE["salary_range"]).get("currency", "EUR"),
        "languages": cfg.get("languages", _DEFAULT_PROFILE["languages"]),
    }


_PROFILE = _load_profile()

PROFILE_CRITERIA = f"""
Ideal candidate profile for job scoring:

MUST-HAVES (weight heavily):
- AI/ML focus or genuine openness to AI integration
- High autonomy and freedom to choose tools/approaches
- Strategic thinking valued over process compliance
- Complex problems, not administrative busywork
- Leadership or senior IC role

STRONG POSITIVES:
- Remote-friendly or {_PROFILE["location"]}-based
- Equity/RSU component
- Startup or scale-up environment
- Building things, not just reporting on them
- Cross-functional collaboration
- Innovation mandate with executive sponsorship

RED FLAGS (score down):
- Heavy PMBOK/PMO process language
- "Coordinate meetings" as primary responsibility
- No mention of AI or technology innovation
- Very rigid hierarchy descriptions
- "Must have 10+ years in [narrow specialty]"

SALARY & EFFORT CONTEXT:
- Target: {_PROFILE["salary_min"]//1000}-{_PROFILE["salary_max"]//1000}k {_PROFILE["salary_currency"]} base. Below {_PROFILE["salary_min"]*3//4//1000}k is a dealbreaker unless exceptional trajectory.
- Sweet spot: Staff/Lead at Series B-D (PMF achieved, reasonable hours, real equity).
- Green flags: "sustainable pace", "work-life balance", 4-day week, async-first.
- If salary not posted, estimate based on company stage, role level, and location.

SALARY SCORING:
- Include 'estimated_salary' (string, e.g. "110-130k EUR") in your response.
- Include 'effort_flag' (string: "sweet-spot", "moderate", "high-intensity", or "unknown") in your response.

PREPARATION TOUGHNESS:
- Include 'prep_level' (integer 1-5) estimating interview prep needed:
  1 = wing it (conversational, portfolio-based)
  2 = light prep (case study, system design chat, 1-2 days)
  3 = moderate (technical interviews, coding, 1-2 weeks prep)
  4 = heavy (leetcode, ML theory, deep domain, 2-4 weeks)
  5 = new domain (learn new language/stack/domain, months)
- Include 'prep_notes' (string, one sentence on what prep is needed).
"""

# --------------------------------------------------------------------------
# Shared AI scoring prompt -- used by both job_scorer.py and daily_pipeline.py
# --------------------------------------------------------------------------

SCORING_SYSTEM_PROMPT_BASE = (
    "You are an EXTREMELY strict job fit evaluator. You must be harsh -- most jobs "
    "do NOT fit this specific candidate. Your job is to save the candidate time by "
    "ruthlessly filtering out poor matches.\n\n"
    "THE CANDIDATE:\n"
    f"- {_PROFILE['background_summary']}\n"
    "- Building AI tools: LLM pipelines, MCP servers, agentic systems\n"
    f"- Target roles: {', '.join(_PROFILE['target_roles'])}\n"
    f"- Location: {_PROFILE['location']}. Remote EMEA OK.\n"
    f"- Salary: {_PROFILE['salary_min']//1000}-{_PROFILE['salary_max']//1000}k {_PROFILE['salary_currency']} base\n"
    f"- Languages: {_PROFILE['languages']}\n\n"
    "SCORING CALIBRATION (follow EXACTLY):\n"
    "- 9-10: DREAM JOB. Must meet ALL: (a) AI-native company or strong AI mandate, "
    f"(b) exact role match (TPM/PM/DevRel/Product Eng/AI Lead), (c) {_PROFILE['location']} or full "
    f"remote EU, (d) {_PROFILE['salary_min']//1000}k+ {_PROFILE['salary_currency']} realistic. Max 2-3 per 200 jobs.\n"
    "- 7-8: STRONG FIT. Right type of role (PM/TPM/DevRel/Product) at a good company. "
    f"Minor gaps like different city than {_PROFILE['location']}, or good company but role is slightly adjacent. "
    "Max 10-15 per 200.\n"
    "- 5-6: MAYBE. Interesting company but role is process-heavy, OR good role type but "
    "at a non-tech company. Requires compromise.\n"
    "- 3-4: WEAK. Wrong domain (pure backend, DevOps, QA, design) but some transferable "
    "skills. Or right domain but too junior/senior.\n"
    "- 1-2: NO FIT. Completely wrong field: sales, accounting, HR, legal, nursing, "
    "support, marketing-only, finance, construction, trades.\n\n"
    "HARD CAPS (override everything above):\n"
    "- Sales roles (SDR, AE, Account Exec, BDR): MAX 1\n"
    "- Accounting/Finance/Tax/Audit: MAX 1\n"
    "- HR/Recruiting/People Ops: MAX 1\n"
    "- Customer Support/Success (non-engineering): MAX 1\n"
    "- Legal/Compliance/AML/Regulatory: MAX 1\n"
    "- Healthcare/Nursing/Clinical: MAX 1\n"
    "- Marketing-only (no product): MAX 2\n"
    "- Pure backend/frontend engineer (no PM/TPM/product component): MAX 4\n"
    "- DevOps/SRE/Infra (no AI/product): MAX 3\n"
    "- Non-remote US-only: MAX 3\n"
    "- Roles outside EU that aren't remote: MAX 3\n"
    "- Junior/entry-level: MAX 1\n"
    "- Roles requiring fluency in French/Spanish/Portuguese/etc. (not EN/DE): MAX 3\n"
    "- Staffing agency generic postings: MAX 4\n"
    "- Roles with no AI/tech/product component: MAX 3\n\n"
    "IMPORTANT: If the job title alone tells you it's wrong (Accountant, Nurse, "
    "Sales Rep, HR Specialist), score 1 immediately. Do not overthink it.\n\n"
)

# job_scorer.py uses this directly (no review_flag)
SCORING_SYSTEM_PROMPT = (
    SCORING_SYSTEM_PROMPT_BASE + "Return ONLY valid JSON with double quotes: "
    '{"score": int, "reasoning": "one sentence", '
    '"estimated_salary": "110-130k EUR", '
    '"effort_flag": "sweet-spot|moderate|high-intensity|unknown", '
    '"prep_level": 1-5, "prep_notes": "one sentence"}. '
    "No markdown, no extra text."
)

# daily_pipeline.py adds review_flag for second-pass triage
SCORING_SYSTEM_PROMPT_WITH_REVIEW = (
    SCORING_SYSTEM_PROMPT_BASE + "SECOND-PASS FLAG:\n"
    "Set review_flag to true if score is 4-6 AND the role has an unusual angle "
    "that might fit (non-obvious role at a dream company, wildcard career move). "
    "For clear fits (7+) or clear misses (1-3), set review_flag to false.\n\n"
    "Return ONLY a JSON object with double quotes: "
    '{"score": int, "reasoning": "one sentence", '
    '"estimated_salary": "110-130k EUR", '
    '"effort_flag": "sweet-spot|moderate|high-intensity|unknown", '
    '"prep_level": 1-5, "prep_notes": "one sentence", '
    '"review_flag": true/false, "review_reason": "one sentence or empty"}. '
    "No markdown, no extra text."
)


# --------------------------------------------------------------------------
# Hard pre-filters -- skip roles BEFORE sending to AI
# --------------------------------------------------------------------------

# Titles that are an instant reject (case-insensitive substring match).
# These roles have zero relevance to TPM/PM/DevRel/Product Eng/AI.
REJECT_TITLE_PATTERNS: list[str] = [
    # Finance / Accounting
    "accountant",
    "accounting",
    "bookkeeper",
    "controller",
    "accounts payable",
    "accounts receivable",
    "payroll",
    "financial crimes",
    "financial analyst",
    "compensation analyst",
    "tax manager",
    "tax analyst",
    "auditor",
    "treasury",
    # Sales (non-engineering)
    "sales rep",
    "sales development rep",
    "sales associate",
    "account executive",
    "business development representative",
    "inside sales",
    "outside sales",
    "telesales",
    "business development director",
    "business development manager",
    # Customer support
    "customer support",
    "customer service",
    "customer success associate",
    "support specialist",
    "support technician",
    "help desk",
    "onboarding technician",
    # HR / People
    "hr specialist",
    "hr manager",
    "hr generalist",
    "recruiter",
    "talent acquisition",
    "benefits manager",
    "benefits administrator",
    "employee relations",
    "people operations",
    # Legal / Compliance
    "paralegal",
    "legal counsel",
    "compliance officer",
    "regulatory compliance",
    "ctf compliance",
    "global head of aml",
    # Healthcare / Medical
    "nurse",
    "nursing",
    "physician",
    "therapist",
    "pharmacist",
    "clinical trial",
    "pmhnp",
    "medical director",
    # Trades / Physical
    "driver",
    "warehouse",
    "mechanic",
    "electrician",
    "plumber",
    "construction",
    "forklift",
    "welder",
    "machinist",
    "technician senior",
    "network support technician",
    # Marketing (non-product)
    "affiliate marketing",
    "marketing operations",
    "seo specialist",
    "content writer",
    "copywriter",
    "social media manager",
    "growth manager",
    # Design (non-product)
    "graphic designer",
    "visual designer",
    "technical artist",
    # Food / Agriculture
    "food assurance",
    "food safety",
    # Other unrelated
    "salesforce developer",
    "salesforce administrator",
    "smart contract engineer",
    "crypto trader",
    "qa engineer",
    "quality assurance engineer",
    "buyer support",
    "head of support",
]

# Patterns that reject UNLESS title also contains a qualifying word.
# Prevents false positives like "Technical Account Manager" or "Product Marketing Manager".
REJECT_WITH_ALLOWLIST: dict[str, list[str]] = {
    "account manager": ["technical", "product", "solutions", "strategic", "engineering", "partner"],
    "marketing manager": ["product", "technical", "growth engineering", "developer", "platform"],
    "growth manager": ["product", "engineering", "platform"],
}

# Patterns requiring word-boundary matching (avoids "aml" matching inside other words)
REJECT_TITLE_REGEX: list[re.Pattern] = [
    re.compile(r"\baml\b", re.IGNORECASE),
]

# Blocked companies -- never score these.
BLOCKED_COMPANIES: list[str] = [
    "nebius",
    "yandex",
    # Big tech ad platforms (user preference)
    "google ads",
    "meta ads",
]

# Locations that are US-only signals -- cap score at 3 unless remote-EU.
US_ONLY_LOCATIONS: list[str] = [
    "united states",
    "new york",
    "san francisco",
    "los angeles",
    "chicago",
    "seattle",
    "austin",
    "boston",
    "denver",
    "atlanta",
    "miami",
    "dallas",
    "houston",
    "phoenix",
    "washington, dc",
    "san jose",
    "san diego",
]

# EU-compatible locations (no penalty)
EU_LOCATIONS: list[str] = [
    "germany",
    "deutschland",
    "frankfurt",
    "berlin",
    "munich",
    "hamburg",
    "cologne",
    "stuttgart",
    "dusseldorf",
    "mannheim",
    "wiesbaden",
    "remote",
    "emea",
    "europe",
    "eu",
    "france",
    "paris",
    "netherlands",
    "amsterdam",
    "spain",
    "barcelona",
    "ireland",
    "dublin",
    "portugal",
    "lisbon",
    "poland",
    "warsaw",
    "austria",
    "vienna",
    "switzerland",
    "zurich",
    "geneva",
    "uk",
    "london",
    "belgium",
    "brussels",
    "denmark",
    "copenhagen",
    "sweden",
    "stockholm",
    "finland",
    "helsinki",
    "norway",
    "oslo",
    "czech",
    "prague",
    "italy",
    "milan",
    "rome",
    "estonia",
    "tallinn",
    "ukraine",
    "kyiv",
    "dach",
    "brazil",  # some remote-ok roles list Brazil
]


def pre_filter_job(
    title: str, company: str, location: str, remote: bool = False
) -> tuple[bool, str, int | None]:
    """
    Check if a job should be rejected or score-capped before AI scoring.

    Returns:
        (should_skip, reason, max_score_cap)
        - should_skip=True means don't score at all, assign score=0
        - max_score_cap=None means no cap (proceed normally)
        - max_score_cap=N means score can't exceed N
    """
    title_lower = title.lower().strip()
    company_lower = company.lower().strip()
    location_lower = (location or "").lower().strip()

    # 1. Blocked companies
    for blocked in BLOCKED_COMPANIES:
        if blocked in company_lower:
            return True, f"Blocked company: {company}", None

    # 2. Reject by title (simple substring)
    for pattern in REJECT_TITLE_PATTERNS:
        if pattern in title_lower:
            return True, f"Rejected title pattern: '{pattern}' in '{title}'", None

    # 2b. Reject by title with allowlist (skip if qualifying word present)
    for pattern, allowlist in REJECT_WITH_ALLOWLIST.items():
        if pattern in title_lower:
            if not any(q in title_lower for q in allowlist):
                return True, f"Rejected title pattern: '{pattern}' in '{title}'", None

    # 2c. Reject by regex (word-boundary patterns)
    for rx in REJECT_TITLE_REGEX:
        if rx.search(title_lower):
            return True, f"Rejected title regex: '{rx.pattern}' in '{title}'", None

    # 3. Junior roles
    if any(
        kw in title_lower
        for kw in ["junior ", "intern ", "internship", "werkstudent", "working student"]
    ):
        if not any(
            kw in title_lower for kw in ["lead", "senior", "staff", "principal", "head", "director"]
        ):
            return True, f"Junior role: {title}", None

    # 4. US-only location cap (unless explicitly remote)
    if not remote and not any(eu in location_lower for eu in EU_LOCATIONS):
        for us_loc in US_ONLY_LOCATIONS:
            if us_loc in location_lower:
                return False, f"US-only location: {location}", 3

    return False, "", None


def score_job(
    client, title: str, company: str, description: str
) -> tuple[int, str, str, str, int, str]:
    """Score a single job posting. Returns (score, reasoning, salary, effort, prep_level, prep_notes)."""
    if not description or pd.isna(description):
        return 0, "No description available", "unknown", "unknown", 0, ""

    desc_truncated = description[:3000]

    response = client.chat.completions.create(
        model="anthropic/claude-sonnet-4.6",
        messages=[
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"CANDIDATE PROFILE:\n{PROFILE_CRITERIA}\n\nJOB POSTING:\nTitle: {title}\nCompany: {company}\nDescription: {desc_truncated}",
            },
        ],
        temperature=0.3,
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return (
            int(result["score"]),
            result["reasoning"],
            result.get("estimated_salary", "unknown"),
            result.get("effort_flag", "unknown"),
            int(result.get("prep_level", 0)),
            result.get("prep_notes", "unknown"),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Fallback to 2 (not 5) -- unknown jobs should not pass the filter
        return (
            2,
            f"Parse error: {response.choices[0].message.content[:100]}",
            "unknown",
            "unknown",
            0,
            "unknown",
        )


def main():
    parser = argparse.ArgumentParser(description="Score job listings against profile")
    parser.add_argument("csv_path", help="Path to scraped jobs CSV")
    parser.add_argument("--limit", type=int, help="Max jobs to score (for cost control)")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    from openai import OpenAI

    # Support OpenRouter keys (sk-or-*) by auto-detecting and setting base_url
    base_url = os.getenv("OPENAI_BASE_URL")
    if not base_url and api_key.startswith("sk-or-"):
        base_url = "https://openrouter.ai/api/v1"
    client = OpenAI(api_key=api_key, base_url=base_url)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    if args.limit:
        df = df.head(args.limit)

    print(f"Scoring {len(df)} jobs...")
    scores = []
    reasonings = []
    salaries = []
    efforts = []
    prep_levels = []
    prep_notes_list = []

    skipped = 0
    for i, row in df.iterrows():
        title = row.get("title", "Unknown")
        company = row.get("company", "Unknown")
        location = row.get("location", "")
        remote = bool(row.get("remote", False))
        description = row.get("description", "")

        # Pre-filter before AI scoring
        should_skip, reason, score_cap = pre_filter_job(title, company, location, remote)

        if should_skip:
            scores.append(0)
            reasonings.append(f"Pre-filtered: {reason}")
            salaries.append("unknown")
            efforts.append("unknown")
            prep_levels.append(0)
            prep_notes_list.append("")
            skipped += 1
            print(f"  [SKIP] {title} @ {company} -- {reason}")
            continue

        score, reasoning, salary, effort, prep, prep_note = score_job(
            client, title, company, description
        )

        # Apply score cap from pre-filter
        if score_cap is not None and score > score_cap:
            reasoning = f"Capped from {score} to {score_cap}: {reasoning}"
            score = score_cap

        scores.append(score)
        reasonings.append(reasoning)
        salaries.append(salary)
        efforts.append(effort)
        prep_levels.append(prep)
        prep_notes_list.append(prep_note)
        # CodeQL flags this as "clear-text logging of sensitive data" but these
        # are public job posting fields (title, company, salary range), not PII.
        print(
            f"  [{score}/10] {title} @ {company} ~{salary} [{effort}] prep:{prep}/5 -- {reasoning}"
        )

    df["fit_score"] = scores
    df["fit_reasoning"] = reasonings
    df["estimated_salary"] = salaries
    df["effort_flag"] = efforts
    df["prep_level"] = prep_levels
    df["prep_notes"] = prep_notes_list

    output_path = csv_path.with_stem(csv_path.stem + "_scored")
    df.to_csv(output_path, index=False)
    print(f"\nSkipped {skipped} jobs via pre-filter")
    print(f"Saved scored results to {output_path}")

    top = df.nlargest(10, "fit_score")
    print("\nTop 10 matches:")
    for _, row in top.iterrows():
        print(f"  [{row['fit_score']}/10] {row.get('title', '?')} @ {row.get('company', '?')}")


# ==========================================================================
# Geo-eligibility + API-submittable helpers (additive)
#
# These delegate the geo classification to tools/batch_probe.py's authoritative,
# home-parameterized gate rather than the legacy US_ONLY/EU_LOCATIONS lists
# above, and add an ATS-host check used to decide whether a role can be applied
# to via a structured ATS API. Tier/floor routing that consumes these lands in a
# follow-up slice.
# ==========================================================================

# Ensure tools/ is importable so the flat `from batch_probe import ...` resolves
# whether this module is run as a script or imported in a test that inserts
# tools/ onto sys.path.
_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# ATS sources whose applications can be driven through a structured API/board.
ATS_SUBMITTABLE_SOURCES: tuple[str, ...] = (
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "smartrecruiters",
    "personio",
)

# Host suffixes that identify a submittable ATS board.
_ATS_HOSTS: tuple[str, ...] = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
    "personio.de",
    "personio.com",
)


# Memoized default profile derived from the runtime geo config. The yaml is
# read once (batch_probe loads it at import time); the profile compiles once.
_GEO_PROFILE: GeoProfile | None = None


def _default_geo_profile() -> GeoProfile:
    """Build (once) a GeoProfile from the tools-side geo config.

    Reads batch_probe's already-loaded ``GeoConfig`` (the ``config/geo.yaml``
    -> ``config/geo.example.yaml`` chain, which parses exactly ``home_tokens``,
    ``allow_pan_region_remote`` and ``extra_foreign_tokens``) and converts it
    via :meth:`GeoProfile.from_home_tokens`. Only those three parsed values are
    passed through — the config file defines no other keys.
    """
    global _GEO_PROFILE
    if _GEO_PROFILE is None:
        import batch_probe

        cfg = batch_probe._CONFIG
        _GEO_PROFILE = GeoProfile.from_home_tokens(
            "geo-config",
            cfg.home_tokens,
            extra_foreign_tokens=cfg.extra_foreign_tokens,
            allow_pan_region_remote=cfg.allow_pan_region_remote,
        )
    return _GEO_PROFILE


def geo_eligibility(
    location: str | None,
    offices: list[str] | None = None,
    remote: bool = False,
    title: str = "",
    description: str = "",
    profile: GeoProfile | None = None,
) -> str:
    """Classify a role's geo eligibility for the configured home region.

    Delegates to the single geo authority,
    :func:`career_os.services.geo.classifier.geo_eligibility`. Authoritative
    ``offices`` override the (unreliable) ``location`` list string; ``remote``
    never rescues a foreign role on its own.

    When ``profile`` is None, a :class:`GeoProfile` is built lazily (and
    memoized) from the ``config/geo.yaml`` runtime config via batch_probe.

    Returns one of the 7 public classes: "home_local", "home_relocate",
    "eligible_remote", "visa_free_relocate", "visa_required_relocate",
    "foreign", "unknown". The "foreign" class is preserved verbatim so the
    ``geo == "foreign"`` consumer in tools/t3_lane.py keeps working unchanged.
    """
    if profile is None:
        profile = _default_geo_profile()
    return _geo_eligibility_engine(location, offices, remote, title, description, profile=profile)


def _is_ats_host(url: str | None) -> bool:
    """True if ``url`` is an https URL on a known submittable-ATS host."""
    if not url:
        return False
    parsed = urlparse(str(url).strip())
    if parsed.scheme != "https":
        return False
    host = parsed.netloc.lower().split(":")[0].removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in _ATS_HOSTS)


def is_api_submittable(job: dict) -> bool:
    """True if ``job`` can be applied to via a structured ATS API/board.

    A job qualifies when it names a known ATS ``source`` OR its ``url`` resolves
    to a validated https ATS host. The host check guards against non-ATS or
    non-https links masquerading as submittable.
    """
    source = str(job.get("source") or job.get("ats") or "").strip().lower()
    if source in ATS_SUBMITTABLE_SOURCES and _is_ats_host(job.get("url")):
        return True
    # No/unknown source but a valid ATS host URL still counts.
    return _is_ats_host(job.get("url"))


# --------------------------------------------------------------------------
# Dream-tier floor (never bury a top target on a sparse JD)
# --------------------------------------------------------------------------

# Top-tier targets that must never vanish from the digest because an empty/sparse
# JD made the AI under-score them. These are FICTIONAL example slugs -- replace the
# tuple (or load it from your own config) with the companies you never want buried.
DREAM_TIER_COMPANIES: tuple[str, ...] = (
    "zephyrx",
    "aspirational labs",
    "fictional ai systems",
    "sample target corp",
)
DREAM_TIER_FLOOR = 8

# Word-boundary match (not substring): short slugs are not distinctive enough for a
# substring match (it would floor "Nonlinear ..." or "Linear Technology"). Floored
# roles are review-flagged anyway, so a rare whole-word collision surfaces for human
# review rather than being silently applied.
_DREAM_TIER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(d) for d in DREAM_TIER_COMPANIES) + r")\b",
    re.IGNORECASE,
) if DREAM_TIER_COMPANIES else None


def is_dream_tier(company: str | None) -> bool:
    """True if ``company`` matches a configured dream-tier target (word-boundary)."""
    if _DREAM_TIER_RE is None:
        return False
    return bool(_DREAM_TIER_RE.search(company or ""))


def apply_floors(jobs: list[dict]) -> list[dict]:
    """Raise dream-tier company roles to a score floor so they are never buried.

    A dream-tier role that the AI under-scored is floored and flagged for review.
    Geo is respected: a geo-ineligible dream role is NOT floored into the digest but
    is force-flagged for review so it is never lost. A role a hard-cap deliberately
    buried (wrong function/sales/HR) is likewise not resurrected. Pre-filtered /
    blocked rows (score<=0) are never resurrected.
    """
    for job in jobs:
        if job.get("fit_score", 0) <= 0:
            continue  # pre-filtered / blocked -- do not resurrect
        if not is_dream_tier(job.get("company")):
            continue

        geo_foreign = job.get("geo_class") == "foreign"
        # A hard-cap (sales/HR/wrong-function) deliberately buried this role -- the
        # floor must NOT resurrect it. geo_ineligible caps are handled by the
        # geo_foreign branch below, not treated as a "wrong function" cap.
        wrong_function_cap = (
            bool(job.get("cap_applied")) and job.get("cap_reason") != "geo_ineligible"
        )

        if geo_foreign or wrong_function_cap:
            # Don't floor into the digest: geo-ineligible or deliberately buried by
            # function. Keep it visible in the review queue only -- never lost, never
            # promoted to a top gem.
            reason = "geo-ineligible" if geo_foreign else job.get("cap_reason")
            job["review_flag"] = True
            job.setdefault(
                "review_reason",
                f"Dream-tier company not auto-floored ({reason}, "
                f"{job.get('location', '')}) -- review",
            )
            continue

        if job.get("fit_score", 0) < DREAM_TIER_FLOOR:
            orig = job.get("fit_score", 0)
            job["fit_score"] = DREAM_TIER_FLOOR
            job["floor_applied"] = True
            job["review_flag"] = True
            job["review_reason"] = (
                f"Dream-tier company floored {orig}->{DREAM_TIER_FLOOR}; "
                "verify the role actually fits"
            )
            job["fit_reasoning"] = (
                f"Floored from {orig} to {DREAM_TIER_FLOOR} (dream-tier company): "
                + (job.get("fit_reasoning") or "")
            )
    return jobs


# --------------------------------------------------------------------------
# Tier classifier — routes each scored gem to its operating-model lane
# --------------------------------------------------------------------------

def classify_tier(job: dict) -> str | None:
    """Assign the tiered operating-model lane for a scored job.

    - T1 (dream / high-touch): dream-tier company, OR fit_score >= 8, OR a warm
      intro. These are written by hand.
    - T2 (strong / rapid-fire kit): fit_score 6-7.
    - T3 (volume / auto-fill + 1-click confirm): fit_score >= 5, geo-eligible, and
      on an auto-fillable ATS. The actual no-open-Q check happens in the T3 lane
      before anything is prefilled.
    - None: below the bar (or pre-filtered/blocked) -> not routed to any lane.

    Geo-foreign roles are typically score-capped low upstream, so they fall out
    naturally here (except dream companies, which stay T1 and are review-flagged by
    ``apply_floors``).
    """
    score = job.get("fit_score", 0) or 0
    if score <= 0:
        return None
    if is_dream_tier(job.get("company")) or score >= 8 or job.get("warm_intro"):
        return "T1"
    if score >= 6:
        return "T2"
    if score >= 5 and job.get("geo_class") != "foreign" and is_api_submittable(job):
        return "T3"
    return None


def assign_tiers(jobs: list[dict]) -> list[dict]:
    """Tag each job with its tier + auto_fillable flag (mutates in place)."""
    for job in jobs:
        tier = classify_tier(job)
        job["tier"] = tier
        job["auto_fillable"] = tier == "T3"
    return jobs


if __name__ == "__main__":
    main()
