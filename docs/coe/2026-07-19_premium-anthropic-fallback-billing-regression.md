# COE: premium-Anthropic fallback silently re-entered the scoring chain and billed the API

**Date:** 2026-07-19 · **Severity:** mid-major · **Area:** Eyas/Kestrel AI-scoring provider chain (cost)
**Ticket:** G-1371 · **PRs:** Eyas #196, Kestrel (premium-fallback-guard)
**Related:** `docs/coe/2026-07-09_redundant-scoring-run-cost.md` (the ~$45 redundant-run incident this one explains the *setup* for), G-438/G-442 (cost-control epic), G-636 (tier-0 poller), G-1315 (Anthropic-fallback fix), G-1322/G-1356 (Llama→Mistral scorer swap)

## Impact

Both scheduled AI-scorers (`daily-scan`, `tier-0-ats-poller`) had provider fallback chains that **terminated in premium Anthropic** (`claude-sonnet-5`). Whenever the cheaper providers ahead of it failed (429 rate-limit / 402 out-of-credits / missing key / provider outage), every dropped job silently billed Anthropic at premium pay-per-token rates, with no alarm.

- **Blast radius (measured):** `daily-scan` = 37 runs in 30 days at ~3,785 jobs/run; `tier-0-ats-poller` = **182 runs** in 30 days (every 15 min, 07–17h Mon–Fri). A single full run that falls entirely to Anthropic is ~$22–27 (per the 2026-07-09 COE).
- **Realised cost:** the 2026-07-09 incident (~$45, two redundant full runs) is the visible tip; the user reported being "charged more" on the Anthropic API for the trailing month — consistent with intermittent premium cascades every time the cheap providers rate-limited.
- **Second exposure path (openrouter):** `openrouter`'s registry-default model is a premium Claude model (`anthropic/claude-sonnet-*`). A chain routing through openrouter without an `OPENROUTER_MODEL` override bills premium Claude too — the stopgap chain `mistral,openrouter,together` is only safe because the workflow pins `OPENROUTER_MODEL` to a cheap Mistral. The same hazard is live in Kestrel's documented "free" chains.
- **Nearly hit:** the exact-dollar figure is only on the Anthropic Console (Admin Usage/Cost API), so the true total wasn't quantified in-session. The bleed was *ongoing at discovery* — the morning `daily-scan` had already run, and the poller was still active.
- This is a **regression**: the identical failure mode (daily scan reaching premium Claude) was fixed on 2026-04-19 and re-appeared. Kestrel (upstream) carries the same architecture and the same gap.

## Timeline

- **2026-04-19** — Original fix: daily scan set to OpenRouter **Llama 3.3 70B free tier** ($0/mo) after a Sonnet swap cost $27+ in one run. Enforced by a memory note (`feedback_scoring_cost_control`): *"NEVER change SCORING_MODEL to Claude/Sonnet without calculating cost impact first."* — discipline, not a test.
- **2026-04-21** — G-438/G-442 cost-control epic ships (prefilter, batch, prompt caching, presets). Chain still terminated on a free/cheap provider.
- **~2026-07 (G-1322 / G-1356)** — Quality fix: a 2026-07-09 benchmark finds Llama 3.3 the *worst* scorer (inflates scores ~2pts, drives T1 tier inflation). The free Llama tier is swapped for Mistral as the lead. **Correct on quality — but it deleted the $0 terminal provider, leaving `…,anthropic` as the terminal leg.** No cost review; nobody was thinking about billing.
- **2026-06-27 (G-636, 40d3606)** — `tier-0-ats-poller` added, "same convention as daily-scan" → inherits `mistral,openai,together,anthropic`, fires ~44×/weekday. Multiplies the latent exposure.
- **2026-07-09 09:51 (G-1315, 1648d42 + fc41bf5)** — the Anthropic leg had been silently HTTP-400-erroring (bad/removed beta header) → harmless because broken (dropped jobs, billed nothing). G-1315 repairs the leg **and bumps `DEFAULT_MODEL` to `claude-sonnet-5`**. Latent risk becomes active billing.
- **2026-07-09 11:08** — repo variable `AI_PROVIDER_FALLBACK` set to `mistral,openrouter,together,anthropic` (Anthropic terminal). Same day as G-1315.
- **2026-07-09** — ~$45 burned on two redundant full runs to "verify the fix" (separate COE).
- **2026-07-19** — User notices higher Anthropic API charges "after our incident on 7 jul." Root-caused this session; stopgap applied; durable guard + tests added.

## Root cause

The 2026-04-19 fix was a **value protected by human discipline, not an invariant protected by code**. "Set the scoring model to the free tier" is a *state*; the surrounding codebase kept changing, and three independent, each-locally-correct changes eroded that state until it was gone:

1. **A quality fix removed the cost floor** (G-1322: Llama inflates scores → switch to Mistral) — which also silently removed the only $0 provider, exposing `anthropic` as the terminal leg. Reviewed for scoring quality; cost impact invisible.
2. **A new feature copied the now-unsafe pattern** (G-636 poller) — multiplying exposure 44×/weekday.
3. **A bug fix un-masked the hazard** (G-1315) — the Anthropic leg was *in* the chain the whole time but harmless because it 400-errored; repairing it (and pointing it at `claude-sonnet-5`) turned latent risk into live billing.

The deeper root cause: **no automated invariant enforced "a scheduled scoring chain may not terminate on a premium provider,"** and **no code-level guard prevented the fallback builder from constructing a premium provider silently.** Per-PR review can't catch this because no single PR reintroduced premium billing — the regression lived in the *composition* of three good changes. A note in a memory file does not survive three sessions and three unrelated motivations.

