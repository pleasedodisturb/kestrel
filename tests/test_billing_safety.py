"""Billing-safety invariants for AI scoring (G-1371, COE 2026-07-19).

Background: the scoring pipeline routes through an `AI_PROVIDER_FALLBACK` chain.
In the downstream fork (Eyas) that chain silently terminated in premium Anthropic
(`claude-sonnet-5`) for months; whenever the cheaper providers ahead of it failed
(429 / 402 / missing key / outage), every dropped job billed Anthropic at premium
rates with no alarm. The original "run the cheap tier" fix was a value protected
by a note, not an invariant protected by code — and unrelated later changes eroded
it. Kestrel (upstream) carries the same architecture and the same gap: its docs
even recommend chains that collapse onto premium Claude.

This suite turns the discipline into code-enforced invariants:

  1. Every registered provider is cost-classified (forces a cost decision when a
     provider is added).
  2. The factory's premium set matches the classification and contains anthropic.
  3. `_filter_premium` drops premium providers from a chain unless opted in.
  4. `_build_fallback_chain` never builds a premium provider without the opt-in.
  5. No scheduled workflow's *literal* default chain contains a premium provider
     (Kestrel configures the chain via a repo variable, so the primary
     enforcement here is the code guard, tests 3-4).
"""

import re
from pathlib import Path

import pytest

from career_os.ai import factory
from career_os.ai.factory import _ALLOW_PREMIUM_ENV, _PREMIUM_PROVIDERS, _filter_premium

# ---------------------------------------------------------------------------
# Test-owned cost classification. Every provider in the factory registry MUST
# appear here — adding a provider without deciding its cost tier fails CI.
#
#   FREE     — no marginal cost (local / mock)
#   CHEAP    — paid but low $/call for the small models we default to
#   ROUTING  — cost depends on the resolved model (openrouter)
#   PREMIUM  — ~10-20x cheap providers (claude-sonnet-5 / opus-4-8)
# ---------------------------------------------------------------------------
FREE = "free"
CHEAP = "cheap"
ROUTING = "routing"
PREMIUM = "premium"

COST_TIER: dict[str, str] = {
    "mock": FREE,
    "demo": FREE,
    "ollama": FREE,
    "openrouter": ROUTING,
    # gpt-4o-mini default is cheap; OPENAI_MODEL can point at a pricier model,
    # but unlike openrouter the *default* is not premium, so no guard is needed.
    "openai": CHEAP,
    "together": CHEAP,
    "groq": CHEAP,
    "xai": CHEAP,
    "gemini": CHEAP,
    "mistral": CHEAP,
    "huggingface": CHEAP,
    "hf": CHEAP,
    "anthropic": PREMIUM,
}

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"

# Scheduled workflows whose runs bill on the user's own API keys. nightly.yml
# runs eval on the mock provider only, so it is excluded.
SCHEDULED_SCORING_WORKFLOWS = ["daily-scan.yml"]

# Captures the single-quoted default on an env line — matches both
#   FOO: 'literal'   and   FOO: ${{ vars.X || 'literal' }}
_QUOTED_DEFAULT = r"^\s*{key}:.*?'([^']*)'"


def _quoted_defaults(text: str, key: str) -> list[str]:
    return re.findall(_QUOTED_DEFAULT.format(key=re.escape(key)), text, re.MULTILINE)


# ---------------------------------------------------------------------------
# 1 & 2 — classification completeness and premium-set agreement
# ---------------------------------------------------------------------------
def test_every_registered_provider_is_cost_classified():
    registered = set(factory._PROVIDER_REGISTRY)
    classified = set(COST_TIER)
    missing = registered - classified
    stale = classified - registered
    assert not missing, (
        f"provider(s) {sorted(missing)} are registered but not cost-classified in "
        f"COST_TIER — decide their billing tier (FREE/CHEAP/ROUTING/PREMIUM) before "
        f"they can silently join a fallback chain (G-1371)."
    )
    assert not stale, f"COST_TIER classifies removed provider(s) {sorted(stale)}"


def test_premium_set_matches_classification_and_contains_anthropic():
    classified_premium = {name for name, tier in COST_TIER.items() if tier == PREMIUM}
    assert set(_PREMIUM_PROVIDERS) == classified_premium, (
        "factory._PREMIUM_PROVIDERS and the COST_TIER PREMIUM set disagree — keep "
        "them in sync so the guard covers exactly the premium providers."
    )
    assert "anthropic" in _PREMIUM_PROVIDERS


# ---------------------------------------------------------------------------
# 3 — the pure premium filter
# ---------------------------------------------------------------------------
# A concrete non-Anthropic model openrouter can route to cheaply. Setting
# OPENROUTER_MODEL to this keeps openrouter out of the premium-in-fallback set.
CHEAP_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct"


def test_filter_premium_drops_anthropic_by_default(monkeypatch):
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    # openrouter pointed at a cheap model so this test isolates the anthropic drop
    monkeypatch.setenv("OPENROUTER_MODEL", CHEAP_OPENROUTER_MODEL)
    assert _filter_premium(["mistral", "openrouter", "anthropic"]) == [
        "mistral",
        "openrouter",
    ]


def test_filter_premium_preserves_cheap_order(monkeypatch):
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    chain = ["groq", "mistral", "together"]
    assert _filter_premium(chain) == chain


@pytest.mark.parametrize("optin", ["1", "true", "YES", "on"])
def test_filter_premium_keeps_anthropic_when_opted_in(monkeypatch, optin):
    monkeypatch.setenv(_ALLOW_PREMIUM_ENV, optin)
    assert _filter_premium(["mistral", "anthropic"]) == ["mistral", "anthropic"]


