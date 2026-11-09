# Free-tier routing: what Kestrel can learn from free-claude-code

Researched 2026-10-25. Subject: https://github.com/Alishahryar1/free-claude-code (63,323 stars, `main` at commit `4e92110a0a3232765c6fc7a8c9d34489fb0e65da`, pushed 2026-10-25). Source read via `gh api`; nothing was cloned into this repo and the project was not run.

All path citations below are relative to the upstream repo at that SHA. "Inference" marks my reading, not something the project states. "Not stated" means the project does not say it.

## 0. Three findings that matter most

1. **The project does not publish free-tier quotas at all.** Its provider registry (`src/free_claude_code/config/provider_catalog.py`) holds only IDs, credential env names, base URLs and a boolean `native_messages_passthrough`. The one headline number ("1.3B+ free tokens every month", `README.md:28`) is an aggregate marketing claim with no per-provider breakdown. Per-provider quota data would have to come from elsewhere (its own code comment points at `github.com/cheahjs/free-llm-api-resources`, `provider_catalog.py:831`).
2. **Its error handling is worth copying, its fallback is not suited to batch.** It retries 429 and 5xx with exponential backoff plus jitter and honours `Retry-After` (uncapped, see section 3). It treats 402 as terminal and non-retryable. The fallback chain is an ordered manual list, not health-aware.
3. **Terms and privacy are the real blockers for a free preset, not plumbing.** The project itself flags that Kimi Code and QwenCloud Coding Plan are "personal interactive coding-agent use" only (`README.md:303,311`), and that Gemini's free tier may use data for product improvement outside UK/CH/EEA/EU (`config/admin/provider_manifest.py:143-147`). Kestrel sends job descriptions plus profile-derived context, so training-on-inputs matters. Also: Cerebras, which Kestrel's own Free preset names (`src/career_os/services/presets.py:39`), states it has no permanent free tier (section 5).

## 1. What it is and how it works

**Mechanism.** A local FastAPI proxy that speaks the Anthropic Messages wire format (and OpenAI Responses and Gemini shapes: `api/handlers/messages.py`, `responses.py`, `gemini.py`) to coding agents, and translates to whichever upstream provider is selected. Agents are pointed at it through launchers (`fcc-claude`, `fcc-codex`, ... `README.md:96-150`). Request translation for OpenAI-compatible upstreams lives under `providers/openai_chat/` and `core/openai_responses/`; providers with Anthropic-native endpoints are passed through (`providers/anthropic_messages/passthrough.py`).

**Per-tier model map.** Claude Code asks for Fable/Opus/Sonnet/Haiku; the proxy maps each to a configurable model (`config/settings.py:402-423`):

- `MODEL` (alias; default `DEFAULT_MODEL` from `config/constants.py`) is "mapped to this single model (fallback)" for every request
- `MODEL_FABLE`, `MODEL_OPUS`, `MODEL_SONNET`, `MODEL_HAIKU`: optional per-tier overrides, each may use a different provider
- Model refs are `provider_id/model/name` (`config/model_refs.py`)
- Tier matched by substring of the requested model name (`application/routing.py`, `_ROUTE_SETTINGS`, near line 285)

README `README.md:355-358` documents the same: "`MODEL` is the fallback for every request. Select a model for `MODEL_FABLE`, `MODEL_OPUS`, `MODEL_SONNET`, or `MODEL_HAIKU` to override an individual Claude Code tier."

**Fallback order.** `MODEL_FALLBACKS` (`config/settings.py:424-427`) is an ordered list of `{model, reasoning, api_key_number}` entries (`config/model_refs.py`, class `ModelFallback`). Resolution in `application/routing.py:185-197` (`_fallback_targets`): configured list in order, minus any entry equal to the primary. Validation rejects duplicate model/key pairs (`settings.py:834-844`). Numbered API keys per provider allow "same model, key 2" as a fallback (`README.md:203-205,359`).

