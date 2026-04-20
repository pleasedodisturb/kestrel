"""Pydantic schemas for Analytics API."""

from pydantic import BaseModel, Field

from career_os.schemas.constraints import INT64_MAX, INT64_MIN


class FunnelStage(BaseModel):
    """A single stage in the conversion funnel."""

    stage: str = Field(..., description="Pipeline status name")
    count: int = Field(..., ge=INT64_MIN, le=INT64_MAX, description="Number of applications in this stage")
    percentage: float = Field(
        ...,
        description=(
            "Stage-to-stage conversion percentage. For the first stage this is"
            " count/total*100; for subsequent stages it is"
            " count/previous_stage_count*100 (0 when previous is 0)."
        ),
    )


class TimeInStage(BaseModel):
    """Average days in a specific pipeline stage."""

    stage: str = Field(..., description="Pipeline status name")
    avg_days: float | None = Field(None, description="Average days in stage, null if no data")


class WeeklyCount(BaseModel):
    """Weekly application count."""

    week: str = Field(..., description="ISO week start date (YYYY-MM-DD)")
    count: int = Field(..., ge=INT64_MIN, le=INT64_MAX, description="Number of applications created that week")


class ScoreBucket(BaseModel):
    """A histogram bucket for score distribution."""

    range: str = Field(..., description="Score range label (e.g. '8-9')")
    count: int = Field(..., ge=INT64_MIN, le=INT64_MAX, description="Number of applications in this range")


class PrepMetrics(BaseModel):
    """Interview prep completion metrics."""

    total_sessions: int = Field(0, ge=INT64_MIN, le=INT64_MAX, description="Total prep sessions created")
    completed_sessions: int = Field(
        0, ge=INT64_MIN, le=INT64_MAX, description="Sessions where all checklist items are completed"
    )
    completion_rate: float | None = Field(
        None, description="Percentage of prep sessions fully completed (0-100)"
    )
    total_items: int = Field(0, ge=INT64_MIN, le=INT64_MAX, description="Total checklist items across all sessions")
    completed_items: int = Field(0, ge=INT64_MIN, le=INT64_MAX, description="Total completed checklist items")


class NotificationMetrics(BaseModel):
    """Notification delivery metrics."""

    total_sent: int = Field(0, ge=INT64_MIN, le=INT64_MAX, description="Total notifications sent")
    total_failed: int = Field(0, ge=INT64_MIN, le=INT64_MAX, description="Total failed notifications")
    total_queued: int = Field(0, ge=INT64_MIN, le=INT64_MAX, description="Total queued notifications")
    by_category: dict[str, int] = Field(
        default_factory=dict,
        description="Sent notification count per category (follow_up, ghost, discovery, interview)",
    )


class AnalyticsResponse(BaseModel):
    """Full analytics dashboard response."""

    conversion_funnel: list[FunnelStage] = Field(
        ..., description="Conversion funnel with counts and percentages per stage"
    )
    response_rate: float | None = Field(
        None,
        description=(
            "Percentage of applied+ applications that progressed"
            " to interviewing+. None if zero applied."
        ),
    )
    time_in_stage: list[TimeInStage] = Field(..., description="Average days in each status stage")
    applications_over_time: list[WeeklyCount] = Field(..., description="Weekly application counts")
    score_distribution: list[ScoreBucket] = Field(
        ..., description="Fit score distribution histogram"
    )
    prep_metrics: PrepMetrics = Field(
        default_factory=PrepMetrics,
        description="Interview prep completion metrics",
    )
    notification_metrics: NotificationMetrics = Field(
        default_factory=NotificationMetrics,
        description="Notification delivery metrics",
    )
