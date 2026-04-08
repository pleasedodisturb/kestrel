"""Voice discussion mode service.

Supports three conversational modes, all STT-agnostic (work with any text input):
- cover_letter: brainstorm a cover letter referencing profile and application
- coaching: coaching dialogue with role-relevant questions and feedback
- job_evaluation: scored evaluation of a job with pros/cons
"""

from sqlalchemy.orm import Session

from career_os.ai.factory import get_ai_provider
from career_os.models.models import Application, Profile
from career_os.models.voice import VoiceMessage, VoiceSession
from career_os.schemas.ai import AIFeature

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ProfileNotFoundError(Exception):
    pass


class SessionNotFoundError(Exception):
    pass


class ApplicationNotFoundError(Exception):
    pass


class InvalidModeError(Exception):
    pass


VALID_MODES = {"cover_letter", "coaching", "job_evaluation"}


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


def create_session(
    db: Session,
    *,
    profile_id: int,
    mode: str,
    application_id: int | None = None,
    title: str | None = None,
) -> VoiceSession:
    """Create a new voice discussion session."""
    # Validate profile
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    # Validate mode
    if mode not in VALID_MODES:
        raise InvalidModeError(
            f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(VALID_MODES))}"
        )

    # Require application_id for cover_letter mode
    if mode == "cover_letter" and application_id is None:
        raise InvalidModeError(
            "cover_letter mode requires an application_id. "
            "Start a cover letter brainstorm from an application detail page."
        )

    # Validate application_id if provided
    app = None
    if application_id is not None:
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.profile_id == profile_id,
                Application.archived_at.is_(None),
            )
            .first()
        )
        if not app:
            raise ApplicationNotFoundError(
                f"Application {application_id} not found for profile {profile_id}"
            )

    # Auto-generate title if not provided
    if not title:
        if mode == "cover_letter" and app:
            title = f"Cover Letter Brainstorm — {app.company} ({app.role})"
        elif mode == "coaching":
            title = "Coaching Session"
        elif mode == "job_evaluation" and app:
            title = f"Job Evaluation — {app.company} ({app.role})"
        else:
            title = f"Voice Discussion ({mode})"

    session = VoiceSession(
        profile_id=profile_id,
        application_id=application_id,
        mode=mode,
        title=title,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Add system welcome message
    welcome = _generate_welcome(mode, app)
    welcome_msg = VoiceMessage(
        session_id=session.id,
        role="assistant",
        content=welcome,
    )
    db.add(welcome_msg)
    db.commit()
    db.refresh(session)

    return session


def get_session(
    db: Session, *, session_id: int, profile_id: int
) -> VoiceSession:
    """Get a voice session by ID (profile-scoped)."""
    session = (
        db.query(VoiceSession)
        .filter(
            VoiceSession.id == session_id,
            VoiceSession.profile_id == profile_id,
        )
        .first()
    )
    if not session:
        raise SessionNotFoundError(
            f"Voice session {session_id} not found for profile {profile_id}"
        )
    return session


def list_sessions(
    db: Session, *, profile_id: int, mode: str | None = None
) -> list[VoiceSession]:
    """List voice sessions for a profile, optionally filtered by mode."""
    query = (
        db.query(VoiceSession)
        .filter(VoiceSession.profile_id == profile_id)
        .order_by(VoiceSession.updated_at.desc())
    )
    if mode:
        query = query.filter(VoiceSession.mode == mode)
    return list(query.all())


async def send_message(
    db: Session,
    *,
    session_id: int,
    profile_id: int,
    content: str,
) -> tuple[VoiceMessage, VoiceMessage]:
    """Send a user message and get an AI response.

    Returns (user_message, assistant_message).
    """
    session = get_session(db, session_id=session_id, profile_id=profile_id)

    # Store user message
    user_msg = VoiceMessage(
        session_id=session.id,
        role="user",
        content=content,
    )
    db.add(user_msg)
    db.flush()

    # Build context for AI
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    app = None
    if session.application_id:
        app = (
            db.query(Application)
            .filter(Application.id == session.application_id)
            .first()
        )

    # Get conversation history
    history = (
        db.query(VoiceMessage)
        .filter(VoiceMessage.session_id == session.id)
        .order_by(VoiceMessage.created_at)
        .all()
    )

    # Generate AI response
    prompt = _build_prompt(session.mode, content, history, profile, app)
    context = _build_context(session.mode, profile, app)

    provider = get_ai_provider()
    ai_feature = _mode_to_feature(session.mode)
    ai_response = await provider.complete(
        prompt=prompt, feature=ai_feature, context=context
    )

    # Store assistant message
    assistant_msg = VoiceMessage(
        session_id=session.id,
        role="assistant",
        content=ai_response.content,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)
    db.refresh(session)

    return user_msg, assistant_msg


def complete_session(
    db: Session, *, session_id: int, profile_id: int
) -> VoiceSession:
    """Mark a voice session as completed."""
    session = get_session(db, session_id=session_id, profile_id=profile_id)
    session.status = "completed"
    db.commit()
    db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_welcome(mode: str, app: Application | None) -> str:
    """Generate a welcome message based on mode."""
    if mode == "cover_letter":
        if app:
            return (
                f"Let's brainstorm a cover letter for the {app.role} position at "
                f"{app.company}. I'll reference your profile strengths and tailor "
                f"the letter to this specific role. What aspects would you like "
                f"to emphasize? Your key achievements, technical skills, or "
                f"leadership experience?"
            )
        return (
            "Let's brainstorm a cover letter. Tell me about the role "
            "you're applying to and I'll help craft a compelling letter "
            "referencing your profile strengths."
        )

    if mode == "coaching":
        return (
            "Welcome to your coaching session! I'll ask you role-relevant "
            "questions and provide constructive feedback to help you prepare. "
            "What area would you like to focus on today? Interview prep, "
            "career strategy, skills development, or something else?"
        )

    if mode == "job_evaluation":
        if app:
            return (
                f"Let's evaluate the {app.role} position at {app.company}. "
                f"I'll help you assess fit, compensation, growth potential, "
                f"and provide a scored evaluation with pros and cons. "
                f"What's your initial impression of this opportunity?"
            )
        return (
            "Let's evaluate a job opportunity. Describe the role and "
            "company, and I'll provide a scored assessment with pros "
            "and cons referencing your profile."
        )

    return "Welcome! How can I help you today?"


def _mode_to_feature(mode: str) -> AIFeature:
    """Map voice mode to AI feature for mock provider."""
    feature_map = {
        "cover_letter": AIFeature.voice_cover_letter,
        "coaching": AIFeature.voice_coaching,
        "job_evaluation": AIFeature.voice_job_evaluation,
    }
    return feature_map.get(mode, AIFeature.complete)


def _build_prompt(
    mode: str,
    user_input: str,
    history: list[VoiceMessage],
    profile: Profile | None,
    app: Application | None,
) -> str:
    """Build a prompt for the AI provider including conversation context."""
    parts: list[str] = []

    # System context
    if mode == "cover_letter":
        parts.append(
            "You are a career coach helping brainstorm a cover letter. "
            "Be conversational, specific, and reference the user's profile strengths."
        )
        if app:
            parts.append(f"Target role: {app.role} at {app.company}")
            if app.notes:
                parts.append(f"Role notes: {app.notes}")
            if app.salary_range:
                parts.append(f"Salary range: {app.salary_range}")
    elif mode == "coaching":
        parts.append(
            "You are a career coach providing role-relevant questions and "
            "constructive feedback. Ask probing questions, give actionable advice."
        )
    elif mode == "job_evaluation":
        parts.append(
            "You are a career advisor evaluating a job opportunity. "
            "Provide a scored assessment with specific pros and cons "
            "referencing the user's profile and career goals."
        )
        if app:
            parts.append(f"Evaluating: {app.role} at {app.company}")
            if app.fit_score:
                parts.append(f"Current fit score: {app.fit_score}")
            if app.salary_range:
                parts.append(f"Salary range: {app.salary_range}")
            if app.notes:
                parts.append(f"Notes: {app.notes}")

    # Profile context
    if profile:
        parts.append(f"User profile: {profile.name}")
        if profile.location:
            parts.append(f"Location: {profile.location}")
        if profile.job_family:
            parts.append(f"Job family: {profile.job_family}")

    # Conversation history (last 10 messages for context window)
    recent = history[-10:] if len(history) > 10 else history
    if recent:
        parts.append("\nConversation so far:")
        for msg in recent:
            prefix = "User" if msg.role == "user" else "Assistant"
            parts.append(f"{prefix}: {msg.content}")

    # Current user input
    parts.append(f"\nUser: {user_input}")
    parts.append("\nAssistant:")

    return "\n".join(parts)


def _build_context(
    mode: str,
    profile: Profile | None,
    app: Application | None,
) -> dict:
    """Build context dict for AI provider."""
    context: dict = {"mode": mode}
    if profile:
        context["profile"] = {
            "name": profile.name,
            "location": profile.location,
            "job_family": profile.job_family,
        }
    if app:
        context["application"] = {
            "company": app.company,
            "role": app.role,
            "salary_range": app.salary_range,
            "fit_score": app.fit_score,
            "notes": app.notes,
        }
        context["company"] = app.company
        context["role"] = app.role
    return context
