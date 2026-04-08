"""Company research service — AI-powered one-click company deep-dive.

Produces a structured report with tech stack (categorized), funding data,
Glassdoor ratings + culture signals, values alignment score, ATS detection,
hiring patterns, and industry classification.

Partial reports for obscure companies (no crash). Source failures degrade
gracefully with warnings.

Covers VAL-RESEARCH-001 through VAL-RESEARCH-010.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from career_os.ai.factory import get_ai_provider
from career_os.models.models import Profile
from career_os.schemas.ai import AIFeature, CompanyResearchResult
from career_os.schemas.research import (
    CompanyResearchReport,
    FundingReport,
    GlassdoorReport,
    HiringPatternsReport,
    NewsItem,
    SourceWarning,
    TechStackReport,
    ValuesAlignmentReport,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


class ResearchError(Exception):
    """Raised when the research process fails entirely."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Known ATS platforms to detect from company career pages
def _persist_research_report(
    db: Session,
    company_name: str,
    profile_id: int,
    values_score: float,
    industry_segment: str | None,
    report_json_str: str | None = None,
) -> None:
    """Persist or update a company research report record.

    Used by the interview prep research gate to verify actual research exists.
    Also stores full report JSON so prep can include company-specific data
    (tech_stack, culture, values_alignment, hiring_patterns) in prompts
    (VAL-CROSS-009).
    """
    try:
        from career_os.models.company_research import CompanyResearchReportModel

        existing = (
            db.query(CompanyResearchReportModel)
            .filter(
                CompanyResearchReportModel.company_name == company_name,
                CompanyResearchReportModel.profile_id == profile_id,
            )
            .first()
        )
        if existing:
            existing.values_alignment_score = values_score
            existing.industry_segment = industry_segment
            if report_json_str is not None:
                existing.report_json = report_json_str
        else:
            report = CompanyResearchReportModel(
                profile_id=profile_id,
                company_name=company_name,
                values_alignment_score=values_score,
                industry_segment=industry_segment,
                report_json=report_json_str,
            )
            db.add(report)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist research report for %s: %s", company_name, exc)
        # Don't fail the research request if persistence fails
        import contextlib

        with contextlib.suppress(Exception):
            db.rollback()


KNOWN_ATS_PLATFORMS: list[str] = [
    "Greenhouse",
    "Lever",
    "Ashby",
    "Workday",
    "Taleo",
    "iCIMS",
    "SmartRecruiters",
    "BambooHR",
    "Jobvite",
    "JazzHR",
    "Breezy HR",
    "Recruitee",
    "Personio",
]


def _build_research_prompt(
    company_name: str,
    company_url: str | None,
    profile: Profile,
) -> str:
    """Build the AI prompt for company research.

    Includes user values context so the AI can produce a values
    alignment score with rationale referencing the user's values.
    """
    profile_context = {
        "name": profile.name,
        "location": profile.location or "Not specified",
        "job_family": profile.job_family or "Not specified",
        "values": [
            "innovation and AI-first culture",
            "high autonomy and ownership",
            "collaborative engineering teams",
            "remote-friendly / flexible work",
            "impact-driven product development",
            "continuous learning culture",
            "transparency and open communication",
        ],
    }

    url_hint = f"\nCompany URL: {company_url}" if company_url else ""

    return f"""Research the company "{company_name}" and produce a comprehensive report.
{url_hint}

Return a JSON object with the following structure:

1. tech_stack: Object with categorized technologies:
   - frontend: list of frontend technologies (React, Vue, Angular, etc.)
   - backend: list of backend technologies (Python, Go, Java, etc.)
   - infrastructure: list of infrastructure technologies (AWS, K8s, Terraform, etc.)
   - analytics: list of analytics/data technologies (Snowflake, dbt, Looker, etc.)

2. funding: Object with:
   - stage: funding stage (e.g., "Series C", "Pre-seed", "Public", "Bootstrapped")
   - total_raised: total funding raised (e.g., "$120M")
   - lead_investor: lead investor name
   - last_round_date: date of last round (YYYY-MM format)

3. glassdoor: Object with:
   - overall_rating: numeric rating 0-5
   - ceo_approval: CEO approval percentage (0-100)
   - culture_keywords: list of ≥3 culture signal keywords from review sentiment
   - work_life_balance: numeric rating 0-5

4. values_alignment: numeric score 1-10 representing alignment with user's values:
   {json.dumps(profile_context['values'], indent=2)}
   Include a rationale referencing specific user values.

5. ats_platform: detected ATS platform (Greenhouse, Lever, Ashby, Workday, etc.) or null

6. hiring_patterns: Object with:
   - active_postings: number of current job postings
   - posting_velocity: posting rate (e.g., "12/month")
   - top_departments: list of departments with most open roles

7. industry_segment: industry classification and sub-category
   (e.g., "Enterprise SaaS / AI Platform")

8. employee_count: estimated number of employees (e.g., "500-1000")

If data is unavailable for any section, use null or empty values. Do not fabricate data.

User profile context:
{json.dumps(profile_context, indent=2)}
"""


