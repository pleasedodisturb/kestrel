# Preset Tier Validation: Do Natural Quality Tiers Exist?

*Research date: 2026-04-21 | Related tickets: G-455, G-442 (cost presets)*

## Question

The cost-optimization-strategy.md proposes 5 tiers (Free/Budget/Quality/Private/Custom). Do benchmark data and real-world structured output quality support that many tiers, or should we simplify?

## TL;DR Recommendation

**Keep 5 tiers, but rename and reframe them.** The data shows three distinct quality clusters for scoring (Free, Budget, Quality) plus two orthogonal concerns (Privacy, Custom). This is not a linear 5-step ladder — it is a 3-tier quality axis crossed with a privacy axis and an escape hatch.

```
Quality Axis:     Free ──── Budget ──── Quality
                   │           │           │
Privacy Axis:   (public)    (public)    (public or private)
                                           │
                                        Private ← same quality, different routing
                                           │
Escape Hatch:                           Custom ← user overrides everything
```

## Evidence: The Three Quality Clusters

### Cluster 1: Free Tier (Llama 3.3 70B via Groq/Cerebras/SambaNova)

**Representative model:** Llama 3.3 70B Instruct (open-source, free inference)

| Benchmark | Score | Source |
|-----------|-------|--------|
| MMLU | 86.0% | Meta, llm-stats.com |
| MMLU-Pro | 68.9% | llm-stats.com |
| GPQA Diamond | 50.5% | llm-stats.com |
| HumanEval | 88.4% | llm-stats.com |
| MATH | 77.0% | Meta |
| IFEval | 92.1% | Meta |

**Structured output:** Both Galaxy.ai and Meta report Llama 3.3 70B supports function calling and structured output. However, multiple sources note it "requires manual prompt engineering" for structured JSON and "outputs malformed JSON in some cases" for complex agentic workflows. For Kestrel's scoring use case (single schema, 10 fields, no tool chaining), this is manageable with retry logic.

**JSON quality rating:** MEDIUM-HIGH (per free-model-landscape-2026.md)

**Cost:** $0/month (Groq/Cerebras/SambaNova free tiers, combined 3,000+ RPD)

### Cluster 2: Budget Tier (GPT-4o-mini via OpenRouter)

**Representative model:** GPT-4o-mini

| Benchmark | Score | Source |
|-----------|-------|--------|
| MMLU | 82.0% | OpenAI |
| GPQA Diamond | 40.2% | llm-stats.com |
| HumanEval | 87.2% | llm-stats.com |
| MATH | 70.2% | OpenAI |

**Wait — Llama 3.3 70B scores higher on every benchmark?**

Yes. The counterintuitive finding is that Llama 3.3 70B (the "free" model) outperforms GPT-4o-mini (the "budget" model) on raw benchmarks. Llama 3.3 70B wins on MMLU (+4), MMLU-Pro (no GPT-4o-mini score available), GPQA (+10.3), HumanEval (+1.2), and MATH (+6.8).

**So why keep a Budget tier at all?** Three reasons:

1. **Structured output reliability.** GPT-4o-mini has native JSON mode and function calling baked into the API. OpenAI's structured output is deterministic — the model is constrained to produce valid JSON matching a provided schema. Llama 3.3 70B relies on prompt-based JSON generation, which fails in edge cases. For Kestrel's 18,000 scores/month, even a 2% JSON failure rate means 360 retries/month on the free tier vs near-zero on Budget.

2. **Inference provider stability.** Free providers (Groq, Cerebras, SambaNova) have no SLA. Rate limits shift without notice. Groq's 6K TPM limit can bottleneck batch scoring. OpenRouter with a $10 deposit provides stable, SLA-backed access to GPT-4o-mini with no platform-level RPD cap.

3. **Cost is negligible.** GPT-4o-mini costs ~$0.81/month for 18,000 scores. The "budget" tier is not about saving money vs free — it is about buying reliability for less than a cup of coffee.

**JSON quality rating:** HIGH (native structured output, deterministic schema adherence)

**Cost:** ~$0.81/month (OpenRouter with $10 one-time deposit)

### Cluster 3: Quality Tier (Claude Sonnet / GPT-4o-class)

**Representative models:** Claude Sonnet 4.6 ($3/$15 per 1M tokens), GPT-4o ($2.50/$10 per 1M tokens)

