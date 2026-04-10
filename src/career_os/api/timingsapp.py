"""TimingsApp integration API routes.

Provides endpoints for:
- Starting/stopping tracked time sessions
- Listing sessions with filtering
- Time analytics (total hours, category breakdown, 4-week trend)
- Running session status
- Connection testing
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import (
    DESC_FILTER_BY_CATEGORY,
    DESC_PROFILE_ID,
    RESP_NOT_FOUND,
    TIME_SESSION_NOT_FOUND,
)
from career_os.database import get_db
from career_os.schemas.timingsapp import (
    TimeAnalyticsResponse,
    TimeSessionCreate,
    TimeSessionListResponse,
    TimeSessionResponse,
    TimeSessionStop,
    TimeSessionUpdate,
)
from career_os.services.timingsapp import (
    ConcurrentSessionError,
    TimeSessionAlreadyStoppedError,
    TimeSessionNotFoundError,
    check_timingsapp_connection,
    get_running_session,
    get_session,
    get_time_analytics,
    list_sessions,
    start_session,
    stop_session,
    update_session,
)

router = APIRouter(prefix="/api/timingsapp", tags=["timingsapp"])


@router.post("/sessions", status_code=201, responses={409: {"description": "Conflict"}})
async def create_session(
    payload: TimeSessionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> TimeSessionResponse:
    """Start a new tracked time session.

    Creates a local session record and optionally starts a timer
    in TimingsApp if the integration is configured and enabled.
    Category is auto-assigned from context if not provided.
    """
    try:
        session_record = start_session(db, payload)
    except ConcurrentSessionError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    return TimeSessionResponse.model_validate(session_record)


@router.put(
    "/sessions/{session_id}/stop",
    responses={400: {"description": "Bad request"}, 404: {"description": RESP_NOT_FOUND}},
)
async def stop_session_endpoint(
    session_id: int,
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    payload: TimeSessionStop | None = None,
) -> TimeSessionResponse:
    """Stop a tracked time session.

    Updates the session with stop time, duration, and optionally
    stops the timer in TimingsApp.
    """
    try:
        session_record = stop_session(
            db,
            session_id,
            profile_id=profile_id,
            notes=payload.notes if payload else None,
        )
        return TimeSessionResponse.model_validate(session_record)
    except TimeSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=TIME_SESSION_NOT_FOUND) from exc
    except TimeSessionAlreadyStoppedError as exc:
        raise HTTPException(status_code=400, detail="Session is already stopped") from exc


@router.get("/sessions")
async def list_sessions_endpoint(
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[str | None, Query(description=DESC_FILTER_BY_CATEGORY)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TimeSessionListResponse:
    """List tracked time sessions for a profile."""
    sessions, total = list_sessions(
        db,
        profile_id=profile_id,
        category=category,
        limit=limit,
        offset=offset,
    )
    return TimeSessionListResponse(
        sessions=[TimeSessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.get("/sessions/running")
async def get_running_session_endpoint(
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> TimeSessionResponse | None:
    """Get the currently running (unstopped) time session, or null."""
    session_record = get_running_session(db, profile_id=profile_id)
    if session_record is None:
        return None
    return TimeSessionResponse.model_validate(session_record)


@router.get("/sessions/{session_id}", responses={404: {"description": RESP_NOT_FOUND}})
async def get_session_endpoint(
    session_id: int,
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> TimeSessionResponse:
    """Get a specific time session by ID."""
    try:
        session_record = get_session(db, session_id, profile_id=profile_id)
        return TimeSessionResponse.model_validate(session_record)
    except TimeSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=TIME_SESSION_NOT_FOUND) from exc


@router.patch("/sessions/{session_id}", responses={404: {"description": RESP_NOT_FOUND}})
async def update_session_endpoint(
    session_id: int,
    payload: TimeSessionUpdate,
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> TimeSessionResponse:
    """Update a time session's details."""
    try:
        session_record = update_session(db, session_id, payload, profile_id=profile_id)
        return TimeSessionResponse.model_validate(session_record)
    except TimeSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=TIME_SESSION_NOT_FOUND) from exc


@router.get("/analytics")
async def get_analytics(
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    weeks: Annotated[int, Query(ge=1, le=52, description="Number of weeks to analyze")] = 4,
) -> TimeAnalyticsResponse:
    """Get time analytics with total hours, category breakdown, and weekly trend."""
    return get_time_analytics(db, profile_id=profile_id, weeks=weeks)


@router.post("/test")
async def test_connection(
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Test the TimingsApp API connection using stored credentials."""
    success, message = check_timingsapp_connection(db)
    return {
        "success": success,
        "message": message,
    }
