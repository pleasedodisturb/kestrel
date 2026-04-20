"""Onboarding service: step completion logic and progress computation.

Business rules:
- Steps can be completed in any order (D-07).
- Re-completing a step is a no-op — original timestamp is preserved (D-06).
- OnboardingState row is created on first mark_step_complete call, not on profile creation (D-13).
- GET for a profile with no state row returns a synthesized empty response (A2 assumption).
"""

from sqlalchemy.orm import Session

from career_os.errors.onboarding import OnboardingValidationError
from career_os.models.models import _utcnow
from career_os.models.onboarding import OnboardingState
from career_os.schemas.onboarding import VALID_STEPS, OnboardingStatusResponse

# Step order defines next_step computation (first incomplete step wins).
# Must match VALID_STEPS from schemas/onboarding.py.
STEP_ORDER: list[str] = [
    "profile_started",
    "profile_completed",
    "demo_seeded",
    "welcome_completed",
    "tour_completed",
    "feedback_prompted",
    "completed",
]


def _compute_next_step(state: OnboardingState) -> str | None:
    """Return the first incomplete step in STEP_ORDER, or None if all done."""
    for step in STEP_ORDER:
        if getattr(state, f"{step}_at") is None:
            return step
    return None


def _compute_progress_pct(state: OnboardingState) -> int:
    """Return percentage of steps completed (0-100, integer)."""
    total = len(STEP_ORDER)
    done = sum(1 for s in STEP_ORDER if getattr(state, f"{s}_at") is not None)
    return int((done / total) * 100)


def _build_response(profile_id: int, state: OnboardingState | None) -> OnboardingStatusResponse:
    """Build OnboardingStatusResponse from an OnboardingState row or synthesized empty state."""
    if state is None:
        return OnboardingStatusResponse(
            profile_id=profile_id,
            current_step=None,
            next_step=STEP_ORDER[0],  # first step is always next for a new user
            is_complete=False,
            progress_pct=0,
        )

    next_step = _compute_next_step(state)
    progress_pct = _compute_progress_pct(state)
    is_complete = next_step is None

    # Build response by copying all columns from the ORM object
    return OnboardingStatusResponse(
        profile_id=state.profile_id,
        current_step=state.current_step,
        next_step=next_step,
        is_complete=is_complete,
        progress_pct=progress_pct,
        profile_started_at=state.profile_started_at,
        profile_completed_at=state.profile_completed_at,
        demo_seeded_at=state.demo_seeded_at,
        welcome_completed_at=state.welcome_completed_at,
        tour_completed_at=state.tour_completed_at,
        feedback_prompted_at=state.feedback_prompted_at,
        completed_at=state.completed_at,
        profile_started_via=state.profile_started_via,
        profile_completed_via=state.profile_completed_via,
        demo_seeded_via=state.demo_seeded_via,
        welcome_completed_via=state.welcome_completed_via,
        tour_completed_via=state.tour_completed_via,
        feedback_prompted_via=state.feedback_prompted_via,
        completed_via=state.completed_via,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


def get_onboarding_status(profile_id: int, db: Session) -> OnboardingStatusResponse:
    """Return the current onboarding status for a profile.

    If no OnboardingState row exists yet (profile never patched), returns a
    synthesized empty response with all steps incomplete (assumption A2).
    Caller is responsible for verifying profile_id exists before calling.
    """
    state = db.query(OnboardingState).filter(OnboardingState.profile_id == profile_id).first()
    return _build_response(profile_id, state)


def mark_step_complete(
    step: str,
    via: str,
    profile_id: int,
    db: Session,
) -> OnboardingStatusResponse:
    """Mark a step complete for a profile and return updated state.

    Creates the OnboardingState row if it does not exist yet (D-13).
    Idempotent: re-completing a step preserves the original timestamp (D-06).
    Step ordering is NOT enforced (D-07).

    Raises:
        OnboardingValidationError: If step is not in VALID_STEPS.
        (Profile existence is validated in the API route before calling this function.)
    """
    if step not in VALID_STEPS:
        raise OnboardingValidationError(
            user_message=f"Unknown onboarding step: '{step}'.",
            resolution=(
                f"Valid steps are: {', '.join(VALID_STEPS)}. Check the step name and try again."
            ),
        )

    # Get or create the OnboardingState row (D-13: lazy creation on first PATCH)
    state = db.query(OnboardingState).filter(OnboardingState.profile_id == profile_id).first()
    if state is None:
        state = OnboardingState(profile_id=profile_id)
        db.add(state)
        db.flush()  # assigns id without committing, allows further updates in same transaction

    # Idempotency check (D-06): if timestamp already set, do not overwrite
    at_field = f"{step}_at"
    via_field = f"{step}_via"

    if getattr(state, at_field) is not None:
        # Already completed — return current state unchanged
        db.commit()
        db.refresh(state)
        return _build_response(profile_id, state)

    # Set timestamp server-side (D-05) and record source surface (D-02)
    setattr(state, at_field, _utcnow())
    setattr(state, via_field, via)
    state.current_step = step  # track last-completed step for resume (D-03)

    db.commit()
    db.refresh(state)
    return _build_response(profile_id, state)
