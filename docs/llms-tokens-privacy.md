---
layout: default
title: LLMs, Tokens, and Privacy
permalink: /docs/llms-tokens-privacy
---

# The 2026 LLM API landscape for BYOK consumer apps

**OpenRouter's OAuth PKCE flow is the strongest single integration point for a BYOK consumer app like Kestrel**, giving end users frictionless access to 300+ models without copying API keys, while per-key spending limits and zero-data-retention controls protect both wallet and privacy. For EU-conscious users, Mistral's La Plateforme is the clear sovereign default — French-hosted, GDPR-native, with self-serve DPAs. Direct keys to Anthropic, OpenAI, and Google should be offered as power-user options. DeepSeek's extraordinary pricing ($0.28/$0.42 per MTok) is tempting but legally radioactive for EU personal data. The broader market context: **LLM API prices dropped roughly 80% between early 2025 and early 2026**, driven by DeepSeek's disruption and aggressive competition. Prompt caching now delivers 90% input discounts at Anthropic, OpenAI, and Google, making system-prompt-heavy use cases like CV analysis dramatically cheaper than headline rates suggest.

---

## Aggregators and model routers offer unified access at minimal cost

### OpenRouter: the aggregator frontrunner

OpenRouter provides a single OpenAI-compatible API across **300+ models from 60+ providers**, processing over 100 trillion tokens annually. For Kestrel, its standout feature is the **OAuth PKCE flow**: the app redirects users to OpenRouter's auth page, they log in (or create an account), authorize the app, and receive a programmatically generated API key — no copying strings from developer consoles. The entire flow takes under two minutes for a non-technical user.

OpenRouter's pricing model is often misunderstood. **Per-token prices match underlying providers exactly** — there is no inference markup. Instead, OpenRouter charges a **5.5% fee when users purchase credits** (effectively ~5.8% on usable purchasing power). Users pre-load credits via credit card or crypto; credits expire after 365 days. For a user spending €10/month, the fee is roughly €0.55.

Privacy controls are granular: prompts and completions are **not stored by default** (only metadata — timestamps, model, token counts). Two separate opt-ins control prompt logging and data use for product improvement. Critically, enabling prompt logging grants OpenRouter an "irrevocable right to further commercial use" of inputs and outputs — Kestrel should strongly discourage this for CV data. Per-request or account-wide **ZDR enforcement** routes only to zero-data-retention endpoints; if none exist for a chosen model, the request fails rather than silently degrading privacy. EU-region routing (`eu.openrouter.ai`) exists but is currently **enterprise-only**.

Users can also bring their own direct provider keys through OpenRouter (first 1M BYOK requests/month free, then 5% surcharge), getting unified routing and fallback while using their own billing relationships.

### Other aggregators at a glance

**Groq** runs custom LPU silicon delivering **394–1,000 tokens/sec** on popular models — roughly 5–10× faster than GPU-based providers. Llama 3.1 8B runs at 840 tok/s; GPT-OSS 120B at 500 tok/s. Pricing is competitive (Llama 3.1 8B at $0.05/$0.08), and there is a free tier with no credit card required. Data retention defaults to 30 days but ZDR is available in account settings.

**Cerebras** uses wafer-scale chips to achieve even higher throughput on some models — **Llama 4 Maverick at 2,522 tok/s**, with a free tier of 1M tokens/day (scaling to 24M/day for developers). However, the model catalog is narrower than OpenRouter or Together AI, and detailed privacy documentation is sparse.

**Together AI** focuses exclusively on open-weight models (200+), with strong fine-tuning support (LoRA, SFT, DPO) and batch inference at 50% discount. SOC 2 compliant, but privacy/DPA documentation is less mature than Anthropic or OpenAI. Pricing starts at $0.02/MTok blended for tiny models, with Llama 3.3 70B around $0.88 blended.

**Fireworks AI** emphasizes speed and structured output — 16 of 17 tracked models support function calling. HIPAA and SOC 2 compliant. Cached input tokens receive a 50% discount.

**DeepInfra** is the price leader for open-weight inference: Llama 3.1 8B at **$0.03/$0.05 per MTok** (cheapest in market), with a claimed zero-retention policy and SOC 2 + ISO 27001 + GDPR + HIPAA compliance.

**Perplexity API** (Sonar models) is uniquely relevant for a job-search app — it combines LLM reasoning with **real-time web search**, returning cited answers. Sonar at $1/$1 per MTok is useful for features like "research this company" or "find similar roles." Sonar Pro at $3/$15 handles deeper analytical queries.

