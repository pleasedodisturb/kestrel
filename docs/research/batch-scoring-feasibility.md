# Batch Scoring Feasibility Research

*Research date: 2026-04-21 | Context: Can multi-job-per-prompt scoring reduce costs without quality loss?*

## Verdict: Yes. Sweet spot is 10-25 jobs per prompt.

## Academic Evidence

### arXiv:2604.03684 (April 2026)
"Researchers waste 80% of LLM annotation costs by classifying one text at a time."

- Batch sizes of 25-100 maintained accuracy with <2 percentage point loss
- For structured scoring (not fine-grained emotion analysis), degradation is minimal
- Cost savings: 80%+ at batch sizes of 25-100

### ICLR 2024 (arXiv:2309.00384)
- Performance degradation is **architecture-dependent**: some models handle batching well, others collapse
- Degradation caused by managing multiple classification schemes simultaneously, not by token count
- Fine-grained semantic tasks (emotion analysis) degrade more than coarse classification

## Position Bias

Items score differently based on their position within a batch. Jobs listed first or last may receive different scores than jobs in the middle.

**Mitigation:** Randomize job order within each batch. For critical scoring, consider Batch Permutation and Ensembling (BPE) — majority vote over repeated permutations.

## Context Window Math

At 10 jobs per prompt:
- System prompt + profile: ~2,500 tokens (cached)
- 10 job summaries: ~500 tokens each = ~5,000 tokens
- Total input: ~7,500 tokens per call (well within any context window)
- Total output: ~2,000 tokens (10 x 200-token scores)

At 25 jobs per prompt:
- Total input: ~15,000 tokens
- Still well within 128K+ context windows of modern models

## Batch API (Asynchronous Processing)

### Anthropic Message Batches API
- 50% off input and output tokens
- Results within 24 hours
- No quality difference vs real-time
- Can stack with prompt caching for up to 95% total reduction
- Perfect for nightly discovery scoring

### OpenAI Batch API
- Same 50% discount, 24-hour window
- GPT-4.1 Mini at batch pricing: $0.20/$0.80 per 1M tokens

## Prompt Caching

System prompt + user profile (~2,500 tokens) is identical across all 600 daily scoring calls.

| Provider | Cache Read Cost | TTL | Savings |
|----------|----------------|-----|---------|
| Anthropic | 0.1x standard input | 5 min (default), 1 hour (premium) | 90% |
| OpenAI | Similar caching | Varies | ~50-90% |

Cache write costs 1.25x on first call, then 0.1x for all subsequent calls within TTL. For sequential scoring runs, 5-minute TTL is sufficient.

## Combined Cost Calculation

**Using Haiku 4.5 ($1.00/$5.00 per 1M tokens)**

### Baseline: 600 individual calls, no optimization
- Daily: $3.30 | Monthly: $99

### Optimized: Pre-filter (60%) + Batch (10/prompt) + Cache + Batch API
- After pre-filter: 240 jobs
- Batched: 24 API calls
- Cached portion: 0.1x rate
- Batch API: 0.5x rate
- Daily: ~$0.18 | **Monthly: ~$5.40**

### Without Batch API (real-time scoring)
- Pre-filter + batching + caching alone
- **Monthly: ~$12**

## Recommendations for Kestrel

1. **Implement batch scoring** with configurable batch size (default: 10)
2. **Add prompt caching** to all providers that support it (Anthropic first)
3. **Add Batch API support** for nightly discovery runs
4. **Randomize job order** within batches to mitigate position bias
5. **Run A/B validation** comparing batch vs individual scoring quality on real data

## Open Question

Does batching degrade Kestrel's specific scoring format (structured JSON with dimensional scores, ATS keywords, desire score)? The academic papers tested simpler classification. Empirical A/B testing needed with our exact prompt and schema.

## Sources

- [arXiv:2604.03684 — Batch Prompting Cost Savings](https://arxiv.org/abs/2604.03684v1)
- [ICLR 2024 — Batch Scoring Quality](https://arxiv.org/pdf/2309.00384)
- [Anthropic API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [OpenAI Batch API Pricing](https://platform.openai.com/docs/pricing/)