| Benchmark | Claude 3.5 Sonnet | GPT-4o | Source |
|-----------|------------------|--------|--------|
| MMLU | 88.7% | 88.7% | Anthropic, OpenAI |
| GPQA Diamond | 59.4% | 53.6% | Anthropic, OpenAI |
| HumanEval | 92.0% | 90.2% | Anthropic, OpenAI |
| MATH | 78.3% | 76.6% | Anthropic, OpenAI |
| Arena Elo | ~1286 | ~1278 | LMSYS (Feb 2026) |

**Is the gap between Budget and Quality meaningful for scoring?**

For Kestrel's scoring use case specifically — **no, not much.** Scoring is a structured classification task: read a job description, compare against a user profile, output dimensional scores in JSON. Academic evidence (arXiv:2604.03684) shows classification tasks see <2 percentage point degradation even with batch prompting. GPT-4o-mini handles this adequately.

**Where Quality matters is non-scoring operations:**

| Operation | Why Quality Helps | Monthly Volume |
|-----------|------------------|----------------|
| Company research | Multi-hop reasoning, synthesizing public data | ~300 |
| Interview prep | Nuanced question generation, domain knowledge | ~90 |
| Cover letters | User-facing prose, tone matching, PII handling | ~90 |

The GPQA gap tells the story: Claude Sonnet scores 59.4% vs GPT-4o-mini's 40.2% — a **19.2 percentage point gap** on graduate-level reasoning. For tasks requiring actual reasoning (not just classification), Quality tier models are measurably better.

**JSON quality rating:** HIGH (both have native structured output APIs)

**Cost:** $5-25/month depending on volume and operation mix

## The Quality Gap: Quantified

| Dimension | Free (Llama 3.3 70B) | Budget (GPT-4o-mini) | Quality (Sonnet) | Gap: Free→Budget | Gap: Budget→Quality |
|-----------|----------------------|---------------------|------------------|-------------------|---------------------|
| MMLU | 86.0% | 82.0% | 88.7% | -4.0 pts | +6.7 pts |
| GPQA Diamond | 50.5% | 40.2% | 59.4% | -10.3 pts | +19.2 pts |
| HumanEval | 88.4% | 87.2% | 92.0% | -1.2 pts | +4.8 pts |
| MATH | 77.0% | 70.2% | 78.3% | -6.8 pts | +8.1 pts |
| JSON reliability | Prompt-based | Native/deterministic | Native/deterministic | **Major** | Negligible |
| Inference stability | No SLA, shifting limits | SLA-backed, stable | SLA-backed, stable | **Major** | Negligible |
| Monthly cost | $0 | ~$0.81 | $5-25 | $0.81 | $4-24 |

**Key insight:** The Free→Budget gap is not about benchmark scores (Llama actually wins). It is about **operational reliability** — deterministic JSON output and stable inference. The Budget→Quality gap is about **reasoning depth** — relevant for generation tasks but not for scoring.

## Do We Need Both "Private" and "Quality"?

**Yes, because they are orthogonal.**

Privacy is not a quality level — it is a routing constraint. A user who wants Private tier still wants Quality-level output; they just need it from a provider that does not train on their data.

| Provider | Training on Data | ZDR Available | Quality Level |
|----------|-----------------|---------------|---------------|
| OpenRouter (free models) | Varies by upstream | No | Free |
| OpenRouter (GPT-4o-mini) | No (OpenAI policy) | No | Budget |
| Anthropic API (Sonnet) | No (API default) | Yes (Zero Data Retention) | Quality |
| Ollama (local) | N/A (local) | N/A | Varies |

Private tier = Quality-tier models + ZDR/local routing. It exists because some users handle sensitive data (resumes, salary expectations) and need guarantees that data is never used for training and has minimal retention.

The cost-optimization-strategy.md already identified this split: scoring uses public data (any provider), while cover letters and interview prep use private data (ZDR providers or local).

## StructEval Benchmark: JSON Is "Solved" for All Tiers

The StructEval benchmark (arXiv:2505.20139, Dec 2025) evaluated structured output across 18 formats and 44 task types. Key finding for Kestrel:

> "JSON, HTML, CSV generation and YAML→JSON, React→HTML conversions show near-perfect performance [>90%], indicating that JSON generation specifically is effectively solved."

Even o1-mini (a smaller reasoning model) achieved only 75.58% **average across all 18 formats** — but JSON generation specifically was >90% for all tested models, including open-source ones. This means the JSON quality gap between tiers is smaller than the overall benchmark gaps suggest.

**Implication for Kestrel:** The structured JSON scoring output is the *easiest* task we ask models to do. The tier differentiation matters more for free-text generation (cover letters, research summaries) than for scoring.

## Recommendation for G-442: Preset Boundaries

