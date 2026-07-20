"""Cross-provider contract tests (G-1348).

Two invariants that must hold for EVERY real provider, so a single provider can't
silently drift or die:

1. Every ``*_provider`` module imports. `openai_provider` imported a
   non-existent `_scoring_user_prompt` from `openrouter_provider`, so one of the
   11 advertised providers raised ImportError and was unusable — with no test
   catching it (G-1348).
2. Every real provider prepends ROLE_FIT_GATE_PROMPT (the anti-halo role-fit
   gate) to what it actually sends for scoring. openai was the only real provider
   missing it. Asserted against the outgoing HTTP payload rather than an internal
   helper, so it holds regardless of how each provider builds its request.
"""

import importlib
import json
import pkgutil

import httpx
import pytest

import career_os.ai as ai_pkg
from career_os.ai.base import ROLE_FIT_GATE_PROMPT

# ---------------------------------------------------------------------------
# 1 — every provider module must import
# ---------------------------------------------------------------------------
PROVIDER_MODULES = sorted(
    m.name for m in pkgutil.iter_modules(ai_pkg.__path__) if m.name.endswith("_provider")
)


def test_provider_modules_discovered():
    """Guard the guard: the module sweep must actually find the providers."""
    assert len(PROVIDER_MODULES) >= 10, PROVIDER_MODULES
    assert "openai_provider" in PROVIDER_MODULES


@pytest.mark.parametrize("module_name", PROVIDER_MODULES)
def test_provider_module_imports(module_name: str):
    """Every provider module must import (G-1348: openai_provider did not)."""
    importlib.import_module(f"career_os.ai.{module_name}")


# ---------------------------------------------------------------------------
# 2 — every real provider prepends the anti-halo role-fit gate when scoring
# ---------------------------------------------------------------------------
# name -> (module, class, kwargs). "mock"/"demo" are excluded: MockProvider
# returns canned data and never calls an LLM, so the guard is meaningless there.
REAL_PROVIDERS = {
    "anthropic": ("anthropic_provider", "AnthropicProvider", {"api_key": "test-key"}),
    "gemini": ("gemini_provider", "GeminiProvider", {"api_key": "test-key"}),
    "groq": ("groq_provider", "GroqProvider", {"api_key": "test-key"}),
    "huggingface": ("huggingface_provider", "HuggingFaceProvider", {"api_key": "test-key"}),
    "mistral": ("mistral_provider", "MistralProvider", {"api_key": "test-key"}),
    "ollama": ("ollama_provider", "OllamaProvider", {}),
    "openai": ("openai_provider", "OpenAIProvider", {"api_key": "test-key"}),
    "openrouter": ("openrouter_provider", "OpenRouterProvider", {"api_key": "test-key"}),
    "together": ("together_provider", "TogetherProvider", {"api_key": "test-key"}),
    "xai": ("xai_provider", "XAIProvider", {"api_key": "test-key"}),
}

# A distinctive slice of the gate — matching the whole multi-paragraph prompt is
# brittle, but this phrase is unique to it.
_GATE_MARKER = "role-fit gate (anti-halo)"


class _Captured(Exception):
    """Raised to short-circuit once the outgoing request has been captured."""


@pytest.fixture
def capture_request(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture the body of the first outgoing HTTP request, then short-circuit.

    Patches both `post` (what most providers call) and `send` (the lower-level
    path), so this works no matter how a provider issues its request.
    """
    bodies: list[str] = []

    async def fake_post(self, url, **kwargs):  # noqa: ANN001, ANN202
        payload = kwargs.get("json")
        bodies.append(json.dumps(payload) if payload is not None else str(kwargs))
        raise _Captured

    async def fake_send(self, request, **kwargs):  # noqa: ANN001, ANN202
        bodies.append(request.content.decode("utf-8", errors="replace"))
        raise _Captured

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    return bodies


@pytest.mark.parametrize("provider_name", sorted(REAL_PROVIDERS))
async def test_every_real_provider_prepends_role_fit_gate(
    provider_name: str, capture_request: list[str]
):
    """The anti-halo gate must reach the API for every real provider (G-1348)."""
    module_name, class_name, kwargs = REAL_PROVIDERS[provider_name]
    cls = getattr(importlib.import_module(f"career_os.ai.{module_name}"), class_name)
    provider = cls(**kwargs)

    try:
        await provider.score("Senior Backend Engineer at Acme", {"title": "PM"})
    except _Captured:
        pass  # expected — we only need the outgoing request
    except Exception as exc:  # pragma: no cover - diagnostic aid
        if not capture_request:
            pytest.fail(f"{provider_name}: no request captured before {exc!r}")

    assert capture_request, f"{provider_name} issued no HTTP request during score()"
    assert _GATE_MARKER in capture_request[0], (
        f"{provider_name} does not send ROLE_FIT_GATE_PROMPT when scoring — every "
        f"real provider must prepend the anti-halo role-fit gate (G-1348)."
    )


def test_gate_marker_is_actually_in_the_prompt():
    """Pin the marker to the real constant so the test can't silently pass."""
    assert _GATE_MARKER in ROLE_FIT_GATE_PROMPT
