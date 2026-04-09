"""Analytics service — business logic for pipeline analytics."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from career_os.models.models import ActivityLog, Application
from career_os.schemas.analytics import (
    AnalyticsResponse,
    FunnelStage,
    NotificationMetrics,
    PrepMetrics,
    ScoreBucket,
    TimeInStage,
    WeeklyCount,
)
from career_os.schemas.applications import ApplicationStatus

# All statuses in funnel order
ALL_STATUSES = [s.value for s in ApplicationStatus]

# Funnel progression order — used for stage-to-stage conversion percentages.
# Terminal / branch statuses (rejected, ghosted) don't participate in the
# linear progression; their "previous stage" is defined separately.
FUNNEL_ORDER = [
    "discovered",
    "interested",
    "applied",
    "interviewing",
    "offer",
    "accepted",
]

# Map each status to the status that feeds into it for conversion calculation.
# For example, "applied" feeds from "interested", so Applied/Interested is the
# conversion rate.  "discovered" has no predecessor so its percentage is
# count/total.  Terminal branches like "rejected" and "ghosted" use "offer" and
# "total" respectively.
FUNNEL_PREVIOUS: dict[str, str | None] = {
    "discovered": None,  # first stage → percentage = count/total
    "interested": "discovered",
    "applied": "interested",
    "interviewing": "applied",
    "offer": "interviewing",
    "accepted": "offer",
    "rejected": "offer",  # rejected comes from offer stage
    "ghosted": None,  # ghosted can come from any stage → percentage = count/total
}

# Statuses that count as "responded" (progressed beyond applied)
RESPONDED_STATUSES = {"interviewing", "offer", "accepted"}

# Statuses at or beyond "applied" (denominator for response rate)
APPLIED_PLUS_STATUSES = {"applied", "interviewing", "offer", "accepted", "rejected", "ghosted"}

# Score histogram bucket boundaries
SCORE_BUCKETS: list[tuple[str, float, float]] = [
    ("0-2", 0.0, 2.0),
    ("2-4", 2.0, 4.0),
    ("4-6", 4.0, 6.0),
    ("6-8", 6.0, 8.0),
    ("8-10", 8.0, 10.01),  # 10.01 to include 10.0
]


def _active_apps_query(db: Session, profile_id: int):
    """Base query for non-archived applications."""
    return db.query(Application).filter(
        Application.profile_id == profile_id,
        Application.archived_at.is_(None),
    )


def _compute_stage_to_stage_percentage(
    status: str,
    count: int,
    status_counts: dict[str, int],
    total: int,
) -> float:
    """Compute the stage-to-stage conversion percentage for a funnel stage.

    For the first stage (discovered) and ghosted: count / total * 100.
    For subsequent stages: count / previous_stage_count * 100.
    Returns 0 when the denominator is 0.
    """
    if total == 0:
        return 0.0

    previous = FUNNEL_PREVIOUS.get(status)
    if previous is None:
        # First stage or ghosted — relative to total
        return round(count / total * 100, 1)

    prev_count = status_counts.get(previous, 0)
    if prev_count == 0:
        return 0.0
    return round(count / prev_count * 100, 1)


def _find_latest_status_log(
    app_obj: Application,
    stage: str,
    logs: list[ActivityLog],
) -> datetime | None:
    """Find the most recent log entry for a given stage.

    Delegates to ``_find_stage_entry_time`` which inspects activity-log
    details strings.
    """
    return _find_stage_entry_time(app_obj, stage, logs)


def _compute_stage_delta(log_entry: datetime | None, now: datetime) -> float | None:
    """Calculate elapsed days between *log_entry* and *now*.

    Returns ``None`` when *log_entry* is ``None`` or the delta is negative.
    """
    if log_entry is None:
        return None

    if log_entry.tzinfo is None:
        log_entry = log_entry.replace(tzinfo=UTC)

    delta = (now - log_entry).total_seconds() / 86400
    if delta < 0:
        return None
    return delta


def _compute_time_in_stage(
    db: Session,
    profile_id: int,
    all_apps: list[Application],
) -> list[TimeInStage]:
    """Compute average time-in-stage from activity_log status-transition timestamps.

    For each application that is currently in status S, we look at the
    activity_log for the most recent "status_changed" entry whose details
    contain ``to 'S'`` (the transition *into* that status).  The time-in-stage
    is the delta between that timestamp and now.

    If an application has no activity_log entry for its current status we
    fall back to ``created_at`` (only for the "discovered" stage, which is
    the initial state and may not have a log entry).
    """
    now = datetime.now(UTC)

    # Pre-fetch activity log entries for this profile's applications that
    # record status changes, ordered newest-first.
    app_ids = [a.id for a in all_apps]
    if not app_ids:
        return [TimeInStage(stage=s, avg_days=None) for s in ALL_STATUSES]

    status_logs = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.profile_id == profile_id,
            ActivityLog.application_id.in_(app_ids),
            ActivityLog.action == "status_changed",
        )
        .order_by(ActivityLog.created_at.desc())
        .all()
    )

    # Build a lookup: application_id → list of (created_at, details)
    # ordered newest-first (already the case from the query).
    log_by_app: dict[int, list[ActivityLog]] = {}
    for log in status_logs:
        log_by_app.setdefault(log.application_id, []).append(log)

    time_stages: list[TimeInStage] = []
    for status in ALL_STATUSES:
        apps_in_stage = [a for a in all_apps if a.status.lower() == status]
        if not apps_in_stage:
            time_stages.append(TimeInStage(stage=status, avg_days=None))
            continue

        days_list: list[float] = []
        for app_obj in apps_in_stage:
            entered_at = _find_latest_status_log(app_obj, status, log_by_app.get(app_obj.id, []))
            delta = _compute_stage_delta(entered_at, now)
            if delta is not None:
                days_list.append(delta)

        avg = round(sum(days_list) / len(days_list), 1) if days_list else None
        time_stages.append(TimeInStage(stage=status, avg_days=avg))

    return time_stages


def _find_stage_entry_time(
    app_obj: Application,
    status: str,
    logs: list[ActivityLog],
) -> datetime | None:
    """Find when an application entered its current status.

    Searches activity_log entries (newest first) for a ``status_changed``
    whose details indicate a transition *into* ``status``.

    The actual persisted format (from the applications service and CLI) is:
    ``"Status changed from 'old_status' to 'new_status'"``

    Falls back to ``app_obj.created_at`` for the "discovered" stage
    (the initial state) when no log entry is found.
    """
    target = status.lower()
    for log in logs:
        details = (log.details or "").lower()
        # Actual persisted format: "Status changed from 'old' to 'new'"
        if f"to '{target}'" in details:
            return log.created_at
        # Also support arrow format for backwards compatibility
        if f"→ {target}" in details or f"-> {target}" in details:
            return log.created_at

    # Fallback for initial stage: use created_at
    if target == "discovered":
        return app_obj.created_at

    return None


def _compute_prep_metrics(db: Session, profile_id: int) -> PrepMetrics:
    """Compute interview prep completion metrics (VAL-CROSS-007)."""
    from career_os.models.interview_prep import InterviewPrepItem, InterviewPrepSession

    sessions = (
        db.query(InterviewPrepSession).filter(InterviewPrepSession.profile_id == profile_id).all()
    )
    total_sessions = len(sessions)
    if total_sessions == 0:
        return PrepMetrics()

    total_items = 0
    completed_items = 0
    completed_sessions = 0

    for session in sessions:
        items = db.query(InterviewPrepItem).filter(InterviewPrepItem.session_id == session.id).all()
        session_total = len(items)
        session_completed = sum(1 for it in items if it.completed)
        total_items += session_total
        completed_items += session_completed
        if session_total > 0 and session_completed == session_total:
            completed_sessions += 1

    completion_rate = (
        round(completed_sessions / total_sessions * 100, 1) if total_sessions > 0 else None
    )

    return PrepMetrics(
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
        completion_rate=completion_rate,
        total_items=total_items,
        completed_items=completed_items,
    )


def _compute_notification_metrics(db: Session, profile_id: int) -> NotificationMetrics:
    """Compute notification delivery metrics (VAL-CROSS-007)."""
    from career_os.models.pushover import NotificationLog

    logs = db.query(NotificationLog).filter(NotificationLog.profile_id == profile_id).all()
    if not logs:
        return NotificationMetrics()

    total_sent = sum(1 for log in logs if log.status == "sent")
    total_failed = sum(1 for log in logs if log.status == "failed")
    total_queued = sum(1 for log in logs if log.status == "queued")

    by_category: dict[str, int] = {}
    for log in logs:
        if log.status == "sent":
            by_category[log.category] = by_category.get(log.category, 0) + 1

    return NotificationMetrics(
        total_sent=total_sent,
        total_failed=total_failed,
        total_queued=total_queued,
        by_category=by_category,
    )


def _compute_funnel_stats(
    all_apps: list[Application],
) -> tuple[list[FunnelStage], float | None]:
    """Compute the conversion funnel and response rate from applications.

    Returns a tuple of (funnel_stages, response_rate).
    """
    total = len(all_apps)

    status_counts: dict[str, int] = {s: 0 for s in ALL_STATUSES}
    for app_obj in all_apps:
        status_key = app_obj.status.lower()
        if status_key in status_counts:
            status_counts[status_key] += 1

    funnel = [
        FunnelStage(
            stage=status,
            count=count,
            percentage=_compute_stage_to_stage_percentage(status, count, status_counts, total),
        )
        for status, count in status_counts.items()
    ]

    applied_plus = sum(1 for a in all_apps if a.status.lower() in APPLIED_PLUS_STATUSES)
    responded = sum(1 for a in all_apps if a.status.lower() in RESPONDED_STATUSES)
    response_rate: float | None = None
    if applied_plus > 0:
        response_rate = round(responded / applied_plus * 100, 1)

    return funnel, response_rate


def _compute_weekly_activity(all_apps: list[Application]) -> list[WeeklyCount]:
    """Group applications by ISO week and return sorted weekly counts."""
    if not all_apps:
        return []

    week_counts: dict[str, int] = {}
    for a in all_apps:
        created = a.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        # Start of ISO week (Monday)
        iso_year, iso_week, _ = created.isocalendar()
        week_start = datetime.fromisocalendar(iso_year, iso_week, 1)
        week_key = week_start.strftime("%Y-%m-%d")
        week_counts[week_key] = week_counts.get(week_key, 0) + 1

    return [
        WeeklyCount(week=week_key, count=week_counts[week_key])
        for week_key in sorted(week_counts.keys())
    ]


def _compute_score_distribution(all_apps: list[Application]) -> list[ScoreBucket]:
    """Build a histogram of fit scores across predefined buckets."""
    score_dist: list[ScoreBucket] = []
    for label, low, high in SCORE_BUCKETS:
        count = sum(1 for a in all_apps if a.fit_score is not None and low <= a.fit_score < high)
        score_dist.append(ScoreBucket(range=label, count=count))
    return score_dist


def get_analytics(db: Session, *, profile_id: int) -> AnalyticsResponse:
    """Compute all analytics metrics for a profile."""
    base = _active_apps_query(db, profile_id)
    all_apps = base.all()

    funnel, response_rate = _compute_funnel_stats(all_apps)
    time_stages = _compute_time_in_stage(db, profile_id, all_apps)
    weekly = _compute_weekly_activity(all_apps)
    score_dist = _compute_score_distribution(all_apps)
    prep_metrics = _compute_prep_metrics(db, profile_id)
    notification_metrics = _compute_notification_metrics(db, profile_id)

    return AnalyticsResponse(
        conversion_funnel=funnel,
        response_rate=response_rate,
        time_in_stage=time_stages,
        applications_over_time=weekly,
        score_distribution=score_dist,
        prep_metrics=prep_metrics,
        notification_metrics=notification_metrics,
    )
