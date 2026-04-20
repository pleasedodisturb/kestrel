"""Anthropic AI provider with prompt caching support.

Connects directly to the Anthropic Messages API (https://api.anthropic.com)
for AI completions. Uses prompt caching (cache_control on system blocks) for
90% cost reduction on repeated system prompts.

Requires ANTHROPIC_API_KEY in environment.
"""

import json
import logging

import httpx

from career_os.ai.base import AIProvider, ComplexityTier, ProviderQuotaError
from career_os.ai.cache_monitor import record_cache_event
from career_os.ai.observability import observe, update_current_generation
from career_os.ai.openrouter_provider import (
    _SCHEMA_MAP,
    _scoring_user_prompt,
    _system_prompt_for_feature,
    _try_parse_structured,
)
from career_os.schemas.ai import AIFeature, AIResponse, TokenUsage

logger = logging.getLogger(__name__)

# Compact JSON separators — eliminates whitespace tokens (~30% reduction on profile data)
_COMPACT = (",", ":")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_BATCH_API_URL = "https://api.anthropic.com/v1/messages/batches"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_VERSION = "2023-06-01"


_TIER_MODELS: dict[ComplexityTier, str] = {
    ComplexityTier.SIMPLE: "claude-haiku-4-5-20251001",
    ComplexityTier.STANDARD: "claude-sonnet-4-20250514",
    ComplexityTier.COMPLEX: "claude-opus-4-20250514",
}


class AnthropicProvider(AIProvider):
    """AI provider backed by the Anthropic Messages API with prompt caching."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize with API key and optional model override.

        Args:
            api_key: Anthropic API key (should start with sk-ant-).
            model: Model identifier (default: claude-sonnet-4-20250514).
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

    @observe(name="anthropic-complete", as_type="generation")
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
        update_current_generation(
            model=model,
            metadata={"feature": feature.value, "tier": (tier or "standard")},
        )
        expects_structured = feature in _SCHEMA_MAP

        for attempt in range(1, max_retries + 2):
            user_content = prompt
            if attempt > 1:
                user_content += (
                    "\n\nIMPORTANT: Return ONLY valid JSON"
                    " with no surrounding text or markdown fences."
                )

            messages = [{"role": "user", "content": user_content}]

            # Build system blocks with cache_control for prompt caching.
            # When context is provided (e.g. profile data for scoring), it's
            # appended to the system block so repeated calls for the same user
            # hit the prompt cache across features (Anthropic caches by prefix).
            system_blocks: list[dict] | None = None
            system_msg = _system_prompt_for_feature(feature)
            if system_msg:
                if context:
                    # Combine system prompt + context into one cached block.
                    # Profile data pushes block past 1024-token cache minimum.
                    ctx_json = json.dumps(context, separators=_COMPACT)
                    combined = f"{system_msg}\n\nCandidate Profile:\n{ctx_json}"
                    system_blocks = [
                        {
                            "type": "text",
                            "text": combined,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                else:
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

            # Track cache hit/miss for break detection
            record_cache_event(feature, usage)

            # Try to parse structured data for known features
            structured = _try_parse_structured(content, feature)

            if structured is not None or not expects_structured:
                update_current_generation(
                    usage_details={
                        "input": usage.input_tokens,
                        "output": usage.output_tokens,
                        "cache_read_input_tokens": usage.cache_read_input_tokens,
                        "cache_creation_input_tokens": usage.cache_creation_input_tokens,
                    },
                )
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

        Profile data is passed as context so it lands in the cached system
        block — enabling cross-call cache reuse when scoring multiple jobs
        for the same user.
        """
        prompt = _scoring_user_prompt(job_description)
        return await self.complete(prompt, feature=AIFeature.score, context=profile_data, tier=tier)

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
        # Build system block with profile in cached prefix — same pattern
        # as score(). For batch, every request shares this system block so
        # Anthropic can cache it server-side across the batch.
        system_msg = _system_prompt_for_feature(AIFeature.score)
        system_blocks: list[dict] | None = None
        if system_msg:
            ctx_json = json.dumps(profile_data, separators=_COMPACT)
            combined = f"{system_msg}\n\nCandidate Profile:\n{ctx_json}"
            system_blocks = [
                {
                    "type": "text",
                    "text": combined,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        requests: list[dict] = []
        for job in jobs:
            prompt = _scoring_user_prompt(job["description"])

            params: dict = {
                "model": self._model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_blocks:
                params["system"] = system_blocks

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
