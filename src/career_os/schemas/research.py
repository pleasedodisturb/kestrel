"""Pydantic schemas for Company Research API.

Covers:
- VAL-RESEARCH-001: One-click company deep-dive with all report sections
- VAL-RESEARCH-002: Tech stack categorized by frontend/backend/infra/analytics
- VAL-RESEARCH-003: Funding data (stage, amount, investors)
- VAL-RESEARCH-004: Glassdoor rating + culture signals (≥3 keywords)
- VAL-RESEARCH-005: Values alignment score (1-10 with rationale)
- VAL-RESEARCH-006: ATS platform detection
- VAL-RESEARCH-007: Hiring patterns (velocity, departments)
- VAL-RESEARCH-008: Partial report for obscure companies
- VAL-RESEARCH-009: API failure graceful degradation
- VAL-RESEARCH-010: Industry segment classification
"""

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CompanyResearchRequest(BaseModel):
    """Request body for POST /api/research/company."""

    company_name: str = Field(
        ..., min_length=1, description="Company name to research"
    )
    profile_id: int = Field(
        ..., description="Profile ID for values alignment scoring"
    )
    company_url: str | None = Field(
        default=None, description="Optional company website URL for enrichment"
    )


# ---------------------------------------------------------------------------
# Report section schemas
# ---------------------------------------------------------------------------


class TechStackReport(BaseModel):
    """Categorized tech stack (VAL-RESEARCH-002)."""

    frontend: list[str] = Field(default_factory=list, description="Frontend technologies")
    backend: list[str] = Field(default_factory=list, description="Backend technologies")
    infrastructure: list[str] = Field(
        default_factory=list, description="Infrastructure/DevOps technologies"
    )
    analytics: list[str] = Field(
        default_factory=list, description="Analytics/data technologies"
    )


class FundingReport(BaseModel):
    """Funding data (VAL-RESEARCH-003)."""

    stage: str | None = Field(default=None, description="Funding stage (e.g., Series C)")
    total_raised: str | None = Field(
        default=None, description="Total funding raised (e.g., $120M)"
    )
    lead_investor: str | None = Field(default=None, description="Lead investor name")
    last_round_date: str | None = Field(
        default=None, description="Date of last funding round (YYYY-MM)"
    )


class GlassdoorReport(BaseModel):
    """Glassdoor ratings and culture signals (VAL-RESEARCH-004)."""

    overall_rating: float | None = Field(
        default=None, ge=0, le=5, description="Overall Glassdoor rating (0-5)"
    )
    ceo_approval: int | None = Field(
        default=None, ge=0, le=100, description="CEO approval percentage"
    )
    culture_keywords: list[str] = Field(
        default_factory=list,
        description="Culture signal keywords from review sentiment (≥3)",
    )
    work_life_balance: float | None = Field(
        default=None, ge=0, le=5, description="Work-life balance rating (0-5)"
    )


class ValuesAlignmentReport(BaseModel):
    """Values alignment scoring (VAL-RESEARCH-005)."""

    score: float = Field(
        ..., ge=0, le=10, description="Values alignment score (1-10)"
    )
    rationale: str = Field(
        ...,
        description="Rationale referencing user's specific values",
    )


class HiringPatternsReport(BaseModel):
    """Hiring patterns (VAL-RESEARCH-007)."""

    active_postings: int | None = Field(
        default=None, description="Number of currently active job postings"
    )
    posting_velocity: str | None = Field(
        default=None, description="Posting rate (e.g., '12/month')"
    )
    top_departments: list[str] = Field(
        default_factory=list,
        description="Departments with most open roles",
    )


# ---------------------------------------------------------------------------
# Report source warning
# ---------------------------------------------------------------------------


class NewsItem(BaseModel):
    """A recent news item about the company."""

    title: str = Field(..., description="News headline")
    url: str | None = Field(default=None, description="Link to the article")
    date: str | None = Field(default=None, description="Publication date (YYYY-MM-DD)")
    summary: str | None = Field(default=None, description="Brief summary of the news")


class SourceWarning(BaseModel):
    """Warning for a failed data source (VAL-RESEARCH-009)."""

    source: str = Field(..., description="Name of the failed data source")
    error: str = Field(..., description="Brief description of the failure")


# ---------------------------------------------------------------------------
# Full research report
# ---------------------------------------------------------------------------


class CompanyResearchReport(BaseModel):
    """Full structured company research report.

    All sections are present; missing data for obscure companies will
    have default/empty values (VAL-RESEARCH-008). Source warnings
    indicate graceful degradation (VAL-RESEARCH-009).
    """

    company_name: str = Field(..., description="Researched company name")
    tech_stack: TechStackReport = Field(
        default_factory=TechStackReport,
        description="Categorized tech stack (VAL-RESEARCH-002)",
    )
    funding: FundingReport = Field(
        default_factory=FundingReport,
        description="Funding data (VAL-RESEARCH-003)",
    )
    glassdoor: GlassdoorReport = Field(
        default_factory=GlassdoorReport,
        description="Glassdoor ratings and culture (VAL-RESEARCH-004)",
    )
    values_alignment: ValuesAlignmentReport = Field(
        ...,
        description="Values alignment score and rationale (VAL-RESEARCH-005)",
    )
    ats_platform: str | None = Field(
        default=None,
        description="Detected ATS platform (VAL-RESEARCH-006)",
    )
    hiring_patterns: HiringPatternsReport = Field(
        default_factory=HiringPatternsReport,
        description="Hiring patterns data (VAL-RESEARCH-007)",
    )
    industry_segment: str | None = Field(
        default=None,
        description="Industry segment classification (VAL-RESEARCH-010)",
    )
    employee_count: str | None = Field(
        default=None, description="Estimated employee count"
    )
    news: list[NewsItem] = Field(
        default_factory=list,
        description="Recent news items about the company",
    )
    warnings: list[SourceWarning] = Field(
        default_factory=list,
        description="Warnings for failed data sources (VAL-RESEARCH-009)",
    )
