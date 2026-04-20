"""Together.ai AI provider.

Connects to the Together.ai API (https://api.together.xyz) for open-source
model inference via an OpenAI-compatible chat completions endpoint.

Requires TOGETHER_API_KEY in environment.
"""

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

TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"


class TogetherProvider(AIProvider):
    """AI provider backed by the Together.ai API (OpenAI-compatible)."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize with API key and optional model override.

        Args:
            api_key: Together.ai API key.
            model: Model identifier (default: meta-llama/Llama-3.3-70B-Instruct-Turbo).
        """
        if not api_key:
            raise ValueError("TOGETHER_API_KEY is required for TogetherProvider")
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "together"

    @property
    def privacy_tier(self) -> str:
        """Together.ai has ZDR/training opt-out enabled — green tier."""
        return "green"

    @observe(name="together-complete", as_type="generation")
    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        max_retries: int = 1,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to the Together.ai API."""
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
                    TOGETHER_API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code in (402, 429):
                    detail = _extract_error_detail(response)
                    raise ProviderQuotaError("together", response.status_code, detail)
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
                    provider="together",
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
            provider="together",
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
        """Score a job against a profile via the Together.ai API."""
        prompt = _scoring_user_prompt(
            job_description, json.dumps(profile_data, separators=_COMPACT)
        )
        return await self.complete(prompt, feature=AIFeature.score)


def _extract_error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of error message from a Together.ai error response."""
    try:
        body = response.json()
        error = body.get("error", {})
        return error.get("message", "") if isinstance(error, dict) else str(error)
    except Exception:
        return ""
