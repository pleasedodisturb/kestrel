"""Ollama AI provider.

Connects to a local Ollama instance via its OpenAI-compatible API.
No API key required — just a running Ollama server.
"""

import json
import logging
from urllib.parse import urlparse

import httpx

from career_os.ai.base import ROLE_FIT_GATE_PROMPT, AIProvider, ComplexityTier
from career_os.ai.openrouter_provider import _system_prompt_for_feature, _try_parse_structured
from career_os.schemas.ai import AIFeature, AIResponse, TokenUsage

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.3"
_TIMEOUT_SECONDS = 120.0


class OllamaConnectionError(Exception):
    """Raised when the Ollama server is unreachable."""

    def __init__(self, base_url: str, detail: str = "") -> None:
        self.base_url = base_url
        message = (
            f"Cannot connect to Ollama at {base_url}. "
            "Is Ollama running? Start it with: ollama serve"
        )
        if detail:
            message += f" ({detail})"
        super().__init__(message)


class OllamaProvider(AIProvider):
    """AI provider backed by a local Ollama instance."""

    # Hosts that must never be used as Ollama targets (cloud metadata endpoints).
    _BLOCKED_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal"})

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
    ) -> None:
        """Initialize with Ollama server URL and model name.

        Args:
            base_url: Ollama server base URL (default: http://localhost:11434).
            model: Model name to use (default: llama3.3).

        Raises:
            ValueError: If the URL scheme is not http/https or targets a blocked host.
        """
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Ollama base URL must use http or https scheme, got: {parsed.scheme}")
        if parsed.hostname in self._BLOCKED_HOSTS:
            raise ValueError(f"Ollama base URL targets a blocked host: {parsed.hostname}")
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def name(self) -> str:
        return "ollama"

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to Ollama.

        The tier parameter is accepted for interface compatibility but ignored
        — Ollama uses a single local model for all tiers.
        """
        messages = [{"role": "user", "content": prompt}]

        system_msg = _system_prompt_for_feature(feature)
        if system_msg:
            messages.insert(0, {"role": "system", "content": system_msg})

        payload: dict = {
            "model": self._model,
            "messages": messages,
        }

        # Request JSON output for structured features (not plain complete)
        if feature != AIFeature.complete:
            payload["format"] = "json"

        url = f"{self._base_url}/v1/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(self._base_url, str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise OllamaConnectionError(
                self._base_url, f"Request timed out after {_TIMEOUT_SECONDS}s"
            ) from exc

        content = data["choices"][0]["message"]["content"]
        model_used = data.get("model", self._model)

        # Extract token usage from Ollama response
        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0)
            or usage_data.get("prompt_eval_count", 0),
            output_tokens=usage_data.get("completion_tokens", 0) or usage_data.get("eval_count", 0),
        )

        # Try to parse structured data for known features
        structured = _try_parse_structured(content, feature)

        # JSON retry: if structured feature but parsing failed, retry once
        if feature != AIFeature.complete and structured is None:
            structured = await self._retry_json(messages, payload, url, feature)

        return AIResponse(
            content=content,
            provider="ollama",
            feature=feature,
            structured=structured,
            model=model_used,
            usage=usage,
        )

    async def _retry_json(
        self,
        messages: list[dict],
        payload: dict,
        url: str,
        feature: AIFeature,
    ) -> object | None:
        """Retry once with an explicit JSON instruction appended."""
        logger.debug("Ollama response was not valid JSON for %s, retrying once", feature)
        retry_messages = [*messages, {"role": "user", "content": "Return valid JSON only."}]
        retry_payload = {**payload, "messages": retry_messages}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=retry_payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            logger.debug("Ollama JSON retry failed")
            return None

        content = data["choices"][0]["message"]["content"]
        return _try_parse_structured(content, feature)

    async def embed(self, text: str, **kwargs: object) -> list[float]:
        """Generate an embedding vector via Ollama's /api/embeddings endpoint.

        Uses the model specified by EMBEDDING_MODEL (default: nomic-embed-text),
        NOT the chat model configured for completions/scoring.

        Raises:
            OllamaConnectionError: If the Ollama server is unreachable.
            RuntimeError: If the response doesn't contain a valid embedding.
        """
        from career_os.config import settings

        model = kwargs.get("model", settings.embedding_model) or "nomic-embed-text"
        url = f"{self._base_url}/api/embeddings"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={"model": model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(self._base_url, str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise OllamaConnectionError(
                self._base_url, f"Embedding request timed out after {_TIMEOUT_SECONDS}s"
            ) from exc

        embedding = data.get("embedding")
        if not embedding or not isinstance(embedding, list):
            raise RuntimeError(
                f"Ollama /api/embeddings did not return a valid embedding "
                f"(model={model}, keys={list(data.keys())})"
            )
        return embedding

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        *,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile via Ollama."""
        prompt = (
            ROLE_FIT_GATE_PROMPT + f"Score this job against the candidate profile. "
            f"Return a JSON object with: fit_score (0-10), reasoning (detailed, ≥100 chars), "
            f"estimated_salary (string), effort_flag (low/medium/high), prep_level, prep_notes, "
            f"readiness_score (0-100), career_alignment (0-10), "
            f"score_breakdown (array of ≥3 objects, each with: factor (string), "
            f"contribution (positive or negative float), description (string)), "
            f"dimensional_scores (object with 6 floats 0-10: technical_fit, "
            f"seniority_alignment, compensation_fit, location_fit, career_trajectory, "
            f"company_fit), "
            f"ats_keywords (array of 10-15 objects, each with: keyword (string), "
            f"category (one of technical/soft_skill/tool/certification/domain), "
            f"matched (boolean — true if the profile demonstrates this keyword)).\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Profile:\n{json.dumps(profile_data, indent=2)}"
        )
        return await self.complete(prompt, feature=AIFeature.score)
