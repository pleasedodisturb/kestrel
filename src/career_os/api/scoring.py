"""Scoring API routes - AI-powered job scoring engine."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from career_os.ai.base import ProviderQuotaError
from career_os.ai.openrouter_provider import CreditsExhaustedError
from career_os.api.constants import DESC_PROFILE_ID, RESP_404
from career_os.database import get_db
from career_os.schemas.constraints import INT32_MAX
from career_os.schemas.scoring import (
    BatchScoreRequest,
    BatchScoreResponse,
    FeedbackCreate,
    FeedbackResponse,
    FeedbackStats,
    ProfileCompletenessResponse,
    ScoreContextResponse,
    ScoreRequest,
    ScoreResponse,
    ScoringWeightsResponse,
    ScoringWeightsUpdate,
    SuggestionsResponse,
    WeightSuggestionResponse,
)
from career_os.services.preference_learning import (
    SUGGESTION_MIN_FEEDBACK,
    generate_suggestions,
)
from career_os.services.pushover import send_credits_exhausted_alert
from career_os.services.scoring import (
    FeedbackNotFoundError,
    InvalidFeedbackError,
    JobNotFoundError,
    ProfileIncompleteError,
    ProfileNotFoundError,
    ScoringError,
    apply_confidence_range,
    batch_score_discovery,
    compute_profile_completeness,
    compute_score_context,
    flag_stale_scores,
    get_feedback_stats,
    get_or_create_weights,
    get_score_for_application,
    get_score_for_job,
    list_feedback,
    score_job,
    submit_feedback,
    update_weights,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scoring"])


# ---------------------------------------------------------------------------
# Single Job Scoring
# ---------------------------------------------------------------------------


@router.post(
    "/api/score",
    status_code=201,
    responses={
        **RESP_404,
        402: {"description": "Payment required"},
        422: {"description": "Profile incomplete"},
        500: {"description": "Internal server error"},
        502: {"description": "Bad gateway"},
    },
)
async def score_endpoint(
    payload: ScoreRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ScoreResponse:
    """Score a job against a profile.

    Returns full score breakdown including fit_score, readiness_score,
    career_alignment, reasoning, estimated_salary, effort_flag, prep_level,
    and prep_notes.
    """
    try:
        scored = await score_job(
            db,
            payload.profile_id,
            payload.job_description,
            job_url=payload.job_url,
            job_title=payload.job_title,
            job_company=payload.job_company,
            discovered_job_id=payload.discovered_job_id,
            application_id=payload.application_id,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileIncompleteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CreditsExhaustedError, ProviderQuotaError) as exc:
        raise HTTPException(
            status_code=402,
            detail=f"AI scoring credits exhausted: {exc}",
        ) from exc
    except ScoringError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scoring error: {exc}") from exc

    return ScoreResponse.model_validate(scored)


# ---------------------------------------------------------------------------
# Scoring Weights
# ---------------------------------------------------------------------------


@router.get("/api/scoring-weights", responses=RESP_404)
async def get_weights_endpoint(
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> ScoringWeightsResponse:
    """Get scoring weights for a profile."""
    try:
        weights = get_or_create_weights(db, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ScoringWeightsResponse.model_validate(weights)


@router.put("/api/scoring-weights", responses=RESP_404)
async def update_weights_endpoint(
    payload: ScoringWeightsUpdate,
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> ScoringWeightsResponse:
    """Update scoring weights for a profile.

    Marks all existing scores for this profile as stale.
    """
    try:
        weights = update_weights(
            db,
            profile_id,
            payload.model_dump(exclude_none=True),
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ScoringWeightsResponse.model_validate(weights)


# ---------------------------------------------------------------------------
# Batch Scoring
# ---------------------------------------------------------------------------


@router.post(
    "/api/score/batch",
    responses={
        **RESP_404,
        422: {"description": "Profile incomplete"},
        500: {"description": "Internal server error"},
    },
)
async def batch_score_endpoint(
    payload: BatchScoreRequest,
    db: Annotated[Session, Depends(get_db)],
) -> BatchScoreResponse:
    """Batch score discovered jobs for a profile.

    If discovered_job_ids is empty, scores all unscored jobs.
    """
    try:
        result = await batch_score_discovery(
            db,
            payload.profile_id,
            discovered_job_ids=payload.discovered_job_ids or None,
            rescore_stale=payload.rescore_stale,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileIncompleteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Batch scoring error: {exc}") from exc

    credits_exhausted = result.get("credits_exhausted", False)

    if credits_exhausted:
        try:
            send_credits_exhausted_alert(
                db,
                profile_id=payload.profile_id,
                scored_count=result["scored_count"],
                total_count=result["scored_count"] + len(result.get("errors", [])),
            )
        except Exception:
            logger.warning("Could not send Pushover notification for credits exhausted")

    return BatchScoreResponse(
        scored_count=result["scored_count"],
        total_time_seconds=result["total_time_seconds"],
        scores=[ScoreResponse.model_validate(s) for s in result["scores"]],
        errors=result["errors"],
        credits_exhausted=credits_exhausted,
    )


# ---------------------------------------------------------------------------
# Score Context Helper
# ---------------------------------------------------------------------------


def _build_score_context(
    db: Session, profile_id: int, fit_score: float
) -> ScoreContextResponse | None:
    """Compute and return a ScoreContextResponse, or None when data is insufficient."""
    ctx = compute_score_context(db, profile_id, fit_score)
    if ctx is None:
        return None
    return ScoreContextResponse(**ctx)


# ---------------------------------------------------------------------------
# Profile Completeness Helper (Epic 10 / G-278)
# ---------------------------------------------------------------------------


def _build_profile_completeness(
    db: Session, profile_id: int, fit_score: float
) -> ProfileCompletenessResponse:
    """Compute and return a ProfileCompletenessResponse for the given profile and score.

    The confidence_range is centered on the actual fit_score so clients get
    concrete lower/upper bounds (e.g. "6.2 – 8.8") rather than a raw half-width.

    An improvement_hint is included when completeness < 50% to prompt the user.
    """
    result = compute_profile_completeness(db, profile_id)
    half_width: float = result["half_width"]
    low_bound, high_bound = apply_confidence_range(fit_score, half_width)
    missing_fields: list[str] = result["missing_fields"]

    hint: str | None = None
    if missing_fields:
        fields_str = ", ".join(missing_fields)
        hint = f"This score has high uncertainty. Add {fields_str} to improve accuracy."

    return ProfileCompletenessResponse(
        completeness=result["completeness"],
        confidence_range=(low_bound, high_bound),
        missing_fields=missing_fields,
        improvement_hint=hint,
    )


# ---------------------------------------------------------------------------
# Score Retrieval
# ---------------------------------------------------------------------------


@router.get("/api/score/job/{discovered_job_id}", responses=RESP_404)
async def get_job_score_endpoint(
    discovered_job_id: Annotated[int, Path(ge=1, le=INT32_MAX)],
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> ScoreResponse | None:
    """Get the latest score for a discovered job.

    Includes ``score_context`` (percentile/rank) when the profile has >= 5 scored jobs.
    """
    scored = get_score_for_job(db, profile_id, discovered_job_id)
    if not scored:
        raise HTTPException(status_code=404, detail="No score found for this job")
    response = ScoreResponse.model_validate(scored)
    response.score_context = _build_score_context(db, profile_id, scored.fit_score)
    response.profile_completeness = _build_profile_completeness(db, profile_id, scored.fit_score)
    return response


@router.get(
    "/api/score/application/{application_id}",
    responses=RESP_404,
)
async def get_application_score_endpoint(
    application_id: Annotated[int, Path(ge=1, le=INT32_MAX)],
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> ScoreResponse | None:
    """Get the latest score for an application.

    Includes ``score_context`` (percentile/rank) when the profile has >= 5 scored jobs.
    """
    scored = get_score_for_application(db, profile_id, application_id)
    if not scored:
        raise HTTPException(status_code=404, detail="No score found for this application")
    response = ScoreResponse.model_validate(scored)
    response.score_context = _build_score_context(db, profile_id, scored.fit_score)
    response.profile_completeness = _build_profile_completeness(db, profile_id, scored.fit_score)
    return response


# ---------------------------------------------------------------------------
# Profile Switch / Stale Scores
# ---------------------------------------------------------------------------


@router.post("/api/scoring/flag-stale")
async def flag_stale_endpoint(
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    """Mark all scores for a profile as stale.

    Called when profile changes that could affect scoring (e.g., profile switch,
    skills update, goals change).
    """
    count = flag_stale_scores(db, profile_id)
    return {"stale_count": count}


# ---------------------------------------------------------------------------
# Scoring Feedback (Epic 6 / G-274)
# ---------------------------------------------------------------------------


@router.post(
    "/api/score/{scored_job_id}/feedback",
    status_code=201,
    responses={
        **RESP_404,
        400: {"description": "Invalid feedback data"},
    },
)
async def submit_feedback_endpoint(
    scored_job_id: Annotated[int, Path(ge=1, le=INT32_MAX)],
    payload: FeedbackCreate,
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> FeedbackResponse:
    """Submit user feedback on an AI-generated score.

    Accepts explicit corrections (too_high, too_low, correct) with an optional
    user_score (0-10) and free-text reason. Records a snapshot of the original
    AI score for calibration purposes.
    """
    try:
        feedback = submit_feedback(
            db,
            scored_job_id=scored_job_id,
            profile_id=profile_id,
            direction=payload.direction.value,
            user_score=payload.user_score,
            reason=payload.reason,
        )
    except FeedbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidFeedbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FeedbackResponse.model_validate(feedback)


@router.get("/api/score/feedback")
async def list_feedback_endpoint(
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> list[FeedbackResponse]:
    """List all feedback records for a profile, newest first."""
    records = list_feedback(db, profile_id)
    return [FeedbackResponse.model_validate(r) for r in records]


@router.get("/api/score/feedback/stats")
async def feedback_stats_endpoint(
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> FeedbackStats:
    """Return summary statistics for feedback submitted by a profile.

    Includes total count, explicit vs implicit breakdown, average deviation,
    and per-direction counts.
    """
    stats = get_feedback_stats(db, profile_id)
    return FeedbackStats(**stats)


# ---------------------------------------------------------------------------
# Bayesian Preference Learning (Epic 11 / G-279)
# ---------------------------------------------------------------------------


@router.get("/api/score/suggestions")
async def suggestions_endpoint(
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> SuggestionsResponse:
    """Get weight adjustment suggestions based on accumulated feedback.

    Analyzes patterns in user feedback (explicit corrections and implicit
    signals) using a Bayesian preference model to suggest scoring weight
    changes. Returns suggestions only when ≥15 feedback records exist and
    the model has sufficient confidence.

    Suggestions are presented for review — they are never auto-applied.
    """
    from career_os.models.scoring import ScoringFeedback as SFModel

    feedback_count = db.query(SFModel).filter(SFModel.profile_id == profile_id).count()
    ready = feedback_count >= SUGGESTION_MIN_FEEDBACK

    if not ready:
        return SuggestionsResponse(
            suggestions=[],
            feedback_count=feedback_count,
            min_feedback_required=SUGGESTION_MIN_FEEDBACK,
            ready=False,
        )

    suggestions = generate_suggestions(db, profile_id)
    return SuggestionsResponse(
        suggestions=[WeightSuggestionResponse(**s.to_dict()) for s in suggestions],
        feedback_count=feedback_count,
        min_feedback_required=SUGGESTION_MIN_FEEDBACK,
        ready=True,
    )