# ---------------------------------------------------------------------------
# 3b — openrouter routing guard (G-1378): openrouter bills premium when it would
# route to Anthropic (OPENROUTER_MODEL unset -> premium default, or anthropic/*).
# ---------------------------------------------------------------------------
def test_filter_premium_drops_openrouter_when_model_unset(monkeypatch):
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)  # -> premium default
    assert _filter_premium(["groq", "openrouter"]) == ["groq"]


def test_filter_premium_drops_openrouter_when_model_is_anthropic(monkeypatch):
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-opus-4.8")
    assert _filter_premium(["groq", "openrouter"]) == ["groq"]


def test_filter_premium_keeps_openrouter_when_model_is_cheap(monkeypatch):
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", CHEAP_OPENROUTER_MODEL)
    assert _filter_premium(["groq", "openrouter"]) == ["groq", "openrouter"]


def test_filter_premium_keeps_premium_openrouter_when_opted_in(monkeypatch):
    monkeypatch.setenv(_ALLOW_PREMIUM_ENV, "1")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)  # premium default
    assert _filter_premium(["groq", "openrouter"]) == ["groq", "openrouter"]


@pytest.mark.parametrize(
    ("model", "kept"),
    [
        ("  ANTHROPIC/Claude-Opus-4.8  ", False),  # casing + whitespace -> still dropped
        ("  meta-llama/llama-3.3-70B-Instruct  ", True),  # cheap, messy -> kept
    ],
)
def test_filter_premium_openrouter_normalizes_model(monkeypatch, model, kept):
    """`.strip().lower()` on OPENROUTER_MODEL is load-bearing (env is user-supplied)."""
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", model)
    result = _filter_premium(["groq", "openrouter"])
    assert ("openrouter" in result) is kept


def test_filter_premium_keeps_non_anthropic_premium_openrouter(monkeypatch):
    """Deliberate scope boundary (G-1378): a non-Anthropic model (even a pricey one)
    is treated as the operator's explicit choice and kept — the codebase classifies
    only the anthropic family as PREMIUM, and other OpenRouter models cannot be
    cost-classified by name. See the module NOTE in factory.py."""
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/o1-pro")
    assert _filter_premium(["groq", "openrouter"]) == ["groq", "openrouter"]


# ---------------------------------------------------------------------------
# 4 — the chain builder never constructs a premium provider without the opt-in
# ---------------------------------------------------------------------------
class _Stub:
    """Minimal stand-in so we don't need real API keys to build a chain."""

    def __init__(self, name: str) -> None:
        self.name = name


@pytest.fixture
def stub_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Replace the registry with keyless name-stamped stubs."""
    stubs = {name: (lambda n=name: _Stub(n)) for name in factory._PROVIDER_REGISTRY}
    monkeypatch.setattr(factory, "_PROVIDER_REGISTRY", stubs)
    return stubs


def test_build_fallback_chain_excludes_premium_by_default(monkeypatch, stub_registry):
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    # openrouter pointed at a cheap model so only anthropic is dropped here
    monkeypatch.setenv("OPENROUTER_MODEL", CHEAP_OPENROUTER_MODEL)
    monkeypatch.setenv("AI_PROVIDER_FALLBACK", "groq,openrouter,anthropic")
    chain = factory._build_fallback_chain()
    assert chain is not None
    names = [p.name for p in chain]
    assert "anthropic" not in names, "premium anthropic must not be built silently"
    assert names == ["groq", "openrouter"]


def test_build_fallback_chain_excludes_unconfigured_openrouter(monkeypatch, stub_registry):
    # groq,openrouter with no OPENROUTER_MODEL -> openrouter routes premium -> dropped.
    # Only groq survives (< 2), so _build_fallback_chain returns None: no premium
    # leg is ever constructed. NB this is not a hard failure — get_ai_provider then
    # falls through to the primary AI_PROVIDER (a warning is logged for the
    # collapse); the billing-safety guarantee is only that no premium provider is
    # built here.
    monkeypatch.delenv(_ALLOW_PREMIUM_ENV, raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setenv("AI_PROVIDER_FALLBACK", "groq,openrouter")
    assert factory._build_fallback_chain() is None


def test_build_fallback_chain_includes_premium_when_opted_in(monkeypatch, stub_registry):
    monkeypatch.setenv(_ALLOW_PREMIUM_ENV, "1")
    monkeypatch.setenv("AI_PROVIDER_FALLBACK", "mistral,anthropic")
    chain = factory._build_fallback_chain()
    assert chain is not None
    assert [p.name for p in chain] == ["mistral", "anthropic"]


# ---------------------------------------------------------------------------
# 5 — scheduled-workflow invariant (best-effort; chain is usually a repo var)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("workflow", SCHEDULED_SCORING_WORKFLOWS)
def test_scheduled_chain_has_no_premium_literal_default(workflow):
    path = WORKFLOWS_DIR / workflow
    assert path.exists(), f"expected scheduled workflow not found: {path}"
    defaults = _quoted_defaults(path.read_text(), "AI_PROVIDER_FALLBACK")
    if not defaults:
        pytest.skip(
            f"{workflow} sets AI_PROVIDER_FALLBACK from a repo variable, not a literal "
            f"default — the premium chain is enforced by the _filter_premium code guard "
            f"(tests 3-4), not this file-level check."
        )
    premium_tiered = {name for name, tier in COST_TIER.items() if tier == PREMIUM}
    for chain in defaults:
        providers = {p.strip().lower() for p in chain.split(",") if p.strip()}
        hit = providers & premium_tiered
        assert not hit, (
            f"{workflow}: premium provider(s) {sorted(hit)} in default chain "
            f"'{chain}'. Premium fallback must be opt-in, not a hardcoded default "
            f"(G-1371)."
        )