| Provider | Models | Speed advantage | Cheapest model (blended) | Free tier | ZDR |
|---|---|---|---|---|---|
| OpenRouter | 300+ (all types) | Varies by backend | Free models available | 50 req/day | ✅ Per-request |
| Groq | ~15 open-weight | 5–10× GPU speed | $0.05/$0.08 (Llama 8B) | ✅ No CC needed | ✅ Account setting |
| Cerebras | ~15 open-weight | 10–20× GPU speed | $0.10 blended (Llama 8B) | 1M tok/day | Not documented |
| Together AI | 200+ open-weight | Standard | $0.02/$0.04 (Gemma 3n) | Signup credits | Not documented |
| Fireworks AI | 17+ open-weight | Optimized engine | $0.20 blended (Qwen3 8B) | $1 credit | Not documented |
| DeepInfra | 93+ open-weight | Standard | $0.02/$0.02 (Llama 3.2 3B) | Signup credits | ✅ Default |
| Perplexity | 6 Sonar models | Built-in search | $1/$1 (Sonar) | None | Not documented |

---

## First-party APIs: pricing, models, and the privacy fine print

### Anthropic Claude

The current lineup is **Opus 4.6** ($5/$25 per MTok, 1M context), **Sonnet 4.6** ($3/$15, 1M context), and **Haiku 4.5** ($1/$5, 200K context). These represent dramatic price improvements — Opus 4.1 cost $15/$75 just months ago. Prompt caching delivers **90% savings** on cache reads ($0.30/MTok for cached Sonnet input vs. $3.00 fresh). Batch API offers 50% off. Stacking both yields cached-batch Opus input at ~$0.25/MTok — 95% below list.

API data is **never used for training** under Anthropic's Commercial Terms. Retention was reduced to **7 days** in September 2025 (down from 30). ZDR is available but requires enterprise approval — not self-serve. There is **no native EU data processing**; EU residency requires routing through AWS Bedrock (6–7 EU regions) or Google Vertex AI (10 EU regions), each with a ~10% price premium. DPA with SCCs is automatically incorporated into Commercial Terms since January 2026.

Key creation requires signing up at console.anthropic.com, adding a payment method ($5 minimum), and generating a key shown only once. Moderately technical — rated 3/5 for non-technical users.

### OpenAI

The model range spans **GPT-5.4** ($2.50/$10, flagship), **GPT-5** ($1.25/$10, general), **GPT-5 Mini** ($0.25/$2), and **GPT-5 Nano** ($0.05/$0.40). Reasoning models include **o4-mini** ($1.10/$4.40) and **o3** ($2/$8). Legacy GPT-4.1 ($2/$8, 1M context) remains available. Automatic prompt caching delivers **50–75% input savings** with no code changes. Batch API gives 50% off.

API data is **not used for training** (long-standing policy). Default retention is **30 days** for abuse monitoring. ZDR requires contacting the sales team — not self-serve. Regional processing endpoints are available (including EU) with a 10% premium for models released after March 2026. DPA with SCCs is published; OpenAI Ireland Limited processes EEA data.

Structured output is the most mature in the industry — constrained decoding guarantees valid JSON schemas. Key creation at platform.openai.com is polished but requires a $5 minimum prepayment and navigating project/org structure. Rated 3/5 for non-technical users.

### Google Gemini

The standout value proposition is **Gemini 2.5 Flash** at $0.15–$0.30 input / $0.60–$2.50 output, with a **1M-token context window**. Gemini 2.5 Pro at $1.25/$10 competes with GPT-5 on quality at the same price. Flash-Lite at $0.10/$0.40 is among the cheapest mainstream options. Gemini 3.1 Pro ($2/$12) is in preview.

The critical distinction: **AI Studio free tier data may be used for training** — paid tier and Vertex AI explicitly exclude training. Google AI Studio's free tier is the **most generous in the market** (~500–1,000 requests/day on Flash models, no credit card required). For any Google account holder, getting an API key takes under a minute. Vertex AI with EU regional endpoints provides full GDPR compliance, ZDR (24-hour TTL, project-isolated), and enterprise SLAs, but requires Google Cloud onboarding.

All Gemini models are natively multimodal (text, code, images, audio, video), with the industry's largest context windows.

### Mistral AI