### Keep 5 Presets, Define Clear Boundaries

| Preset | Models | Routing | Monthly Cost | Best For |
|--------|--------|---------|-------------|----------|
| **Free** | Llama 3.3 70B | Groq → Cerebras → SambaNova fallback chain | $0 | Users who want $0 cost and accept occasional JSON retries and provider instability |
| **Budget** | GPT-4o-mini | OpenRouter ($10 one-time deposit) | ~$0.81 | **Default for most users.** Deterministic JSON, stable inference, negligible cost |
| **Quality** | Sonnet (scoring) + Opus (generation) | OpenRouter or Anthropic API | $5-25 | Users who want best-in-class for research, interview prep, and cover letters |
| **Private** | Sonnet/Opus via Anthropic ZDR, or Ollama local | Direct API with ZDR, or local | $5-25 + hardware | Users handling sensitive data who need zero-data-retention guarantees |
| **Custom** | User-configured | User-configured | Varies | Power users who want full control over model/provider routing per operation |

### Implementation Guidance for G-442

1. **Default preset: Budget.** Not Free. The $0.81/month cost is below the threshold where free matters, and the JSON reliability difference is operationally significant at 18,000 scores/month.

2. **Onboarding should explain the $10 unlock.** OpenRouter's $10 one-time deposit is the key friction point. The onboarding flow should explain: "A one-time $10 deposit unlocks reliable scoring for ~12 months."

3. **Hybrid routing within Quality/Private presets.** These presets should not use Opus for everything — route scoring through Budget-tier models (GPT-4o-mini) and reserve Quality-tier models for generation tasks. The cost-optimization-strategy.md already specifies this ($25/mo hybrid vs $307/mo uniform Sonnet).

4. **Free preset needs a health warning.** Free inference providers have no SLA and shifting rate limits. The preset should document: "Scoring may take 30+ minutes/day due to rate limits. JSON output may occasionally require retries. Provider availability is not guaranteed."

5. **Private preset needs provider verification.** Before routing through a "private" provider, verify ZDR status. Anthropic API has ZDR by default for API calls. OpenRouter does NOT guarantee ZDR — it depends on the upstream provider. Ollama is inherently private (local).

### What "Simplify to Free/Paid/Custom" Would Lose

Collapsing to 3 tiers merges:
- **Budget + Quality** into "Paid" — losing the distinction between $0.81/mo scoring-only and $25/mo full-featured. Users who only score jobs would overpay 30x.
- **Quality + Private** into "Paid" — losing the privacy routing distinction. Users who need ZDR would not know which providers are safe.

The 5-tier model is not complexity for its own sake. It maps to real user segments with different constraints (cost, quality, privacy, control). The key is that the **default** (Budget) works for 80% of users, and the other presets are discoverable but not required.

## Sources

- [StructEval: Benchmarking LLMs' Capabilities to Generate Structural Outputs](https://arxiv.org/abs/2505.20139)
- [GPT-4o Mini vs Llama 3.3 70B Benchmark (LowTouch AI)](https://www.lowtouch.ai/gpt-4o-mini-vs-llama-benchmark/)
- [GPT-4o-mini vs Llama 3.3 70B Instruct Comparison (llm-stats.com)](https://llm-stats.com/models/compare/gpt-4o-mini-2024-07-18-vs-llama-3.3-70b-instruct)
- [GPT-4o-mini vs Llama 3.3 70B Instruct (Galaxy.ai)](https://blog.galaxy.ai/compare/gpt-4o-mini-vs-llama-3-3-70b-instruct)
- [LLM Benchmarks 2026: 30+ Models Ranked (iternal.ai)](https://iternal.ai/llm-selection-guide)
- [LMSYS Chatbot Arena April 2026 Rankings](https://aidevdayindia.org/blogs/lmsys-chatbot-arena-current-rankings/lmsys-chatbot-arena-leaderboard-current-top-models.html)
- [Artificial Analysis: AI Model Comparison](https://artificialanalysis.ai/models)
- [Cleanlab: LLM Structured Output Benchmarks](https://cleanlab.ai/blog/structured-output-benchmark/)
- [arXiv:2604.03684 — Batch Prompting Cost Savings](https://arxiv.org/abs/2604.03684v1)
- [Anthropic API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing)
- Kestrel internal: `docs/research/free-model-landscape-2026.md`
- Kestrel internal: `docs/research/cost-optimization-strategy.md`
- Kestrel internal: `docs/research/batch-scoring-feasibility.md`
- Kestrel internal: `docs/research/openrouter-rate-limits.md`
