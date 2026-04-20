"""Analytics dashboard API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.analytics import AnalyticsResponse
from career_os.schemas.constraints import INT64_MAX
from career_os.services.analytics import get_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
async def analytics(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description="Profile to show analytics for")],
    db: Annotated[Session, Depends(get_db)],
) -> AnalyticsResponse:
    """Get analytics dashboard data.

    Returns conversion funnel, response rate, time-in-stage,
    applications over time, and score distribution.
    All charts handle empty data gracefully.
    """
    return get_analytics(db, profile_id=profile_id)