def _parse_ai_result(
    result: CompanyResearchResult | None,
    company_name: str,
) -> tuple[
    TechStackReport,
    FundingReport,
    GlassdoorReport,
    float,
    str,
    str | None,
    HiringPatternsReport,
    str | None,
    str | None,
    list[NewsItem],
    list[SourceWarning],
]:
    """Parse the AI structured result into typed report sections.

    Returns a tuple of all report components.
    Falls back to partial/empty data on any parse error.
    """
    warnings: list[SourceWarning] = []

    if result is None:
        warnings.append(
            SourceWarning(
                source="ai_provider",
                error="AI provider returned no structured data",
            )
        )
        return (
            TechStackReport(),
            FundingReport(),
            GlassdoorReport(),
            5.0,
            "No data available from AI provider for values alignment assessment.",
            None,
            HiringPatternsReport(),
            None,
            None,
            [],
            warnings,
        )

    # Parse tech stack
    try:
        tech_data = result.tech_stack if isinstance(result.tech_stack, dict) else {}
        tech_stack = TechStackReport(
            frontend=tech_data.get("frontend", []),
            backend=tech_data.get("backend", []),
            infrastructure=tech_data.get("infrastructure", []),
            analytics=tech_data.get("analytics", []),
        )
    except Exception as exc:
        logger.warning("Failed to parse tech stack for %s: %s", company_name, exc)
        tech_stack = TechStackReport()
        warnings.append(SourceWarning(source="tech_stack", error=str(exc)))

    # Parse funding
    try:
        funding_data = result.funding if isinstance(result.funding, dict) else {}
        funding = FundingReport(
            stage=funding_data.get("stage"),
            total_raised=funding_data.get("total_raised"),
            lead_investor=funding_data.get("lead_investor"),
            last_round_date=funding_data.get("last_round_date"),
        )
    except Exception as exc:
        logger.warning("Failed to parse funding for %s: %s", company_name, exc)
        funding = FundingReport()
        warnings.append(SourceWarning(source="funding", error=str(exc)))

    # Parse glassdoor
    try:
        glass_data = result.glassdoor if isinstance(result.glassdoor, dict) else {}
        glassdoor = GlassdoorReport(
            overall_rating=glass_data.get("overall_rating"),
            ceo_approval=glass_data.get("ceo_approval"),
            culture_keywords=glass_data.get("culture_keywords", []),
            work_life_balance=glass_data.get("work_life_balance"),
        )
    except Exception as exc:
        logger.warning("Failed to parse glassdoor for %s: %s", company_name, exc)
        glassdoor = GlassdoorReport()
        warnings.append(SourceWarning(source="glassdoor", error=str(exc)))

    # Parse values alignment
    values_score = 5.0
    values_rationale = "No data found"
    try:
        va = result.values_alignment
        if isinstance(va, (int, float)):
            values_score = float(va)
            values_rationale = "Score derived from AI analysis of company data."
        elif isinstance(va, dict):
            values_score = float(va.get("score", 5.0))
            values_rationale = va.get(
                "rationale", "Score derived from AI analysis of company data."
            )
        else:
            values_score = float(va)
    except Exception as exc:
        logger.warning(
            "Failed to parse values alignment for %s: %s", company_name, exc
        )
        warnings.append(SourceWarning(source="values_alignment", error=str(exc)))

    # ATS platform
    ats_platform = result.ats_platform if result.ats_platform else None

    # Hiring patterns
    try:
        hp_data = (
            result.hiring_patterns
            if isinstance(result.hiring_patterns, dict)
            else {}
        )
        hiring_patterns = HiringPatternsReport(
            active_postings=hp_data.get("active_postings"),
            posting_velocity=hp_data.get("posting_velocity"),
            top_departments=hp_data.get("top_departments", []),
        )
    except Exception as exc:
        logger.warning(
            "Failed to parse hiring patterns for %s: %s", company_name, exc
        )
        hiring_patterns = HiringPatternsReport()
        warnings.append(SourceWarning(source="hiring_patterns", error=str(exc)))

    # Industry segment
    industry_segment = result.industry_segment if result.industry_segment else None

    # Employee count
    employee_count = result.employee_count if result.employee_count else None

    # News items
    news: list[NewsItem] = []
    if result.news:
        for item in result.news:
            try:
                if isinstance(item, dict):
                    news.append(NewsItem(**item))
            except Exception as exc:
                logger.warning("Failed to parse news item for %s: %s", company_name, exc)

    return (
        tech_stack,
        funding,
        glassdoor,
        values_score,
        values_rationale,
        ats_platform,
        hiring_patterns,
        industry_segment,
        employee_count,
        news,
        warnings,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def research_company(
    db: Session,
    company_name: str,
    profile_id: int,
    company_url: str | None = None,
    simulate_partial: bool = False,
) -> CompanyResearchReport:
    """Research a company and return a structured report.

    Uses the configured AI provider to generate company intelligence.
    Falls back to partial report for obscure companies. Source failures
    produce warnings rather than crashes.

    When simulate_partial=True (VAL-RESEARCH-009), passes a flag to the
    AI provider context so the mock provider returns partial data with
    source_warnings for graceful degradation testing.

    Args:
        db: Database session.
        company_name: Name of the company to research.
        profile_id: Profile ID for values alignment context.
        company_url: Optional company website URL.
        simulate_partial: If True, mock provider returns partial data.

    Returns:
        CompanyResearchReport with all sections populated (or partial).

    Raises:
        ProfileNotFoundError: If the profile doesn't exist.
        ResearchError: If the research fails entirely.
    """
    # Verify profile exists
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    # Build prompt and call AI provider
    prompt = _build_research_prompt(company_name, company_url, profile)

    warnings: list[SourceWarning] = []

    try:
        provider = get_ai_provider()
        response = await provider.complete(
            prompt=prompt,
            feature=AIFeature.company_research,
            context={
                "company_name": company_name,
                "profile_id": profile_id,
                "simulate_partial": simulate_partial,
            },
        )
        structured = response.structured
    except Exception as exc:
        logger.warning(
            "AI provider failed for company research '%s': %s",
            company_name,
            exc,
        )
        structured = None
        warnings.append(
            SourceWarning(
                source="ai_provider",
                error=f"AI provider error: {exc}",
            )
        )

    # Parse the AI result into structured report sections
    (
        tech_stack,
        funding,
        glassdoor,
        values_score,
        values_rationale,
        ats_platform,
        hiring_patterns,
        industry_segment,
        employee_count,
        news,
        parse_warnings,
    ) = _parse_ai_result(
        structured if isinstance(structured, CompanyResearchResult) else None,
        company_name,
    )

    warnings.extend(parse_warnings)

    # VAL-RESEARCH-009: Add source_warnings for missing sections in partial mode
    if simulate_partial:
        partial_sections = []
        if not glassdoor.overall_rating and not glassdoor.culture_keywords:
            partial_sections.append("glassdoor")
        if not hiring_patterns.active_postings and not hiring_patterns.top_departments:
            partial_sections.append("hiring_patterns")
        if not industry_segment:
            partial_sections.append("industry_segment")
        if not employee_count:
            partial_sections.append("employee_count")
        if ats_platform is None:
            partial_sections.append("ats_platform")
        for section in partial_sections:
            warnings.append(
                SourceWarning(
                    source=section,
                    error=f"Data unavailable for {section} (partial simulation)",
                )
            )

    # Build report JSON for persistence (VAL-CROSS-009: prep uses research data)
    report_json_data = {
        "tech_stack": tech_stack.model_dump() if tech_stack else {},
        "glassdoor": glassdoor.model_dump() if glassdoor else {},
        "values_alignment": {"score": values_score, "rationale": values_rationale},
        "hiring_patterns": hiring_patterns.model_dump() if hiring_patterns else {},
    }
    report_json_str = json.dumps(report_json_data)

    # Persist the research report for freshness/gate checks
    _persist_research_report(
        db=db,
        company_name=company_name,
        profile_id=profile_id,
        values_score=values_score,
        industry_segment=industry_segment,
        report_json_str=report_json_str,
    )

    return CompanyResearchReport(
        company_name=company_name,
        tech_stack=tech_stack,
        funding=funding,
        glassdoor=glassdoor,
        values_alignment=ValuesAlignmentReport(
            score=values_score,
            rationale=values_rationale,
        ),
        ats_platform=ats_platform,
        hiring_patterns=hiring_patterns,
        industry_segment=industry_segment,
        employee_count=employee_count,
        news=news,
        warnings=warnings,
    )
