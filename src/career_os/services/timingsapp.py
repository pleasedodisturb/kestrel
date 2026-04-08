"""TimingsApp integration service.

Handles:
- Start/stop tracked time sessions from Career OS
- Auto-categorize sessions by activity type
- Create corresponding TimingsApp entries
- Time analytics: total hours, category breakdown, 4-week trend

Covers: VAL-TIME-001, VAL-TIME-002, VAL-TIME-003
"""

import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from career_os.models.integrations import IntegrationConfig
from career_os.models.timingsapp import TimeSession
from career_os.schemas.timingsapp import (
    ActivityCategory,
    CategoryBreakdown,
    TimeAnalyticsResponse,
    TimeSessionCreate,
    TimeSessionUpdate,
    WeeklyTrend,
)
from career_os.services.timingsapp_client import (
    CATEGORY_PROJECT_MAP,
    TimingsAppAPIError,
    TimingsAppClient,
)

logger = logging.getLogger(__name__)


class TimingsAppNotConfiguredError(Exception):
    """Raised when TimingsApp integration is not configured or disabled."""


class TimeSessionNotFoundError(Exception):
    """Raised when a time session is not found."""


class TimeSessionAlreadyStoppedError(Exception):
    """Raised when trying to stop an already-stopped session."""


class ConcurrentSessionError(Exception):
    """Raised when trying to start a session while another is already running."""


# ---------------------------------------------------------------------------
# Category auto-assignment
# ---------------------------------------------------------------------------

# Keywords that map to each category
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "applying": [
        "apply", "application", "submit", "cover letter", "resume",
        "cv", "tailoring", "applied",
    ],
    "researching": [
        "research", "company", "market", "discover", "search", "browse",
        "explore", "looking", "searching",
    ],
    "prepping": [
        "prep", "interview", "practice", "mock", "star stor", "prepare",
        "rehearse", "whiteboard",
    ],
    "networking": [
        "network", "connect", "linkedin", "meetup", "coffee chat",
        "referral", "outreach", "event",
    ],
    "learning": [
        "learn", "course", "tutorial", "study", "read", "skill",
        "certification", "training", "udemy", "coursera",
    ],
}


def auto_categorize(activity_name: str, notes: str | None = None) -> str:
    """Determine the activity category from the activity name and notes.

    Returns the best-matching category, defaulting to 'researching'
    if no clear match is found.
    """
    text = (activity_name + " " + (notes or "")).lower()

    best_category = "researching"
    best_score = 0

    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


# ---------------------------------------------------------------------------
# TimingsApp client helpers
# ---------------------------------------------------------------------------


def _get_timingsapp_credentials(db: Session) -> tuple[str, str | None]:
    """Retrieve TimingsApp API token and URL from integration config.

    Returns (api_token, api_url).
    Raises TimingsAppNotConfiguredError if not configured or disabled.
    """
    row = (
        db.query(IntegrationConfig)
        .filter(IntegrationConfig.name == "timingsapp")
        .first()
    )
    if row is None or not row.enabled:
        raise TimingsAppNotConfiguredError("TimingsApp integration is not enabled")

    creds: dict[str, str] = {}
    if row.credentials:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            creds = json.loads(row.credentials)

    api_token = creds.get("api_token", "").strip()
    api_url = creds.get("api_url", "").strip() or None

    if not api_token:
        raise TimingsAppNotConfiguredError("TimingsApp API token not configured")

    return api_token, api_url


def get_client(db: Session) -> TimingsAppClient:
    """Get a TimingsAppClient from stored credentials."""
    api_token, api_url = _get_timingsapp_credentials(db)
    kwargs: dict = {}
    if api_url:
        kwargs["base_url"] = api_url
    return TimingsAppClient(api_token, **kwargs)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


