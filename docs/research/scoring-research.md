# Scoring Research: Turning Job Listings Into Actionable Decisions

**Researched:** 2026-04-16
**Status:** Research complete — architecture validated, iterating on consistency
**Scope:** Kestrel scoring engine — the core decision-making system

---

## Philosophy: Human-First, Data-Driven

This document follows a deliberate research philosophy: we do deep, thorough research to understand the full landscape, but research findings **inform** decisions — they don't make them.

Every recommendation here weighs:

- **Developer wellbeing** — mental load, emotional cost, maintenance burden for a solo developer
- **Sustainability** — will this still be manageable in 6 months? In 2 years?
- **Real-world consequences** — for the developer, for users, for the project's future
- **Balance** — across competing concerns, not optimizing for a single metric

"Recommended" doesn't mean "optimal." It means: sane, balanced, and reflective of what we actually care about. We research deeply so we *can* make informed trade-offs. Then we make the human decision.

Scoring is where Kestrel earns its keep. Testing (G-268) catches bugs. CI/CD ships code. But scoring is the product — it answers the question users actually care about: "Should I apply to this job?"

---

## Context: What We Already Have

Kestrel's scoring system is the most mature domain in the codebase:

| Area | What's In Place | Status |
|------|----------------|--------|
| **Dual scoring** | Fit score (objective match) + desire score (subjective want) | Core architecture |
| **6 dimensions** | Skills, experience, culture, growth, compensation, location per score | Granular feedback |
| **Quadrant model** | Dream / Strong / Safe Bet / Reach / Skip classification | Decision framework |
| **Rubric-based prompting** | v1.1 rubrics with anchored examples per dimension | Validated via benchmark |
| **Red flag detection** | Ghost jobs, stale posts, vague responsibilities, staffing agencies, unrealistic requirements, missing salary | Active, tuning |
| **Golden set regression** | 3 domains (general tech, finance, design), 20+ jobs each | Expanding |
| **User feedback loop** | Bayesian preference learning after ~10 corrections | Designed (G-279) |
| **Provider abstraction** | MockProvider (dev), OpenRouterProvider (prod), Anthropic, Ollama | Clean factory pattern |
| **Benchmark infrastructure** | G-286: 120-call A/B framework (20 jobs x 3 runs x 2 variants) | Proven |

**Key metrics from G-286 benchmark:**
- Rubric v1.1 reduced scoring variance by 15.7% (mean std 0.364 -> 0.307)
- Reject category: 100% in-band (most consistent)
- Strong category: 11.8-20% in-band (least consistent — inherently fuzzy)
- 18 red flags detected, 10 false positives (55% FP rate on vague_responsibilities)

---

## Research Synthesis: Six Streams

### Stream 1: Scoring Architecture

**The data says:** Dual-score (fit + desire) outperforms single-score systems. A single number collapses two fundamentally different questions — "Can I do this job?" and "Do I want this job?" — into one ambiguous signal. Six dimensions per score give users granular feedback on *why* a job scored the way it did, not just the final number. The quadrant model (Dream / Strong / Safe Bet / Reach / Skip) maps the dual scores into actionable categories that directly answer "should I apply?"

**The trade-off:** More dimensions = more AI tokens per score. Dual scoring doubles the cost compared to a single composite score. Six dimensions per score means 12 total dimension evaluations, each requiring the model to reason independently. At scale, this is the difference between $3/month and $6/month for typical usage.

**Our recommendation:** Keep dual scoring. The quadrant is the killer feature — it answers "should I apply?" not just "how good is the match?" A Dream job (high fit + high desire) and a Reach job (low fit + high desire) both score high on desire, but the user's action is completely different: apply confidently vs. apply with a stretch narrative. Single-score systems lose this distinction entirely. The 2x cost is worth it because the output is 10x more useful.

