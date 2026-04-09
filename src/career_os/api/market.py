"""Market Intelligence API routes - salary trends, skill demand, hiring patterns,
market positioning, and dream company opportunity radar."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.market import (
    HiringPatternsResponse,
    MarketRefreshRequest,
    MarketRefreshResponse,
    OpportunityRadarResponse,
    PositioningResponse,
    SalaryTrendsResponse,
    SkillTrendsResponse,
)
from career_os.services.market import (
    ProfileNotFoundError,
    get_hiring_patterns,
    get_market_positioning,
    get_opportunity_radar,
    get_salary_trends,
    get_skill_trends,
    refresh_market_data,
)

router = APIRouter(tags=["market-intelligence"])


# ---------------------------------------------------------------------------
# VAL-MARKET-001: Salary Trends
# ---------------------------------------------------------------------------


@router.get("/api/market/salary-trends")
async def salary_trends_endpoint(
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
    role: Annotated[str | None, Query(description="Filter by role substring")] = None,
    location: Annotated[str | None, Query(description="Filter by location substring")] = None,
) -> SalaryTrendsResponse:
    """Get salary trends by role and location.

    Returns time-series with median, p25, p75, sample_size grouped by
    normalized role type.
    """
    try:
        result = get_salary_trends(db, profile_id, role=role, location=location)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SalaryTrendsResponse(**result)


# ---------------------------------------------------------------------------
# VAL-MARKET-002: Skill Demand Trends
# ---------------------------------------------------------------------------


@router.get("/api/market/skill-trends")
async def skill_trends_endpoint(
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> SkillTrendsResponse:
    """Get most-demanded skills ranked by mention count.

    Returns skill_name, mention_count, trend_direction, percentage_of_postings.
    Updates with each discovery sweep.
    """
    try:
        result = get_skill_trends(db, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SkillTrendsResponse(**result)


# ---------------------------------------------------------------------------
# VAL-MARKET-003: Company Hiring Patterns
# ---------------------------------------------------------------------------


@router.get("/api/market/hiring-patterns")
async def hiring_patterns_endpoint(
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> HiringPatternsResponse:
    """Get company hiring patterns.

    Returns active companies with posting counts, velocity (postings/week),
    and trending roles.
    """
    try:
        result = get_hiring_patterns(db, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return HiringPatternsResponse(**result)


# ---------------------------------------------------------------------------
# VAL-MARKET-004: Market Positioning
# ---------------------------------------------------------------------------


@router.get("/api/market/positioning")
async def positioning_endpoint(
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> PositioningResponse:
    """Get market positioning - profile match % by role type.

    Compares user's skills against skills extracted from discovered job
    descriptions.
    """
    try:
        result = get_market_positioning(db, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PositioningResponse(**result)


# ---------------------------------------------------------------------------
# VAL-MARKET-005: Dream Company Opportunity Radar
# ---------------------------------------------------------------------------


@router.get("/api/market/opportunity-radar")
async def opportunity_radar_endpoint(
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
    dream_companies: Annotated[
        str | None,
        Query(description="Comma-separated list of dream company names (overrides profile)"),
    ] = None,
) -> OpportunityRadarResponse:
    """Get opportunity radar for dream companies.

    Reads dream companies from profile's dream_companies field by default.
    An explicit query param overrides the profile setting.
    Jobs from dream-tier companies are flagged with priority: 'dream'
    and alert: True.
    """
    import json as json_mod

    from career_os.models.models import Profile

    # If explicit query param provided, use it; otherwise read from profile
    companies_list: list[str] | None = None
    if dream_companies:
        companies_list = [c.strip() for c in dream_companies.split(",") if c.strip()]
    else:
        # Read from profile's dream_companies field
        profile = db.query(Profile).filter(Profile.id == profile_id).first()
        if profile and profile.dream_companies:
            try:
                companies_list = json_mod.loads(profile.dream_companies)
            except (json_mod.JSONDecodeError, TypeError):
                companies_list = None

    try:
        result = get_opportunity_radar(db, profile_id, dream_companies=companies_list)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return OpportunityRadarResponse(**result)


# ---------------------------------------------------------------------------
# VAL-MARKET-006: Refresh
# ---------------------------------------------------------------------------


@router.post("/api/market/refresh")
async def refresh_market_endpoint(
    payload: MarketRefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MarketRefreshResponse:
    """Trigger a refresh of market intelligence data.

    Called automatically after each discovery sweep. Can also be called
    manually.
    """
    try:
        result = refresh_market_data(db, payload.profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return MarketRefreshResponse(**result)
