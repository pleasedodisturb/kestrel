"""Batch scoring — multiple jobs per prompt.

Sends N jobs in a single LLM prompt and parses a JSON array of ScoreResult
objects from the response.  Based on arXiv:2604.03684 which confirms <2pp
quality loss at batch sizes 25-100.

Position bias is mitigated by randomizing job order within each batch.
If batch parsing fails, the service falls back to individual scoring.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re

from career_os.ai.base import AIProvider
from career_os.schemas.ai import AIFeature, AIResponse, ScoreResult

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10
MAX_DESCRIPTION_LENGTH = 8000

# Patterns that could be used for prompt injection in job descriptions
_INJECTION_PATTERNS = re.compile(
    r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|above|prior)\s+instructions",
    re.IGNORECASE,
)


def _sanitize_description(text: str) -> str:
    """Sanitize a job description before interpolating into an LLM prompt.

    Truncates to MAX_DESCRIPTION_LENGTH and strips known injection patterns.
    Job descriptions come from scraped external boards (attacker-controlled).
    """
    if not text:
        return "N/A"
    text = text[:MAX_DESCRIPTION_LENGTH]
    text = _INJECTION_PATTERNS.sub("[filtered]", text)
    return text


def get_batch_size() -> int:
    """Return the configured batch size from env var or default."""
    raw = os.environ.get("BATCH_SCORING_SIZE", "")
    if raw.strip():
        try:
            size = int(raw)
            if size < 1:
                logger.warning(
                    "BATCH_SCORING_SIZE=%s invalid, using default %d", raw, DEFAULT_BATCH_SIZE
                )
                return DEFAULT_BATCH_SIZE
            return size
        except ValueError:
            logger.warning(
                "BATCH_SCORING_SIZE=%s not an int, using default %d", raw, DEFAULT_BATCH_SIZE
            )
            return DEFAULT_BATCH_SIZE
    return DEFAULT_BATCH_SIZE


def build_batch_prompt(
    jobs: list[dict],
    profile_data: dict,
) -> tuple[str, list[str]]:
    """Build a multi-job scoring prompt.

    Args:
        jobs: List of dicts, each with at least 'id' and 'description'.
              May also contain 'title', 'company', 'url'.
        profile_data: User profile data dict.

    Returns:
        Tuple of (prompt_text, ordered_job_ids) where ordered_job_ids is
        the randomized order of job IDs as they appear in the prompt.
    """
    # Randomize order within the batch (position bias mitigation)
    shuffled = list(jobs)
    random.shuffle(shuffled)
    ordered_ids = [str(j["id"]) for j in shuffled]

    job_blocks: list[str] = []
    for idx, job in enumerate(shuffled, 1):
        block_parts = [f"--- Job {idx} (ID: {job['id']}) ---"]
        if job.get("title"):
            block_parts.append(f"Title: {job['title']}")
        if job.get("company"):
            block_parts.append(f"Company: {job['company']}")
        if job.get("url"):
            block_parts.append(f"URL: {job['url']}")
        desc = _sanitize_description(job.get("description", "N/A"))
        block_parts.append(f"Description:\n{desc}")
        job_blocks.append("\n".join(block_parts))

    jobs_section = "\n\n".join(job_blocks)

    prompt = (
        f"Score each of the following {len(shuffled)} jobs against the candidate profile. "
        f"Return a JSON ARRAY where each element is an object with:\n"
        f"- job_id (string matching the ID in the job header)\n"
        f"- fit_score (0-10)\n"
        f"- reasoning (detailed, >=100 chars)\n"
        f"- estimated_salary (string)\n"
        f"- effort_flag (low/medium/high)\n"
        f"- prep_level (string)\n"
        f"- prep_notes (string)\n"
        f"- readiness_score (0-100)\n"
        f"- career_alignment (0-10)\n"
        f"- score_breakdown (array of >=3 objects with factor, contribution, description)\n"
        f"- dimensional_scores (object with 6 floats 0-10: technical_fit, "
        f"seniority_alignment, compensation_fit, location_fit, career_trajectory, "
        f"company_fit)\n"
        f"- ats_keywords (array of 10-15 objects with keyword, category, matched)\n"
        f"- desire_score (0-10)\n"
        f"- desire_reasoning (string)\n\n"
        f"Return ONLY a JSON array of {len(shuffled)} objects. "
        f"No surrounding text or markdown.\n\n"
        f"JOBS:\n\n{jobs_section}\n\n"
        f"PROFILE:\n{json.dumps(profile_data, indent=2)}"
    )

    return prompt, ordered_ids


def _extract_json_array(text: str) -> list[dict] | None:
    """Extract a JSON array from LLM output, handling markdown fences.

    Returns the parsed list or None if extraction fails.
    """
    cleaned = text.strip()
    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        end = -1 if lines[-1].startswith("```") else len(lines)
        cleaned = "\n".join(lines[1:end]) if len(lines) > 2 else cleaned

    # Strip trailing commas before ] or }
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    # Try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try to find array in the text using bracket matching
    start = cleaned.find("[")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : i + 1]
                candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                try:
                    data = json.loads(candidate)
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError:
                    return None
    return None


def parse_batch_response(
    content: str,
    ordered_ids: list[str],
) -> dict[str, ScoreResult]:
    """Parse a batch scoring response into a map of job_id -> ScoreResult.

    Args:
        content: Raw LLM response text.
        ordered_ids: The job IDs in the order they were sent.

    Returns:
        Dict mapping job_id (str) to ScoreResult. Jobs that fail validation
        are omitted from the result.
    """
    items = _extract_json_array(content)
    if items is None:
        logger.warning("Batch response did not contain a valid JSON array")
        return {}

    results: dict[str, ScoreResult] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        job_id = str(item.get("job_id", ""))
        if not job_id:
            # Try positional fallback — if the array has the right length
            # and no job_id fields, map by position
            continue
        try:
            score_result = ScoreResult.model_validate(item)
            results[job_id] = score_result
        except Exception as exc:
            logger.warning(
                "Failed to validate ScoreResult for job %s in batch: %s",
                job_id,
                exc,
            )

    # Positional fallback: if no job_ids were found but array length matches,
    # assume results are in prompt order
    if not results and items and len(items) == len(ordered_ids):
        logger.info("No job_id fields in batch response, using positional mapping")
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            try:
                score_result = ScoreResult.model_validate(item)
                results[ordered_ids[idx]] = score_result
            except Exception as exc:
                logger.warning(
                    "Failed to validate ScoreResult at position %d in batch: %s",
                    idx,
                    exc,
                )

    return results


def chunk_jobs(jobs: list[dict], batch_size: int) -> list[list[dict]]:
    """Split jobs into batches of the given size."""
    return [jobs[i : i + batch_size] for i in range(0, len(jobs), batch_size)]


async def batch_score_jobs(
    provider: AIProvider,
    jobs: list[dict],
    profile_data: dict,
    *,
    batch_size: int | None = None,
) -> dict[str, ScoreResult]:
    """Score multiple jobs using multi-job-per-prompt batching.

    Splits jobs into chunks of batch_size, sends each chunk as a single
    prompt, and collects results.  Falls back to individual scoring for
    any jobs whose batch parsing fails.

    Args:
        provider: AI provider to use for scoring.
        jobs: List of dicts with at least 'id' and 'description'.
        profile_data: User profile data dict.
        batch_size: Jobs per prompt (default from env/config).

    Returns:
        Dict mapping job_id (str) to ScoreResult for successfully scored jobs.
    """
    if batch_size is None:
        batch_size = get_batch_size()

    if not jobs:
        return {}

    all_results: dict[str, ScoreResult] = {}
    failed_jobs: list[dict] = []

    batches = chunk_jobs(jobs, batch_size)
    logger.info(
        "Batch scoring %d jobs in %d batches of up to %d",
        len(jobs),
        len(batches),
        batch_size,
    )

    for batch_idx, batch in enumerate(batches):
        prompt, ordered_ids = build_batch_prompt(batch, profile_data)

        try:
            response: AIResponse = await provider.complete(
                prompt,
                feature=AIFeature.score,
                tier=None,
            )
            batch_results = parse_batch_response(response.content, ordered_ids)

            if batch_results:
                all_results.update(batch_results)
                logger.info(
                    "Batch %d/%d: parsed %d/%d scores",
                    batch_idx + 1,
                    len(batches),
                    len(batch_results),
                    len(batch),
                )

            # Identify jobs that weren't in the parsed results
            parsed_ids = set(batch_results.keys())
            for job in batch:
                if str(job["id"]) not in parsed_ids:
                    failed_jobs.append(job)

        except Exception as exc:
            logger.warning(
                "Batch %d/%d failed (%s), adding %d jobs to fallback queue",
                batch_idx + 1,
                len(batches),
                exc,
                len(batch),
            )
            failed_jobs.extend(batch)

    # Fallback: score individually any jobs that failed in batch
    if failed_jobs:
        logger.info(
            "Falling back to individual scoring for %d jobs",
            len(failed_jobs),
        )
        for job in failed_jobs:
            try:
                response = await provider.score(
                    job_description=job.get("description", ""),
                    profile_data=profile_data,
                )
                if response.structured and isinstance(response.structured, ScoreResult):
                    all_results[str(job["id"])] = response.structured
                else:
                    logger.warning(
                        "Individual fallback for job %s did not return ScoreResult",
                        job["id"],
                    )
            except Exception as exc:
                logger.warning(
                    "Individual fallback for job %s failed: %s",
                    job["id"],
                    exc,
                )

    return all_results