**Key decisions already made right:**
- Fit and desire as independent axes, not weighted sub-components of one score
- Quadrant naming that implies action (Dream = go for it, Skip = don't waste time)
- Six dimensions that users can drill into for self-improvement (e.g., "your skills match is strong but experience is weak" is actionable; "you're a 72% match" is not)

### Stream 2: Scoring Consistency

**The data says:** The G-286 A/B benchmark (120 calls: 20 jobs x 3 runs x 2 variants) quantified exactly how much LLM scoring varies across identical inputs. Rubric v1.1 — which adds anchored examples and explicit boundary definitions per dimension — reduced mean standard deviation by 15.7% (0.364 to 0.307). Reject-category jobs are 100% in-band across runs. Strong-category jobs are the most volatile, with only 11.8-20% in-band.

**The trade-off:** Tighter rubrics improve consistency but may reduce nuance. The "strong" category spans a wide range because mid-tier jobs genuinely vary — a job might be strong on skills but weak on growth, landing in "strong" overall but for very different reasons each run. Over-constraining the rubric to force consistency would flatten legitimate variation.

**Our recommendation:** Accept that "strong" is inherently fuzzy. Focus enforcement on reject/dream boundaries (clear-cut decisions where inconsistency matters most) and let the middle breathe. Golden set regression tests should use wider acceptance bands for strong/mediocre categories than for reject/dream. A user who sees a job flip between "strong" and "safe bet" across re-scores is mildly confused; a user who sees it flip between "dream" and "skip" has lost trust in the system.

**What the benchmark taught us:**
- Variance is not a bug to eliminate — it's a signal to manage per category
- Rubric anchoring (concrete examples of what a "4/5 on skills" looks like) delivers more consistency than prompt length alone
- Three runs per job is sufficient to detect systematic drift; diminishing returns beyond that

### Stream 3: Multi-Domain Scoring

**The data says:** Scoring must work for ANY job family — tech, finance, design, healthcare, legal. Not just tech/TPM roles. A software engineer's "skills match" looks nothing like a financial analyst's. Golden sets now cover 3 domains (general tech, finance, design) with 20+ jobs each, validating that the scoring rubric generalizes across fundamentally different career tracks.

**The trade-off:** Job-family-aware weighting adds complexity. Each domain needs its own golden set for regression testing. A "location" dimension matters differently for a remote-first tech role vs. a hospital-based nursing position. Maintaining domain-specific weighting means N configuration files instead of one, and each new domain requires curated test data.

**Our recommendation:** Expand golden sets incrementally. Three domains is a solid start — it proves the architecture generalizes without drowning in maintenance. Add healthcare/legal when real users in those domains request them. Keep weighting configurable per job family so the system can adapt without code changes. The rubric's natural language format means domain-specific nuance comes from prompt wording, not from hardcoded logic.

**Domain coverage roadmap:**
- Shipped: general tech, finance, design (3 domains, 60+ golden set jobs)
- Next: healthcare, legal (when user demand surfaces)
- Architecture: per-domain golden sets with shared scoring rubric + domain-specific weight overrides

### Stream 4: Red Flag Detection

**The data says:** Pattern matching catches ghost jobs, stale postings, vague responsibilities, staffing agencies, unrealistic requirements, and missing salary — problems that waste user time before they even get to scoring. G-297 raised the vague_responsibilities threshold from 200 to 400 characters (reducing false positives for jobs with legitimately concise but adequate descriptions). The G-286 benchmark showed 18 flags across the test set, with 10 false positives — a 55% false positive rate concentrated almost entirely on the vague_responsibilities flag.

**The trade-off:** Aggressive flags catch more real issues but generate more false positives. Lenient flags miss real problems but don't annoy users with incorrect warnings. At 55% FP rate, vague_responsibilities is currently more noise than signal — users learn to ignore it, which undermines trust in the flags that are accurate.

**Our recommendation:** Keep raising thresholds based on data. The 55% FP rate on vague_responsibilities is still too high — it should be under 30% before it's trustworthy. Track FP rate per flag type systematically (not just during benchmarks) so we can tune each flag independently. Reject-category flags (ghost jobs, stale postings) are high-confidence and should stay aggressive. Informational flags (vague responsibilities, missing salary) should be lenient and clearly marked as "heads up" rather than "warning."

**Flag confidence tiers:**
- High confidence (keep aggressive): ghost job patterns, 90+ day stale postings, known staffing agency domains
- Medium confidence (tune carefully): unrealistic requirements (10+ years for a junior role), salary missing from non-exempt roles
- Low confidence (widen thresholds): vague responsibilities, generic job descriptions

### Stream 5: Scoring Feedback & Learning

**The data says:** User corrections injected after approximately 10 examples allow Bayesian preference learning (G-279) to personalize scoring over time. The system learns what *this specific user* values — maybe they weight remote work heavily, or they don't care about company size. Scoring improves the more you use it because the model incorporates demonstrated preferences, not just stated ones.

**The trade-off:** Early corrections with a small sample can over-fit. A user who corrects two finance roles upward might skew all future finance scoring, even if those two corrections reflected a mood rather than a stable preference. Users may also not provide enough feedback — the system works best with 10+ corrections but many users may stop at 2-3.

**Our recommendation:** Keep the 10-correction threshold as the minimum for preference learning to kick in meaningfully. Below 10, corrections are stored but weighted lightly. Add a "confidence" indicator showing how personalized the scoring is — something like "new user" (0-5 corrections), "learning" (5-15), "calibrated" (15+). This sets expectations: early scores are generic, and the system gets better as you use it. Don't hide the cold-start problem; make it part of the value proposition ("the more you use Kestrel, the smarter it gets").

**Design decisions:**
- Corrections stored permanently, not session-scoped
- Preference learning is per-profile (multi-user isolation)
- Explicit corrections ("this should be higher") weighted more than implicit signals (time spent viewing)
- Users can reset their preference model if their career goals change

### Stream 6: Provider Abstraction & Cost

**The data says:** The factory pattern with MockProvider and OpenRouterProvider (plus Anthropic and Ollama) keeps the scoring engine cleanly separated from the AI provider. MockProvider returns deterministic scores for development and testing — no API calls, no cost, instant results. OpenRouterProvider routes to the best-value model for scoring (currently Claude, but swappable). Ollama enables fully local, free scoring for users who want zero data leaving their machine.

**The trade-off:** Real AI scoring costs approximately $3-10/month via OpenRouter for typical usage (50-200 jobs scored). MockProvider is free but deterministic — it doesn't actually evaluate job fit, so it's useless for real users. Ollama is free but requires local GPU resources and produces lower-quality scores than cloud models.

**Our recommendation:** Keep the abstraction clean — it's one of the best architectural decisions in the codebase. Add cost tracking per score call so users can see their spending in real-time and set budget limits. MockProvider as "Demo Mode" for zero-cost onboarding is exactly right — let users explore the interface, understand the quadrant model, and see what scoring looks like before connecting a real provider. When they're ready, switching to OpenRouter is a config change, not a code change.

**Cost optimization opportunities:**
- Batch scoring (score 10 jobs in one prompt instead of 10 separate calls) — potential 30-40% token savings
- Embedding pre-filter (G-272) as a cheap first pass before expensive AI scoring — but no clean similarity threshold exists yet (max_reject 0.6475 > min_strong_dream 0.6066)
- Cache scores aggressively — a job listing doesn't change, so re-scoring is waste
- Model tier selection: use a cheaper model for pre-screening, reserve the expensive model for final scoring

---

## What We Explicitly Chose NOT to Do

These came up in research but were rejected for good reasons:

| Rejected Approach | Why |
|-------------------|-----|
| Single composite score | Loses the fit/desire tension. "75% match" doesn't tell you whether to apply |
| Embedding-only pre-filter as primary scorer | G-272 showed no clean similarity threshold: max_reject 0.6475 > min_strong_dream 0.6066. Embeddings can't distinguish "good fit, don't want" from "bad fit, really want" |
| Fixed weights across all job families | A nurse's "location" dimension and a remote developer's "location" dimension are fundamentally different. One-size-fits-all weights produce one-size-fits-none scores |
| Real-time scoring on every page load | Too expensive. Score once when the job is discovered, cache the result, re-score only on user request or profile change |
| Deterministic rule-based scoring | Misses nuance that LLMs capture. "5 years Python experience" and "5 years building distributed systems in Python" are different, and only an LLM knows that |
| Crowd-sourced scoring calibration | No user base yet. When there is one, aggregate preference data could improve rubrics, but it's a post-launch optimization |
| Continuous re-scoring as profiles change | Profile changes should trigger a re-score flag, not automatic re-scoring. Users control when they spend tokens |
| Provider-specific prompt tuning | The rubric should work across providers. If it only works on Claude, we've built a vendor lock-in, not a scoring system |

---

## Key Decisions Made Right

Looking back across the scoring system's evolution, these architectural bets paid off:

| Decision | Why It Was Right |
|----------|-----------------|
| **Dual scoring (fit vs desire)** | The quadrant model is only possible because fit and desire are independent axes. This is the single most differentiating design decision |
| **Rubric-based prompting** | 15.7% variance reduction in a controlled benchmark. Rubrics are the difference between "ask the AI what it thinks" and "give the AI a grading framework" |
| **Golden sets across domains** | Catching regressions before they ship. Three domains prove the system generalizes beyond tech |
| **User feedback loop with threshold** | 10-correction minimum prevents over-fitting while still enabling personalization |
| **Red flag pre-screening before AI scoring** | Cheap pattern matching eliminates obviously bad jobs before spending tokens on them |
| **Provider abstraction** | MockProvider for dev, OpenRouter for prod, Ollama for privacy. Users choose their cost/quality/privacy trade-off |
| **Profile-aware scoring** | Scores are relative to the user's profile, not absolute. The same job scores differently for different people — as it should |

---

## Decision Matrix

Key decisions across all streams, with the reasoning:

| Decision | Choice | Runner-Up | Why This Choice |
|----------|--------|-----------|-----------------|
| Score structure | Dual (fit + desire) | Single composite | Enables quadrant model, the killer UX feature |
| Dimension count | 6 per score | 3 broad categories | Granularity enables actionable feedback without overwhelming |
| Classification | Quadrant model (5 categories) | Percentile ranking | Categories map to actions; percentiles don't |
| Consistency approach | Category-specific tolerance bands | Uniform tight bands | "Strong" is inherently fuzzier than "reject" |
| Rubric format | Anchored examples per dimension | Generic scoring instructions | 15.7% variance reduction, proven in benchmark |
| Multi-domain support | Configurable weights + domain golden sets | One-size-fits-all | Different careers have different priorities |
| Red flag strategy | Tiered confidence with per-flag thresholds | Uniform aggressive flagging | 55% FP rate proves uniform approach fails |
| Feedback learning | Bayesian with 10-correction threshold | Immediate weight adjustment | Prevents over-fitting on small sample |
| Provider strategy | Factory pattern, user-selectable | Hardcoded to one provider | Cost/quality/privacy is a user choice |
| Pre-filter | Deferred (no clean threshold) | Embedding similarity gate | G-272 data showed overlapping distributions |
| Cost control | Score-once + cache | Real-time re-scoring | Job listings don't change; re-scoring is waste |
| Benchmark method | 20 jobs x 3 runs x 2 variants | Ad-hoc spot checks | Statistically meaningful, reproducible |

---

## Cost Summary

### Scoring Costs (Monthly, Typical Usage)

| Usage Pattern | Jobs Scored | Estimated Cost | Provider |
|---------------|-------------|----------------|----------|
| Light (browsing) | 50 jobs/mo | ~$1.50 | OpenRouter |
| Active (job searching) | 200 jobs/mo | ~$6.00 | OpenRouter |
| Heavy (multiple searches) | 500 jobs/mo | ~$15.00 | OpenRouter |
| Demo mode | Unlimited | $0 | MockProvider |
| Local/privacy | Unlimited | $0 (+ GPU) | Ollama |

### Optimization Levers

| Optimization | Potential Savings | Status |
|--------------|-------------------|--------|
| Score caching (don't re-score unchanged jobs) | 30-50% | Implemented |
| Batch scoring (multiple jobs per prompt) | 30-40% per batch | Planned |
| Embedding pre-filter (skip obvious mismatches) | 20-30% fewer AI calls | Blocked (no clean threshold) |
| Cheaper model for pre-screening | 50-70% on first pass | Planned |
| Profile-change re-score flags (not auto) | Avoids unnecessary re-scores | Implemented |

### Benchmark Infrastructure Cost

| Item | Cost | Notes |
|------|------|-------|
| G-286 benchmark (120 calls) | ~$3.60 | One-time validation |
| Golden set regression (60+ jobs, single run) | ~$1.80 | Per regression run |
| Full benchmark re-run (new rubric version) | ~$3.60 | As needed |

---

## Detailed Research & Artifacts

Key artifacts from the scoring research and benchmarks:

| File | Content |
|------|---------|
| `docs/research/benchmark-results-summary.json` | G-286 benchmark raw results |
| `docs/how-scoring-works.md` | User-facing scoring explainer |
| `tests/golden_sets/` | Golden set fixtures across 3 domains |
| `src/career_os/scoring/` | Scoring engine implementation |
| `src/career_os/ai/` | Provider abstraction layer |

---

## Next Steps

1. **Reduce vague_responsibilities FP rate** — current 55% is too high; target <30% with threshold tuning
2. **Add cost tracking per score call** — users should see what scoring costs them in real-time
3. **Expand golden sets** — healthcare and legal domains when user demand surfaces
4. **Batch scoring** — score multiple jobs per prompt for 30-40% token savings
5. **Confidence indicator** — show users how personalized their scoring is (new vs. calibrated)
6. **Embedding pre-filter** — revisit when better threshold separation emerges (currently blocked by overlapping distributions)

This research is designed to evolve. As the benchmark infrastructure matures and more domains are validated, the recommendations here will be updated with fresh data.

---

*Research synthesized 2026-04-16 from G-286 benchmark data, G-268 scoring evolution (11 epics), G-279 preference learning design, G-272 embedding analysis, and G-297 red flag tuning. Philosophy: human-first, data-driven.*
