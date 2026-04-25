"""Mistral AI provider.

Connects to the Mistral AI API (https://api.mistral.ai) via an
OpenAI-compatible chat completions endpoint.

Requires MISTRAL_API_KEY in environment.

Mistral is an EU-based company (Paris, France) with strong GDPR
compliance.  Privacy tier is **green**.
"""

import json
import logging

import httpx

from career_os.ai.base import AIProvider, ProviderQuotaError
from career_os.ai.openrouter_provider import (
    _SCHEMA_MAP,
    _system_prompt_for_feature,
    _try_parse_structured,
)
from career_os.schemas.ai import AIFeature, AIResponse

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_MODEL = "mistral-large-latest"


class MistralProvider(AIProvider):
    """AI provider backed by the Mistral AI API (OpenAI-compatible)."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize with API key and optional model override.

        Args:
            api_key: Mistral AI API key.
            model: Model identifier (default: mistral-large-latest).
        """
        if not api_key:
            raise ValueError("MISTRAL_API_KEY is required for MistralProvider")
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "mistral"

    @property
    def privacy_tier(self) -> str:
        """Mistral AI is EU-based (Paris) with GDPR compliance — green tier."""
        return "green"

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        max_retries: int = 1,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to the Mistral AI API."""
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
                    MISTRAL_API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code in (402, 429):
                    detail = _extract_error_detail(response)
                    raise ProviderQuotaError("mistral", response.status_code, detail)
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            model_used = data.get("model", self._model)

            structured = _try_parse_structured(content, feature)

            if structured is not None or not expects_structured:
                return AIResponse(
                    content=content,
                    provider="mistral",
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
            provider="mistral",
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
        """Score a job against a profile via the Mistral AI API."""
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
    """Best-effort extraction of error message from a Mistral AI error response."""
    try:
        body = response.json()
        error = body.get("error", {})
        return error.get("message", "") if isinstance(error, dict) else str(error)
    except Exception:
        return ""