Execution semantics (`application/execution.py`, candidate loop around lines 449-660):
- `candidates = (primary, *fallbacks)` (line 449)
- A candidate that fails **before any content reaches the client** is abandoned and the next candidate is tried; if it was the last candidate the failure is raised (`if index + 1 >= len(candidates): raise candidate_failure`, ~line 610)
- Inference from `core/stream_recovery.py:78-85` (`assess_recovery`): with no content released, the action is RESTART regardless of the `retryable` flag, so a non-retryable 402/401 on the primary still moves on to the next fallback. Retryability only matters once content has been streamed (continuation or handoff).
- For native-Anthropic requests, fallbacks whose provider lacks native messages support are dropped (`routing.py:285-313`, `route_native_messages`)
- README warning (`README.md:201-203`): "A failed request may reach and consume usage from more than one provider before succeeding."

**Retry and rate limiting (per provider).**
- Defaults: `PROVIDER_RATE_LIMIT=1`, `PROVIDER_RATE_WINDOW=2` (seconds), `PROVIDER_MAX_CONCURRENCY=2` (`config/settings.py:601-609`). Enforced by a strict sliding-window limiter, `core/rate_limit.py:9-65`, which sleeps until the oldest slot expires rather than failing.
- Transient retries: `UPSTREAM_TRANSIENT_TOTAL_ATTEMPTS = 10`, `DEFAULT_UPSTREAM_BASE_DELAY = 2.0`, `DEFAULT_UPSTREAM_MAX_DELAY = 60.0`, `DEFAULT_UPSTREAM_JITTER = 1.0` (`providers/admission.py:36-39`).
- Recovery is coordinated per model: the first failing request becomes the "leader", schedules one probe, and other concurrent requests wait on it ("one provider recovery probe", `admission.py:751-850`). This stops a thundering herd against an already-limited free endpoint.

**Admin UI.** Static single-page admin (`api/admin_static/`, `api/admin_routes.py`) for provider keys, a searchable model dropdown, fallback list editing, per-fallback reasoning effort, provider health "Test" buttons, integrations for editors. Config persisted via `config/admin/persistence.py`. Not relevant to Kestrel beyond the idea of a "Test this key" button.

## 2. Provider registry extracted

The catalog has **61** `ProviderDescriptor` entries (`config/provider_catalog.py`; 3 are `local=True`; 2 use connected OAuth accounts: OpenAI/ChatGPT, GitHub Copilot).

Column notes:
- **Free tier**: "implied" means only that the README example model ID or manifest text mentions free/trial; no quota is given. "Not stated" is the default. The project states no per-provider rate limits anywhere I could find (searched `README.md`, `config/admin/provider_manifest.py`, `provider_catalog.py`).
- **Terms restriction**: only those the project itself quotes. Absence means "not stated", not "unrestricted".
- **API style**: from catalog comments. Everything is "OpenAI-compatible Chat Completions" except where noted. Only `anthropic` sets `native_messages_passthrough=True` (`provider_catalog.py:221`).
- **Kestrel adapter**: Kestrel has `mock, openrouter, anthropic, ollama, openai, together, groq, xai, gemini, mistral, huggingface` in `src/career_os/ai/factory.py:80-135`. Kestrel's factory only exposes a configurable base URL for Ollama (`factory.py:91`), so OpenAI-compatible providers without an adapter are **not** reachable today without new code (inference from reading `factory.py` and `config.py`).