Contributing design gaps found while root-causing:
- **No premium/cheap classification exists on providers** — the fallback builder skips a provider only when its name is unknown or it fails to construct (missing key), never for cost. Cost was not a property the code could reason about.
- **openrouter's default model is premium Claude** — so "openrouter" reads as cheap but isn't unless `OPENROUTER_MODEL` is pinned. Kestrel's docs even recommend chains (`groq,cerebras,sambanova,openrouter,anthropic`) that silently collapse to `groq,openrouter,anthropic` because `cerebras`/`sambanova` aren't registered — landing everything on premium Claude via openrouter's default.
- **Score-cache keys omit model/provider** (both the pipeline JSON cache and the encrypted SQLite cache), so a model bump silently invalidates nothing and a premium call is unattributable.

## Detection

Detected only when the **user noticed a higher API bill** ~10 days later — the worst detection channel (lagging, manual, money already spent). Could have been caught automatically at three points, none of which existed:
- A CI invariant test failing when `anthropic` re-entered a scheduled chain (G-1322 / G-636 would both have tripped it).
- A per-run digest line logging the *winning provider* + per-provider job counts (a premium cascade would have shown in the digest, not just the invoice).
- A hard spend-cap / loud alarm when the only reachable provider is a paid one.

The 400-broken Anthropic leg actively *masked* the regression for weeks — a broken safety-relevant path hides the risk it carries until something repairs it.

## Resolution

**Immediate stopgap (2026-07-19):**
```
gh variable set AI_PROVIDER_FALLBACK --body "mistral,openrouter,together"   # daily-scan: drop terminal anthropic
gh workflow disable "tier-0-ats-poller.yml" -R pleasedodisturb/Eyas          # pause the 44x/weekday poller
```
**Durable fix (PR #196, G-1371) — Eyas, mirrored in Kestrel:**
- Removed `anthropic` from both workflow default chains.
- **Code guard:** `factory._filter_premium()` — a pure, unit-tested function that drops premium providers from a fallback chain unless `AI_ALLOW_PREMIUM_FALLBACK=1`. The chain builder can no longer construct a premium provider silently, even if a workflow re-adds it.
- **`tests/test_billing_safety.py`** — CI-enforced invariants: every provider is cost-classified; the premium set matches; the filter drops/keeps premium correctly; the chain builder excludes premium by default; no scheduled workflow default chain contains a premium provider; any openrouter leg must pin a cheap `OPENROUTER_MODEL`. Added to `ci.yml`'s ratchet list so it actually gates.
- **Test-isolation hardening:** added `api.mistral.ai` + Gemini to the conftest HTTP block (they were unblocked — a test could have billed them).
- **Follow-up (G-1371):** hard spend guardrail + winning-provider in the daily digest; poller cadence review.

## What went well / what went wrong

- ✅ The 2026-07-09 COE + `feedback_estimate_cost_before_bulk_paid_ops` documented the *cost shape* of a full run, which made root-causing fast.
- ✅ Stopgap (repo variable + workflow disable) stops billing on the next scheduled run without waiting for a merge.
- ✗ The original fix was encoded as a memory note ("NEVER change X"), invisible to the agent making an unrelated quality change three months later.
- ✗ A quality change (G-1322) and a feature change (G-636) each altered the cost-critical chain with no cost review, because cost wasn't a *checked* property of the chain.
- ✗ The Anthropic leg was left in the chain even while broken — a latent hazard nobody removed because it wasn't currently firing.
- ✗ No provider-attribution in run logs, so the premium cascade was invisible until the invoice.

## How a future agent avoids this   ← the point of the whole doc

- **Encode cost floors as CI invariants, never as prose.** If a pipeline "must run on a free/cheap tier," write a test that fails when it doesn't. A memory note saying "never do X" will not survive an unrelated change by a future session. (`tests/test_billing_safety.py` is now that invariant in both Eyas and Kestrel.)
- **Any edit to a provider chain, scoring model, cost preset, or provider default model is a cost-review edit** — even when the motivation is quality or a new feature. Before changing the chain, ask: does it still terminate on a $0/near-$0 provider, and does every routing leg (openrouter) pin a cheap model? Run the billing suite.
- **A premium provider must never be a *silent* terminal fallback.** If all cheap providers fail, degrade to no-score + alarm, not cascade to premium. Premium fallback = explicit `AI_ALLOW_PREMIUM_FALLBACK=1` only.
- **"Cheap provider" can hide a premium model.** openrouter routes to whatever `OPENROUTER_MODEL` says, and the default is premium Claude. Classify by *resolved cost*, not provider brand.
- **A broken safety path is still a hazard — remove it, don't leave it.** A dangerous leg that's currently harmless only because it errors is a landmine waiting for a bug fix. When a bug fix repairs a previously-broken path, ask "should this path exist at all?" (G-1315 repaired the Anthropic leg without asking that.)
- **Attribute cost in run output.** Log the winning provider + per-provider job counts every run, so a premium cascade shows up in the digest the same day, not on next month's invoice.

## Action items

- [x] G-1371 / PR #196 — remove `anthropic` from both Eyas scheduled chains; add `_filter_premium` guard + `test_billing_safety.py`; wire into CI; harden conftest host block (this session).
- [x] Port the guard + billing-safety suite to **Kestrel** (upstream) so fork and parent hold the same invariant (this session).
- [ ] G-1371 — hard spend guardrail + winning-provider logged in the daily digest; poller cadence review (follow-up).
- [ ] Kestrel — fix `docs/guides/cost-optimization.md` examples that terminate chains in anthropic / reference unregistered providers (`cerebras`,`sambanova`,`openai`) that silently collapse the chain onto premium (new ticket).
- [ ] Consider adding provider/model to the score-cache key so a model bump invalidates cache and premium calls are attributable (new ticket).
