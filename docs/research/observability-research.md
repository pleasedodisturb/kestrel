---
title: "Observability Research"
description: "Research synthesis for LLM observability — platform selection, integration patterns, deployment model"
---

# Observability Research: Seeing Inside Your AI Pipeline

**Researched:** 2026-04-20
**Status:** Research complete — Langfuse v3 selected, blueprint shipped
**Scope:** LLM observability for Kestrel's AI provider layer

---

## Philosophy: Human-First, Data-Driven

This document follows a deliberate research philosophy: we do deep, thorough research to understand the full landscape, but research findings **inform** decisions — they don't make them.

Every recommendation here weighs:

- **Developer wellbeing** — mental load, maintenance burden for a solo developer
- **Sustainability** — will this still be manageable in 6 months?
- **Real-world consequences** — for the developer, for users, for the project's future
- **Balance** — across competing concerns, not optimizing for a single metric

Observability is where Kestrel moves from "it works on my machine" to "I can prove it works, and I know when it doesn't." Scoring, coaching, gap analysis — all of them depend on AI calls that are fundamentally non-deterministic. Without observability, debugging means guessing.

---

## Context: What We Already Have

Kestrel's AI layer is mature but opaque:

| Area | What's In Place | Status |
|------|----------------|--------|
| **6 providers** | Mock, OpenRouter, Anthropic, Together, Ollama + factory pattern | Production-ready |
| **Token tracking** | `TokenUsage` in `AIResponse` (input/output/cache tokens) | Captured, never persisted |
| **Response caching** | `CachedProvider` with encrypted SQLite, 7-day TTL | Active, no metrics |
| **PII masking** | `MaskedProvider` with regex-based detection | Active, no metrics |
| **Complexity routing** | SIMPLE/STANDARD/COMPLEX tier → model mapping | Active, no visibility |
| **Borderline 2-pass** | Scores in [4.0, 6.5] get rescored and averaged | Active, no cost tracking |

The gap: we capture token usage in every AIResponse object, but it's never persisted, aggregated, or visualized. Cache hit rates, PII detection counts, and provider error rates are invisible.

---

## Research Synthesis: Four Streams

### Stream 1: Platform Selection

**The data says:** Six platforms were evaluated: Langfuse, Phoenix (Arize), Opik (Comet), Braintrust, Helicone, and OpenLIT.

| Platform | License | Self-hosted | GitHub Stars | Python SDK | OpenAI-compat | Eval built-in |
|----------|---------|-------------|-------------|------------|---------------|---------------|
| Langfuse | MIT | Yes (Docker) | 25K+ | v4 (decorator-based) | Yes | Yes |
| Phoenix | BSD-3 | Yes (Docker) | 8K+ | Yes | Yes | Yes |
| Opik | Apache-2.0 | Yes (Docker) | 4K+ | Yes | Yes | Yes |
| Braintrust | Proprietary | No (cloud only) | — | Yes | Yes | Yes |
| Helicone | Apache-2.0 | Yes (Docker) | 5K+ | Proxy-based | Proxy | No |
| OpenLIT | Apache-2.0 | Yes (OTEL) | 2K+ | OpenTelemetry | Via OTEL | Basic |

**The trade-off:** Langfuse has the largest community and most mature self-hosted story, but requires 6 services (Postgres, ClickHouse, Redis, MinIO, web, worker). Phoenix is simpler (single container) but less feature-complete. Helicone is proxy-based (no code changes) but can't capture application-level context. OpenLIT uses OpenTelemetry (industry standard) but the ecosystem is still immature for LLM-specific traces.

**Our recommendation:** Langfuse v3. The 6-service stack sounds heavy, but it's a docker-compose away and the resource requirements (4 vCPU / 8 GB) are reasonable for a self-hosted platform. The Python SDK v4's `@observe` decorator pattern maps perfectly to Kestrel's provider architecture. The MIT license means no licensing surprises. And the headless init (`LANGFUSE_INIT_*` env vars) makes first-time setup trivial.

**What we ruled out:**
- Phoenix: Good for quick prototyping, but less mature for production self-hosting
- Helicone: Proxy approach doesn't capture cache/PII layer metadata
- OpenLIT: OTEL collector adds operational complexity without clear benefit over Langfuse's simpler model
- Braintrust: Cloud-only is a non-starter for a privacy-first, self-hosted project