As a French company under CNIL oversight, Mistral offers **EU data processing by default** (Sweden primary, Ireland backup). Mistral Large 3 at $2/$6 is 40–60% cheaper on output than Claude Sonnet or GPT-5. Mistral Small 3.1 at $0.20/$0.60 and Ministral 8B at $0.10/$0.10 cover budget tiers. Codestral targets code generation with 256K context.

API data is **not used for training**. Default retention is 30 days. **ZDR is available on the API** as a configurable flag. DPA is self-serve at legal.mistral.ai. Open-weight models (Mistral 7B, Mixtral) are available under Apache 2.0 for complete on-premises sovereignty. ISO 27001 certification was still in progress as of late 2025.

### DeepSeek, xAI, and Cohere

**DeepSeek V3.2** at $0.28/$0.42 per MTok (with 90% cache-hit discounts to $0.028 input) is the cheapest frontier-class API. However, **all data is processed and stored in mainland China**, subject to Chinese national security laws with no opt-out. No GDPR compliance — DeepSeek has claimed GDPR does not apply. Under active investigation by Italian, Irish, Belgian, Dutch, and French regulators. Banned by multiple government agencies. A January 2025 breach exposed 1M+ chat logs. **Not suitable for EU personal data under any circumstances via the direct API.** Self-hosting the open-weight models is the safe alternative.

**xAI Grok 4** ($3/$15) and **Grok 4.1 Fast** ($0.20/$0.50) offer a **2M-token context window** — the largest available. Notably, xAI provides an **EU API endpoint** (eu-west-1), though GDPR controversies persist from the Grok/X training data disputes. DPA available; Irish DPC investigation ongoing.

**Cohere Command A** ($2.50/$10) targets enterprise RAG workflows with strong embedding and reranking. Private VPC/on-premises deployment eliminates cloud data exposure entirely. Free trial tier (1,000 calls/month) is generous but non-production only.

### Frontier model pricing comparison

| Model | Input/MTok | Output/MTok | Cached input | Context | Provider |
|---|---|---|---|---|---|
| GPT-5 Nano | $0.05 | $0.40 | $0.005 | 128K | OpenAI |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | — | 1M | Google |
| Mistral Small 3.1 | $0.20 | $0.60 | — | 128K | Mistral |
| Grok 4.1 Fast | $0.20 | $0.50 | — | 2M | xAI |
| GPT-5 Mini | $0.25 | $2.00 | $0.025 | 200K | OpenAI |
| DeepSeek V3.2 | $0.28 | $0.42 | $0.028 | 128K | DeepSeek |
| Gemini 2.5 Flash | $0.30 | $2.50 | $0.03 | 1M | Google |
| Haiku 4.5 | $1.00 | $5.00 | $0.10 | 200K | Anthropic |
| GPT-5 | $1.25 | $10.00 | $0.125 | 400K | OpenAI |
| Gemini 2.5 Pro | $1.25 | $10.00 | $0.125 | 2M | Google |
| Mistral Large 3 | $2.00 | $6.00 | — | 128K | Mistral |
| GPT-5.4 | $2.50 | $10.00 | $0.25 | 200K | OpenAI |
| Sonnet 4.6 | $3.00 | $15.00 | $0.30 | 1M | Anthropic |
| Grok 4 | $3.00 | $15.00 | — | 2M | xAI |
| Opus 4.6 | $5.00 | $25.00 | $0.50 | 1M | Anthropic |

---

## Data retention and training policies across the landscape

This is the single most consequential dimension for Kestrel, where users send CVs, salary expectations, and employment history to third-party APIs.

### The training question is largely settled for API access

Every major Western provider — Anthropic, OpenAI, Google (paid tier), Mistral, Cohere, xAI — **does not train on API data by default**. This is a contractual commitment, not just a policy preference. The distinction between consumer chat products (which increasingly opt users into training) and API access (which does not) is critical for Kestrel's privacy story. **DeepSeek is the sole exception**: its privacy policy states all inputs are used for training with no opt-out.

### Retention varies significantly

**Anthropic** leads with **7-day retention** (reduced September 2025), the shortest among major providers. **OpenAI** retains for **30 days**. **Google Vertex AI** defaults to 24-hour in-memory caching. **Mistral** retains for 30 days. **DeepInfra** claims zero retention (data only in memory during inference). **Groq** defaults to 30 days but offers ZDR in account settings.

Zero-data-retention is available at Anthropic and OpenAI but **requires enterprise sales approval** — not self-serve for individual API users. Google offers project-level ZDR on Vertex AI. Mistral and Groq offer ZDR as account settings. OpenRouter provides ZDR as a per-request flag, routing only to compliant endpoints.

