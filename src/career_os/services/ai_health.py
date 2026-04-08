"""AI provider health check service.

Checks connectivity, credits, and rate limits for configured AI providers.
Each provider is checked independently — one failure does not affect others.

Reads provider configuration from stored integration config (ai_providers)
and only reports health for runtime-supported providers (mock, openrouter).
"""

import contextlib
import json
import logging
import os
import time

import httpx
from sqlalchemy.orm import Session

from career_os.models.integrations import IntegrationConfig
from career_os.schemas.ai_health import (
    AIHealthResponse,
    ProviderCredits,
    ProviderHealthStatus,
    ProviderRateLimit,
)

logger = logging.getLogger(__name__)

# Runtime-supported providers (from ai/factory.py)
RUNTIME_SUPPORTED_PROVIDERS = {"mock", "openrouter"}

# Provider display names
_PROVIDER_DISPLAY_NAMES = {
    "mock": "Mock (Development)",
    "openrouter": "OpenRouter",
}

# Credential key mapping from integration config → env var fallback
_CREDENTIAL_KEY_MAP = {
    "openrouter": "openrouter_api_key",
}


# ---------------------------------------------------------------------------
# Per-provider health check functions
# ---------------------------------------------------------------------------


async def _check_mock() -> ProviderHealthStatus:
    """Mock provider is always reachable."""
    return ProviderHealthStatus(
        name="mock",
        display_name="Mock (Development)",
        status="reachable",
        is_default=False,
        error_message=None,
        credits=None,
        rate_limit=None,
        response_time_ms=0.1,
    )


async def _check_openrouter(api_key: str) -> ProviderHealthStatus:
    """Check OpenRouter API connectivity and credits."""
    if not api_key.strip():
        return ProviderHealthStatus(
            name="openrouter",
            display_name="OpenRouter",
            status="not_configured",
            error_message="OPENROUTER_API_KEY not set",
        )

    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=10.0) as client:
            # OpenRouter exposes credits via /api/v1/auth/key
            resp = await client.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        elapsed_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            # OpenRouter returns {"data": {"label": "...", "usage": ..., "limit": ...}}
            key_data = data.get("data", {})
            credits = None
            if key_data:
                usage = key_data.get("usage")
                limit = key_data.get("limit")
                if limit is not None:
                    remaining = (limit - usage) if usage is not None else None
                    credits = ProviderCredits(
                        remaining=remaining,
                        total=limit,
                        unit="USD",
                    )
                elif usage is not None:
                    credits = ProviderCredits(
                        remaining=None,
                        total=None,
                        unit="USD",
                    )

            rate_limit = None
            if key_data.get("rate_limit"):
                rl = key_data["rate_limit"]
                rate_limit = ProviderRateLimit(
                    requests_per_minute=rl.get("requests"),
                    tokens_per_minute=rl.get("tokens"),
                )

            return ProviderHealthStatus(
                name="openrouter",
                display_name="OpenRouter",
                status="reachable",
                credits=credits,
                rate_limit=rate_limit,
                response_time_ms=round(elapsed_ms, 1),
            )

        if resp.status_code in (401, 403):
            return ProviderHealthStatus(
                name="openrouter",
                display_name="OpenRouter",
                status="error",
                error_message=f"Authentication failed (HTTP {resp.status_code})",
                response_time_ms=round(elapsed_ms, 1),
            )

        return ProviderHealthStatus(
            name="openrouter",
            display_name="OpenRouter",
            status="unreachable",
            error_message=f"Unexpected HTTP {resp.status_code}",
            response_time_ms=round(elapsed_ms, 1),
        )

    except httpx.TimeoutException:
        return ProviderHealthStatus(
            name="openrouter",
            display_name="OpenRouter",
            status="unreachable",
            error_message="Connection timed out",
        )
    except Exception as exc:
        logger.debug("OpenRouter health check failed: %s", exc)
        return ProviderHealthStatus(
            name="openrouter",
            display_name="OpenRouter",
            status="error",
            error_message=str(exc),
        )





# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _get_stored_ai_config(db: Session | None) -> dict[str, str]:
    """Read AI provider credentials from stored integration config.

    Falls back to environment variables if no stored config exists.
    Returns a dict of credential key → value.
    """
    creds: dict[str, str] = {}
    if db is not None:
        row = (
            db.query(IntegrationConfig)
            .filter(IntegrationConfig.name == "ai_providers")
            .first()
        )
        if row and row.credentials:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                creds = json.loads(row.credentials)

    return creds


def _resolve_default_provider(stored_config: dict[str, str]) -> str:
    """Determine the default AI provider from stored config or env var."""
    stored_default = stored_config.get("default_provider", "").strip().lower()
    if stored_default and stored_default in RUNTIME_SUPPORTED_PROVIDERS:
        return stored_default
    return os.getenv("AI_PROVIDER", "mock").strip().lower()


def _resolve_api_key(provider: str, stored_config: dict[str, str]) -> str:
    """Get the API key for a provider from stored config, falling back to env."""
    config_key = _CREDENTIAL_KEY_MAP.get(provider)
    if config_key:
        stored = stored_config.get(config_key, "").strip()
        if stored:
            return stored
    # Fallback to env var
    env_key_map = {
        "openrouter": "OPENROUTER_API_KEY",
    }
    env_key = env_key_map.get(provider, "")
    return os.getenv(env_key, "") if env_key else ""


async def check_all_providers(db: Session | None = None) -> AIHealthResponse:
    """Check health of all runtime-supported AI providers.

    Reads configuration from stored integration config (ai_providers),
    falling back to environment variables. Only reports providers
    that the runtime factory actually supports (mock, openrouter).
    """
    stored_config = _get_stored_ai_config(db)
    default_provider = _resolve_default_provider(stored_config)

    results: list[ProviderHealthStatus] = []

    # Mock — always available
    try:
        status = await _check_mock()
    except Exception as exc:
        status = ProviderHealthStatus(
            name="mock",
            display_name="Mock (Development)",
            status="error",
            error_message=str(exc),
        )
    results.append(status)

    # OpenRouter — the only real provider currently supported
    openrouter_key = _resolve_api_key("openrouter", stored_config)
    try:
        status = await _check_openrouter(openrouter_key)
    except Exception as exc:
        status = ProviderHealthStatus(
            name="openrouter",
            display_name="OpenRouter",
            status="error",
            error_message=str(exc),
        )
    results.append(status)

    # Mark the default provider
    for p in results:
        p.is_default = p.name == default_provider

    return AIHealthResponse(
        providers=results,
        default_provider=default_provider,
    )


async def check_single_provider(
    provider_name: str, db: Session | None = None
) -> ProviderHealthStatus:
    """Check health of a single AI provider.

    Only runtime-supported providers (mock, openrouter) are checked.
    """
    name = provider_name.strip().lower()

    if name not in RUNTIME_SUPPORTED_PROVIDERS:
        return ProviderHealthStatus(
            name=name,
            display_name=name,
            status="error",
            error_message=(
                f"Provider '{name}' is not supported by the runtime. "
                f"Supported: {', '.join(sorted(RUNTIME_SUPPORTED_PROVIDERS))}"
            ),
        )

    stored_config = _get_stored_ai_config(db)

    checkers = {
        "mock": lambda: _check_mock(),
        "openrouter": lambda: _check_openrouter(
            _resolve_api_key("openrouter", stored_config)
        ),
    }

    checker = checkers.get(name)
    if checker is None:
        return ProviderHealthStatus(
            name=name,
            display_name=name,
            status="error",
            error_message=f"Unknown provider: {name}",
        )

    try:
        status = await checker()
    except Exception as exc:
        status = ProviderHealthStatus(
            name=name,
            display_name=name,
            status="error",
            error_message=str(exc),
        )

    default_provider = _resolve_default_provider(stored_config)
    status.is_default = status.name == default_provider
    return status