### Stream 2: Integration Pattern

**The data says:** Three integration approaches exist:

1. **Decorator-based** (`@observe`): Wrap existing methods, Langfuse SDK handles context propagation
2. **Proxy-based** (Helicone-style): Route HTTP calls through a proxy that logs everything
3. **OpenTelemetry**: Use OTEL spans with LLM-specific semantic conventions

**The trade-off:** Decorators require code changes but give the most control (we can attach metadata like cache hit/miss, PII counts). Proxies need zero code changes but can only see HTTP traffic (no application context). OTEL is future-proof but adds collector infrastructure and the LLM semantic conventions are still in flux.

**Our recommendation:** Decorator-based with Langfuse SDK v4. The `@observe(as_type="generation")` decorator on provider methods + `update_current_generation()` for model/usage data is exactly right for our architecture. The `propagate_attributes()` context manager at the route level injects user/session context. Key insight: Langfuse SDK v4's `get_client()` returns a no-op client when unconfigured, so we can decorate unconditionally — zero overhead when Langfuse isn't set up.

### Stream 3: What to Trace

**The data says:** LLM observability typically captures: model, input/output, token counts, latency, cost, errors, and application metadata. For Kestrel specifically, the following are high-value:

| Signal | Why it matters | Privacy concern |
|--------|---------------|-----------------|
| Model used | Detect tier routing behavior | None |
| Token usage | Cost tracking, budget alerts | None |
| Latency | Provider comparison, SLA monitoring | None |
| Input/output | Debugging prompt issues | Truncated to 500 chars to limit exposure |
| Cache hit/miss | Measure cache effectiveness | None |
| PII detection count | Verify masking is working | Count only, never PII values |
| Feature type | Which AI features are used most | None |
| Complexity tier | Verify routing decisions | None |

**The trade-off:** Logging full prompts gives maximum debuggability but increases storage and privacy risk. Logging nothing is safe but useless.

**Our recommendation:** Log truncated inputs/outputs (500 chars) for debuggability, full token counts for cost tracking, and metadata (feature type, tier, cache status, PII count) for operational visibility. Never log actual PII values — only detection counts. This balances debuggability with Kestrel's privacy-first principles.

### Stream 4: Deployment Model

**The data says:** Langfuse offers cloud (hosted) and self-hosted options. Self-hosted v3 requires: PostgreSQL (metadata), ClickHouse (analytics), Redis (queues), MinIO (blob storage), plus web and worker services.

**The trade-off:** Cloud is zero-ops but sends your LLM traces to Langfuse's servers. Self-hosted keeps everything local but requires 4+ vCPU and 8 GB RAM.

**Our recommendation:** Self-hosted via docker-compose overlay. This aligns with Kestrel's self-hosted, privacy-first philosophy. The compose file uses `docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up` so users opt in explicitly. All credentials live in `langfuse.env` (gitignored). Headless init creates the org/project/keys on first boot.

---

## Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Langfuse v3 over Phoenix/Opik/Helicone | Largest community, MIT license, best self-hosted story, decorator SDK maps to our architecture |
| 2 | Optional dependency (`pip install kestrel-app[observability]`) | Kestrel must work without Langfuse installed |
| 3 | Unconditional decoration with no-op fallback | SDK handles no-op when unconfigured; simpler than conditional imports everywhere |
| 4 | Truncated I/O (500 chars) | Balance debuggability with privacy/storage |
| 5 | PII count only, never values | Aligns with privacy-first principles |
| 6 | Docker Compose overlay (not embedded) | Users opt into observability infrastructure explicitly |
| 7 | Port 3100 for Langfuse UI | Avoids conflicts with Kestrel (8100) and frontend (8101) |

---

## What's Next

This is Phase 1 (blueprint + instrumentation). Future phases:

- **Phase 2:** Langfuse evaluation/scoring dimensions — use Langfuse's eval framework to grade AI output quality
- **Phase 3:** Dataset creation from production traces — build regression test sets from real-world data
- **Phase 4:** Cost alerting and budget enforcement — alert when monthly AI spend exceeds thresholds