| Provider id | Free tier | Stated quota / limits | Terms restriction (project's own notes) | API style | Kestrel adapter |
|---|---|---|---|---|---|
| nvidia_nim | implied (default `MODEL`, key from build.nvidia.com) | not stated | not stated | OpenAI-compat (`integrate.api.nvidia.com/v1`) | no |
| open_router | implied (`openrouter/free` example) | not stated | not stated | OpenAI-compat | yes |
| groq | not stated | not stated | not stated | OpenAI-compat | yes |
| cline_pass | no (subscription) | not stated | not stated | OpenAI-compat | no |
| openai (ChatGPT OAuth) | no (subscription) | not stated | not stated | ChatGPT Codex backend | no |
| openai_api | no | not stated | not stated | OpenAI native | yes (`openai`) |
| anthropic | no | not stated | not stated | Anthropic native | yes |
| github_copilot | no (subscription) | "depend on your subscription and organization policies" (`README.md`) | not stated | Copilot SDK | no |
| xai | not stated | not stated | not stated | OpenAI-compat | yes |
| alibaba_cloud | no (pay-as-you-go) | not stated | not stated | OpenAI-compat | no |
| qwencloud (Token Plan) | no | not stated | not stated | OpenAI-compat | no |
| qwencloud_coding | no (plan) | not stated | "local, personal, interactive coding-agent use" (`README.md:310-312`) | OpenAI-compat | no |
| together | not stated | not stated | not stated | OpenAI-compat | yes |
| deepinfra | not stated | not stated | not stated | OpenAI-compat | no |
| siliconflow | not stated | not stated | not stated | OpenAI-compat | no |
| nebius | not stated | not stated | not stated | OpenAI-compat | no |
| chutes | not stated | not stated | not stated | OpenAI-compat | no |
| featherless | not stated | "plan-available" models (`provider_manifest.py:252`) | not stated | OpenAI-compat | no |
| agnes | not stated | not stated | not stated | OpenAI-compat | no |
| zenmux | implied (`...-free` model example) | not stated | not stated | OpenAI-compat gateway | no |
| wandb | not stated | not stated | not stated | OpenAI-compat | no |
| azure_openai | no | not stated | not stated | OpenAI-compat (v1) | no |
| gemini | yes ("free tier has per-model rate limits", `provider_manifest.py:143-147`) | not stated by project | "data may be used for improvement outside the UK/CH/EEA/EU" | OpenAI-compat layer | yes |
| vertex | no | not stated | not stated | OpenAI-compat via Vertex, ADC auth | no |
| deepseek | not stated | not stated | not stated | OpenAI-compat | no |
| mistral | yes ("Experiment plan is free tier with rate limits", `provider_manifest.py:52`) | not stated | not stated | OpenAI-compat | yes |
| mistral_codestral | not stated | not stated | "IDE/personal endpoint" (`provider_catalog.py:26` comment) | OpenAI-compat | no |
| opencode_zen | not stated | not stated | not stated | OpenAI-compat | no |
| opencode_go | no (subscription) | not stated | not stated | OpenAI-compat | no |
| vercel | not stated | not stated | not stated | OpenAI-compat gateway | no |
| bedrock | no | not stated | not stated | OpenAI-compat (Mantle) | no |
| huggingface | not stated | not stated | not stated | OpenAI-compat router | yes |
| cohere | not stated | not stated | not stated | OpenAI-compat (compat API) | no |
| wafer | not stated | not stated | not stated | OpenAI-compat | no |
| kimi | no (credits) | not stated | not stated | OpenAI-compat | no |
| kimi_code | no (subscription) | not stated | "personal interactive coding-agent use" (`README.md:303-305`) | OpenAI-compat | no |
| kilo | implied (`kilo-auto/free`) | not stated | not stated | OpenAI-compat gateway | no |
| minimax | not stated | not stated | not stated | OpenAI-compat | no |
| cerebras | not stated by project | not stated | not stated | OpenAI-compat | no |
| sambanova | not stated | not stated | not stated | OpenAI-compat | no |
| fireworks | not stated | not stated | not stated | OpenAI-compat | no |
| novita | not stated | not stated | not stated | OpenAI-compat | no |
| cloudflare | not stated | not stated | not stated | OpenAI-compat (account-scoped) | no |
| zai | no (Coding Plan quota) | not stated | not stated | OpenAI-compat | no |
| zai_api | not stated (example `glm-4.7-flash`) | not stated | not stated | OpenAI-compat | no |
| tokenrouter | implied (`kimi-k3-free`) | not stated | not stated | OpenAI-compat gateway | no |
| nararoute | implied (`kimi-k3-free`) | not stated | not stated | OpenAI-compat gateway | no |
| poolside | not stated | not stated | not stated | OpenAI-compat | no |
| llm7 | not stated | not stated | not stated | OpenAI-compat | no |
| scaleway | not stated | not stated | not stated | OpenAI-compat | no |
| lightning | not stated | not stated | not stated | OpenAI-compat gateway | no |
| experiential | not stated | not stated | not stated | OpenAI-compat gateway | no |
| cheaperinference | not stated | not stated | not stated | OpenAI-compat gateway | no |
| orcarouter | implied (`...-free`) | not stated | not stated | OpenAI-compat gateway | no |
| atlascloud | not stated | not stated | not stated | OpenAI-compat gateway | no |
| xkiro | implied (`:free` example) | not stated | not stated | OpenAI-compat gateway | no |
| opper | not stated | not stated | not stated | OpenAI-compat gateway | no |
| ollama_cloud | not stated | not stated | not stated | OpenAI-compat (`ollama.com/v1`) | no (local `ollama` yes) |
| lmstudio | local, zero cost | n/a | n/a | OpenAI-compat local | no |
| llamacpp | local, zero cost | n/a | n/a | OpenAI-compat local | no |
| ollama | local, zero cost | n/a | n/a | Ollama native base URL | yes |

Takeaway: of 61, the project positively says "free tier" for only two (Gemini, Mistral Experiment). About ten more are implied by example `-free` model IDs. The README's "ToS-friendly" claim (`README.md:28`) is the project's assertion that it removes providers that disallow its use; it is not a statement that the terms permit unattended batch use.

## 3. 429 vs 402 vs other errors

Code path (`providers/failure_policy.py`, `providers/admission.py`):

- **Status first, then structured body, then message text.** `retryable_transient_status` (`failure_policy.py:170-202`) checks in order: context-window markers (not retryable), HTTP 413 (not retryable), `openai.RateLimitError` -> 429, `httpx.HTTPStatusError` status, `status_code` attribute, status found inside the error body, then **substring markers in the exception/body text**: `rate_limit`/`rate limit`/`too many requests` -> 429 (`:25,196-197`); `resourceexhausted`/`limit reached`/`overloaded`/`capacity` -> 503 (`:26-34,198-199`); `internal server error` -> 500 (`:35,200-201`). So it does inspect the error body and message text, not status alone. Inference: this is a defence against providers that return 200/400 with a rate-limit message.
- **Retryable set** is exactly 429 plus 500-599 (`_is_retryable_status`, `:573-574`). Timeouts and network errors also retry (`:233-257`).
- **402 is terminal.** Mapped to `FailureKind.PERMISSION`, status 402, `retryable=False`, message "Provider requires payment or additional credits. Add credits or resolve billing." (`:40-42,392-393,409-410`). 401 and 403 are likewise non-retryable (`:355-356, 394-395`). 400 -> invalid request, non-retryable. Note Kestrel's `fallback.py` treats 402 and 429 together as `ProviderQuotaError` (per its own docstring); this project separates them, which matters because 429 on a free tier usually clears and 402 does not.
- **Retry-After** is parsed: numeric seconds or an HTTP date, clamped to >= 0, non-finite ignored (`admission.py:1019-1041`). The delay is `max(min(base*2^(attempt-1), max_delay) + jitter, retry_after)` (`:1003-1008`). **Inference/caution:** `retry_after` is not capped by `DEFAULT_UPSTREAM_MAX_DELAY=60`, so a provider returning `Retry-After: 86400` (a daily-quota reset) would make a request wait up to a day while other requests coalesce behind it. For interactive coding that is a bug-in-waiting; for a nightly batch it must be bounded explicitly. I did not find a cap in the files I read; I did not search the whole repo exhaustively.
- **Attempt bound:** 10 attempts per execution (`admission.py:36`). After exhaustion, the failure is classified (`classify_provider_failure`, `failure_policy.py:68-102`) and the fallback chain advances.
- **Streams:** an opened stream that fails mid-way is replayed only if no unsafe content was released (`core/stream_recovery.py:68-112`). Irrelevant to Kestrel's non-streaming batch calls.
- **Quota burn warning:** documented at `README.md:201-203` (quoted in section 1). Mechanism: each candidate attempt is a real request to a different provider, and nothing refunds the earlier ones. For Kestrel this has a concrete analogue: a batch prompt of 10 jobs that is retried or fallback-hopped spends 10 jobs' worth of tokens per hop.

## 4. Fit for Kestrel's batch scoring workload

Workload: ~100-500 scoring prompts per night, 10 jobs per prompt (so 10-50 prompts at the current batch size, or 100-500 if sending individually), non-interactive, JSON output, scheduled.

(a) **Permitted by terms for unattended batch?** The project gives no evidence either way for most providers; it only identifies exclusions (Kimi Code, QwenCloud Coding Plan, Codestral "IDE/personal", and OAuth subscription routes like ChatGPT/Copilot, which are subscription-for-interactive-use). Excluded for Kestrel: all subscription/OAuth providers. For the rest I could not establish from the project's data; terms need per-provider review (open question, not guessed).

(b) **Reachable through existing Kestrel adapters:** `openrouter`, `groq`, `gemini`, `mistral`, `together`, `huggingface`, `xai`, `ollama` already exist. Any other OpenAI-compatible provider (NVIDIA NIM, Cerebras, SambaNova, Cloudflare, etc.) is only reachable through OpenRouter if OpenRouter routes to it, or by adding a small generic "OpenAI-compatible base URL + key" adapter (inference: `factory.py` has no such option today).

(c) **Rate limits adequate for 100-500 prompts/night:** The project gives no numbers, so I fetched provider pages (access date 2026-10-25):
- Gemini free tier: limits are per project across RPM/TPM/RPD, exact per-model values are shown only in AI Studio (the doc page numbers did not render in a static fetch). **Uncertain** whether 100-500/night fits; with batch size 10, 10-50 requests is plausible.
- OpenRouter `:free` models: documented as low daily request caps, raised if you have bought credits; the numeric values did not render in my fetch. Historically ~50/day without credits and ~1000/day with >= $10 purchased (from memory, **unverified today**).
- Groq: rate-limits page returned an empty shell; **not verified**.
- Mistral Experiment plan: help-center article URL I tried 404'd; **not verified**.
- Cerebras: documented Free Trial is "$5 in free credits" expiring after 30 days, with per-model Free Trial rate limits (the table columns did not parse cleanly, so I give no RPM figure); the page says it has no permanent free tier.
- Free tiers also change without notice (the project says so itself: "Free-tier availability and limits are controlled by each provider and may change", `README.md:44`).

Conclusion for (c): plausible but unverified for Gemini and OpenRouter free models at batch size 10; not plausible for Cerebras as a lasting free option.

## 5. Privacy of recommended free providers

Accessed 2026-10-25. Only provider-published text I could actually read.

| Provider | Training / data use on API inputs | Source |
|---|---|---|
| Google Gemini API, unpaid quota | **Yes, may be used.** "Unpaid Services" include "unpaid quota in Gemini API"; Google uses submitted content to improve products, with human review after disconnecting it from account/key/project, and says "Do not submit sensitive, confidential, or personal information to the Unpaid Services." Paid quota: Google "doesn't use your prompts ... to improve our products". | https://ai.google.dev/gemini-api/terms (Unpaid Services / Paid Services sections) |
| OpenRouter (incl. `:free` models) | Prompt retention on OpenRouter is opt-in; OpenRouter documents which downstream providers may train and offers settings to control it. Free-model downstream policies **not read in detail**. Kestrel's registry already marks OpenRouter yellow. | https://openrouter.ai/docs/guides/privacy/data-collection |
| Groq | Privacy policy covers customer-service recordings and general "improve and develop the Services"; **the API data-use/ZDR statement I needed was not retrievable** (`console.groq.com/docs/your-data` returned an empty shell). Treat as unknown. | https://groq.com/privacy-policy |
| Mistral (Experiment plan) | **Not found** (help-center article 404). Unknown. | attempted https://help.mistral.ai/... (404) |
| NVIDIA NIM (build.nvidia.com) | **Not checked.** | n/a |
| Cerebras | Not checked for data use; also not free long-term (above). | https://inference-docs.cerebras.ai/support/rate-limits |

Implication (inference): Kestrel's pipeline sends job descriptions (public data) in scoring, but scoring prompts embed profile summaries, skills and goals. Free tiers that train on inputs conflict with Kestrel's existing PII boundary logic in `src/career_os/ai/privacy.py`. A Free preset on a training-allowed tier should be gated behind an explicit warning and, ideally, a profile-redaction step (Kestrel has `pii_masking.py`).

## 6. Recommendations for Kestrel

### (a) Adopt now in Phase 1b cost safety
1. **Split 402 from 429 in the fallback chain.** 402 (credits exhausted) is terminal for that provider for the run: trip a circuit breaker, fall through immediately, do not retry. 429 gets bounded backoff. This matches `failure_policy.py:392-410` vs `:181-182`.
2. **Honour `Retry-After` but cap it.** Parse numeric and HTTP-date forms (`admission.py:1019-1041` is a clean reference). Add what the project lacks: a hard ceiling (e.g. a few minutes per attempt, and a per-night wall-clock budget). A Retry-After beyond the ceiling means "daily quota gone": mark the provider exhausted for the run and move on.
3. **Body-text 429/overload detection** for providers that return 200 or 400 with a rate-limit message (`failure_policy.py:25-35,195-201`).
4. **Bound attempts and surface the multiplication.** Cap total attempts per batch across all providers, log "attempt N on provider P", and record spend per hop. Mirrors the README's quota-burn warning; it is the same lesson as the 2026-07 Together fallback leak.
5. **Per-provider strict sliding-window limiter** (`core/rate_limit.py`, ~60 lines, clean). Free tiers punish bursts; Kestrel's batch loop should self-pace instead of discovering limits via 429s.
6. **Fix the Free preset's description now:** `presets.py:39` names Cerebras, which has no permanent free tier. Replace with providers that do (see shortlist). Add `last_verified` per preset entry, as the privacy registry already does.
7. **Recovery-probe coalescing idea**, simplified: when a provider starts returning 429 in a batch, one worker probes while others wait, instead of every worker hammering it. Only needed if scoring is concurrent.

### (b) Adopt later
- Generic "OpenAI-compatible base URL + key" adapter (covers NVIDIA NIM, Cerebras, SambaNova, Cloudflare, and ~40 others with no per-provider code). Needs a privacy-registry entry per use and PII gate wiring.
- Numbered keys per provider (key 1 / key 2 as separate fallback entries); only meaningful for users who have several free accounts, which raises its own ToS questions.
- "Test this key/model" check button in settings (the admin UI idea).
- A single-sourced, dated provider table (id, free-tier status, limits, terms, training, last_verified) in a data file, generated and reviewed monthly, instead of facts scattered through code. The project's lack of such data is the main gap.

### (c) Do not adopt
- **Protocol translation proxy / Anthropic-format shim.** Kestrel is a client of providers, not a proxy for agents.
- **Tier-by-model-name mapping (Fable/Opus/Sonnet/Haiku).** Kestrel's SIMPLE/STANDARD/COMPLEX routing is already the right abstraction for its workload.
- **Mid-stream recovery/continuation** (`stream_recovery.py`, `continuation.py`). Kestrel batch calls are not streamed to a user.
- **Subscription/OAuth providers** (ChatGPT, Copilot, Kimi Code, QwenCloud Coding Plan, Codestral IDE endpoint). Interactive-use terms, per the project's own notes.
- **Gateways of unknown provenance** (TokenRouter, NaraRoute, OrcaRouter, xKiro, LLM7, etc.). Sending profile-derived data through small unaudited resellers is incompatible with Kestrel's privacy posture; the project gives no data-use information for any of them.
- **Its fallback model**: a flat ordered list with no health state. Kestrel should keep its provider chain plus a per-run exhausted-provider set.

### Is a real "Free" preset viable for a first-time user?
**Viable only conditionally, with one key, not zero keys.**
- Zero keys: no. Every hosted free tier in this registry requires an account and API key (the project has no keyless hosted option; `llm7` and gateways are unvetted). The only zero-key path is local Ollama, which needs hardware and a model download.
- One key: **yes**, via a single free key such as Google AI Studio (Gemini) or OpenRouter. Requires: (1) an in-app warning that Gemini's unpaid tier may train on inputs and not to put sensitive data in; (2) conservative scoring caps matching real daily quotas (pre-filter strict, batch size 10, hard nightly request ceiling); (3) circuit breaker for 429/402 with a clear "free quota used up, resumes tomorrow" state instead of an error; (4) re-verification of limits at release time (they change without notice); (5) Kestrel's existing PII boundary applied, so personal-data features (cover letters, interview prep) stay off free tiers.
- A two-key variant (OpenRouter free models as fallback for Gemini) increases headroom but doubles the privacy surface.

### Free-preset provider shortlist (provisional)
1. **Google Gemini, free tier**: existing adapter, only truly "free" tier confirmed here, but trains on inputs (section 5). Needs a warning.
2. **OpenRouter free (`:free`) models**: existing adapter, one key, low daily caps; downstream policies vary per model.
3. **Groq**: existing adapter; free-tier limits and data policy **not verified** (needs a check before listing).
4. **Mistral Experiment plan**: existing adapter; limits and data policy **not verified**.
5. **Local Ollama**: existing adapter, zero data leaves the device; the privacy-best "free" option, hardware permitting.
Excluded: Cerebras (no permanent free tier), all subscription/OAuth routes, unvetted gateways.

## 7. License note

free-claude-code is `AGPL-3.0-only` (`LICENSE:1-4`, SPDX line at top). Kestrel is also AGPL-3.0, so licenses are compatible in direction: copying its code into Kestrel would be permitted provided Kestrel's AGPL terms, copyright notices and source availability are respected. Raw facts (a provider's base URL, an env-var name) are not copyrightable; the *selection and arrangement* in the catalog, its wording, and its code are. My recommendation: **learn, don't vendor**. Reasons: (1) it is a Python 3.14 codebase with its own dependency tree (`httpx2`, 61 provider adapters), so copied code would drag in structure Kestrel doesn't need; (2) provider facts like quotas and terms go stale and must be re-verified by Kestrel anyway; (3) the retry/Retry-After/limiter patterns are small and easy to reimplement from the descriptions above with Kestrel's own tests; (4) clean attribution is simpler when nothing is copied. If a specific function is ever copied, keep its attribution comment and note the upstream SHA. This is not legal advice.