### The complete privacy matrix

| Provider | Trains on API data? | Retention | ZDR available? | Data location | DPA self-serve? |
|---|---|---|---|---|---|
| Anthropic | No | 7 days | Enterprise only | US (EU via Bedrock/Vertex) | ✅ Auto w/ Commercial Terms |
| OpenAI | No | 30 days | Enterprise only | US (EU regional endpoints) | ✅ Published |
| Google (Vertex) | No | 24 hours | ✅ Project-level | US/EU regions | ✅ Google Cloud DPA |
| Google (AI Studio free) | **May use data** | Unknown | No | US | Limited |
| Mistral | No | 30 days | ✅ API flag | EU (Sweden/Ireland) | ✅ Self-serve |
| xAI | No (API) | Unclear | Unclear | US or EU (eu-west-1) | ✅ Published |
| Cohere | No | Configurable | Enterprise only | US/Canada | Contact required |
| DeepSeek | **Yes, all data** | **Indefinite** | **No** | **China only** | **No** |
| OpenRouter | No (prompts not stored) | Metadata only | ✅ Per-request | US (EU enterprise) | Unclear |
| Groq | No | 30 days | ✅ Account setting | US | ✅ Available |
| DeepInfra | No | Zero (claimed) | ✅ Default | US | Available |
| Together AI | No (stated) | Not documented | Not documented | US | Not documented |
| Fireworks AI | No (stated) | Not documented | Not documented | US | Not documented |

### OpenRouter's layered privacy model

When a user sends data through OpenRouter to a downstream provider, **two separate data-handling layers apply**. OpenRouter itself does not store prompts (unless the user opts into logging), but the downstream provider's policies also govern the data. A request routed to Anthropic still faces Anthropic's 7-day retention. OpenRouter's ZDR enforcement ensures routing only to endpoints that also guarantee zero retention — but the user must understand this dual layer. OpenRouter's model-level privacy flags ("does not train," "zero data retention," "data retention") make this transparent per endpoint.

---

## EU sovereignty: what actually works for a Frankfurt-based app

### Mistral is the only viable EU-sovereign option for consumer BYOK

**Mistral AI** processes API data in EU data centers by default (Sweden, Ireland), is directly subject to GDPR and CNIL oversight, offers a self-serve DPA, and provides ZDR on the API. Its open-weight models can be self-hosted for complete data sovereignty. With a €500M EU Commission contract and €1.7B in recent funding, it has institutional backing for long-term viability. For Kestrel's privacy-first users, Mistral is the unambiguous default recommendation.

**OVHcloud AI Endpoints** offers 40+ open-source models from a Gravelines (France) data center with **explicit zero data retention** ("we keep only data required for billing"), ISO 27000/SOC certification, and healthcare-grade data hosting. A free tier exists. This is an excellent secondary EU-sovereign option, though the model selection is limited to open-weight models and the API maturity may not match Mistral's.

**Scaleway** provides serverless LLM endpoints from Paris-based infrastructure with a strong data sovereignty statement: "We do not collect, read, reuse, or analyze the content of your inputs." Pricing starts at €0.20/MTok. Good for EU-only processing of open-weight models.

**Aleph Alpha** has pivoted entirely to enterprise/government sovereign AI (PhariaAI platform) and **no longer offers individual API access**. Not viable for consumer BYOK.

**Nebius** operates EU data centers (Finland) and offers an AI Studio with 56+ models, but its privacy documentation is less mature than Mistral or OVHcloud. Better positioned as GPU infrastructure than a managed LLM API.

### Accessing US providers with EU residency

Anthropic offers EU processing via **AWS Bedrock** (6–7 EU regions) or **Google Vertex AI** (10 EU regions) with ~10% price premiums. OpenAI provides regional processing endpoints for newer models at 10% premium. xAI has an EU API endpoint (eu-west-1). Google Vertex AI supports EU regional endpoints natively. These are viable for users who want Claude/GPT quality with EU data residency but add integration complexity compared to direct API calls.

---

## BYOK user experience: making key setup painless

### OpenRouter OAuth eliminates the biggest friction point

For a non-technical job seeker, generating an API key at OpenAI or Anthropic involves navigating developer consoles, understanding projects and organizations, prepaying $5+, and copying a key shown only once. **OpenRouter's OAuth PKCE reduces this to a redirect-and-authorize flow** — comparable to "Sign in with Google." The user creates an OpenRouter account, loads a few dollars in credits, and the app receives a scoped API key programmatically.

