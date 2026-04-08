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

PROFILE_CRITERIA = """
Ideal candidate profile for job scoring:

MUST-HAVES (weight heavily):
- AI/ML focus or genuine openness to AI integration
- High autonomy and freedom to choose tools/approaches
- Strategic thinking valued over process compliance
- Complex problems, not administrative busywork
- Leadership or senior IC role

STRONG POSITIVES:
- Remote-friendly or Frankfurt-based
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
- Target: 120-160k EUR base. Below 100k is a dealbreaker unless exceptional trajectory.
- Sweet spot: Staff/Lead at Series B-D (100-140k base, PMF achieved, reasonable hours, real equity).
- Caution: Director+ at hypergrowth companies (Delivery Hero, HelloFresh) -- intense culture.
- Caution: Founding roles at pre-seed/seed -- equity lottery + 60hr weeks.
- Green flags: "sustainable pace", "work-life balance", 4-day week, async-first.
- Germany market bands: Senior 80-110k, Staff/Lead 100-140k, Director 120-160k.
- Remote-first international companies pay 15-30% above local German market.
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
    "- Senior TPM/Product Manager with 10+ years at Amazon (Ring, Alexa), Wolt, CloudMade\n"
    "- Building AI tools: LLM pipelines, MCP servers, agentic systems\n"
    "- Target roles: Senior TPM at AI companies, Product Engineer, AI Program Lead, "
    "DevRel (AI), Founding Engineer at AI startups\n"
    "- Location: Frankfurt, Germany. Remote EMEA OK. Cannot relocate outside Germany.\n"
    "- Salary: 120-160k EUR base\n"
    "- Languages: English (fluent), German (A2), Ukrainian/Russian (native)\n\n"
    "SCORING CALIBRATION (follow EXACTLY):\n"
    "- 9-10: DREAM JOB. Must meet ALL: (a) AI-native company or strong AI mandate, "
    "(b) exact role match (TPM/PM/DevRel/Product Eng/AI Lead), (c) Frankfurt or full "
    "remote EU, (d) 120k+ EUR realistic. Max 2-3 per 200 jobs.\n"
    "- 7-8: STRONG FIT. Right type of role (PM/TPM/DevRel/Product) at a good company. "
    "Minor gaps like Berlin not Frankfurt, or good company but role is slightly adjacent. "
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
    SCORING_SYSTEM_PROMPT_BASE
    + "Return ONLY valid JSON with double quotes: "
    '{"score": int, "reasoning": "one sentence", '
    '"estimated_salary": "110-130k EUR", '
    '"effort_flag": "sweet-spot|moderate|high-intensity|unknown", '
    '"prep_level": 1-5, "prep_notes": "one sentence"}. '
    "No markdown, no extra text."
)

# daily_pipeline.py adds review_flag for second-pass triage
SCORING_SYSTEM_PROMPT_WITH_REVIEW = (
    SCORING_SYSTEM_PROMPT_BASE
    + "SECOND-PASS FLAG:\n"
    "Set review_flag to true if score is 4-6 AND the role has an unusual angle "
    "that might fit (non-obvious role at a dream company, wildcard career move). "
    "For clear fits (7+) or clear misses (1-3), set review_flag to false.\n\n"
    'Return ONLY a JSON object with double quotes: '
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
    "accountant", "accounting", "bookkeeper", "controller",
    "accounts payable", "accounts receivable", "payroll",
    "financial crimes", "financial analyst", "compensation analyst",
    "tax manager", "tax analyst", "auditor", "treasury",
    # Sales (non-engineering)
    "sales rep", "sales development rep", "sales associate",
    "account executive", "business development representative",
    "inside sales", "outside sales", "telesales",
    "business development director", "business development manager",
    # Customer support
    "customer support", "customer service", "customer success associate",
    "support specialist", "support technician", "help desk",
    "onboarding technician",
    # HR / People
    "hr specialist", "hr manager", "hr generalist", "recruiter",
    "talent acquisition", "benefits manager", "benefits administrator",
    "employee relations", "people operations",
    # Legal / Compliance
    "paralegal", "legal counsel", "compliance officer",
    "regulatory compliance", "ctf compliance",
    "global head of aml",
    # Healthcare / Medical
    "nurse", "nursing", "physician", "therapist", "pharmacist",
    "clinical trial", "pmhnp", "medical director",
    # Trades / Physical
    "driver", "warehouse", "mechanic", "electrician", "plumber",
    "construction", "forklift", "welder", "machinist",
    "technician senior", "network support technician",
    # Marketing (non-product)
    "affiliate marketing", "marketing operations",
    "seo specialist", "content writer", "copywriter",
    "social media manager", "growth manager",
    # Design (non-product)
    "graphic designer", "visual designer", "technical artist",
    # Food / Agriculture
    "food assurance", "food safety",
    # Other unrelated
    "salesforce developer", "salesforce administrator",
    "smart contract engineer", "crypto trader",
    "qa engineer", "quality assurance engineer",
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
    "nebius", "yandex",
    # Big tech ad platforms (user preference)
    "google ads", "meta ads",
]

# Locations that are US-only signals -- cap score at 3 unless remote-EU.
US_ONLY_LOCATIONS: list[str] = [
    "united states", "new york", "san francisco", "los angeles",
    "chicago", "seattle", "austin", "boston", "denver",
    "atlanta", "miami", "dallas", "houston", "phoenix",
    "washington, dc", "san jose", "san diego",
]

# EU-compatible locations (no penalty)
EU_LOCATIONS: list[str] = [
    "germany", "deutschland", "frankfurt", "berlin", "munich", "hamburg",
    "cologne", "stuttgart", "dusseldorf", "mannheim", "wiesbaden",
    "remote", "emea", "europe", "eu",
    "france", "paris", "netherlands", "amsterdam", "spain", "barcelona",
    "ireland", "dublin", "portugal", "lisbon", "poland", "warsaw",
    "austria", "vienna", "switzerland", "zurich", "geneva",
    "uk", "london", "belgium", "brussels", "denmark", "copenhagen",
    "sweden", "stockholm", "finland", "helsinki", "norway", "oslo",
    "czech", "prague", "italy", "milan", "rome",
    "estonia", "tallinn", "ukraine", "kyiv",
    "dach", "brazil",  # some remote-ok roles list Brazil
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
    if any(kw in title_lower for kw in ["junior ", "intern ", "internship", "werkstudent", "working student"]):
        if not any(kw in title_lower for kw in ["lead", "senior", "staff", "principal", "head", "director"]):
            return True, f"Junior role: {title}", None

    # 4. US-only location cap (unless explicitly remote)
    if not remote and not any(eu in location_lower for eu in EU_LOCATIONS):
        for us_loc in US_ONLY_LOCATIONS:
            if us_loc in location_lower:
                return False, f"US-only location: {location}", 3

    return False, "", None


def score_job(client, title: str, company: str, description: str) -> tuple[int, str, str, str, int, str]:
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
        return 2, f"Parse error: {response.choices[0].message.content[:100]}", "unknown", "unknown", 0, "unknown"


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

        score, reasoning, salary, effort, prep, prep_note = score_job(client, title, company, description)

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
        print(f"  [{score}/10] {title} @ {company} ~{salary} [{effort}] prep:{prep}/5 -- {reasoning}")

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
