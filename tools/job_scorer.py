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

import pandas as pd
import yaml

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
        "values": cfg.get("values", _DEFAULT_PROFILE["values"]),
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
    f"- Location: {_PROFILE['location']}. Remote EU/EMEA OK.\n"
    f"- Salary: {_PROFILE['salary_min']//1000}-{_PROFILE['salary_max']//1000}k {_PROFILE['salary_currency']} base\n"
    f"- Languages: {_PROFILE['languages']}\n"
    f"- Values: {', '.join(_PROFILE['values'])}\n\n"
    "TARGET DISTRIBUTION (enforce strictly):\n"
    "Out of every 100 jobs scored, the distribution MUST look like this:\n"
    "- Score 9-10: 1-2 jobs (truly exceptional -- all criteria met perfectly)\n"
    "- Score 7-8: 5-8 jobs (strong fits with minor gaps)\n"
    "- Score 5-6: 10-15 jobs (interesting but significant compromises)\n"
    "- Score 3-4: 30-40 jobs (most jobs land here -- mediocre or wrong focus)\n"
    "- Score 1-2: 40-50 jobs (clearly wrong field or level)\n"
    "Most jobs should score 3-5. Scores of 6+ should be RARE and reserved for roles "
    "with clear AI/ML focus, EU-compatible location, AND senior-level autonomy. "
    "When in doubt, score LOWER.\n\n"
    "SCORING CALIBRATION (follow EXACTLY):\n\n"
    "9-10 DREAM JOB (max 1-2 per 100 jobs):\n"
    "Must meet ALL of these -- no exceptions:\n"
    "  (a) AI-native company OR company with strong AI-first mandate\n"
    f"  (b) Exact role match: {', '.join(_PROFILE['target_roles'][:4])}\n"
    f"  (c) {_PROFILE['location']} or fully remote EU\n"
    f"  (d) {_PROFILE['salary_min']//1000}k+ {_PROFILE['salary_currency']} realistic salary\n"
    "  (e) High autonomy signals: small team, builder culture, ships product\n"
    f"  (f) Values alignment: {', '.join(_PROFILE['values'][:3])}\n"
    "Missing even ONE of (a)-(d) means it CANNOT be 9-10.\n\n"
    "7-8 STRONG FIT (max 5-8 per 100 jobs):\n"
    "Must meet at least 4 of these 5:\n"
    "  (a) AI/ML is central to the role or company\n"
    "  (b) Role type matches target roles\n"
    f"  (c) EU-compatible location ({_PROFILE['location']}, remote EU)\n"
    f"  (d) Salary {_PROFILE['salary_min']//1000}k+ {_PROFILE['salary_currency']} realistic\n"
    "  (e) Autonomy/builder signals in JD\n"
    "A role at a great company but in the wrong function is NOT 7-8.\n"
    "A perfect role type at a non-tech company is NOT 7-8.\n\n"
    "5-6 MAYBE (requires real tradeoffs):\n"
    "Has ONE strong positive but MULTIPLE gaps. Examples:\n"
    "  - Great company but role is process-heavy or not AI-focused\n"
    "  - Right role type but at a non-AI company, or company has weak tech culture\n"
    "  - AI focus exists but location is problematic (on-site non-EU)\n"
    "  - Interesting domain overlap but title is generic PM\n"
    "A generic 'Product Manager' at a tech company with no AI keywords = 5, not 6.\n"
    "Only give 6 if there are clear builder/AI signals beyond just being at a tech company.\n\n"
    "3-4 WEAK (this is where most jobs belong):\n"
    "  - Generic PM/TPM role with no AI/ML mention = 3-4\n"
    "  - Right seniority but wrong domain (insurance, logistics, banking without AI)\n"
    "  - 'Product Manager' with backlog management, stakeholder coordination, sprints = 3\n"
    "  - Good company but completely wrong function (e.g., data engineer, QA, pure ops)\n"
    "  - TPM role heavy on PMBOK/PMO/governance/status tracking = 3\n"
    "  - US-only on-site roles regardless of how good the company is = 3-4\n"
    "  - Non-tech companies even with 'PM' title = 3\n"
    "Score 4 only if there is at least one transferable aspect worth noting.\n\n"
    "1-2 NO FIT:\n"
    "  - Completely wrong field: sales, accounting, HR, legal, nursing, support, "
    "marketing-only, finance, construction, trades\n"
    "  - Junior/entry-level roles\n"
    "  - Roles requiring skills completely outside candidate's background\n\n"
    "CONCRETE EXAMPLES (use these as anchors):\n"
    "- 'Senior AI Product Manager' at AI-native company, remote EU = 9 (dream job)\n"
    "- 'DevRel Engineer' at open-source AI company, major EU city = 8 (right domain+location)\n"
    "- 'Product Engineer, AI Platform' at fintech startup, remote EU = 7 "
    "(right domain, right location, startup autonomy)\n"
    "- 'Senior Product Manager, Payments' at top fintech, hybrid = 5 "
    "(great company, but payments not AI, hybrid limits autonomy)\n"
    "- 'Product Manager' at insurance company, managing backlog = 3 "
    "(generic PM, no AI, no autonomy signals)\n"
    "- 'Technical Program Manager' at FAANG, US on-site = 4 "
    "(right role type but wrong location, likely bureaucratic at scale)\n"
    "- 'Project Manager' at consulting firm = 3 (process-heavy, no product ownership)\n"
    "- 'Backend Developer' at non-tech company = 3 (wrong function, no product angle)\n"
    "- 'Customer Success Manager' at SaaS = 2 (wrong function entirely)\n\n"
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
    "FINAL CHECK: Before returning your score, ask yourself: 'Would I confidently "
    "tell this candidate to spend 2 hours on this application?' If the answer is "
    "'maybe' or 'probably not', the score should be 5 or below.\n\n"
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



