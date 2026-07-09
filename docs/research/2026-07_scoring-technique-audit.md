# Scoring Technique Audit — 2026-07

**Researched:** 2026-07-09 (7 parallel research agents)
**Status:** Research complete → itemized into tickets (see bottom)
**Scope:** Validate Kestrel's LLM job-fit scoring against 2025–2026 state of the art
**Builds on:** [`scoring-research.md`](./scoring-research.md) (2026-04 architecture) and [`../archive/2026-04-14_scoring-evolution.md`](../archive/2026-04-14_scoring-evolution.md) (G-268/272/273/276/279/286 evolution). Nothing here duplicates those — they cover *architecture*; this covers *judge mechanics* and *calibration*.

---

## Why this audit happened

The daily scan kept pushing **wrong-role jobs at prestigious companies to the top tier** — SWE / SRE / designer / partnerships roles at Mistral, Vercel, HuggingFace surfacing as "apply first" for a PM/TPM candidate. Initial hypothesis (a miscalibrated model) was **wrong**: the top-tier count was stable across model swaps, so the driver is model-independent. Two model-independent causes were confirmed:

1. **Tier logic** — `classify_tier` promoted any dream-company role to the top tier regardless of fit (`is_dream_tier OR score>=8`). *Fixed in G-1322 (Eyas PR #193): dream is now a fit multiplier, not a bypass.*
2. **The scoring prompt itself** — a wrong-role dream-company job still *scores* ~8/10, because company/domain prestige haloes the holistic fit number. **This audit targets cause #2.**

We hadn't revisited scoring technique since ~2026-04. Seven agents swept the 2025–2026 literature across: LLM-judge rubric/calibration, halo/prestige bias, resume-JD matching SOTA, anti-inflation/score-discrimination, eval + golden sets, structured-output prompts, and cost-efficient scoring at scale.

---

## The one-sentence diagnosis (all 7 agents converged)

**The bug is aggregation, not the model:** our `fit_score` behaves like an OR/max over dimensions, so a strong-but-irrelevant signal (company prestige + domain) *substitutes for* role fit instead of being *gated by* it. This is the textbook **halo effect / prominent-label bias** in LLM-as-a-judge ([Scoring Bias, arXiv 2506.22316](https://arxiv.org/html/2506.22316v1); [Justice or Prejudice?, arXiv 2410.02736](https://arxiv.org/html/2410.02736v1)). The fix is structural: **role fit must be a hard gate (min/multiplier); company prestige belongs on the desire axis, not the fit axis.**

---

## Convergent techniques, ranked by leverage-per-effort

### Tier 1 — the direct fix for the halo bug (do first)

**A. Role-fit hard gate with code-enforced cap.**
Add explicit gate fields to the scoring schema — `role_match.is_same_role_family` (bool + evidence) and `disqualifiers[]` (missing mandatory license/clearance/visa, hard location conflict, seniority >1 level off). If a gate fails, **cap `fit_score` in code after parsing** (`min(fit_score, 3)`), so the model cannot rationalize past it. This is the single highest-leverage change; DeCE reports decomposition+gating lifts expert-correlation from r=0.35 (holistic pointwise) to r=0.78. *Agents: LLM-judge, halo, structured-output, resume-JD. Effort M, fully unit-testable against golden sets.*
Sources: [DeCE 2509.16093](https://arxiv.org/html/2509.16093v1), [DeepEval DAG gates](https://deepeval.com/blog/llm-as-a-judge)

**B. Split role-fit from company-attractiveness; cap company_fit; move prestige to the desire axis.**
`company_fit` should score culture/values/size **only — not domain prestige**, and may adjust fit by **at most ±1** ("never rescues a role the candidate can't do"). Prestige/"I'd love to work there" is a *desire* signal, which our dual-axis model already has a home for. Tier the dimensions in the prompt: `technical_fit` + `seniority_alignment` = primary; `career_trajectory`/`compensation_fit`/`location_fit` = secondary; `company_fit` = minor/capped. *Agents: LLM-judge, halo, structured-output. Effort S (prompt wording).*

**C. Reason-before-score ordering + a required `against`/weakness field per dimension.**
JSON generates top-to-bottom, so a score emitted *before* its rationale is a cold guess the model then rationalizes upward (generosity bias). Reorder every object so evidence comes first and the number last; require each dimension to name ≥1 weakness grounded in the JD, and make the model enumerate **reasons-to-reject first**. Directly counteracts the "every good company is an 8" halo. *Agents: LLM-judge, halo, anti-inflation, structured-output. Effort S.*

**D. Negative reference anchor.**
Put a worked "strong company + wrong role → 2/10" exemplar in-context (balanced with a genuine high anchor, so we don't teach a positive prior). Teaches the anti-halo behavior by demonstration, not just instruction. *Agents: LLM-judge, halo, anti-inflation. Effort S.*

### Tier 2 — calibration & scale hygiene (high evidence, low cost)

**E. Judge on a 0–5 scale (display 0–10).**
A controlled 2026 study found 0–5 gives the best human–LLM alignment (ICC 0.853) and **0–10 was the *worst* scale tested** (0.805) — the extra granularity is fake precision the model fills with clustering. Score dimensions 0–5, aggregate up to the 0–10 the UI shows. *Agents: LLM-judge, anti-inflation. Effort S–M (re-anchor + re-baseline golden sets).*
Source: [Grading Scale Impact 2601.03444](https://arxiv.org/html/2601.03444v1)

**F. Spread as a first-class golden-set metric + pick the judge model by spread.**
We caught the flat-distribution problem by luck. Make it a standing gate: add std-dev, score-entropy, mode-share, and chosen-vs-rejected gap to the G-286 benchmark, and prefer broad-range scorers. Documented per-model tendencies (DeepSeek/Mistral cluster low, Qwen saturates high, GPT-OSS spreads) mean model choice is itself a calibration lever. *Agents: anti-inflation, eval. Effort S–M.*

**G. Post-hoc per-provider calibration (isotonic/Platt/Bayesian corrector).**
Fit a raw→calibrated map from golden-set labels so cheap-model scores are comparable across runs/models. Reuse the G-279 Bayesian preference infra. *Agents: anti-inflation, resume-JD, cost. Effort M.*

### Tier 3 — evaluation infrastructure (process fixes for the mistake we just made)

**H. Human-labeled golden set + Cohen's κ + NDCG regression eval on the PRODUCTION path.**
Our 18-job MAE benchmark misled us because it scored a *proxy path* (`tools/job_scorer`), not production, and used a model-derived reference instead of human labels. The fix: ~60–120 human-labeled pairs (label the *rank/quadrant*, not just a number), a `tests/eval/` suite (DeepEval — pytest-native, matches our stack) that calls the **real scoring entrypoint** and gates PRs on **weighted Cohen's κ ≥ 0.60** and **NDCG@5** deltas vs baseline. Fit scoring is a *ranking* problem, not a regression problem — stop optimizing MAE-to-a-reference-model. *Agent: eval. Effort M. Highest process leverage.*
Source: [Galileo judge calibration](https://galileo.ai/blog/calibrate-llm-judge-human-annotations)

**I. Shadow-mode for every scoring change.**
`SCORING_SHADOW_VARIANT` + a `shadow_scores` table: a candidate rubric/model scores real production jobs in parallel, logged not shown, compared against the golden set before promotion. Reuses the exact G-272 embedding-shadow pattern. Makes "measure on production, not a proxy" structurally unskippable. *Agent: eval. Effort M.*

**J. Nightly drift canary — PSI + golden re-score → Pushover.**
Guards against a silent OpenRouter model swap rotting scores with zero code change. Nightly: compute Population Stability Index of the score/quadrant distribution vs a rolling 30-day baseline (pure numpy) and re-score the frozen golden set; alert only on the **joint** condition (PSI>0.2 AND κ drop). *Agent: eval. Effort S–M.*

### Tier 4 — cost & architecture (bigger, sequence after Tier 1–2 land)

**K. Reframe the blocked embedding pre-filter (G-272) as a confidence-routed cascade.**
G-272 stalled because a single cosine threshold can't cleanly *reject* (overlapping distributions). The SOTA answer: embeddings were never meant to be a gate — use embedding similarity + lexical must-have overlap + ESCO skills-overlap as **routing features**. Clear-reject / clear-strong jobs skip the LLM; only the ambiguous middle gets the full rubric call. ConFit v2's "embed a hypothetical *ideal* resume" trick directly addresses the overlap problem. Generalizes the G-273 borderline 2-pass; cuts LLM volume ~40–60% at 3k jobs/day. *Agents: cost, resume-JD. Effort M.*
Sources: [ConFit v2 2502.12361](https://arxiv.org/pdf/2502.12361), [Escalation decision theory 2605.06350](https://arxiv.org/pdf/2605.06350)

**L. ESCO skills-overlap as a numeric feature + separate title→occupation axis.**
Upgrade the G-276 ESCO table from normalization to a quantitative skills-coverage score; normalize the JD title to an ESCO/ISCO occupation separately from content. Feeds the cascade router (K), grounds the LLM's skills/seniority dimensions, and gives free non-LLM explainability ("6/8 required skills matched; occupation = Data Engineer"). *Agents: resume-JD, halo. Effort M.*

**M. Distill accumulated LLM scores into a small local feature model.**
Logistic-regression-on-embeddings matches GPT-4-class classification from tens of examples (Bank of England 2025). We generate thousands of labeled scores daily + Bayesian corrections — a distillation dataset in waiting. Becomes the near-free cheap tier of the cascade. **Start logging `(embedding, structured signals, LLM score, user correction)` now — every unlogged day is training data lost.** *Agents: cost, resume-JD. Effort L to build / S to start logging.*
Source: [LR makes small LLMs strong classifiers 2408.03414](https://arxiv.org/pdf/2408.03414)

**N. Relative/percentile batch scoring.**
Absolute pointwise calibration is the root cause of drift; relative ranking sidesteps it (absolute scores are far more stable when *derived from* relative tiers). We already emit percentiles (G-271) and batch-score 10/prompt — have the model tier a batch relative to itself. *Agent: anti-inflation. Effort M.*

---

## Explicitly deferred (avoid over-engineering at ~$0.81/mo)

- **Pairwise / Bradley-Terry** full pipeline — only if absolute labels prove too noisy; the simple pairwise CLI first.
- **Probability-weighted (logprob) continuous scoring** — provider-conditional (not clean on Anthropic), revisit if on the OpenAI/OpenRouter path.
- **Learned router** (skip-cheap-tier) — our own data says premium rarely beats cheap here, so there's little for a router to optimize.
- **Embedding/semantic drift, heavyweight eval platforms** (Braintrust/LangSmith) — until we actually need dashboards.

---

## Itemized audit → tickets

The 14 findings (A–N) bundle into 4 coherent tickets under the CareerOS Open Source project:

| Ticket | Findings | Title | Priority |
|--------|----------|-------|----------|
| **G-1335** | A, B, C, D | Fix scoring halo — role-fit hard gate + company-prestige cap + reason-before-score + negative anchor | **P1 (High)** |
| **G-1336** | H, I, J | Scoring eval infra — human golden set + κ/NDCG on the production path + shadow-mode + drift canary | P2 (High) |
| **G-1337** | E, F, G | Scoring calibration hygiene — 0–5 judge scale + spread metrics + per-provider calibration | P2–P3 |
| **G-1338** | K, L, M, N | Scoring cost/architecture — confidence-routed cascade (unblock G-272) + ESCO feature + distillation logging + relative scoring | P3 |

Already shipped this sweep: **G-1322** (Eyas PR #193) — the `classify_tier` dream-fit gate (tier-logic half of the T1 fix).

**Recommended sequence:** G-1335 (the halo fix — validated by unit tests + shadow-mode, **not** a full paid re-run) → G-1336 (make quality measurable and changes safe) → G-1337 → G-1338. The distillation-logging step inside G-1338 is cheap and should start immediately so the dataset accumulates while the rest is scheduled.

### Findings-to-ticket map (A–N)

- **G-1335:** A role-fit hard gate w/ code cap · B cap `company_fit` + tier dimensions + prestige→desire · C reason-before-score + `against` field · D negative reference anchor
- **G-1336:** H human golden set + κ/NDCG eval on prod path · I shadow-mode · J nightly drift canary
- **G-1337:** E 0–5 judge scale · F spread metrics + judge-by-spread · G post-hoc per-provider calibration
- **G-1338:** K embedding→confidence-routed cascade · L ESCO skills-overlap + title axis · M distillation-label logging · N relative/percentile batch scoring

**Cross-cutting rules baked into all of the above:**
1. Eval must call the **production scoring function**, never a reimplementation (the lesson from the proxy-path miss).
2. Treat any stronger-LLM reference judge as a **validated-then-trusted noisy label** — different model family than the scorer, order-randomized, κ-checked against human labels — never as ground truth.
