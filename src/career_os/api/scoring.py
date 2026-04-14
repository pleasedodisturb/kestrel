"""Scoring API routes - AI-powered job scoring engine."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.ai.base import ProviderQuotaError
from career_os.ai.openrouter_provider import CreditsExhaustedError
from career_os.api.constants import DESC_PROFILE_ID, RESP_404
from career_os.database import get_db
from career_os.schemas.scoring import (
    BatchScoreRequest,
    BatchScoreResponse,
    ScoreContextResponse,
    ScoreRequest,
    ScoreResponse,
    ScoringWeightsResponse,
    ScoringWeightsUpdate,
)
from career_os.services.pushover import send_credits_exhausted_alert
from career_os.services.scoring import (
    JobNotFoundError,
    ProfileIncompleteError,
    ProfileNotFoundError,
    ScoringError,
    batch_score_discovery,
    compute_score_context,
    flag_stale_scores,
    get_or_create_weights,
    get_score_for_application,
    get_score_for_job,
    score_job,
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
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
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
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
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
# Score Retrieval
# ---------------------------------------------------------------------------


@router.get("/api/score/job/{discovered_job_id}", responses=RESP_404)
async def get_job_score_endpoint(
    discovered_job_id: int,
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
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
    return response


@router.get(
    "/api/score/application/{application_id}",
    responses=RESP_404,
)
async def get_application_score_endpoint(
    application_id: int,
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
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
    return response


# ---------------------------------------------------------------------------
# Profile Switch / Stale Scores
# ---------------------------------------------------------------------------


@router.post("/api/scoring/flag-stale")
async def flag_stale_endpoint(
    profile_id: Annotated[int, Query(description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    """Mark all scores for a profile as stale.

    Called when profile changes that could affect scoring (e.g., profile switch,
    skills update, goals change).
    """
    count = flag_stale_scores(db, profile_id)
    return {"stale_count": count}