def start_session(
    db: Session,
    payload: TimeSessionCreate,
    *,
    client: TimingsAppClient | None = None,
) -> TimeSession:
    """Start a new tracked time session.

    Creates a local TimeSession record and optionally starts a timer
    in TimingsApp if integration is configured.

    Raises ConcurrentSessionError if the profile already has a running session.
    """
    # Enforce one open session per profile
    existing_running = (
        db.query(TimeSession)
        .filter(
            TimeSession.profile_id == payload.profile_id,
            TimeSession.stopped_at.is_(None),
        )
        .first()
    )
    if existing_running is not None:
        raise ConcurrentSessionError(
            f"Profile {payload.profile_id} already has a running session "
            f"(session {existing_running.id}: {existing_running.activity_name}). "
            f"Stop it before starting a new one."
        )

    # Auto-categorize if not provided
    category = payload.category
    if category is None:
        category_str = auto_categorize(payload.activity_name, payload.notes)
    else:
        category_str = category.value

    session_record = TimeSession(
        profile_id=payload.profile_id,
        activity_name=payload.activity_name,
        category=category_str,
        notes=payload.notes,
        started_at=datetime.now(UTC),
    )
    db.add(session_record)
    db.commit()
    db.refresh(session_record)

    # Try to start timer in TimingsApp
    if client is None:
        try:
            client = get_client(db)
        except TimingsAppNotConfiguredError:
            logger.info("TimingsApp not configured — local session only")
            return session_record

    project = CATEGORY_PROJECT_MAP.get(category_str, "Job Search")
    try:
        result = client.start_timer(
            project=project,
            title=session_record.activity_name,
            notes=session_record.notes,
        )
        entry_self = result.get("self", "")
        session_record.timingsapp_entry_id = entry_self
        session_record.timingsapp_project = project
        db.commit()
        db.refresh(session_record)
    except TimingsAppAPIError as exc:
        logger.warning("Failed to start TimingsApp timer: %s", exc)

    return session_record


def stop_session(
    db: Session,
    session_id: int,
    *,
    profile_id: int,
    notes: str | None = None,
    client: TimingsAppClient | None = None,
) -> TimeSession:
    """Stop a tracked time session.

    Updates the session with stop time and duration, and optionally
    stops the timer in TimingsApp.
    """
    session_record = (
        db.query(TimeSession)
        .filter(
            TimeSession.id == session_id,
            TimeSession.profile_id == profile_id,
        )
        .first()
    )
    if session_record is None:
        raise TimeSessionNotFoundError(
            f"Time session {session_id} not found for profile {profile_id}"
        )
    if session_record.stopped_at is not None:
        raise TimeSessionAlreadyStoppedError(
            f"Time session {session_id} is already stopped"
        )

    now = datetime.now(UTC)
    session_record.stopped_at = now

    # Compute duration
    started = session_record.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    session_record.duration_seconds = (now - started).total_seconds()

    if notes:
        if session_record.notes:
            session_record.notes += f"\n{notes}"
        else:
            session_record.notes = notes

    db.commit()
    db.refresh(session_record)

    # Try to stop timer in TimingsApp
    if client is None:
        try:
            client = get_client(db)
        except TimingsAppNotConfiguredError:
            return session_record

    if session_record.timingsapp_entry_id:
        try:
            client.stop_timer()
        except TimingsAppAPIError as exc:
            logger.warning("Failed to stop TimingsApp timer: %s", exc)

    return session_record


def get_session(
    db: Session,
    session_id: int,
    *,
    profile_id: int,
) -> TimeSession:
    """Get a time session by ID, scoped to profile."""
    session_record = (
        db.query(TimeSession)
        .filter(
            TimeSession.id == session_id,
            TimeSession.profile_id == profile_id,
        )
        .first()
    )
    if session_record is None:
        raise TimeSessionNotFoundError(
            f"Time session {session_id} not found for profile {profile_id}"
        )
    return session_record


