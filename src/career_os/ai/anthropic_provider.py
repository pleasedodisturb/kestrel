"""Anthropic AI provider with prompt caching support.

Connects directly to the Anthropic Messages API (https://api.anthropic.com)
for AI completions. Uses prompt caching (cache_control on system blocks) for
90% cost reduction on repeated system prompts.

Requires ANTHROPIC_API_KEY in environment.
"""

import json
import logging
from urllib.parse import urlparse

import httpx

from career_os.ai.base import (
    ROLE_FIT_GATE_PROMPT,
    AIProvider,
    ComplexityTier,
    ProviderQuotaError,
)
from career_os.ai.openrouter_provider import (
    _SCHEMA_MAP,
    _system_prompt_for_feature,
    _try_parse_structured,
)
from career_os.schemas.ai import AIFeature, AIResponse, TokenUsage

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_BATCH_API_URL = "https://api.anthropic.com/v1/messages/batches"
DEFAULT_MODEL = "claude-sonnet-5"
ANTHROPIC_VERSION = "2023-06-01"


_TIER_MODELS: dict[ComplexityTier, str] = {
    ComplexityTier.SIMPLE: "claude-haiku-4-5-20251001",
    ComplexityTier.STANDARD: "claude-sonnet-5",
    ComplexityTier.COMPLEX: "claude-opus-4-8",
}