Key security features for consumer protection:

- **Per-key credit limits** with daily/weekly/monthly reset intervals cap runaway spending
- **Model/provider restrictions** per key prevent access to expensive models
- **Key expiration** via ISO 8601 timestamps enables automatic rotation
- **Automated leak detection** (GitHub secret scanning partner) with email notification
- OpenRouter is the only provider offering all of these on a per-key basis

### Key generation ease rankings

| Provider | Ease (1–5) | Notes |
|---|---|---|
| OpenRouter (OAuth) | ⭐⭐⭐⭐⭐ | 1–2 min, no key visible to user, seamless |
| Google AI Studio | ⭐⭐⭐⭐ | Any Google account, instant key, free tier, no card needed |
| Groq | ⭐⭐⭐⭐ | Free tier, no card, but open-weight models only |
| OpenRouter (manual) | ⭐⭐⭐⭐ | Simple dashboard, clear credit loading |
| OpenAI | ⭐⭐⭐ | Polished UI but $5 prepay, confusing org/project structure |
| Anthropic | ⭐⭐⭐ | Magic-link login is nice, $5 prepay, key shown once |
| Mistral | ⭐⭐⭐ | Clean console, free trial key available |
| DeepSeek | ⭐⭐ | Chinese interface challenges, GDPR concerns |

---

## Reliability, latency, and rate limits in practice

For a consumer app, latency perception matters: users expect responses to start within 1–2 seconds. **Groq and Cerebras offer sub-second time-to-first-token** with output speeds 5–20× faster than GPU providers, making them excellent for real-time interactions like interview prep or quick job-description analysis. Mainstream providers (OpenAI, Anthropic, Google) typically deliver 80–120 tok/s with 300–600ms TTFT — adequate but noticeably slower.

**OpenRouter's multi-provider fallback** is a significant reliability advantage: if Anthropic's API returns errors, OpenRouter automatically retries via an alternative provider. This resilience is difficult to replicate with direct provider keys. Anthropic averages ~99.85% uptime but has frequent minor incidents. OpenAI averages an incident every 2–3 days with no formal uptime SLA for standard API users.

Rate limits vary dramatically by tier. Anthropic's base tier starts at ~5 RPM for Sonnet (scaling with spend history). OpenAI's Tier 1 allows ~500 RPM for GPT-4.1. Google's free tier caps at 5–15 RPM depending on model. **OpenRouter imposes no platform-level rate limits for paid users**, though underlying provider limits still apply. For Kestrel, implementing exponential backoff with user-friendly "processing" messages and model-tiering (cheap models for simple tasks, premium for complex analysis) is essential.

---

## What Kestrel should actually build

### The recommended provider stack

**Primary entry point: OpenRouter via OAuth PKCE.** This serves ~80% of users who want simplicity. They get access to 300+ models, spending controls, ZDR enforcement, and multi-provider reliability through a single account. The 5.5% credit fee is negligible relative to the UX and operational benefits.

**EU-sovereign default: Mistral La Plateforme.** Present this prominently with a 🇪🇺 badge for privacy-conscious users. EU data processing by default, GDPR-native, self-serve DPA. Mistral Large 3 at $2/$6 offers good quality at competitive pricing.

**Power-user direct keys: Anthropic and OpenAI.** For users who want maximum control, lowest cost (no 5.5% OpenRouter fee), or specific model preferences. Claude Sonnet 4.6 excels at nuanced text analysis — ideal for CV review and cover letter generation. GPT-5.4 has the most mature structured output for parsing job listings.

**Free-tier option: Google AI Studio.** Any Google account holder can get started instantly with Gemini 2.5 Flash at no cost. Critical caveat: the app must warn users that free-tier data may be used for Google's model training. Recommend upgrading to paid tier for CV processing.

**Budget speed option: Groq (via OpenRouter or direct).** For users who want instant responses on non-sensitive tasks (formatting, general questions), Groq's free tier and sub-100ms TTFT are compelling.

### Educating users about privacy tradeoffs

The app should implement a **tiered disclosure model**:

1. **First-run screen**: Plain-language explanation that CV data will be processed by third-party AI services, that API data is not used for training (unlike consumer chatbots), and that retention periods vary by provider.

2. **Provider selection cards**: Each provider option should display a privacy summary — training policy (green checkmark for all API providers except DeepSeek), data location flag (🇪🇺/🇺🇸/🇨🇳), retention period, and a simple privacy rating.