def list_sessions(
    db: Session,
    *,
    profile_id: int,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TimeSession], int]:
    """List time sessions for a profile with optional category filter."""
    query = db.query(TimeSession).filter(TimeSession.profile_id == profile_id)

    if category:
        query = query.filter(TimeSession.category == category)

    total = query.count()
    sessions = (
        query.order_by(TimeSession.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return sessions, total


def get_running_session(
    db: Session,
    *,
    profile_id: int,
) -> TimeSession | None:
    """Get the currently running (unstopped) session for a profile."""
    return (
        db.query(TimeSession)
        .filter(
            TimeSession.profile_id == profile_id,
            TimeSession.stopped_at.is_(None),
        )
        .order_by(TimeSession.started_at.desc())
        .first()
    )


def update_session(
    db: Session,
    session_id: int,
    payload: TimeSessionUpdate,
    *,
    profile_id: int,
) -> TimeSession:
    """Update a time session."""
    session_record = get_session(db, session_id, profile_id=profile_id)

    if payload.activity_name is not None:
        session_record.activity_name = payload.activity_name
    if payload.category is not None:
        session_record.category = payload.category.value
    if payload.notes is not None:
        session_record.notes = payload.notes

    db.commit()
    db.refresh(session_record)
    return session_record


# ---------------------------------------------------------------------------
# Time analytics
# ---------------------------------------------------------------------------


def get_time_analytics(
    db: Session,
    *,
    profile_id: int,
    weeks: int = 4,
) -> TimeAnalyticsResponse:
    """Compute time analytics for a profile.

    Returns total hours, category breakdown, and weekly trend.
    """
    now = datetime.now(UTC)
    start_of_period = now - timedelta(weeks=weeks)

    # Get all completed sessions in the period
    sessions = (
        db.query(TimeSession)
        .filter(
            TimeSession.profile_id == profile_id,
            TimeSession.started_at >= start_of_period,
            TimeSession.stopped_at.isnot(None),
        )
        .all()
    )

    # Also include running sessions (count time so far)
    running = (
        db.query(TimeSession)
        .filter(
            TimeSession.profile_id == profile_id,
            TimeSession.started_at >= start_of_period,
            TimeSession.stopped_at.is_(None),
        )
        .all()
    )

    all_sessions = sessions + running

    # --- Total hours ---
    total_seconds = 0.0
    for s in sessions:
        if s.duration_seconds:
            total_seconds += s.duration_seconds

    # Add running time for active sessions
    for s in running:
        started = s.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        total_seconds += (now - started).total_seconds()

    total_hours = round(total_seconds / 3600, 2)
    total_sessions_count = len(all_sessions)

    # --- Category breakdown ---
    category_seconds: dict[str, float] = {}
    category_counts: dict[str, int] = {}
    all_categories = [c.value for c in ActivityCategory]

    for cat in all_categories:
        category_seconds[cat] = 0.0
        category_counts[cat] = 0

    for s in sessions:
        cat = s.category
        if cat in category_seconds:
            category_seconds[cat] += s.duration_seconds or 0.0
            category_counts[cat] += 1

    for s in running:
        cat = s.category
        if cat in category_seconds:
            started = s.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            category_seconds[cat] += (now - started).total_seconds()
            category_counts[cat] += 1

    breakdown: list[CategoryBreakdown] = []
    for cat in all_categories:
        cat_hours = round(category_seconds[cat] / 3600, 2)
        pct = round((category_seconds[cat] / total_seconds * 100) if total_seconds > 0 else 0.0, 1)
        breakdown.append(
            CategoryBreakdown(
                category=cat,
                total_hours=cat_hours,
                percentage=pct,
                session_count=category_counts[cat],
            )
        )

    # --- Weekly trend (4-week) ---
    weekly_trend: list[WeeklyTrend] = []

    for i in range(weeks):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)

        # Monday of the week
        iso_year, iso_week, _ = week_start.isocalendar()
        week_monday = datetime.fromisocalendar(iso_year, iso_week, 1).replace(tzinfo=UTC)
        week_label = week_monday.strftime("%Y-%m-%d")

        week_total = 0.0
        week_cat_hours: dict[str, float] = {cat: 0.0 for cat in all_categories}

        for s in all_sessions:
            started = s.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)

            if week_start <= started < week_end:
                if s.duration_seconds:
                    secs = s.duration_seconds
                elif s.stopped_at is None:
                    secs = (now - started).total_seconds()
                else:
                    secs = 0.0
                week_total += secs
                cat = s.category
                if cat in week_cat_hours:
                    week_cat_hours[cat] += secs

        weekly_trend.append(
            WeeklyTrend(
                week=week_label,
                total_hours=round(week_total / 3600, 2),
                category_hours={
                    cat: round(hrs / 3600, 2)
                    for cat, hrs in week_cat_hours.items()
                },
            )
        )

    # Reverse so oldest week is first
    weekly_trend.reverse()

    # --- Avg daily hours ---
    days_in_period = weeks * 7
    avg_daily = round(total_hours / days_in_period, 2) if days_in_period > 0 else 0.0

    return TimeAnalyticsResponse(
        total_hours=total_hours,
        total_sessions=total_sessions_count,
        category_breakdown=breakdown,
        weekly_trend=weekly_trend,
        avg_daily_hours=avg_daily,
    )


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------


def check_timingsapp_connection(db: Session) -> tuple[bool, str]:
    """Test the TimingsApp API connection using stored credentials.

    Returns (success, message).
    """
    try:
        client = get_client(db)
    except TimingsAppNotConfiguredError as exc:
        return False, str(exc)

    try:
        ok = client.test_connection()
        if ok:
            row = (
                db.query(IntegrationConfig)
                .filter(IntegrationConfig.name == "timingsapp")
                .first()
            )
            if row:
                row.status = "connected"
                row.status_message = "TimingsApp API connection successful"
                row.last_tested_at = datetime.now(UTC)
                db.commit()
            return True, "TimingsApp API connection successful"
        return False, "TimingsApp API connection failed"
    except TimingsAppAPIError as exc:
        return False, f"TimingsApp API error: {exc}"
