"""OpenAI direct AI provider.

Connects to the OpenAI API (https://api.openai.com) via the native
chat completions endpoint.

Requires OPENAI_API_KEY in environment.
"""

import io
import json
import logging

import httpx

from career_os.ai.base import AIProvider, ProviderQuotaError
from career_os.ai.observability import observe, update_current_generation
from career_os.ai.openrouter_provider import (
    _SCHEMA_MAP,
    _scoring_user_prompt,
    _system_prompt_for_feature,
    _try_parse_structured,
)
from career_os.schemas.ai import AIFeature, AIResponse

logger = logging.getLogger(__name__)

# Compact JSON separators — eliminates whitespace tokens (~30% reduction on profile data)
_COMPACT = (",", ":")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_BATCH_API_URL = "https://api.openai.com/v1/batches"
OPENAI_FILES_API_URL = "https://api.openai.com/v1/files"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(AIProvider):
    """AI provider backed by the OpenAI API (native)."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize with API key and optional model override.

        Args:
            api_key: OpenAI API key.
            model: Model identifier (default: gpt-4o-mini).
        """
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider")
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "openai"

    @observe(name="openai-complete", as_type="generation")
    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        max_retries: int = 1,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to the OpenAI API."""
        update_current_generation(
            model=self._model,
            metadata={"feature": feature.value},
        )
        expects_structured = feature in _SCHEMA_MAP

        for attempt in range(1, max_retries + 2):
            user_content = prompt
            if attempt > 1:
                user_content += (
                    "\n\nIMPORTANT: Return ONLY valid JSON"
                    " with no surrounding text or markdown fences."
                )

            messages: list[dict[str, str]] = [
                {"role": "user", "content": user_content},
            ]

            system_msg = _system_prompt_for_feature(feature)
            if system_msg:
                messages.insert(0, {"role": "system", "content": system_msg})

            payload = {
                "model": self._model,
                "messages": messages,
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    OPENAI_API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code in (402, 429):
                    detail = _extract_error_detail(response)
                    raise ProviderQuotaError("openai", response.status_code, detail)
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            model_used = data.get("model", self._model)

            structured = _try_parse_structured(content, feature)

            if structured is not None or not expects_structured:
                usage_data = data.get("usage", {})
                update_current_generation(
                    usage_details={
                        "input": usage_data.get("prompt_tokens", 0),
                        "output": usage_data.get("completion_tokens", 0),
                    },
                )
                return AIResponse(
                    content=content,
                    provider="openai",
                    feature=feature,
                    structured=structured,
                    model=model_used,
                )

            if attempt <= max_retries:
                logger.warning(
                    "Structured parse failed for %s, retrying (attempt %d/%d)",
                    feature,
                    attempt,
                    max_retries + 1,
                )

        # Exhausted retries — return last response without structured data
        return AIResponse(
            content=content,
            provider="openai",
            feature=feature,
            structured=None,
            model=model_used,
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile via the OpenAI API."""
        prompt = _scoring_user_prompt(
            job_description, json.dumps(profile_data, separators=_COMPACT)
        )
        return await self.complete(prompt, feature=AIFeature.score)

    async def batch_score(
        self,
        jobs: list[dict],
        profile_data: dict,
        **kwargs: object,
    ) -> str:
        """Submit a batch of jobs for scoring via OpenAI Batch API.

        Builds a JSONL file of chat completion requests (one per job),
        uploads it via the Files API, then creates a batch. Each request
        uses the same system prompt and scoring format as real-time
        ``score()``.

        Args:
            jobs: List of dicts, each with at least 'id' and 'description' keys.
            profile_data: User profile data dict.

        Returns:
            Batch ID string for polling results.
        """
        system_msg = _system_prompt_for_feature(AIFeature.score) or ""
        profile_json = json.dumps(profile_data, separators=_COMPACT)

        # Build JSONL content — one line per job
        lines: list[str] = []
        for job in jobs:
            scoring_prompt = (
                "Score this job against the candidate profile. "
                "Return a JSON object with: fit_score (0-10), reasoning "
                "(detailed, >=100 chars), "
                "estimated_salary (string), effort_flag (low/medium/high), "
                "prep_level, prep_notes, "
                "readiness_score (0-100), career_alignment (0-10), "
                "score_breakdown (array of >=3 objects, each with: factor "
                "(string), contribution (positive or negative float), "
                "description (string)), "
                "dimensional_scores (object with 6 floats 0-10: technical_fit, "
                "seniority_alignment, compensation_fit, location_fit, "
                "career_trajectory, company_fit), "
                "ats_keywords (array of 10-15 objects, each with: keyword "
                "(string), category (one of technical/soft_skill/tool/"
                "certification/domain), matched (boolean)), "
                "desire_score (0-10), desire_reasoning (string).\n\n"
                f"Candidate Profile:\n{profile_json}\n\n"
                f"Job Description:\n{job['description']}"
            )

            messages: list[dict[str, str]] = []
            if system_msg:
                messages.append({"role": "system", "content": system_msg})
            messages.append({"role": "user", "content": scoring_prompt})

            request_obj = {
                "custom_id": str(job["id"]),
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": self._model,
                    "messages": messages,
                },
            }
            lines.append(json.dumps(request_obj, separators=_COMPACT))

        jsonl_content = "\n".join(lines)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }

        # 1. Upload JSONL file
        async with httpx.AsyncClient(timeout=60.0) as client:
            file_resp = await client.post(
                OPENAI_FILES_API_URL,
                headers=headers,
                data={"purpose": "batch"},
                files={"file": ("batch_scoring.jsonl", io.BytesIO(jsonl_content.encode()))},
            )
            if file_resp.status_code in (402, 429):
                detail = _extract_error_detail(file_resp)
                raise ProviderQuotaError("openai", file_resp.status_code, detail)
            file_resp.raise_for_status()
            file_id = file_resp.json()["id"]

        # 2. Create batch
        async with httpx.AsyncClient(timeout=60.0) as client:
            batch_resp = await client.post(
                OPENAI_BATCH_API_URL,
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "input_file_id": file_id,
                    "endpoint": "/v1/chat/completions",
                    "completion_window": "24h",
                },
            )
            if batch_resp.status_code in (402, 429):
                detail = _extract_error_detail(batch_resp)
                raise ProviderQuotaError("openai", batch_resp.status_code, detail)
            batch_resp.raise_for_status()
            batch_data = batch_resp.json()

        batch_id = batch_data["id"]
        logger.info("OpenAI batch %s submitted with %d requests", batch_id, len(jobs))
        return batch_id

    async def get_batch_results(self, batch_id: str) -> dict:
        """Poll batch status and retrieve results when complete.

        GETs the batch status from the OpenAI API. When the batch has
        completed, fetches the output file and parses each JSONL line
        into an :class:`AIResponse`.

        Returns:
            Dict with 'status' key and 'results' dict (keyed by custom_id)
            when status is 'ended'.
        """
        headers = {"Authorization": f"Bearer {self._api_key}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                f"{OPENAI_BATCH_API_URL}/{batch_id}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        # Map OpenAI statuses to our convention
        openai_status = data.get("status", "unknown")
        status_map = {
            "completed": "ended",
            "in_progress": "in_progress",
            "validating": "in_progress",
            "finalizing": "in_progress",
            "cancelling": "canceling",
            "cancelled": "canceled",
            "expired": "expired",
            "failed": "failed",
        }
        status = status_map.get(openai_status, "unknown")

        if status != "ended":
            return {"status": status, "results": {}}

        output_file_id = data.get("output_file_id")
        if not output_file_id:
            return {"status": status, "results": {}}

        # Fetch JSONL output file content
        async with httpx.AsyncClient(timeout=120.0) as client:
            file_resp = await client.get(
                f"{OPENAI_FILES_API_URL}/{output_file_id}/content",
                headers=headers,
            )
            file_resp.raise_for_status()

        parsed_results: dict[str, AIResponse] = {}
        for line in file_resp.text.strip().split("\n"):
            if not line.strip():
                continue
            entry = json.loads(line)
            custom_id = entry.get("custom_id", "")
            response_body = entry.get("response", {}).get("body", {})

            if entry.get("error"):
                logger.warning(
                    "OpenAI batch result for %s had error: %s",
                    custom_id,
                    entry["error"],
                )
                continue

            choices = response_body.get("choices", [])
            if not choices:
                logger.warning("OpenAI batch result for %s had no choices", custom_id)
                continue

            content = choices[0].get("message", {}).get("content", "")
            model_used = response_body.get("model", self._model)
            structured = _try_parse_structured(content, AIFeature.score)

            parsed_results[custom_id] = AIResponse(
                content=content,
                provider="openai",
                feature=AIFeature.score,
                structured=structured,
                model=model_used,
            )

        logger.info(
            "OpenAI batch %s completed: %d results parsed",
            batch_id,
            len(parsed_results),
        )
        return {"status": status, "results": parsed_results}


def _extract_error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of error message from an OpenAI error response."""
    try:
        body = response.json()
        error = body.get("error", {})
        return error.get("message", "") if isinstance(error, dict) else str(error)
    except Exception:
        return ""