# --------------------------------------------------------------------------
# Hard caps -- post-scoring enforcement AFTER AI or fallback scoring
# --------------------------------------------------------------------------

# Each rule: (pattern_list, max_score, cap_name)
# Pattern matching is case-insensitive substring against job title.
HARD_CAP_RULES: list[tuple[list[str], int, str]] = [
    # Sales/finance/HR/legal/healthcare/support titles: MAX 1
    (
        [
            "sales", "account executive", "sdr", "bdr",
            "accountant", "accounting", "bookkeeper", "payroll",
            "tax ", "auditor", "treasury", "financial analyst",
            "fincrime", "financial crime",
            "hr specialist", "hr manager", "hr generalist", "recruiter",
            "talent acquisition", "people ops",
            "paralegal", "legal counsel", "compliance officer",
            "nurse", "nursing", "physician", "therapist", "pharmacist",
            "clinical",
            "customer support", "customer service", "help desk",
            "support analyst", "support specialist", "support technician",
        ],
        1,
        "sales_finance_hr_legal_healthcare_support",
    ),
    # Customer Success/Support titles: MAX 2
    (
        ["customer success", "client success"],
        2,
        "customer_success",
    ),
    # Marketing/media/SEO/CRM/content titles: MAX 2
    (
        [
            "marketing manager", "seo ", "seo specialist",
            "content writer", "copywriter", "social media",
            "content reviewer", "content moderator",
            "crm manager", "crm specialist",
            "media buyer", "media planner",
            "affiliate marketing", "marketing operations",
        ],
        2,
        "marketing_media_seo_crm",
    ),
    # Design/UX titles (no product): MAX 3
    # Allowlist: if title also contains "product", skip this cap
    (
        [
            "graphic designer", "visual designer", "ui designer",
            "ux designer", "ux researcher", "interaction designer",
            "motion designer", "brand designer",
        ],
        3,
        "design_ux_no_product",
    ),
    # Junior/entry-level: MAX 1
    (
        [
            "junior ", "entry level", "entry-level", "intern ",
            "internship", "werkstudent", "working student",
        ],
        1,
        "junior_entry_level",
    ),
    # DevOps/SRE (no AI/product): MAX 3
    (
        [
            "devops", "site reliability", "sre ",
            "infrastructure engineer", "platform engineer",
        ],
        3,
        "devops_sre_no_ai_product",
    ),
    # Pure backend/frontend engineer (no PM/product in title): MAX 4
    (
        [
            "backend engineer", "frontend engineer", "fullstack engineer",
            "full stack engineer", "full-stack engineer",
            "software engineer", "software developer",
            "web developer", "java developer", "python developer",
            ".net developer", "golang developer", "rust developer",
        ],
        4,
        "pure_engineer_no_product",
    ),
]