## 8. Sources (accessed 2026-10-25)

- Repo: https://github.com/Alishahryar1/free-claude-code at `4e92110a0a3232765c6fc7a8c9d34489fb0e65da`. Files read: `README.md`, `LICENSE`, `src/free_claude_code/config/provider_catalog.py`, `config/settings.py`, `config/model_refs.py`, `config/admin/provider_manifest.py`, `providers/failure_policy.py`, `providers/admission.py`, `providers/admission_policy.py`, `providers/nvidia_nim/retry.py`, `core/rate_limit.py`, `core/stream_recovery.py`, `application/execution.py`, `application/routing.py`.
- Gemini API additional terms (Unpaid/Paid Services): https://ai.google.dev/gemini-api/terms
- Gemini rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- OpenRouter limits: https://openrouter.ai/docs/api-reference/limits ; FAQ: https://openrouter.ai/docs/faq ; data collection: https://openrouter.ai/docs/guides/privacy/data-collection
- Cerebras rate limits / free trial FAQ: https://inference-docs.cerebras.ai/support/rate-limits
- Groq privacy policy: https://groq.com/privacy-policy
- Kestrel files compared: `src/career_os/ai/factory.py`, `src/career_os/ai/fallback.py`, `src/career_os/ai/privacy.py`, `src/career_os/services/presets.py`.
- Fetch failures (so those facts are open): Groq rate limits and data-use pages, Mistral Experiment-plan article (404), Cloudflare Workers AI limits (no usable text), NVIDIA build terms (not attempted), numeric OpenRouter and Gemini free-tier values (rendered client-side).

Open items for a follow-up ticket: verify Groq, Mistral Experiment, NVIDIA NIM and Cloudflare free-tier limits and training clauses with a real browser; check OpenRouter's current `:free` caps via `GET /api/v1/key`.
