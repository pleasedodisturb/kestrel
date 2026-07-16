"""Hugging Face Inference API provider.

Connects to the Hugging Face Inference API via its OpenAI-compatible
chat completions endpoint (https://api-inference.huggingface.co/v1).

Requires HF_API_KEY (or HUGGINGFACE_API_KEY) in environment.

**Privacy note:** Hugging Face Inference API uses shared serverless
infrastructure.  Privacy tier is **yellow**.
"""

import json
import logging

import httpx

from career_os.ai.base import ROLE_FIT_GATE_PROMPT, AIProvider, ProviderQuotaError
from career_os.ai.openrouter_provider import (
    _SCHEMA_MAP,
    _system_prompt_for_feature,
    _try_parse_structured,
)
from career_os.schemas.ai import AIFeature, AIResponse, TokenUsage

logger = logging.getLogger(__name__)

HF_API_URL = "https://api-inference.huggingface.co/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"


class HuggingFaceProvider(AIProvider):
    """AI provider backed by the Hugging Face Inference API (OpenAI-compatible).

    Uses the serverless Inference API which supports thousands of models
    hosted on Hugging Face infrastructure.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize with API key and optional model override.

        Args:
            api_key: Hugging Face API key (User Access Token).
            model: Model identifier (default: meta-llama/Llama-3.3-70B-Instruct).
        """
        if not api_key:
            raise ValueError("HF_API_KEY is required for HuggingFaceProvider")
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "huggingface"

    @property
    def privacy_tier(self) -> str:
        """Hugging Face Inference API uses shared serverless infra — yellow tier."""
        return "yellow"

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        max_retries: int = 1,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to the Hugging Face Inference API."""
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
                    HF_API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code in (402, 429):
                    detail = _extract_error_detail(response)
                    raise ProviderQuotaError("huggingface", response.status_code, detail)
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            model_used = data.get("model", self._model)

            # Extract token usage from OpenAI-format response
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
            )

            structured = _try_parse_structured(content, feature)

            if structured is not None or not expects_structured:
                return AIResponse(
                    content=content,
                    provider="huggingface",
                    feature=feature,
                    structured=structured,
                    model=model_used,
                    usage=usage,
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
            provider="huggingface",
            feature=feature,
            structured=None,
            model=model_used,
            usage=usage,
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile via the Hugging Face Inference API."""
        prompt = (
            ROLE_FIT_GATE_PROMPT + f"Score this job against the candidate profile. "
            f"Return a JSON object with: fit_score (0-10), reasoning (detailed, >=100 chars), "
            f"estimated_salary (string), effort_flag (low/medium/high), prep_level, prep_notes, "
            f"readiness_score (0-100), career_alignment (0-10), "
            f"score_breakdown (array of >=3 objects, each with: factor (string), "
            f"contribution (positive or negative float), description (string)), "
            f"dimensional_scores (object with 6 floats on a 0-5 scale, NOT 0-10 "
            "(0=no fit, 5=perfect): technical_fit, "
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
    """Best-effort extraction of error message from a Hugging Face error response."""
    try:
        body = response.json()
        error = body.get("error", {})
        return error.get("message", "") if isinstance(error, dict) else str(error)
    except Exception:
        return ""
