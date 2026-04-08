"""Scoring API routes — AI-powered job scoring engine."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.scoring import (
    BatchScoreRequest,
    BatchScoreResponse,
    ScoreRequest,
    ScoreResponse,
    ScoringWeightsResponse,
    ScoringWeightsUpdate,
)
from career_os.services.scoring import (
    JobNotFoundError,
    ProfileNotFoundError,
    ScoringError,
    batch_score_discovery,
    flag_stale_scores,
    get_or_create_weights,
    get_score_for_application,
    get_score_for_job,
    score_job,
    update_weights,
)

router = APIRouter(tags=["scoring"])


# ---------------------------------------------------------------------------
# Single Job Scoring
# ---------------------------------------------------------------------------


@router.post("/api/score", response_model=ScoreResponse, status_code=201)
async def score_endpoint(
    payload: ScoreRequest,
    db: Session = Depends(get_db),
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
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScoringError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scoring error: {exc}") from exc

    return ScoreResponse.model_validate(scored)


# ---------------------------------------------------------------------------
# Scoring Weights
# ---------------------------------------------------------------------------


@router.get("/api/scoring-weights", response_model=ScoringWeightsResponse)
async def get_weights_endpoint(
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> ScoringWeightsResponse:
    """Get scoring weights for a profile."""
    try:
        weights = get_or_create_weights(db, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ScoringWeightsResponse.model_validate(weights)


@router.put("/api/scoring-weights", response_model=ScoringWeightsResponse)
async def update_weights_endpoint(
    payload: ScoringWeightsUpdate,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
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


@router.post("/api/score/batch", response_model=BatchScoreResponse)
async def batch_score_endpoint(
    payload: BatchScoreRequest,
    db: Session = Depends(get_db),
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Batch scoring error: {exc}") from exc

    return BatchScoreResponse(
        scored_count=result["scored_count"],
        total_time_seconds=result["total_time_seconds"],
        scores=[ScoreResponse.model_validate(s) for s in result["scores"]],
        errors=result["errors"],
    )


# ---------------------------------------------------------------------------
# Score Retrieval
# ---------------------------------------------------------------------------


@router.get("/api/score/job/{discovered_job_id}", response_model=ScoreResponse | None)
async def get_job_score_endpoint(
    discovered_job_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> ScoreResponse | None:
    """Get the latest score for a discovered job."""
    scored = get_score_for_job(db, profile_id, discovered_job_id)
    if not scored:
        raise HTTPException(status_code=404, detail="No score found for this job")
    return ScoreResponse.model_validate(scored)


@router.get(
    "/api/score/application/{application_id}",
    response_model=ScoreResponse | None,
)
async def get_application_score_endpoint(
    application_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> ScoreResponse | None:
    """Get the latest score for an application."""
    scored = get_score_for_application(db, profile_id, application_id)
    if not scored:
        raise HTTPException(status_code=404, detail="No score found for this application")
    return ScoreResponse.model_validate(scored)


# ---------------------------------------------------------------------------
# Profile Switch / Stale Scores
# ---------------------------------------------------------------------------


@router.post("/api/scoring/flag-stale")
async def flag_stale_endpoint(
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Mark all scores for a profile as stale.

    Called when profile changes that could affect scoring (e.g., profile switch,
    skills update, goals change).
    """
    count = flag_stale_scores(db, profile_id)
    return {"stale_count": count}
