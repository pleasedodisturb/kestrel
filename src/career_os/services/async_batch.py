"""Async batch scoring service.

Orchestrates async Batch API submission and result retrieval for providers
that support it (Anthropic Message Batches, OpenAI Batch API). These APIs
accept a set of requests and return results within 24 hours at 50% cost
discount compared to real-time API calls.

This is distinct from the synchronous multi-job-per-prompt batching in
scoring.py (G-440). That sends multiple jobs in one prompt; this submits
individual requests to a provider's async batch queue.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from career_os.ai.base import AIProvider
from career_os.schemas.ai import ScoreResult

logger = logging.getLogger(__name__)


class BatchStatus(StrEnum):
    """Possible states of an async batch job."""

    in_progress = "in_progress"
    ended = "ended"
    canceling = "canceling"
    canceled = "canceled"
    expired = "expired"
    failed = "failed"
    unknown = "unknown"


class BatchSubmissionError(Exception):
    """Raised when batch submission fails."""


class BatchNotReadyError(Exception):
    """Raised when batch results are requested before the batch has completed."""


class BatchResultError(Exception):
    """Raised when batch result retrieval fails."""


async def submit_batch(
    provider: AIProvider,
    jobs: list[dict],
    profile_data: dict,
) -> str:
    """Submit a batch of jobs for async scoring.

    Each job dict must contain at least ``id`` (unique identifier) and
    ``description`` (job posting text). The provider's ``batch_score()``
    method builds the per-job requests and POSTs them to the async batch
    endpoint.

    Args:
        provider: AI provider that supports batch scoring.
        jobs: List of dicts with at least 'id' and 'description' keys.
        profile_data: User profile data dict used for scoring context.

    Returns:
        Batch ID string for polling status/results.

    Raises:
        BatchSubmissionError: If the provider rejects the batch or an
            unexpected error occurs during submission.
    """
    if not jobs:
        raise BatchSubmissionError("Cannot submit an empty batch")

    for job in jobs:
        if "id" not in job or "description" not in job:
            raise BatchSubmissionError("Each job must have 'id' and 'description' keys")

    try:
        batch_id = await provider.batch_score(jobs, profile_data)
    except NotImplementedError as exc:
        raise BatchSubmissionError(
            f"Provider '{provider.name}' does not support batch scoring"
        ) from exc
    except Exception as exc:
        raise BatchSubmissionError(f"Batch submission failed: {exc}") from exc

    logger.info(
        "Batch %s submitted via %s with %d jobs",
        batch_id,
        provider.name,
        len(jobs),
    )
    return batch_id


async def check_batch_status(
    provider: AIProvider,
    batch_id: str,
) -> dict:
    """Check the status of an async batch job.

    Args:
        provider: AI provider that submitted the batch.
        batch_id: The batch ID returned by :func:`submit_batch`.

    Returns:
        Dict with at least a ``status`` key (one of :class:`BatchStatus`
        values) and optionally ``counts`` with request processing stats.

    Raises:
        BatchResultError: If the status check fails.
    """
    try:
        result = await provider.get_batch_results(batch_id)
    except NotImplementedError as exc:
        raise BatchResultError(
            f"Provider '{provider.name}' does not support batch results"
        ) from exc
    except Exception as exc:
        raise BatchResultError(f"Batch status check failed: {exc}") from exc

    status_raw = result.get("status", "unknown")
    # Normalize to our enum
    try:
        status = BatchStatus(status_raw)
    except ValueError:
        status = BatchStatus.unknown

    return {"status": status, "batch_id": batch_id, "provider": provider.name}


async def retrieve_batch_results(
    provider: AIProvider,
    batch_id: str,
) -> list[dict]:
    """Retrieve completed batch results as a list of ScoreResult dicts.

    Calls the provider's ``get_batch_results()`` which fetches status and,
    when the batch has ended, parses the JSONL result stream into
    ``AIResponse`` objects keyed by custom_id (job ID).

    Args:
        provider: AI provider that submitted the batch.
        batch_id: The batch ID returned by :func:`submit_batch`.

    Returns:
        List of dicts, each with ``job_id`` (str), ``score_result``
        (:class:`ScoreResult` or None), and ``error`` (str or None).

    Raises:
        BatchNotReadyError: If the batch has not finished processing.
        BatchResultError: If result retrieval fails.
    """
    try:
        result = await provider.get_batch_results(batch_id)
    except NotImplementedError as exc:
        raise BatchResultError(
            f"Provider '{provider.name}' does not support batch results"
        ) from exc
    except Exception as exc:
        raise BatchResultError(f"Batch result retrieval failed: {exc}") from exc

    status_raw = result.get("status", "unknown")

    if status_raw != "ended":
        raise BatchNotReadyError(
            f"Batch {batch_id} is not ready (status: {status_raw}). "
            "Results are only available when status is 'ended'."
        )

    raw_results: dict = result.get("results", {})
    parsed: list[dict] = []

    for job_id, ai_response in raw_results.items():
        entry: dict = {"job_id": job_id, "score_result": None, "error": None}

        if ai_response is None:
            entry["error"] = "No response from provider"
            parsed.append(entry)
            continue

        structured = ai_response.structured
        if structured is None:
            entry["error"] = "Provider returned unstructured response"
            parsed.append(entry)
            continue

        # structured is already a ScoreResult (parsed by the provider)
        if isinstance(structured, ScoreResult):
            entry["score_result"] = structured
        else:
            # Try to coerce dict → ScoreResult
            try:
                entry["score_result"] = ScoreResult(**structured)
            except Exception as exc:
                entry["error"] = f"Failed to parse score result: {exc}"

        parsed.append(entry)

    logger.info(
        "Batch %s: %d results retrieved, %d successful",
        batch_id,
        len(parsed),
        sum(1 for r in parsed if r["score_result"] is not None),
    )
    return parsed
