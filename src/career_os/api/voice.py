"""Voice Discussion Mode API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import DESC_ACTIVE_PROFILE_ID, RESP_404, RESP_404_422
from career_os.database import get_db
from career_os.schemas.voice import (
    VoiceMessageCreate,
    VoiceMessageResponse,
    VoiceSendResponse,
    VoiceSessionCreate,
    VoiceSessionListResponse,
    VoiceSessionResponse,
)
from career_os.services.voice import (
    ApplicationNotFoundError,
    InvalidModeError,
    ProfileNotFoundError,
    SessionNotFoundError,
    complete_session,
    create_session,
    get_session,
    list_sessions,
    send_message,
)

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post(
    "/sessions",
    status_code=201,
    responses=RESP_404_422,
)
async def create_voice_session(
    data: VoiceSessionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> VoiceSessionResponse:
    """Create a new voice discussion session.

    Modes:
    - cover_letter: brainstorm cover letter (requires application_id)
    - coaching: career coaching dialogue
    - job_evaluation: evaluate a job opportunity (requires application_id)
    """
    try:
        session = create_session(
            db,
            profile_id=data.profile_id,
            mode=data.mode,
            application_id=data.application_id,
            title=data.title,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidModeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _session_response(session)


@router.get("/sessions")
async def list_voice_sessions(
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    mode: Annotated[str | None, Query(description="Filter by mode")] = None,
) -> VoiceSessionListResponse:
    """List voice discussion sessions for a profile."""
    sessions = list_sessions(db, profile_id=profile_id, mode=mode)
    return VoiceSessionListResponse(
        sessions=[_session_response(s) for s in sessions],
        total=len(sessions),
    )


@router.get("/sessions/{session_id}", responses=RESP_404)
async def get_voice_session(
    session_id: int,
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> VoiceSessionResponse:
    """Get a voice session with all messages."""
    try:
        session = get_session(db, session_id=session_id, profile_id=profile_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _session_response(session)


@router.post(
    "/sessions/{session_id}/messages",
    responses=RESP_404,
)
async def send_voice_message(
    session_id: int,
    data: VoiceMessageCreate,
    db: Annotated[Session, Depends(get_db)],
) -> VoiceSendResponse:
    """Send a message in a voice session and receive AI response.

    Accepts text from any STT tool (SuperWhisper, MacWhisper, system dictation)
    or directly typed input.
    """
    try:
        user_msg, assistant_msg = await send_message(
            db,
            session_id=session_id,
            profile_id=data.profile_id,
            content=data.content,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session = get_session(db, session_id=session_id, profile_id=data.profile_id)

    return VoiceSendResponse(
        user_message=VoiceMessageResponse.model_validate(user_msg),
        assistant_message=VoiceMessageResponse.model_validate(assistant_msg),
        session=_session_response(session),
    )


@router.post(
    "/sessions/{session_id}/complete",
    responses=RESP_404,
)
async def complete_voice_session(
    session_id: int,
    profile_id: Annotated[int, Query(description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> VoiceSessionResponse:
    """Mark a voice session as completed."""
    try:
        session = complete_session(db, session_id=session_id, profile_id=profile_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _session_response(session)


def _session_response(session) -> VoiceSessionResponse:
    """Convert a VoiceSession ORM object to response schema."""
    return VoiceSessionResponse(
        id=session.id,
        profile_id=session.profile_id,
        application_id=session.application_id,
        mode=session.mode,
        title=session.title,
        status=session.status,
        messages=[VoiceMessageResponse.model_validate(m) for m in session.messages],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
