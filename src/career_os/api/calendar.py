"""Calendar integration API routes.

Covers:
- VAL-CAL-001: Interview creates calendar event with all details
- VAL-CAL-002: Follow-up dates as calendar events
- VAL-CAL-003: Prep reminders before interviews (configurable)
- VAL-CAL-004: Multi-provider support (iCal, Google Calendar, Fantastical)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.models.models import FollowUp
from career_os.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventListResponse,
    CalendarEventResponse,
    CalendarEventUpdate,
    CalendarProviderConfigResponse,
    FantasticalUrlResponse,
    GoogleCalendarUrlResponse,
)
from career_os.services.calendar import (
    ApplicationNotFoundError,
    CalendarEventNotFoundError,
    ProfileNotFoundError,
    create_calendar_event,
    create_follow_up_calendar_event,
    delete_calendar_event,
    export_event_ical,
    export_events_ical,
    generate_fantastical_url,
    generate_google_calendar_url,
    get_calendar_event,
    get_event_provider_urls,
    list_calendar_events,
    update_calendar_event,
)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.post("/events", status_code=201, responses={404: {"description": "Not found"}})
async def create_event(
    payload: CalendarEventCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CalendarEventResponse:
    """Create a calendar event (interview, follow-up, or prep reminder).

    For interviews, a prep reminder is auto-created at the configured lead time.
    """
    try:
        event = create_calendar_event(db, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CalendarEventResponse.model_validate(event)


@router.get("/events")
async def list_events(
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
    event_type: Annotated[str | None, Query(description="Filter by event type")] = None,
    application_id: Annotated[int | None, Query(description="Filter by application")] = None,
) -> CalendarEventListResponse:
    """List calendar events for a profile with optional filters."""
    events, total = list_calendar_events(
        db,
        profile_id=profile_id,
        event_type=event_type,
        application_id=application_id,
    )
    return CalendarEventListResponse(
        events=[CalendarEventResponse.model_validate(e) for e in events],
        total=total,
    )


@router.get("/events/{event_id}", responses={404: {"description": "Not found"}})
async def get_event(
    event_id: int,
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> CalendarEventResponse:
    """Get a single calendar event by ID."""
    try:
        event = get_calendar_event(db, event_id, profile_id=profile_id)
    except CalendarEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CalendarEventResponse.model_validate(event)


@router.patch("/events/{event_id}", responses={404: {"description": "Not found"}})
async def update_event(
    event_id: int,
    payload: CalendarEventUpdate,
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> CalendarEventResponse:
    """Update a calendar event.

    If start_time is changed on an interview event, associated prep reminders are updated.
    """
    try:
        event = update_calendar_event(db, event_id, payload, profile_id=profile_id)
    except CalendarEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CalendarEventResponse.model_validate(event)


@router.delete(
    "/events/{event_id}",
    status_code=204,
    responses={404: {"description": "Not found"}},
)
async def delete_event(
    event_id: int,
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a calendar event."""
    try:
        delete_calendar_event(db, event_id, profile_id=profile_id)
    except CalendarEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Follow-up -> Calendar event
# ---------------------------------------------------------------------------


@router.post(
    "/events/from-follow-up/{follow_up_id}",
    status_code=201,
    responses={404: {"description": "Not found"}},
)
async def create_from_follow_up(
    follow_up_id: int,
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> CalendarEventResponse:
    """Create a calendar event from a follow-up."""
    follow_up = (
        db.query(FollowUp)
        .filter(
            FollowUp.id == follow_up_id,
            FollowUp.profile_id == profile_id,
        )
        .first()
    )
    if not follow_up:
        raise HTTPException(status_code=404, detail=f"Follow-up {follow_up_id} not found")
    event = create_follow_up_calendar_event(db, follow_up)
    return CalendarEventResponse.model_validate(event)


# ---------------------------------------------------------------------------
# iCal export (Provider 1)
# ---------------------------------------------------------------------------


@router.get("/events/{event_id}/ical", responses={404: {"description": "Not found"}})
async def export_ical(
    event_id: int,
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Export a single calendar event as .ics file.

    Returns text/calendar content type for direct download.
    """
    try:
        ical_data = export_event_ical(db, event_id, profile_id=profile_id)
    except CalendarEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        content=ical_data,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="event-{event_id}.ics"'},
    )


@router.get("/export/ical")
async def export_all_ical(
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
    event_type: Annotated[str | None, Query(description="Filter by event type")] = None,
    application_id: Annotated[int | None, Query(description="Filter by application")] = None,
) -> Response:
    """Export calendar events as .ics file.

    Supports filtering by event type and application.
    """
    ical_data = export_events_ical(
        db,
        profile_id=profile_id,
        event_type=event_type,
        application_id=application_id,
    )
    return Response(
        content=ical_data,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="career-os-events.ics"'},
    )


# ---------------------------------------------------------------------------
# Google Calendar URL (Provider 2)
# ---------------------------------------------------------------------------


@router.get("/events/{event_id}/google", responses={404: {"description": "Not found"}})
async def google_calendar_url(
    event_id: int,
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> GoogleCalendarUrlResponse:
    """Get a Google Calendar 'Add Event' URL for an event."""
    try:
        url = generate_google_calendar_url(db, event_id, profile_id=profile_id)
    except CalendarEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GoogleCalendarUrlResponse(url=url, event_id=event_id)


# ---------------------------------------------------------------------------
# Fantastical URL (Provider 3)
# ---------------------------------------------------------------------------


@router.get("/events/{event_id}/fantastical", responses={404: {"description": "Not found"}})
async def fantastical_url(
    event_id: int,
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> FantasticalUrlResponse:
    """Get a Fantastical URL scheme for adding an event."""
    try:
        url = generate_fantastical_url(db, event_id, profile_id=profile_id)
    except CalendarEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FantasticalUrlResponse(url=url, event_id=event_id)


# ---------------------------------------------------------------------------
# Multi-provider export
# ---------------------------------------------------------------------------


@router.get("/events/{event_id}/providers", responses={404: {"description": "Not found"}})
async def event_providers(
    event_id: int,
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> CalendarProviderConfigResponse:
    """Get export URLs/data for all supported calendar providers."""
    try:
        providers = get_event_provider_urls(db, event_id, profile_id=profile_id)
    except CalendarEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CalendarProviderConfigResponse(event_id=event_id, providers=providers)