class AnthropicProvider(AIProvider):
    """AI provider backed by the Anthropic Messages API with prompt caching."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize with API key and optional model override.

        Args:
            api_key: Anthropic API key (should start with sk-ant-).
            model: Model identifier (default: claude-sonnet-5).
        """
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for AnthropicProvider")
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "anthropic"

    def _resolve_model(self, tier: ComplexityTier | None) -> str:
        """Return the model to use for a request.

        If the provider was constructed with an explicit model override (via env
        var), that always wins.  Otherwise, the tier selects the model from
        ``_TIER_MODELS``.  If tier is None, STANDARD is used.
        """
        if self._model != DEFAULT_MODEL:
            return self._model
        effective_tier = tier or ComplexityTier.STANDARD
        return _TIER_MODELS[effective_tier]

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        tier: ComplexityTier | None = None,
        max_retries: int = 1,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to the Anthropic Messages API."""
        model = self._resolve_model(tier)
        expects_structured = feature in _SCHEMA_MAP

        for attempt in range(1, max_retries + 2):
            user_content = prompt
            if attempt > 1:
                user_content += (
                    "\n\nIMPORTANT: Return ONLY valid JSON"
                    " with no surrounding text or markdown fences."
                )

            messages = [{"role": "user", "content": user_content}]

            # Build system blocks with cache_control for prompt caching
            system_blocks: list[dict] | None = None
            system_msg = _system_prompt_for_feature(feature)
            if system_msg:
                system_blocks = [
                    {
                        "type": "text",
                        "text": system_msg,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]

            payload: dict = {
                "model": model,
                "max_tokens": 4096,
                "messages": messages,
            }
            if system_blocks:
                payload["system"] = system_blocks

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        ANTHROPIC_API_URL,
                        headers={
                            "x-api-key": self._api_key,
                            "anthropic-version": ANTHROPIC_VERSION,
                            "anthropic-beta": "token-efficient-tool-use-2025-04-14",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if response.status_code in (402, 429):
                        detail = _extract_error_detail(response)
                        if response.status_code == 429:
                            retry_after = response.headers.get("retry-after")
                            if retry_after:
                                retry_msg = f"retry-after: {retry_after}s"
                                detail = f"{detail} ({retry_msg})" if detail else retry_msg
                        raise ProviderQuotaError("anthropic", response.status_code, detail)
                    response.raise_for_status()
                    data = response.json()
            except httpx.ConnectError as exc:
                raise httpx.ConnectError(
                    f"Cannot connect to Anthropic API at {ANTHROPIC_API_URL}: {exc}"
                ) from exc
            except httpx.TimeoutException as exc:
                raise httpx.TimeoutException(f"Anthropic API request timed out: {exc}") from exc

            # Anthropic Messages API returns content as array of blocks
            content_blocks = data.get("content", [])
            content = "".join(
                block.get("text", "") for block in content_blocks if block.get("type") == "text"
            )
            model_used = data.get("model", self._model)

            # Extract token usage from Anthropic response
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                cache_creation_input_tokens=usage_data.get("cache_creation_input_tokens", 0),
                cache_read_input_tokens=usage_data.get("cache_read_input_tokens", 0),
            )

            # Try to parse structured data for known features
            structured = _try_parse_structured(content, feature)

            if structured is not None or not expects_structured:
                return AIResponse(
                    content=content,
                    provider="anthropic",
                    feature=feature,
                    structured=structured,
                    model=model_used,
                    usage=usage,
                )

            # Structured parse failed — retry if we have attempts left
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
            provider="anthropic",
            feature=feature,
            structured=None,
            model=model_used,
            usage=usage,
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        *,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile via the Anthropic API.

        Profile data is placed in the system prefix (alongside the scoring
        instructions) so that Anthropic's prompt caching can reuse it across
        multiple scoring calls for the same profile.  Only the job description
        varies per call, maximising cache hits.
        """
        model = self._resolve_model(tier)

        # -- system prefix: scoring instructions + profile (cacheable) --------
        system_msg = _system_prompt_for_feature(AIFeature.score) or ""
        profile_block = f"\n\nCandidate Profile:\n{json.dumps(profile_data, indent=2)}"
        system_blocks = [
            {
                "type": "text",
                "text": system_msg + profile_block,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        # -- user message: only the job description (changes per call) --------
        user_content = (
            ROLE_FIT_GATE_PROMPT + "Score this job against the candidate profile. "
            "Return a JSON object with: fit_score (0-10), reasoning (detailed, >=100 chars), "
            "estimated_salary (string), effort_flag (low/medium/high), prep_level, prep_notes, "
            "readiness_score (0-100), career_alignment (0-10), "
            "score_breakdown (array of >=3 objects, each with: factor (string), "
            "contribution (positive or negative float), description (string)), "
            "dimensional_scores (object with 6 floats 0-10: technical_fit, "
            "seniority_alignment, compensation_fit, location_fit, career_trajectory, "
            "company_fit), "
            "ats_keywords (array of 10-15 objects, each with: keyword (string), "
            "category (one of technical/soft_skill/tool/certification/domain), "
            "matched (boolean -- true if the profile demonstrates this keyword)), "
            "desire_score (0-10, how much the candidate would WANT this job -- "
            "considering company reputation, growth potential, culture signals, "
            "role excitement, compensation attractiveness, work-life balance), "
            "desire_reasoning (string explaining what makes this job desirable "
            "or undesirable from the candidate's perspective).\n\n"
            f"Job Description:\n{job_description}"
        )

        payload: dict = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": user_content}],
            "system": system_blocks,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    ANTHROPIC_API_URL,
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": ANTHROPIC_VERSION,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code in (402, 429):
                    detail = _extract_error_detail(response)
                    if response.status_code == 429:
                        retry_after = response.headers.get("retry-after")
                        if retry_after:
                            retry_msg = f"retry-after: {retry_after}s"
                            detail = f"{detail} ({retry_msg})" if detail else retry_msg
                    raise ProviderQuotaError("anthropic", response.status_code, detail)
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as exc:
            raise httpx.ConnectError(
                f"Cannot connect to Anthropic API at {ANTHROPIC_API_URL}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise httpx.TimeoutException(f"Anthropic API request timed out: {exc}") from exc

        content_blocks = data.get("content", [])
        content = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )
        model_used = data.get("model", self._model)

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_creation_input_tokens=usage_data.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=usage_data.get("cache_read_input_tokens", 0),
        )

        structured = _try_parse_structured(content, AIFeature.score)

        return AIResponse(
            content=content,
            provider="anthropic",
            feature=AIFeature.score,
            structured=structured,
            model=model_used,
            usage=usage,
        )

    async def batch_score(
        self,
        jobs: list[dict],
        profile_data: dict,
        **kwargs: object,
    ) -> str:
        """Submit a batch of jobs for scoring via Anthropic Batch API.

        Builds one scoring request per job and POSTs to the Message Batches
        endpoint. Each request reuses the same system prompt and scoring
        prompt format as the real-time ``score()`` path.

        Args:
            jobs: List of dicts, each with at least 'id' and 'description' keys.
            profile_data: User profile data dict.

        Returns:
            Batch ID string for polling results.
        """
        # System prefix: scoring instructions + profile data (cacheable across
        # all jobs in the batch — identical for every request).
        system_msg = _system_prompt_for_feature(AIFeature.score) or ""
        profile_block = f"\n\nCandidate Profile:\n{json.dumps(profile_data, indent=2)}"
        system_blocks = [
            {
                "type": "text",
                "text": system_msg + profile_block,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        requests: list[dict] = []
        for job in jobs:
            prompt = (
                ROLE_FIT_GATE_PROMPT + "Score this job against the candidate profile. "
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
                f"Job Description:\n{job['description']}"
            )

            params: dict = {
                "model": self._model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
                "system": system_blocks,
            }

            requests.append(
                {
                    "custom_id": str(job["id"]),
                    "params": params,
                }
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                ANTHROPIC_BATCH_API_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "Content-Type": "application/json",
                },
                json={"requests": requests},
            )
            if response.status_code in (402, 429):
                detail = _extract_error_detail(response)
                raise ProviderQuotaError("anthropic", response.status_code, detail)
            response.raise_for_status()
            data = response.json()

        batch_id = data["id"]
        logger.info("Submitted batch %s with %d scoring requests", batch_id, len(requests))
        return batch_id

    async def get_batch_results(self, batch_id: str) -> dict:
        """Poll batch status and retrieve results when complete.

        GETs the batch status from the Anthropic API. When the batch has
        ended, fetches the JSONL results from ``results_url`` and parses
        each line into an :class:`AIResponse`.

        Returns:
            Dict with 'status' key ('in_progress', 'ended', etc.) and
            'results' key (list of AIResponse objects keyed by custom_id)
            when status is 'ended'.
        """
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{ANTHROPIC_BATCH_API_URL}/{batch_id}",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        status = data.get("processing_status", "unknown")
        if status != "ended":
            return {"status": status, "results": {}}

        results_url = data.get("results_url")
        if not results_url:
            return {"status": status, "results": {}}

        # Validate results_url points to Anthropic's domain before fetching.
        # The request below carries the x-api-key header, so a tampered or
        # unexpected results_url could exfiltrate the API key to an arbitrary
        # host. Restrict to Anthropic's domains.
        parsed_url = urlparse(results_url)
        if parsed_url.hostname not in ("api.anthropic.com", "anthropic.com"):
            logger.error("Batch results_url points to unexpected host: %s", parsed_url.hostname)
            return {"status": status, "results": {}}

        # Fetch JSONL results
        async with httpx.AsyncClient(timeout=120.0) as client:
            results_response = await client.get(results_url, headers=headers)
            results_response.raise_for_status()

        parsed_results: dict[str, AIResponse] = {}
        for line in results_response.text.strip().split("\n"):
            if not line.strip():
                continue
            entry = json.loads(line)
            custom_id = entry.get("custom_id", "")
            result = entry.get("result", {})

            if result.get("type") != "succeeded":
                logger.warning(
                    "Batch result for %s was not successful: %s",
                    custom_id,
                    result.get("type"),
                )
                continue

            message = result.get("message", {})
            content_blocks = message.get("content", [])
            content = "".join(
                block.get("text", "") for block in content_blocks if block.get("type") == "text"
            )
            model_used = message.get("model", self._model)
            structured = _try_parse_structured(content, AIFeature.score)

            parsed_results[custom_id] = AIResponse(
                content=content,
                provider="anthropic",
                feature=AIFeature.score,
                structured=structured,
                model=model_used,
            )

        logger.info("Batch %s completed: %d results parsed", batch_id, len(parsed_results))
        return {"status": status, "results": parsed_results}


def _extract_error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of error message from an Anthropic error response."""
    try:
        body = response.json()
        error = body.get("error", {})
        return error.get("message", "") if isinstance(error, dict) else str(error)
    except Exception:
        return ""
