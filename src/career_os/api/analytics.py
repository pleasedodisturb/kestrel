"""Analytics dashboard API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.analytics import AnalyticsResponse
from career_os.services.analytics import get_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
async def analytics(
    profile_id: int = Query(..., description="Profile to show analytics for"),
    db: Session = Depends(get_db),
) -> AnalyticsResponse:
    """Get analytics dashboard data.

    Returns conversion funnel, response rate, time-in-stage,
    applications over time, and score distribution.
    All charts handle empty data gracefully.
    """
    return get_analytics(db, profile_id=profile_id)
