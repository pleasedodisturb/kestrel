"""Async batch scoring API routes.

Exposes endpoints for submitting async batch scoring jobs, checking their
status, and retrieving results. Uses provider Batch APIs (Anthropic Message
Batches, OpenAI Batch) for 50% cost savings on non-urgent scoring.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from career_os.ai.factory import get_ai_provider
from career_os.database import get_db
from career_os.services.async_batch import (
    BatchNotReadyError,
    BatchResultError,
    BatchSubmissionError,
    check_batch_status,
    retrieve_batch_results,
    submit_batch,
)
from career_os.services.scoring import (
    ProfileIncompleteError,
    ProfileNotFoundError,
    build_profile_data,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["batch-scoring"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class BatchJobItem(BaseModel):
    """A single job to include in the batch."""

    id: str = Field(..., description="Unique job identifier")
    description: str = Field(..., min_length=1, description="Job posting text")


class BatchSubmitRequest(BaseModel):
    """Request body for POST /api/score/batch/submit."""

    profile_id: int = Field(..., description="Profile ID to score against")
    jobs: list[BatchJobItem] = Field(
        ..., min_length=1, max_length=10000, description="Jobs to score"
    )
    provider: str | None = Field(
        default=None,
        description="AI provider override (default: configured AI_PROVIDER)",
    )


class BatchSubmitResponse(BaseModel):
    """Response from POST /api/score/batch/submit."""

    batch_id: str = Field(..., description="Batch ID for polling status/results")
    provider: str = Field(..., description="Provider that accepted the batch")
    job_count: int = Field(..., description="Number of jobs submitted")


class BatchStatusResponse(BaseModel):
    """Response from GET /api/score/batch/{batch_id}/status."""

    batch_id: str
    status: str
    provider: str


class BatchResultItem(BaseModel):
    """A single result from a completed batch."""

    job_id: str
    score_result: dict[str, Any] | None = None
    error: str | None = None


class BatchResultsResponse(BaseModel):
    """Response from GET /api/score/batch/{batch_id}/results."""

    batch_id: str
    results: list[BatchResultItem]
    total: int
    successful: int
    failed: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/api/score/batch/submit",
    status_code=202,
    responses={
        400: {"description": "Bad request (empty batch, invalid jobs)"},
        404: {"description": "Profile not found"},
        422: {"description": "Profile incomplete for scoring"},
        502: {"description": "Provider batch submission failed"},
    },
)
async def batch_submit_endpoint(
    payload: BatchSubmitRequest,
    db: Annotated[Session, Depends(get_db)],
) -> BatchSubmitResponse:
    """Submit an async batch of jobs for scoring.

    Jobs are sent to the provider's Batch API (Anthropic or OpenAI) for
    processing at 50% cost discount. Results are typically available
    within 24 hours.

    Returns a ``batch_id`` for polling status and retrieving results.
    """
    try:
        profile_data = build_profile_data(db, payload.profile_id)
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="Profile not found") from None
    except ProfileIncompleteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    provider = get_ai_provider(payload.provider)

    jobs = [{"id": j.id, "description": j.description} for j in payload.jobs]

    try:
        batch_id = await submit_batch(provider, jobs, profile_data)
    except BatchSubmissionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return BatchSubmitResponse(
        batch_id=batch_id,
        provider=provider.name,
        job_count=len(jobs),
    )


@router.get(
    "/api/score/batch/{batch_id}/status",
    responses={
        502: {"description": "Provider status check failed"},
    },
)
async def batch_status_endpoint(
    batch_id: str,
    provider: Annotated[str | None, Query(description="AI provider name")] = None,
) -> BatchStatusResponse:
    """Check the status of an async batch scoring job."""
    ai_provider = get_ai_provider(provider)

    try:
        status = await check_batch_status(ai_provider, batch_id)
    except BatchResultError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return BatchStatusResponse(
        batch_id=status["batch_id"],
        status=status["status"],
        provider=status["provider"],
    )


@router.get(
    "/api/score/batch/{batch_id}/results",
    responses={
        202: {"description": "Batch not yet complete"},
        502: {"description": "Provider result retrieval failed"},
    },
)
async def batch_results_endpoint(
    batch_id: str,
    provider: Annotated[str | None, Query(description="AI provider name")] = None,
) -> BatchResultsResponse:
    """Retrieve results of a completed async batch scoring job.

    Returns 202 if the batch is still processing. Returns results only
    when all jobs have been scored.
    """
    ai_provider = get_ai_provider(provider)

    try:
        results = await retrieve_batch_results(ai_provider, batch_id)
    except BatchNotReadyError:
        raise HTTPException(
            status_code=202,
            detail=f"Batch {batch_id} is still processing. Poll status endpoint.",
        ) from None
    except BatchResultError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    items = []
    for r in results:
        score_dict = None
        if r["score_result"] is not None:
            score_dict = r["score_result"].model_dump()
        items.append(
            BatchResultItem(
                job_id=r["job_id"],
                score_result=score_dict,
                error=r["error"],
            )
        )

    successful = sum(1 for i in items if i.score_result is not None)
    failed = sum(1 for i in items if i.error is not None)

    return BatchResultsResponse(
        batch_id=batch_id,
        results=items,
        total=len(items),
        successful=successful,
        failed=failed,
    )
