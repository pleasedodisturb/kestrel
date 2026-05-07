# PII Safety Boundary

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Ensure your personal data never reaches an AI provider that might use it for training.

## What This Delivers

Kestrel separates your data into two categories: public data (job descriptions, company names, role titles) and private data (your resume, cover letters, contact information, personal stories). When scoring jobs, only public data goes to the AI provider. Your private data stays on your machine unless you explicitly send it for operations like cover letter generation, and even then, Kestrel checks whether the selected provider has adequate privacy guarantees.

Each AI provider in the system carries privacy metadata: whether it trains on API data, how long it retains inputs, whether it offers zero-data-retention (ZDR) guarantees, and its GDPR compliance status. This information comes from the privacy registry, which is based on research into each provider's actual policies rather than marketing claims. When you pick a provider, Kestrel shows you exactly what happens to your data with that choice.

PII masking runs before any data leaves your machine. Email addresses, phone numbers, LinkedIn URLs, and GitHub URLs are detected and replaced with placeholders. The AI sees anonymized content. When the response comes back, the original values are restored. This happens transparently on every API call.

For providers without ZDR guarantees, Kestrel blocks personal data by default. You can override this for individual operations if you understand the tradeoff, but the default is protective. The system does not rely on you remembering which providers are safe. It checks for you.

## How It Works

The PII masking layer sits between the service layer and the AI provider abstraction. Before a prompt goes to any provider, the masking module scans for known PII patterns and replaces them with tokens. The response comes back, and the tokens are swapped for the original values. The masking uses regex patterns for common PII formats.

The privacy registry is a JSON file that maps each provider to its privacy profile. This data feeds into the frontend's provider selection UI, where privacy tiers are displayed alongside performance and cost information. The registry also informs backend decisions about which operations are allowed with which providers.

## Current Status

*Shipped in [v0.12.0](../../CHANGELOG.md#0120-2026-04-23)*

PII masking is active on all AI API calls. The privacy registry covers all eleven providers with factual privacy metadata sourced from provider documentation and policy pages. The default configuration blocks personal data from providers without ZDR guarantees. Provider privacy tiers are visible in the frontend provider selection UI.

## Related Milestones

- **[AI Provider System](ai-provider-system.md)** -- Privacy layer wraps the provider abstraction
- **[Cost Control](cost-control.md)** -- Privacy tier affects which presets are available

---

*For Contributors*

## Architecture

The PII safety boundary spans the AI provider layer:

- `src/career_os/ai/pii_masking.py` -- Regex-based PII detection and masking. Scans for email addresses, phone numbers, LinkedIn URLs, and GitHub URLs. Replaces matches with indexed tokens (`[EMAIL_1]`, `[PHONE_1]`, etc.) and restores originals in responses.
- `src/career_os/ai/privacy.py` -- Privacy registry loader and per-provider privacy metadata access. Reads from the JSON registry file.
- `src/career_os/privacy_registry.json` -- Per-provider privacy profiles: tier classification, training policy, retention period, ZDR availability, GDPR status.
- `src/career_os/api/privacy.py` -- REST endpoints for querying provider privacy information from the frontend.

The PII masking layer wraps the `CachedAIProvider`, which itself wraps the actual provider implementation. The call chain is: service -> PII mask -> cache check -> provider -> cache store -> PII unmask -> service. This ensures that cached responses also have PII restored correctly.

The privacy registry is a static JSON file rather than a database table. This makes it easy to review, version, and audit. Updates require a code change, which means privacy metadata goes through the same PR review process as any other code.

## Research & Decisions

Annotated links to research and reference documents:

- [Provider Privacy Audit](../research/provider-privacy-audit.md) -- Trust matrix: per-provider training policies, retention periods, ZDR status, and GDPR compliance history
- [LLMs, Tokens, and Privacy](../research/llms-tokens-privacy.md) -- 2026 LLM privacy landscape: EU sovereignty, data handling policies, and the real cost of "free" tiers
- [AI Providers Reference](../reference/AI-PROVIDERS.md) -- Provider guide with privacy tier indicators and setup instructions

## BMAD Integration

**PRD Status:** Not started

A PRD would define PII detection pattern rules, the provider privacy verification and audit process, user consent flow requirements, and the privacy tier classification methodology.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
