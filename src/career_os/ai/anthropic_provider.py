"""Anthropic AI provider with prompt caching support.

Connects directly to the Anthropic Messages API (https://api.anthropic.com)
for AI completions. Uses prompt caching (cache_control on system blocks) for
90% cost reduction on repeated system prompts.

Requires ANTHROPIC_API_KEY in environment.
"""

import json
import logging

import httpx

from career_os.ai.base import AIProvider, ProviderQuotaError
from career_os.ai.openrouter_provider import _system_prompt_for_feature, _try_parse_structured
from career_os.schemas.ai import AIFeature, AIResponse

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_VERSION = "2023-06-01"


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

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to the Anthropic Messages API."""
        messages = [{"role": "user", "content": prompt}]

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
            "model": self._model,
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

        # Try to parse structured data for known features
        structured = _try_parse_structured(content, feature)

        return AIResponse(
            content=content,
            provider="anthropic",
            feature=feature,
            structured=structured,
            model=model_used,
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile via the Anthropic API."""
        prompt = (
            f"Score this job against the candidate profile. "
            f"Return a JSON object with: fit_score (0-10), reasoning (detailed, >=100 chars), "
            f"estimated_salary (string), effort_flag (low/medium/high), prep_level, prep_notes, "
            f"readiness_score (0-100), career_alignment (0-10), "
            f"score_breakdown (array of >=3 objects, each with: factor (string), "
            f"contribution (positive or negative float), description (string)), "
            f"dimensional_scores (object with 6 floats 0-10: technical_fit, "
            f"seniority_alignment, compensation_fit, location_fit, career_trajectory, "
            f"company_fit), "
            f"ats_keywords (array of 10-15 objects, each with: keyword (string), "
            f"category (one of technical/soft_skill/tool/certification/domain), "
            f"matched (boolean -- true if the profile demonstrates this keyword)), "
            f"desire_score (0-10, how much the candidate would WANT this job -- "
            f"considering company reputation, growth potential, culture signals, "
            f"role excitement, compensation attractiveness, work-life balance), "
            f"desire_reasoning (string explaining what makes this job desirable "
            f"or undesirable from the candidate's perspective).\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Profile:\n{json.dumps(profile_data, indent=2)}"
        )
        return await self.complete(prompt, feature=AIFeature.score)


def _extract_error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of error message from an Anthropic error response."""
    try:
        body = response.json()
        error = body.get("error", {})
        return error.get("message", "") if isinstance(error, dict) else str(error)
    except Exception:
        return ""