3. **DeepSeek warning**: If DeepSeek models are offered (via OpenRouter), show a prominent notice: "This model processes data on servers in China. Chinese law permits government access to stored data. Not recommended for CVs or personal information."

4. **PII masking layer**: The single most impactful technical safeguard Kestrel can implement is a **client-side PII redaction step** before any LLM call — stripping phone numbers, addresses, and other identifiers, then re-inserting them into outputs. This reduces GDPR exposure regardless of provider choice.

### OpenRouter as unified entry point vs. direct keys

**Recommend OpenRouter as default, with direct keys as an advanced option.** The unified API eliminates the need to maintain separate integrations for each provider. The OAuth flow removes the #1 UX friction point. Per-key spending limits protect consumers from bill shock. The 5.5% fee is the cost of convenience — for a user spending €10/month, that's €0.55.

The main argument for direct keys: slightly lower cost, simpler audit trail (one data handler instead of two), and access to provider-specific features (Anthropic's extended thinking, OpenAI's specific structured output modes). Offer this as "Advanced Setup" for technically sophisticated users.

### GDPR architecture for Kestrel

Kestrel is likely a **data controller** (or joint controller) under GDPR because it designs the processing pipeline — even though users supply their own keys. This means Kestrel needs DPAs with every integrated provider, must conduct a Data Protection Impact Assessment (Article 35), and should implement lawful basis documentation (explicit consent for sending CV data to third-country processors). A recommended provider allowlist — excluding providers without available DPAs — reduces compliance surface area. The EU AI Act taking effect August 2, 2026 will add further requirements for audit trails and human oversight in high-risk AI applications.

---

## The 2025–2026 market shifts that matter

**Price compression has been extraordinary.** DeepSeek's January 2025 launch of V3 at ~$0.14/$0.28 per MTok forced every major provider to cut prices. GPT-4o input dropped from $5 to $2.50; Claude Opus went from $15 to $5. The cheapest-to-most-expensive spread now exceeds **1,000×** (Mistral Nemo at $0.02 blended vs. o3-pro at $100+ blended).

**Prompt caching is now table-stakes.** Anthropic, OpenAI, and Google all offer 50–90% input discounts on cached content. For Kestrel, structuring prompts with the user's CV as a cached prefix and job-specific queries as the variable suffix could reduce per-interaction costs to under $0.01 for mid-tier models.

**Structured output and function calling have reached near-parity** across major providers. OpenAI's constrained decoding is the most mature. Anthropic shipped constrained decoding in mid-2025. Fireworks AI is optimized for structured output on open-weight models. This matters for Kestrel's job-listing parsing and data extraction features.

**Chinese model data concerns intensified.** DeepSeek was banned by Australian, Italian, South Korean, and US government agencies. Multiple EU DPAs launched investigations. DeepSeek's claimed position that "GDPR does not apply" to them is legally untenable but operationally relevant — enforcement is slow. Self-hosting DeepSeek's open-weight models (via Scaleway, OVHcloud, or Nebius) is the safe path to accessing their quality at low cost without the data residency risk.

**OpenRouter emerged as infrastructure.** Revenue grew 10× from $800K/month (October 2024) to ~$8M/month (May 2025), serving 2.5M+ developers across 250K+ apps. Its position as the default aggregator is strengthening, though Together AI ($305M Series B) and Fireworks AI (~$315M ARR) are credible alternatives for open-weight-only workloads.

---

## Conclusion

The optimal architecture for Kestrel is a **three-tier provider strategy**: OpenRouter OAuth as the frictionless default for most users, Mistral as the EU-sovereign recommendation for privacy-conscious users, and direct Anthropic/OpenAI keys for power users who want maximum control. This covers the UX spectrum from "just works" to "I understand the tradeoffs."

The most underappreciated insight: **prompt caching transforms the economics of CV-heavy workloads**. A user's CV cached as a prompt prefix means subsequent queries about that CV cost 90% less on input tokens — making even premium models like Claude Sonnet viable at a few cents per interaction. Kestrel should structure its prompt architecture around this from day one.

DeepSeek models should be available only via OpenRouter (with ZDR enforcement) or via self-hosted open-weight deployments on EU infrastructure — never via direct API for personal data. The privacy warning must be unambiguous.

Finally, the GDPR landscape is not optional. Even in a BYOK model, Kestrel likely bears controller obligations. A provider allowlist restricted to those with available DPAs, combined with a client-side PII masking layer, provides the strongest defensible position. The EU AI Act's August 2026 effective date adds urgency to building audit trail and documentation capabilities now.