# Title keywords that exempt a job from certain caps
PRODUCT_KEYWORDS = [
    "product", "pm ", "tpm", "program manager",
    "devrel", "developer advocate", "developer relations",
]
AI_KEYWORDS = [
    "ai ", "ai/ml", "machine learning", "ml ",
    "artificial intelligence", "llm", "genai",
]


def apply_hard_caps(jobs: list[dict]) -> list[dict]:
    """
    Apply hard score caps AFTER AI or fallback scoring.

    This is a safety net that enforces maximum scores for job categories
    that are objectively poor fits, regardless of what the AI scored.

    Mutates and returns the same list of dicts. Each capped job gets:
        cap_applied: True
        cap_reason: "<rule_name>"
    """
    for job in jobs:
        title_lower = (job.get("title") or "").lower().strip()
        location_lower = (job.get("location") or "").lower().strip()
        current_score = job.get("fit_score", 0)

        if current_score <= 0:
            continue  # Already filtered or zero-scored

        has_product = any(kw in title_lower for kw in PRODUCT_KEYWORDS)
        has_ai = any(kw in title_lower for kw in AI_KEYWORDS)

        for patterns, max_score, cap_name in HARD_CAP_RULES:
            if current_score <= max_score:
                continue  # Already below cap

            matched = any(p in title_lower for p in patterns)
            if not matched:
                continue

            # Exemptions for certain cap categories
            if cap_name == "design_ux_no_product" and has_product:
                continue
            if cap_name == "devops_sre_no_ai_product" and (has_ai or has_product):
                continue
            if cap_name == "pure_engineer_no_product" and (has_product or has_ai):
                continue
            if cap_name == "junior_entry_level":
                # Don't cap if title also has senior/lead/staff
                senior_kws = [
                    "lead", "senior", "staff",
                    "principal", "head", "director",
                ]
                if any(kw in title_lower for kw in senior_kws):
                    continue

            # Apply cap
            job["fit_score"] = max_score
            job["cap_applied"] = True
            job["cap_reason"] = cap_name
            job["fit_reasoning"] = (
                f"Hard-capped from {current_score} to {max_score} ({cap_name}): "
                + (job.get("fit_reasoning") or "")
            )
            break  # Only apply the first (most restrictive) matching cap

        # US-only non-remote cap: MAX 3
        if current_score > 3 and not job.get("cap_applied"):
            is_remote = bool(job.get("remote", False))
            has_eu_signal = any(eu in location_lower for eu in EU_LOCATIONS)
            has_us_signal = any(
                us in location_lower for us in US_ONLY_LOCATIONS
            )
            if has_us_signal and not has_eu_signal and not is_remote:
                job["fit_score"] = 3
                job["cap_applied"] = True
                job["cap_reason"] = "us_only_non_remote"
                job["fit_reasoning"] = (
                    f"Hard-capped from {current_score} to 3 "
                    f"(us_only_non_remote): "
                    + (job.get("fit_reasoning") or "")
                )

    return jobs


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


if __name__ == "__main__":
    main()
