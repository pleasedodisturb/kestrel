# Token Optimization: Raw Research Findings

> Raw findings from the research phase. For opinionated synthesis, see [token-optimization-research.md](./token-optimization-research.md).

## Source: awesome-llm-token-optimization

Full research corpus: https://github.com/pleasedodisturb/awesome-llm-token-optimization

**52 papers, 150+ resources** covering 10 strategy categories. Key findings below.

---

## 1. Prompt Caching (90% savings)

**Providers:** Anthropic (prefix-based, 5-min TTL, 1024-token minimum), OpenAI (auto-caching on long prompts), Google (manual), DeepSeek (auto + manual).

**Anthropic specifics (our primary provider):**
- Cached input reads: $0.30/MTok (vs $3.00 base) = 90% discount
- Cache creation: $3.75/MTok (25% premium on first write)
- Minimum cached prefix: 1024 tokens
- TTL: 5 minutes (extended by each cache hit)
- Prefix-based: only the beginning of the system prompt can be cached

**Key insight for Kestrel:** System prompt alone (~130 tokens compressed) is below 1024 minimum. Must combine with profile data (~400-2000 tokens) to activate caching. This is why profile moves to system block.

**Sources:**
- https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
- https://openai.com/index/api-prompt-caching/

---

## 2. Batch APIs (50% savings)

**Anthropic:** POST to `/v1/messages/batches`, 24-hour SLA, 50% discount, results as JSONL stream.
**OpenAI:** Similar batching at 50% discount.
**Google:** Batch predictions with variable discount.

**Fit for Kestrel:** Discovery sweeps score 50-200 jobs overnight. Perfect batch candidate. Real-time scoring stays synchronous.

---

## 3. Model Routing (60-95% savings)

**Frameworks:** RouteLLM (Berkeley), LiteLLM, NotDiamond, Martian.

**RouteLLM findings:** 85% cost reduction with <3% quality loss when routing between GPT-4 and GPT-3.5 class models using calibrated classifiers.

**Kestrel approach:** Static routing by AIFeature → ComplexityTier (no ML classifier needed at our scale). Map: learning_recommendations/interview_format → SIMPLE, score/gap_analysis → STANDARD, strategy/deep analysis → COMPLEX.

---

## 4. Prompt Compression

### LLMLingua-2 (Microsoft, ACL 2024)
- Package: `llmlingua` on PyPI
- Model: XLM-RoBERTa-large (1.2GB)
- Compression: 3-20× on long documents
- Latency: 2-5s on CPU for moderate-length prompts
- **Verdict for Kestrel:** NOT recommended. Our prompts are <300 tokens. LLMLingua targets 5000+ token RAG contexts. The model download and latency overhead far exceed the savings.

### Manual compression (telegraphic notation)
- Remove filler, use shorthand, inline options
- 20-60% reduction on structured instruction prompts
- Zero dependency, zero latency
- **Verdict for Kestrel:** RECOMMENDED. Applied in G-261 with 67% reduction.

**Sources:**
- https://github.com/microsoft/LLMLingua
- https://arxiv.org/abs/2403.12968

---

## 5. Token-Efficient Tool Use (70% output reduction)

**Anthropic-specific:** Beta header `token-efficient-tool-use-2025-04-14` reduces tool_use content block output by ~70%.

**Mechanism:** Instead of repeating the full tool schema in the output, the model returns only the populated fields in a compact format.

**Implementation:** Single header addition. Already shipping (G-349).

**Source:** https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/token-efficient-tool-use

---

## 6. Response Caching (100% savings on repeats)

**Kestrel implementation:** SQLite + Fernet encryption, SHA-256 keyed by (feature, prompt, context), 7-day TTL, thread-safe via asyncio.to_thread.

Not a novel research finding — standard pattern. Notable design choice: cache key includes profile hash, so profile updates invalidate stale scores.

---

## 7. JSON Serialization Format

**Finding:** `json.dumps(data, indent=2)` adds ~30% whitespace tokens vs `json.dumps(data, separators=(",",":"))`.

**TOON (Token-Oriented Object Notation):** Research variant that removes quotes from keys and uses minimal delimiters. Not adopted — too fragile for production parsing.

**Kestrel approach:** Standard compact JSON (no indent). Conservative, universally parseable, ~30% savings.

**Source:** https://www.thakurcoder.com/blog/2025-11-05-toon-vs-json-supercharge-your-llm-prompts-and-cut-token-costs

---

## 8. KV Cache Compression (inference-only)

**Relevant for:** Self-hosted inference (vLLM, SGLang, TensorRT-LLM).
**Not relevant for Kestrel:** We use API providers. KV cache is managed server-side.

---

## 9. Context Window Management (RAG vs Long Context)

**Finding:** "RAG is 1250× cheaper for many queries" (Google research). For retrieval-heavy workloads, chunking + embedding search is far cheaper than stuffing full documents into context.

**Not relevant for Kestrel:** Scoring prompts are already well within context limits (<4K tokens). No RAG tradeoff needed.

---

## 10. Cache Break Detection

**Problem:** When the cached prompt prefix changes between calls, Anthropic creates a new cache entry instead of reading the existing one. This silently 10×'s input costs.

**Common causes:**
- Timestamps in the system prompt (changes every second)
- Randomized field ordering (Python dict ordering is stable, but JSON serialization of sets isn't)
- Dynamic content in the cached block (feature flags, A/B test variants)
- Profile updates mid-batch

**Detection:** Compare `cache_creation_input_tokens` vs `cache_read_input_tokens`. A healthy batch has 1 creation + N-1 reads. If you see repeated creations, the prefix is changing.

**Kestrel implementation (G-427):** Sliding window per feature, WARNING at <80% hit ratio.

---

## Pricing Landscape (April 2026)

| Provider | Model | Input $/MTok | Output $/MTok | Notes |
|----------|-------|-------------|--------------|-------|
| Anthropic | Opus 4 | $15.00 | $75.00 | Cache read: $1.50 |
| Anthropic | Sonnet 4 | $3.00 | $15.00 | Cache read: $0.30 |
| Anthropic | Haiku 4.5 | $0.80 | $4.00 | Cache read: $0.08 |
| OpenRouter | Sonnet 4 (proxy) | $3.00 | $15.00 | +5.5% credit fee |
| Together.ai | Llama 3.3 70B | $0.88 | $0.88 | ZDR, Frankfurt DC |
| Together.ai | Llama 3.1 8B | $0.18 | $0.18 | Ultra-cheap classification |
| Ollama | Any (local) | $0.00 | $0.00 | Hardware cost only |

**Trend:** LLM API prices dropped ~80% between early 2025 and early 2026 (DeepSeek disruption + competition). Prompt caching discounts (90%) appeared mid-2025 and are now standard across top providers.

---

## Tools & Calculators

- **LLM Pricing Calculator:** https://llmpricecheck.com (300+ models)
- **Cost Tracking:** Langfuse (open-source, self-hosted), Helicone, LiteLLM proxy
- **Token Counting:** tiktoken (OpenAI), anthropic-tokenizer
- **Compression:** LLMLingua (Python), selective pruning (manual)

---

## Research Date

Primary research: 2026-04-15 (G-344 audit)
Implementation: 2026-04-20 (G-348 epic execution)
