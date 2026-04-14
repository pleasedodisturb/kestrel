# Kestrel Scoring Evolution — Epic Breakdown

> Created: 2026-04-14
> Research basis: 3 parallel research agents (competitor, academic, engineering) + codebase analysis
> Research doc: `private/research-scoring-deep-dive-2026-04-14.md`
>
> **Design principle:** Each epic is self-sufficient. An agent receives one epic and has full
> creative and technical freedom to implement A-to-Z. Epics include enough context that the
> agent never needs to ask "why" — it can focus on "how."

---

## Roadmap Overview

```
Phase 1 — Scoring Quality (epics 1-3, parallel)
  ├── Epic 1: Scoring Rubric & Calibration     ←── highest ROI, do first
  ├── Epic 2: Ghost Job Detection               ←── parallel with 1
  └── Epic 3: Score Context & Percentiles       ←── parallel with 1, 2

Phase 2 — Cost & Efficiency (epics 4-5, sequential)
  ├── Epic 4: Embedding Pre-Filter Layer        ←── foundation for cost savings
  └── Epic 5: Borderline 2-Pass Scoring         ←── depends on rubric (Epic 1)

Phase 3 — User Intelligence (epics 6-7, parallel)
  ├── Epic 6: User Feedback Loop                ←── parallel
  └── Epic 7: Dual-Score Architecture           ←── parallel, independent design

Phase 4 — Data Enrichment (epics 8-9, parallel)
  ├── Epic 8: Skill Normalization (ESCO/O*NET)  ←── parallel
  └── Epic 9: WARN Act Layoff Integration       ←── parallel

Phase 5 — Advanced Intelligence (epics 10-11, sequential after Phase 3)
  ├── Epic 10: Uncertainty Ranges for Sparse Profiles
  └── Epic 11: Bayesian Preference Learning
```

### Dependency Graph

```
Epic 1 (Rubric) ─────────────────┐
Epic 2 (Ghost Jobs) ──────────── │ ── no deps, all parallel
Epic 3 (Percentiles) ─────────── │
                                  │
Epic 4 (Embeddings) ──────────── ┤ ← after Phase 1 ships (needs stable scoring to measure)
Epic 5 (2-Pass) ──────────────── ┤ ← depends on Epic 1 (rubric must exist to measure variance)
                                  │
Epic 6 (Feedback) ────────────── ┤ ← after Phase 2 (needs stable scoring to collect feedback on)
Epic 7 (Dual-Score) ──────────── ┤ ← independent design, but benefits from Epic 1 patterns
                                  │
Epic 8 (ESCO) ────────────────── ┤ ← independent, any time after Phase 1
Epic 9 (WARN) ────────────────── ┤ ← independent, any time
                                  │
Epic 10 (Uncertainty) ─────────── ┤ ← after Epic 7 (extends the scoring model)
Epic 11 (Bayesian) ───────────── ┘ ← after Epic 6 (needs feedback data)
```

---

## Epic 1: Scoring Rubric & Few-Shot Calibration

### Why This Matters

The current `_build_scoring_prompt()` at `src/career_os/services/scoring.py:520-551` sends a bare
"Score this job against the candidate profile" instruction. The AI provider (Anthropic) in
`src/career_os/ai/anthropic_provider.py:122-146` includes output format instructions but no
calibration guidance — no rubric, no examples, no anchoring.

Academic research (LLM-Rubric, ACL 2024; G-Eval, EMNLP 2023) shows that adding an explicit rubric
with 2-3 calibration examples per score level yields +25-30% improvement in scoring consistency
(inter-rater agreement with human judges). This is the single highest-ROI change possible.

Temperature=0 still produces 0.5-1.0 point variance on a 10-point scale due to GPU non-determinism.
A rubric anchors the model's understanding of what each score level means, reducing semantic drift
even when numeric output varies slightly.

### Research Context

- **LLM-Rubric (ACL 2024):** https://aclanthology.org/2024.acl-long.745.pdf — rubric + few-shot
  achieves highest inter-rater agreement with human judges
- **G-Eval (EMNLP 2023):** Explicit scoring rubric → LLM generates CoT evaluation steps
- **Autorubric (2026):** https://arxiv.org/html/2603.00077v1 — 2-3 examples per score level is
  the sweet spot, +25-30% accuracy improvement over zero-shot
- **STED framework (2025):** Claude Sonnet maintains near-perfect structural consistency with JSON
  schema even at temperature 0.9 — structured output is not the bottleneck, semantic calibration is
- **LinkedIn JUDE system:** Uses change detection to skip re-inference when content hasn't changed
  (cost optimization that depends on stable, calibrated scoring)

### What to Build

1. **A `SCORING_RUBRIC` constant** in `src/career_os/services/scoring.py` containing:
   - Clear band definitions (what 9-10 means vs 7-8 vs 5-6 vs 3-4 vs 1-2)
   - 3 calibration examples (one at score ~2, one at ~5, one at ~8)
   - Each example: abbreviated JD snippet + abbreviated profile + expected score + 2-sentence reasoning
   - Examples should be generic enough to work across job families but specific enough to anchor

2. **Job-family-aware rubric modifiers** — the rubric should note how weights shift meaning:
   - For SWE (skills_match=0.35): "technical skill gaps are more penalizing"
   - For DevRel (culture_fit=0.25): "community experience and public speaking weight heavily"
   - These modifiers are generated dynamically from the `JOB_FAMILY_WEIGHTS` dict

3. **Integrate rubric into `_build_scoring_prompt()`** — append after the profile section, before
   the weights JSON. The rubric should be concise (~400-600 tokens) to avoid inflating costs.

4. **Integrate rubric into `AnthropicProvider.score()`** — the Anthropic provider at line 122
   builds its own prompt. The rubric should be part of the system message or prepended to the
   user message, so it applies regardless of which provider is used.

### Implementation Guidelines

- The rubric lives in the service layer (`scoring.py`), not in the provider layer. Providers
  receive the complete prompt — they shouldn't need to know about rubrics.
- Calibration examples should be synthetic (not from real users). Create 3 archetypes:
  - **Score 2 example:** "Senior .NET Developer" JD vs TPM profile with Python/AI focus.
    Mismatch on skills, domain, and role type. Score: 2.0.
  - **Score 5 example:** "Product Manager, Growth" JD vs TPM profile with some PM overlap.
    Partial skill match, wrong domain but transferable. Score: 5.5.
  - **Score 8 example:** "Technical Program Manager, AI Platform" JD vs TPM profile with
    strong AI and platform experience. Score: 8.5.
- Keep examples to ~100 words each (JD snippet + profile snippet + score + reasoning)
- Add a `RUBRIC_VERSION` string (e.g., "v1.0") stored in the `weights_snapshot` JSON so we can
  track which rubric version produced each score

### A/B Testing Plan

**Before implementing:** Score a "golden set" of 15-20 jobs against the current prompt. Record:
- fit_score, dimensional_scores, reasoning for each
- Run each job 3 times to measure current variance (std dev)

**After implementing:** Re-score the same golden set with the rubric prompt. Compare:
- Mean absolute difference in fit_scores
- Variance reduction (std dev of 3 runs per job)
- Qualitative: does the reasoning reference the rubric's score bands?
- Edge case: does the rubric overconstrain? (all scores clustering to example values?)

**Success criteria:** Variance (std dev across 3 runs) drops by ≥30%. No score clustering
(all 6 dimensional scores should NOT converge to the same value).

**Golden set construction:** Pick jobs spanning the full range — 4 obvious rejects (score 1-3),
6 mediocre (4-6), 6 strong (7-8), 4 dream (9-10). Use real JDs from past discovery runs stored
in `discovered_jobs` table. Save the golden set as a JSON fixture in `tests/fixtures/`.

### Definition of Done

- [ ] `SCORING_RUBRIC` constant with band definitions and 3 calibration examples
- [ ] `RUBRIC_VERSION` tracked in `weights_snapshot`
- [ ] `_build_scoring_prompt()` includes rubric section
- [ ] Job-family-aware modifiers generated from `JOB_FAMILY_WEIGHTS`
- [ ] Golden set fixture created (`tests/fixtures/scoring_golden_set.json`)
- [ ] Baseline scores recorded (pre-rubric, 3 runs per job)
- [ ] Post-rubric scores recorded and compared
- [ ] Variance reduction ≥30% demonstrated
- [ ] Unit tests: rubric appears in prompt, version tracked, modifiers correct per family
- [ ] Integration test: full scoring pipeline with rubric produces valid `ScoreResult`
- [ ] No increase in prompt token count beyond 600 tokens
- [ ] Existing tests in `tests/test_job_scorer.py` still pass

### Tests to Write

```python
# tests/test_scoring_rubric.py

def test_rubric_included_in_prompt():
    """Verify _build_scoring_prompt includes SCORING_RUBRIC text."""

def test_rubric_version_in_weights_snapshot():
    """Verify rubric_version appears in the weights_snapshot JSON."""

def test_job_family_modifiers_generated():
    """For each family in JOB_FAMILY_WEIGHTS, verify a modifier string is produced."""

def test_rubric_token_count_budget():
    """Rubric section should be <600 tokens (rough word count proxy: <450 words)."""

def test_calibration_examples_cover_score_range():
    """Examples should have scores in bands [1-3], [4-6], [7-9]."""

async def test_scoring_with_rubric_produces_valid_result():
    """End-to-end: score_job with rubric returns a valid ScoreResult."""
```

### Files Touched

- `src/career_os/services/scoring.py` — add `SCORING_RUBRIC`, `RUBRIC_VERSION`, modify
  `_build_scoring_prompt()`, modify `score_job()` to include version in snapshot
- `tests/test_scoring_rubric.py` — new test file
- `tests/fixtures/scoring_golden_set.json` — new fixture

---

## Epic 2: Ghost Job Detection

### Why This Matters

27% of job postings are ghost jobs (Resume Builder 2024 survey) — positions that are posted but
the company isn't actively hiring for them. Common reasons: talent pipeline building, making
existing employees feel replaceable, compliance requirements.

Kestrel already has the data to detect this: `discovered_jobs` stores historical discovery runs.
If the same company+title pair appears repeatedly across runs, that's a strong ghost job signal.
No API calls needed — this is pure rule-based detection using existing data.

The current `red_flags.py` has 7 rules (stale posting, unrealistic requirements, turnover language,
missing salary, staffing agency, vague responsibilities, excessive requirements). Ghost job
detection would be rule #8, fitting cleanly into the existing architecture.

### Research Context

- **Resume Builder 2024 survey:** 27% of postings are ghost jobs
- **Ghost job signals from research:**
  1. Same role reposted monthly (track `title + company` pairs across discovery runs)
  2. Identical JD text across 5+ cities simultaneously
  3. Company has active WARN notices but dozens of open roles
  4. Posting age > 60 days (already detected by `_detect_stale_posting`)
  5. Automated rejection within minutes of application (would need application tracking data)

### What to Build

1. **New rule: `_detect_ghost_job_signals()`** in `src/career_os/services/red_flags.py`
   - Accepts: `db: Session`, `company: str`, `title: str`, `description: str`, `profile_id: int`
   - Queries `discovered_jobs` for same company+title combinations in the last 90 days
   - If ≥3 occurrences of same company+title: severity "caution"
   - If ≥5 occurrences: severity "warning"
   - Optional: fuzzy title matching (strip "Senior"/"Lead"/"Jr" prefixes, normalize whitespace)

2. **Companion rule: `_detect_multi_city_blast()`**
   - Same company + same description text (or >90% similarity) across 3+ different locations
   - This indicates a "spray and pray" posting pattern
   - Severity: "info" (it's not necessarily bad, but worth noting)

3. **Integration into `detect_red_flags()`**
   - The current `detect_red_flags()` function at line 108 of `red_flags.py` is stateless —
    it doesn't take a `db` session. The new ghost job rules need DB access.
   - **Design decision for the agent:** Either (a) add an optional `db` parameter to
    `detect_red_flags()`, or (b) create a separate `detect_data_driven_red_flags(db, ...)` function
    that the caller in `scoring.py` invokes alongside the existing one. Option (b) is cleaner —
    it keeps the original function stateless and testable without DB fixtures.

4. **Reposting tracker** — a lightweight query helper:
   ```python
   def _count_company_title_occurrences(
       db: Session, company: str, title: str, profile_id: int, days: int = 90
   ) -> int
   ```

### Implementation Guidelines

- Title normalization is important: "Senior Software Engineer" and "Sr. Software Engineer" and
  "Software Engineer (Senior)" should match. Use a normalize function that strips common
  prefixes/suffixes and lowercases.
- Company name normalization too: "Google" vs "Google LLC" vs "Alphabet Inc."
  Use a simple approach: lowercase, strip "inc", "llc", "ltd", "gmbh", "ag", etc.
- For description similarity (multi-city blast): use a simple approach like comparing first
  200 characters after stripping whitespace. No need for embeddings here.
- The rules should be fast — they run on every score_job call. Use indexed queries.

### A/B Testing Plan

**Validation approach:** Query the existing `discovered_jobs` table for company+title pairs that
appear 3+ times. Manually review 10-15 of these to confirm they look like ghost jobs (same JD
text, long-running, no evidence of active hiring).

**False positive check:** Also query company+title pairs that appear exactly once and verify they
don't trigger the rule.

**Success criteria:** ≥70% of flagged postings (3+ occurrences) are confirmed ghost/stale when
manually reviewed. ≤5% false positive rate on single-occurrence postings.

### Definition of Done

- [ ] `_detect_ghost_job_signals()` rule added to `red_flags.py`
- [ ] `_detect_multi_city_blast()` rule added to `red_flags.py`
- [ ] Title and company name normalization helpers
- [ ] `detect_data_driven_red_flags(db, ...)` function (or integrated into existing)
- [ ] Called from `score_job()` in `scoring.py` alongside existing `detect_red_flags()`
- [ ] Combined red flags merged into single `red_flags_json` on `ScoredJob`
- [ ] Unit tests for normalization, occurrence counting, threshold logic
- [ ] Integration test: scoring a job that appears 3+ times triggers ghost flag
- [ ] No performance regression on batch scoring (queries must be indexed)
- [ ] Existing `tests/test_red_flags.py` still pass

### Tests to Write

```python
# tests/test_ghost_jobs.py

def test_normalize_company_name():
    """Google LLC → google, Alphabet Inc. → alphabet"""

def test_normalize_job_title():
    """Senior Software Engineer → software engineer"""

def test_ghost_detection_below_threshold():
    """2 occurrences in 90 days → no flag"""

def test_ghost_detection_caution_threshold():
    """3 occurrences in 90 days → caution"""

def test_ghost_detection_warning_threshold():
    """5 occurrences in 90 days → warning"""

def test_ghost_detection_outside_window():
    """5 occurrences but all >90 days ago → no flag"""

def test_multi_city_blast_detection():
    """Same company, similar description, 3+ locations → info flag"""

def test_multi_city_blast_different_descriptions():
    """Same company, different descriptions, 3+ locations → no flag"""

def test_ghost_flags_appear_in_scored_job():
    """Integration: score_job merges ghost flags with rule-based flags."""
```

### Files Touched

- `src/career_os/services/red_flags.py` — new rules, normalization helpers
- `src/career_os/services/scoring.py` — call new detection in `score_job()`
- `tests/test_ghost_jobs.py` — new test file

---

## Epic 3: Score Context & Percentiles

### Why This Matters

A score of 7.2 means nothing in isolation. Is that good? For this user's typical results, is that
above or below average? Research on score trust (Torre.ai's model, JobScan's approach) shows that
users trust scores more when they have comparison context.

This is a low-effort enhancement that makes the existing scoring output significantly more
useful. No AI calls, no new infrastructure — just a query on existing `scored_jobs` data.

### Research Context

- **Torre.ai:** Shows where candidates rank across dozens of factors per application — full
  transparency builds trust
- **JobScan:** 0-100% with explicit "recommended threshold: 75%+" — gives users an anchor
- **Score explanation research (arxiv.org/abs/2409.00079):** Context and comparison data
  significantly improve user trust in AI-generated scores

### What to Build

1. **Percentile calculation** in `src/career_os/services/scoring.py`:
   ```python
   def compute_score_context(db: Session, profile_id: int, fit_score: float) -> dict:
       """Return context for a score relative to the user's history."""
       # Returns: {
       #     "percentile": 82,          # this score is higher than 82% of scored jobs
       #     "rank": 3,                 # 3rd highest score
       #     "total_scored": 47,        # out of 47 total scored jobs
       #     "avg_score": 5.3,          # average across all scored jobs
       #     "score_band_count": 8,     # 8 jobs scored in the same letter grade band
       # }
   ```

2. **Add `score_context` to `ScoreResponse`** schema in `src/career_os/schemas/scoring.py`:
   - New optional field: `score_context: ScoreContextResponse | None`
   - Populated when the response is returned from the API

3. **Populate on read, not write** — score context is dynamic (changes as more jobs are scored).
   Don't store it in the DB. Compute it when building the API response in `src/career_os/api/scoring.py`.

### Implementation Guidelines

- Percentile = `(count of scores below this score) / total_scored * 100`, rounded to int
- Only count non-stale scores for the same profile
- If total_scored < 5, return `score_context: null` (not enough data for meaningful context)
- Keep the query efficient: `SELECT COUNT(*) FROM scored_jobs WHERE profile_id=? AND fit_score < ? AND is_stale = false`
- This should be optional and not slow down the scoring response. If the extra query adds
  measurable latency, make it lazy (only compute when API explicitly requests it via query param).

### A/B Testing Plan

Not applicable — this is purely additive UI data. No scoring behavior changes.

**Validation:** After implementation, manually verify percentile math against a known set:
- Score 5 jobs at [2.0, 4.0, 6.0, 8.0, 9.0]
- Verify that 6.0 returns percentile=40, rank=3, total_scored=5

### Definition of Done

- [ ] `compute_score_context()` function in `scoring.py`
- [ ] `ScoreContextResponse` Pydantic model in `schemas/scoring.py`
- [ ] `score_context` field added to `ScoreResponse`
- [ ] API populates context on GET responses (not stored in DB)
- [ ] Returns null when fewer than 5 scores exist
- [ ] Unit tests for percentile calculation, edge cases (ties, single score, all same score)
- [ ] Frontend types updated (TypeScript `ScoreContext` interface)

### Tests to Write

```python
# tests/test_score_context.py

def test_percentile_calculation():
    """Verify percentile math with known score distribution."""

def test_rank_calculation():
    """3rd highest of 10 scores → rank=3."""

def test_context_null_below_threshold():
    """With <5 scored jobs, score_context is None."""

def test_stale_scores_excluded():
    """Stale scores don't count toward percentile."""

def test_ties_handled():
    """Multiple scores at the same value → correct percentile."""

def test_single_score():
    """With exactly 1 score, context is None (below threshold)."""
```

### Files Touched

- `src/career_os/services/scoring.py` — `compute_score_context()`
- `src/career_os/schemas/scoring.py` — `ScoreContextResponse`, update `ScoreResponse`
- `src/career_os/api/scoring.py` — populate context on GET
- `frontend/src/api/types.ts` — `ScoreContext` interface
- `tests/test_score_context.py` — new test file

---

## Epic 4: Embedding Pre-Filter Layer

### Why This Matters

Currently, `batch_score_discovery()` at `scoring.py:603` sends every unscored discovered job
through the full LLM scoring pipeline (~$0.01/job via Sonnet-class). For a batch of 100 jobs,
that's $1.00 and ~10 minutes of sequential API calls.

Research shows that embedding cosine similarity can filter out 70-80% of obviously irrelevant
jobs at ~$0.0001/job (or free with local Ollama models). This reduces batch cost to ~$0.13
(86% savings) and batch time by ~75%.

The architecture follows the consensus from LinkedIn (JUDE), NVIDIA reranking research, and
Eugene Yan's RecSys+LLM patterns: cheap embedding filter → expensive LLM scorer.

### Research Context

- **ConFit v2 (ACL 2025):** Domain-adapted E5-base outperforms OpenAI text-embedding-3-large on
  resume/JD matching by +17.1% recall, +20.4% nDCG
- **NVIDIA reranking blog:** Sending only top 20 of 75 candidates to expensive model achieves
  95% of full-model accuracy with 72% cost reduction
- **LlamaIndex reranking guide:** Two-stage pattern extensively documented
- **nomic-embed-text-v1.5:** Competitive with OpenAI ada-002, runs locally on Ollama (15-50ms)
- **sqlite-vec:** SQLite extension for vector similarity search, zero additional infrastructure,
  perfect for Kestrel's single-user SQLite architecture
- **Cosine similarity thresholds:** 0.65-0.70 for generous pre-filter (recall-focused),
  0.78 for "minimally relevant", 0.85+ for "strong match"
- **ConFit v2's HyRe technique:** Generate "hypothetical ideal resume" from JD, embed that
  instead of raw JD text → bridges vocabulary gap

### What to Build

1. **Embedding infrastructure:**
   - Add `sqlite-vec` extension to SQLite initialization in `src/career_os/database.py`
   - New table: `embeddings` (id, entity_type, entity_id, model_name, embedding BLOB, created_at)
   - Entity types: "profile", "discovered_job"

2. **Embedding provider interface** in `src/career_os/ai/base.py`:
   ```python
   async def embed(self, text: str, **kwargs) -> list[float]:
       """Generate an embedding vector for the given text."""
   ```
   Implement in OllamaProvider (nomic-embed-text) and AnthropicProvider (via Voyage AI or skip).

3. **Profile embedding builder** in `src/career_os/services/embeddings.py`:
   - Concatenate skills + goals + job family into a structured text
   - Generate and cache the embedding
   - Invalidate when profile changes (hook into profile update service)

4. **Job embedding on discovery** — when a job is discovered, generate its embedding immediately
   (or lazily on first batch score). Store in `embeddings` table.

5. **Pre-filter in `batch_score_discovery()`:**
   - Before the scoring loop at line 638, compute cosine similarity between profile embedding
     and each job embedding
   - Filter out jobs below threshold (configurable, default 0.65)
   - Only send remaining jobs to full LLM scoring
   - Log: "Pre-filtered {X} of {Y} jobs (threshold {Z}), sending {Y-X} to full scoring"

6. **Similarity score stored on DiscoveredJob** — add `embedding_similarity: float | None` column.
   Useful for debugging and for the frontend to show "initial match confidence."

### Implementation Guidelines

- **Start with Ollama locally** — nomic-embed-text is the default. If Ollama is not available,
  fall back to no pre-filtering (graceful degradation, not a hard dependency).
- **Embedding dimension:** nomic-embed-text = 768-dim. Store as BLOB via sqlite-vec.
- **Profile text construction:**
  ```
  Job Family: Technical Program Manager
  Skills: Python (expert), React (intermediate), Kubernetes (beginner), ...
  Goals: AI-native company, senior IC track, remote-first
  Location: Frankfurt, Germany (open to EU remote)
  ```
- **JD text:** Use the full `description` from DiscoveredJob. If >8K tokens, truncate to first
  8K (nomic-embed-text context limit).
- **Threshold tuning:** Start conservative (0.60) and log all similarity scores. After 100+ jobs
  scored both ways (with and without filter), analyze: what's the lowest similarity score that
  still got a fit_score ≥ 5.0 from the LLM? Set threshold just below that.
- **Migration:** Alembic migration to add `embeddings` table and `embedding_similarity` column.

### A/B Testing Plan

**Shadow mode first:** For the first 2 weeks, compute embeddings and similarities but don't
filter. Log similarity alongside LLM scores. After accumulating data:

1. Plot similarity vs fit_score scatter plot
2. Identify natural threshold (similarity below which fit_score is always < 4.0)
3. Compute theoretical savings: "Would have filtered X% of jobs, would have missed Y good ones"
4. Only enable filtering when false-negative rate < 2% at chosen threshold

**Success criteria:**
- 70%+ of jobs filtered at threshold 0.65
- < 2% of filtered jobs would have scored ≥ 6.0 on full LLM scoring
- Batch scoring time reduced by ≥ 60%
- Embedding generation adds < 2 seconds per job on local Ollama

### Definition of Done

- [ ] `sqlite-vec` integrated into database initialization
- [ ] `embeddings` table with Alembic migration
- [ ] `embed()` method on AI provider base class
- [ ] `OllamaProvider.embed()` using nomic-embed-text
- [ ] `src/career_os/services/embeddings.py` — profile and job embedding management
- [ ] `embedding_similarity` column on `discovered_jobs` table
- [ ] Pre-filter logic in `batch_score_discovery()` with configurable threshold
- [ ] Graceful degradation when Ollama unavailable (skip pre-filter, full scoring)
- [ ] Shadow mode logging (similarity computed but not filtered)
- [ ] Config flag to enable/disable filtering: `EMBEDDING_PREFILTER_ENABLED` env var
- [ ] Config for threshold: `EMBEDDING_PREFILTER_THRESHOLD` env var (default 0.65)
- [ ] Unit tests for embedding storage, retrieval, cosine similarity
- [ ] Integration test: batch scoring with pre-filter enabled
- [ ] Performance test: embedding 100 JDs in < 30 seconds on Ollama
- [ ] Documentation: how to set up Ollama with nomic-embed-text

### Tests to Write

```python
# tests/test_embeddings.py

def test_profile_embedding_generated():
    """Profile embedding is created and stored after profile update."""

def test_job_embedding_generated():
    """Job embedding is created when a discovered job is scored."""

def test_cosine_similarity_calculation():
    """Known vectors produce expected cosine similarity."""

def test_prefilter_removes_low_similarity():
    """Jobs below threshold are excluded from scoring batch."""

def test_prefilter_keeps_high_similarity():
    """Jobs above threshold proceed to full scoring."""

def test_graceful_degradation_no_ollama():
    """When Ollama is unavailable, pre-filter is skipped, all jobs scored."""

def test_shadow_mode_logs_without_filtering():
    """In shadow mode, similarities are computed and logged but nothing filtered."""

def test_embedding_invalidation_on_profile_change():
    """Profile embedding is regenerated when skills/goals change."""
```

### Files Touched

- `src/career_os/database.py` — sqlite-vec initialization
- `src/career_os/models/embeddings.py` — new ORM model
- `src/career_os/services/embeddings.py` — new service
- `src/career_os/ai/base.py` — `embed()` method
- `src/career_os/ai/ollama_provider.py` — `embed()` implementation
- `src/career_os/services/scoring.py` — pre-filter in `batch_score_discovery()`
- `src/career_os/models/discovery.py` — `embedding_similarity` column
- `alembic/versions/xxx_add_embeddings.py` — migration
- `src/career_os/config.py` — new env vars
- `tests/test_embeddings.py` — new test file
- `pyproject.toml` — add `sqlite-vec` dependency

---

## Epic 5: Borderline 2-Pass Scoring

### Why This Matters

The biggest scoring consistency problem is in the borderline zone (fit_score 4.0-6.5). This is
where a score of 5.0 vs 5.8 can mean the difference between "skip" and "apply." Research
(LLM-as-Judge on a Budget, 2026) shows that adaptive 2-pass scoring reduces variance by ~50%
in the borderline zone at only 1.3x cost (vs 3x for uniform 3-pass).

This epic depends on Epic 1 (rubric) being done — without a rubric, the variance is too high
to meaningfully measure improvement.

### Research Context

- **LLM-as-Judge on a Budget (2026):** https://arxiv.org/html/2602.15481v1 — adaptive allocation
  achieves same error reduction as uniform 3-pass with ~50% of the budget
- **Temperature=0 variance:** 0.5-1.0 points on a 10-point scale. Borderline scores (4.0-6.5)
  are most sensitive — a user might apply to a 5.8 but skip a 5.0.

### What to Build

1. **Borderline detection** after initial scoring in `score_job()`:
   ```python
   BORDERLINE_LOW = 4.0
   BORDERLINE_HIGH = 6.5
   
   if BORDERLINE_LOW <= score_data.fit_score <= BORDERLINE_HIGH:
       # Run second scoring pass
       response2 = await provider.score(...)
       score_data = _average_score_results(score_data, score_data2)
   ```

2. **Score averaging function** `_average_score_results(a: ScoreResult, b: ScoreResult) -> ScoreResult`:
   - Average numeric fields: fit_score, readiness_score, career_alignment, dimensional_scores
   - Keep the reasoning from the result with the higher fit_score (richer reasoning)
   - Merge score_breakdown factors (deduplicate by factor name, average contributions)
   - Keep ATS keywords from the result with more keywords

3. **Pass tracking** — add `scoring_passes: int` to `ScoredJob` model (default 1). When
   2-pass is triggered, set to 2. Useful for analytics and cost tracking.

4. **Configurable thresholds** via env vars:
   - `BORDERLINE_SCORING_ENABLED` (default true)
   - `BORDERLINE_LOW_THRESHOLD` (default 4.0)
   - `BORDERLINE_HIGH_THRESHOLD` (default 6.5)

### Implementation Guidelines

- The second pass uses the exact same prompt (with rubric from Epic 1). The variance comes from
  the model, not the prompt — we want to average out the noise.
- Don't retry if the second pass fails — use the single score and log a warning.
- In batch scoring, this will slow down borderline jobs by ~2x. Log which jobs triggered 2-pass
  so the user can see the cost impact.
- Consider: should the second pass use a slightly different temperature? Research suggests
  temperature=0 for both passes is fine — the variance comes from infrastructure, not sampling.

### A/B Testing Plan

**Pre-implementation baseline:** Using the golden set from Epic 1, identify jobs that scored in the
4.0-6.5 range. Run each 5 times and record the variance (std dev).

**Post-implementation:** Run the same jobs with 2-pass enabled. Compare:
- Std dev of the averaged scores vs single-pass scores
- Does the average score track closer to human judgment?

**Success criteria:** Std dev in borderline zone reduced by ≥40%.

### Definition of Done

- [ ] Borderline detection in `score_job()` with configurable thresholds
- [ ] `_average_score_results()` function with proper numeric averaging
- [ ] `scoring_passes` column on `ScoredJob` model with Alembic migration
- [ ] Env var configuration for enable/disable and thresholds
- [ ] Graceful handling if second pass fails (fallback to single score)
- [ ] Logging: "Borderline score {X}, running second pass" and "Averaged: {Y}"
- [ ] Unit tests for averaging function (numeric precision, edge cases)
- [ ] Integration test: scoring a borderline job triggers 2 AI calls
- [ ] Cost analysis: what % of real jobs fall in 4.0-6.5?
- [ ] Existing tests still pass

### Tests to Write

```python
# tests/test_borderline_scoring.py

def test_borderline_triggers_second_pass():
    """Score in [4.0, 6.5] triggers a second scoring call."""

def test_non_borderline_single_pass():
    """Score outside [4.0, 6.5] → only 1 scoring call."""

def test_average_score_results_numeric():
    """Averaging two ScoreResults produces correct numeric means."""

def test_average_preserves_better_reasoning():
    """The result with higher fit_score contributes the reasoning."""

def test_second_pass_failure_fallback():
    """If second pass raises, original score is used."""

def test_scoring_passes_tracked():
    """ScoredJob.scoring_passes is 2 when borderline, 1 otherwise."""

def test_borderline_disabled_via_config():
    """When BORDERLINE_SCORING_ENABLED=false, always single pass."""
```

### Files Touched

- `src/career_os/services/scoring.py` — borderline detection, averaging, config
- `src/career_os/models/scoring.py` — `scoring_passes` column
- `src/career_os/config.py` — new env vars
- `alembic/versions/xxx_add_scoring_passes.py` — migration
- `tests/test_borderline_scoring.py` — new test file

---

## Epic 6: User Feedback Loop

### Why This Matters

Every scoring system improves with feedback. Currently, Kestrel scores are fire-and-forget — the
user sees the score but has no way to say "this is wrong." Without feedback, the system can't
learn and the user can't trust it.

Torre.ai and JobScan both allow user corrections. The BAL-PM paper (NeurIPS 2024) shows that
even 10-20 feedback signals can meaningfully calibrate a scoring system via Bayesian updating.

This epic creates the infrastructure for collecting feedback. Epic 11 (Bayesian Learning) later
uses this data to actually adjust scoring behavior.

### Research Context

- **BAL-PM (NeurIPS 2024):** Bayesian Active Learner for Preference Modeling — reduces required
  feedback by 33-68% vs random sampling
- **Torre.ai:** Full transparency + user can see and contest rankings
- **BISTRO (KDD 2024):** Session-based preference drift detection — users' preferences change
  over time, the system must adapt
- **Practical recommendation from engineering research:** Track implicit signals (view, apply,
  dismiss) alongside explicit corrections ("too high" / "too low")

### What to Build

1. **New model: `ScoringFeedback`** in `src/career_os/models/scoring.py`:
   ```python
   class ScoringFeedback(Base):
       __tablename__ = "scoring_feedback"
       id: int (PK)
       scored_job_id: int (FK → scored_jobs.id)
       profile_id: int (FK → profiles.id)
       direction: str  # "too_high", "too_low", "correct"
       user_score: float | None  # optional: what the user thinks the score should be
       reason: str | None  # optional: free-text explanation
       original_fit_score: float  # snapshot of what the AI gave
       created_at: datetime
   ```

2. **New API endpoints** in `src/career_os/api/scoring.py`:
   - `POST /api/score/{scored_job_id}/feedback` — submit feedback
   - `GET /api/score/feedback?profile_id={id}` — list all feedback for a profile
   - `GET /api/score/feedback/stats?profile_id={id}` — summary stats (count, avg deviation, etc.)

3. **Implicit feedback signals** — extend existing models:
   - When a discovered job is promoted to an application: record as positive signal
   - When a discovered job is dismissed/hidden: record as negative signal
   - When an application progresses to "interview": strong positive signal
   - These are stored as `ScoringFeedback` records with `direction` values like
     "implicit_positive", "implicit_negative", "implicit_strong_positive"

4. **Feedback summary for scoring prompt** (foundation for Epic 11):
   - `get_feedback_calibration(db, profile_id) -> list[dict]`
   - Returns the 3-5 most informative feedback examples (highest deviation from AI score)
   - Format: "Previously scored {title} at {company} as {ai_score}, user corrected to {user_score}
     because {reason}"
   - This can optionally be injected into the scoring prompt as additional calibration

### Implementation Guidelines

- Feedback is per-scored-job, not per-job. If a job is re-scored, the old feedback still applies
  to the old score record.
- Implicit signals should be created via service-layer hooks, not direct API calls. When
  `ApplicationService.create()` is called, it should also record implicit positive feedback
  on the associated ScoredJob (if one exists).
- Don't over-engineer the implicit signal tracking — start with just "promoted to application"
  and "application reached interview stage." Add more signals later based on usage.
- The feedback summary for the prompt (step 4) should be behind a feature flag. It's the bridge
  to Epic 11 but shouldn't be enabled until we have enough feedback data (≥10 corrections).

### A/B Testing Plan

**This epic is infrastructure — no scoring behavior changes.** A/B testing applies when Epic 11
uses this data to adjust scoring.

**Validation:** After implementation, manually submit 10 feedback records, verify they're stored
correctly, and verify the summary function returns the most informative examples.

### Definition of Done

- [ ] `ScoringFeedback` ORM model with Alembic migration
- [ ] `POST /api/score/{id}/feedback` endpoint
- [ ] `GET /api/score/feedback` and `GET /api/score/feedback/stats` endpoints
- [ ] Implicit signal recording on application promotion and interview progression
- [ ] `get_feedback_calibration()` function returning top deviations
- [ ] Feature flag for injecting feedback into scoring prompt (`FEEDBACK_CALIBRATION_ENABLED`)
- [ ] Input validation: direction must be valid enum, user_score must be 0-10
- [ ] Unit tests for feedback CRUD, implicit signal creation, calibration summary
- [ ] Integration test: submit feedback → retrieve → verify stats
- [ ] Frontend types updated (TypeScript interfaces for feedback)

### Tests to Write

```python
# tests/test_scoring_feedback.py

def test_submit_feedback():
    """POST feedback with direction and reason."""

def test_submit_feedback_with_user_score():
    """Feedback with explicit user_score stored correctly."""

def test_list_feedback_for_profile():
    """GET feedback returns all entries for a profile."""

def test_feedback_stats():
    """Stats endpoint returns count, avg deviation, most common direction."""

def test_implicit_positive_on_application_create():
    """Creating an application records implicit positive feedback."""

def test_implicit_strong_positive_on_interview():
    """Application reaching 'interview' status records strong positive."""

def test_calibration_summary_top_deviations():
    """Summary returns the 3-5 highest-deviation feedback examples."""

def test_calibration_summary_minimum_threshold():
    """With <10 feedback records, returns empty list."""

def test_feedback_references_correct_score():
    """original_fit_score matches the scored_job's actual fit_score."""
```

### Files Touched

- `src/career_os/models/scoring.py` — `ScoringFeedback` model
- `src/career_os/schemas/scoring.py` — request/response schemas for feedback
- `src/career_os/api/scoring.py` — new endpoints
- `src/career_os/services/scoring.py` — `get_feedback_calibration()`, implicit signal hooks
- `src/career_os/services/applications.py` — hook for implicit feedback on create/status change
- `alembic/versions/xxx_add_scoring_feedback.py` — migration
- `frontend/src/api/types.ts` — feedback types
- `tests/test_scoring_feedback.py` — new test file

---

## Epic 7: Dual-Score Architecture

### Why This Matters

Current Kestrel scoring answers one question: "How well does this job fit the candidate?"
But there's a second, equally important question: "How much would the candidate want this job?"

A job can be a perfect technical match (high fit_score) but undesirable (boring company, no
growth, toxic culture signals). Conversely, a dream company might post a role that's a stretch
(low technical fit but high desire).

HrFlow.ai separates these into Profile Match Score and Job Match Score. This dual-score model
gives users a 2D view of their options, enabling better decision-making.

### Research Context

- **HrFlow.ai dual-score:** Profile Match Score (probability candidate satisfies requirements) +
  Job Match Score (probability candidate would apply). Pre-trained on billions of HR data points.
- **I/O Psychology:** Person-Job Fit decomposes into Demands-Abilities (D-A) fit and
  Needs-Supply (N-S) fit — academic validation for the dual-score concept
- **Torre.ai:** Separates self-awareness (does the profile match application behavior?) from
  pure skill matching — another form of the same insight

### What to Build

1. **New score field: `desire_score`** (0-10) on `ScoredJob` model:
   - Measures "how much would the user want this job?"
   - Factors: company reputation, growth potential, culture signals, role excitement,
     compensation attractiveness, work-life balance signals
   - This is distinct from `fit_score` which measures "how qualified is the user?"

2. **Prompt modification** — the AI provider already generates `career_alignment` (0-10) and
   dimensional scores. `desire_score` is a synthesis of:
   - `career_trajectory` (growth)
   - `company_fit` (culture, reputation)
   - `compensation_fit` (salary attractiveness)
   - Weighted toward the user's stated goals and preferences

3. **Compute `desire_score` from existing dimensions** — two approaches for the agent to evaluate:
   - **Option A: Derived score** — compute desire_score as a weighted average of existing
     dimensional scores, using user goals to determine weights. No additional AI call needed.
   - **Option B: AI-generated** — add desire_score to the ScoreResult schema and have the LLM
     generate it alongside fit_score. More accurate but increases prompt complexity.
   - The agent should implement both, A/B test, and recommend one.

4. **2D visualization concept** — for frontends:
   - X-axis: fit_score (qualification), Y-axis: desire_score (desirability)
   - Quadrants: "Dream Job" (high/high), "Stretch Goal" (low fit/high desire),
     "Safe Bet" (high fit/low desire), "Skip" (low/low)
   - Frontend implementation is out of scope for this epic — just provide the data.

### Implementation Guidelines

- Start with Option A (derived) as the default — it's free and instant.
- For Option A, weight the dimensional scores using the user's goal signals:
  - If user has goals mentioning "leadership" or "management" → weight career_trajectory higher
  - If user has goals mentioning "compensation" or "salary" → weight compensation_fit higher
  - Default weights if no goals: career_trajectory 0.35, company_fit 0.35, compensation_fit 0.30
- For Option B, add `desire_score` to the `ScoreResult` Pydantic model and update the Anthropic
  provider's prompt to request it. Also add `desire_reasoning` (separate from fit reasoning).
- Store both options' results in the A/B test phase. Add `desire_score_method` column ("derived"
  or "ai_generated") for tracking.

### A/B Testing Plan

1. Pick 20 jobs from the golden set
2. Compute desire_score via Option A (derived from dimensions)
3. Compute desire_score via Option B (AI-generated)
4. Ask user to manually rate "how much would you want this job?" (1-10) for each
5. Compare MAE of Option A and Option B against user ratings
6. If Option A MAE is within 1.0 of Option B, prefer A (free, instant, deterministic)

### Definition of Done

- [ ] `desire_score` column on `ScoredJob` model with Alembic migration
- [ ] `desire_score_method` column for A/B tracking
- [ ] Option A: derived score calculation from dimensional scores + goals
- [ ] Option B: AI-generated desire_score via updated ScoreResult schema
- [ ] Both options implemented with config flag to select
- [ ] `DesireScoreResponse` added to scoring schemas
- [ ] A/B comparison documented with recommendation
- [ ] Unit tests for derived calculation, schema validation
- [ ] Integration test: scoring produces both fit_score and desire_score
- [ ] Frontend types updated

### Tests to Write

```python
# tests/test_desire_score.py

def test_derived_desire_score_calculation():
    """Derived score from dimensional scores with default weights."""

def test_derived_desire_score_with_goals():
    """Goals mentioning 'leadership' shift weight to career_trajectory."""

def test_desire_score_bounds():
    """Desire score is clamped to [0, 10]."""

def test_desire_score_null_without_dimensions():
    """If dimensional_scores is None, desire_score is None."""

def test_ai_generated_desire_score():
    """AI provider returns desire_score in ScoreResult."""

def test_desire_score_method_tracked():
    """ScoredJob.desire_score_method reflects which option was used."""
```

### Files Touched

- `src/career_os/models/scoring.py` — `desire_score`, `desire_score_method` columns
- `src/career_os/schemas/scoring.py` — response schema updates
- `src/career_os/schemas/ai.py` — `desire_score` in `ScoreResult` (Option B)
- `src/career_os/services/scoring.py` — derived calculation, integration
- `src/career_os/ai/anthropic_provider.py` — prompt update (Option B)
- `alembic/versions/xxx_add_desire_score.py` — migration
- `frontend/src/api/types.ts` — TypeScript types
- `tests/test_desire_score.py` — new test file

---

## Epic 8: Skill Normalization (ESCO/O*NET)

### Why This Matters

Current skill matching is free-text: the AI sees "Python" in the profile and "Python" in the JD
and (hopefully) connects them. But "React" vs "React.js" vs "ReactJS" vs "React Native" are
treated as different strings. The AI usually handles this, but it's inconsistent.

ESCO (European Skills taxonomy) provides 13,939 canonical skills with synonyms across 28
languages. Normalizing profile skills and JD keywords to ESCO identifiers would:
- Eliminate synonymy problems deterministically
- Enable skill gap analysis without AI calls
- Make embedding pre-filtering (Epic 4) more accurate
- Support future features like "skills trending in your field"

### Research Context

- **ESCO v1.2.0 (May 2024):** 3,039 occupations, 13,939 skills, 28 languages, free REST API
- **ESCOXLM-R (ACL 2023):** XLM-R-large pre-trained on ESCO data, SOTA on 6/9 skill extraction
  tasks, available on HuggingFace (`jjzha/esco-xlm-roberta-large`)
- **Lightcast:** 33,000+ skills but commercial API
- **O*NET:** 974 occupations, 2,400+ technology skill linkages, free API
- **Skill-LLM (2024):** Fine-tuned LLaMA for skill extraction, surpasses BERT-based approaches

### What to Build

1. **ESCO skill cache** — download the ESCO skills CSV/JSON-LD and store locally in SQLite
   (not as an external dependency). ~14K rows. Include: concept_uri, preferred_label, alt_labels,
   description.

2. **Skill normalizer service** in `src/career_os/services/skill_normalizer.py`:
   ```python
   def normalize_skill(raw_skill: str) -> ESCOSkill | None:
       """Map a free-text skill to an ESCO canonical entry."""
   ```
   - First pass: exact match on preferred_label and alt_labels (fast, covers ~60%)
   - Second pass: fuzzy match with Levenshtein distance (covers ~25% more)
   - Third pass: embedding similarity against ESCO skill descriptions (covers remaining)
   - Cache results in a `skill_mappings` table (raw_text → esco_uri)

3. **Profile skill enrichment** — when skills are added/updated on a profile, automatically
   normalize to ESCO URIs. Store both raw text and ESCO URI.

4. **ATS keyword enrichment** — when ATS keywords are extracted by the AI, normalize them to
   ESCO URIs. This enables deterministic matching: profile skill ESCO URI == JD keyword ESCO URI.

5. **O*NET occupation mapping** (optional, lower priority) — map the user's job_family to O*NET
   occupation codes. Use O*NET's skills-per-occupation data to suggest missing skills.

### Implementation Guidelines

- ESCO data is ~15MB as CSV. Download once, store in a dedicated SQLite table. Don't hit the
  API at runtime — it's slow and rate-limited.
- The normalizer should be fast (< 50ms per skill for exact/fuzzy match). Embedding fallback
  can be async.
- For the fuzzy match, use `rapidfuzz` (Levenshtein) or `thefuzz`. Threshold: 85% similarity.
- Cache aggressively — the same skill names appear repeatedly across JDs.
- This epic doesn't change scoring behavior — it enriches the data that feeds into scoring.
  The scoring prompt can later reference ESCO labels for consistency.

### A/B Testing Plan

**Validation approach:**
1. Take 100 skills from existing profiles and JDs
2. Run through the normalizer
3. Manual review: what % mapped correctly? What % mapped to the wrong ESCO entry?
4. Target: ≥85% correct mapping rate, ≤5% incorrect (rest unmapped is OK)

### Definition of Done

- [ ] ESCO skills data loaded into local SQLite table
- [ ] Data loading script/migration for ESCO import
- [ ] `normalize_skill()` with exact, fuzzy, and embedding fallback
- [ ] `skill_mappings` cache table
- [ ] Profile skill enrichment on create/update
- [ ] ATS keyword enrichment post-scoring
- [ ] Unit tests for normalization (exact, fuzzy, edge cases)
- [ ] Integration test: full pipeline from raw skill to ESCO URI
- [ ] Mapping accuracy ≥85% on a 100-skill sample

### Tests to Write

```python
# tests/test_skill_normalizer.py

def test_exact_match():
    """'Python' maps to ESCO Python skill."""

def test_synonym_match():
    """'React.js' and 'ReactJS' map to the same ESCO entry."""

def test_fuzzy_match():
    """'Kubernets' (typo) maps to Kubernetes."""

def test_no_match():
    """Nonsense string returns None."""

def test_cache_hit():
    """Second call for same skill uses cache, not re-computes."""

def test_profile_skill_enrichment():
    """Adding a skill to profile stores esco_uri alongside raw text."""

def test_ats_keyword_enrichment():
    """ATS keywords get esco_uri after scoring."""
```

### Files Touched

- `src/career_os/services/skill_normalizer.py` — new service
- `src/career_os/models/skills.py` — `esco_uri` column on skills model
- `src/career_os/models/esco.py` — new model for ESCO cache table
- `alembic/versions/xxx_add_esco_tables.py` — migration
- `scripts/load_esco_data.py` — data loading script
- `tests/test_skill_normalizer.py` — new test file
- `pyproject.toml` — add `rapidfuzz` dependency

---

## Epic 9: WARN Act Layoff Integration

### Why This Matters

When a company is actively laying off employees, applying there is risky. The US WARN Act
requires companies to give 60 days notice before mass layoffs. This data is public, filed with
state governments, and can be scraped.

Integrating WARN data into red flag detection gives Kestrel a unique differentiator that no
consumer job search tool currently offers. It's a concrete, verifiable signal — not an AI opinion.

### Research Context

- **warn-scraper (biglocalnews/warn-scraper):** Open-source Python CLI that scrapes WARN Act
  notices from state government websites. Covers all US states that publish WARN data.
- **layoffs.fyi:** Crowdsourced tech layoff tracker. No official API, but Apify has a scraper.
- **WARN data quality:** WARN filings include company name, location, number of employees
  affected, effective date. Filed 60 days before layoffs. Coverage varies by state — CA, NY, TX
  have the best data.

### What to Build

1. **WARN data table** in SQLite:
   ```python
   class WARNFiling(Base):
       __tablename__ = "warn_filings"
       id: int (PK)
       company_name: str
       company_name_normalized: str  # lowercase, stripped suffixes
       state: str
       employees_affected: int | None
       effective_date: date | None
       notice_date: date
       source_url: str | None
       created_at: datetime
   ```

2. **Data loading script** — use `warn-scraper` to download WARN data for key states (CA, NY,
   WA, TX, IL, MA, CO, GA). Store in the table. Run as a CLI command:
   `kestrel warn-update` or as part of discovery scheduler.

3. **Red flag rule: `_detect_recent_layoffs()`** in `red_flags.py`:
   - Query WARN filings for the company (using normalized name matching)
   - If any filing in the last 180 days: severity "caution" with employee count
   - If filing in the last 60 days (layoffs imminent or in progress): severity "warning"
   - Include: "Company filed WARN notice on {date} affecting {N} employees in {state}"

4. **Periodic refresh** — add a scheduler task (or CLI command) to refresh WARN data weekly.
   The discovery scheduler at `src/career_os/discovery/scheduler.py` is a natural place to
   hook this in.

### Implementation Guidelines

- `warn-scraper` is a pip-installable CLI. Add it as an optional dependency:
  `pip install warn-scraper`. If not installed, WARN detection is silently skipped.
- Company name matching is the hard part. "Google LLC" in the WARN filing vs "Google" in the
  job posting. Use the same normalization as Epic 2 (ghost jobs).
- WARN data is US-only. For EU roles, this rule simply doesn't apply.
- The data can be stale — WARN filings are public records but not always up-to-date. Set
  expectations: this catches large-scale layoffs at known companies, not stealth cuts.
- Consider also integrating layoffs.fyi data as a supplement — it covers companies that may not
  file WARN notices (< 100 employees, or international).

### A/B Testing Plan

**Validation:**
1. Load WARN data for CA and NY (highest coverage)
2. Cross-reference against known recent layoffs (Google, Meta, Amazon, etc.)
3. Verify at least 80% of known major layoffs appear in the data
4. Test company name matching against 20 job postings from those companies

### Definition of Done

- [ ] `WARNFiling` ORM model with Alembic migration
- [ ] Data loading from warn-scraper for 8+ states
- [ ] `_detect_recent_layoffs()` rule in `red_flags.py`
- [ ] Company name normalization (shared with Epic 2 if available)
- [ ] CLI command: `kestrel warn-update`
- [ ] Graceful skip if warn-scraper not installed
- [ ] Unit tests for filing lookup, name matching, severity thresholds
- [ ] Integration test: scoring a job from a WARN-filed company triggers flag
- [ ] Data freshness: script runs in < 5 minutes for 8 states

### Tests to Write

```python
# tests/test_warn_integration.py

def test_recent_warn_triggers_warning():
    """WARN filing within 60 days → severity 'warning'."""

def test_older_warn_triggers_caution():
    """WARN filing 60-180 days ago → severity 'caution'."""

def test_old_warn_no_flag():
    """WARN filing >180 days ago → no flag."""

def test_company_name_normalization_matches():
    """'Google LLC' filing matches 'Google' job posting."""

def test_no_warn_data_no_flag():
    """Company not in WARN database → no flag."""

def test_graceful_skip_no_warnscraper():
    """If warn-scraper not installed, rule is silently skipped."""

def test_warn_flag_description_includes_details():
    """Flag description includes date, state, and employee count."""
```

### Files Touched

- `src/career_os/models/warn.py` — new ORM model
- `src/career_os/services/red_flags.py` — new detection rule
- `src/career_os/services/warn_data.py` — data loading service
- `src/career_os/cli/warn.py` — CLI command for updates
- `alembic/versions/xxx_add_warn_filings.py` — migration
- `pyproject.toml` — add `warn-scraper` as optional dependency
- `tests/test_warn_integration.py` — new test file

---

## Epic 10: Uncertainty Ranges for Sparse Profiles

### Why This Matters

When a profile has 2 skills and no goals, a fit_score of 7.0 is misleading — the AI is guessing
based on minimal information. Torre.ai solved this elegantly: instead of a point score, show a
range (e.g., "5.0 - 8.5") that narrows as the profile gets richer.

This builds trust by being honest about confidence. It also incentivizes profile completion.

### Research Context

- **Torre.ai:** Uses uncertainty ranges (lower/upper bounds) instead of point scores when data
  is sparse. Penalizes incomplete profiles via "genome completion" scorer.
- **Bayesian uncertainty in recommendations:** Standard approach is to model score as a
  distribution, report mean ± confidence interval.

### What to Build

1. **Profile completeness score** — compute a 0-100% "profile richness" metric:
   - Has job_family: +15%
   - Has location: +15%
   - Has ≥5 skills: +20%
   - Has ≥1 career goal: +15%
   - Has market positioning data: +10%
   - Has ≥3 past positions/experiences: +15%
   - Has dream companies list: +10%

2. **Confidence interval calculation:**
   - At 100% completeness: range = ±0.3 (high confidence)
   - At 50% completeness: range = ±1.5 (moderate uncertainty)
   - At 25% completeness: range = ±3.0 (low confidence — score is nearly meaningless)
   - Formula: `half_width = 3.0 * (1 - completeness_pct / 100) + 0.3`

3. **Add to ScoreResponse:**
   ```python
   profile_completeness: float  # 0-100
   confidence_range: tuple[float, float]  # (low_bound, high_bound)
   ```

4. **UI hint:** When completeness < 50%, include a message:
   "This score has high uncertainty. Add [skills/goals/experience] to improve accuracy."
   Include which specific fields would most improve confidence.

### Definition of Done

- [ ] Profile completeness calculation function
- [ ] Confidence interval formula applied to all scores
- [ ] `profile_completeness` and `confidence_range` in ScoreResponse
- [ ] Missing fields suggestion (what to add to improve confidence)
- [ ] Completeness computed at scoring time, not stored (dynamic)
- [ ] Unit tests for completeness calculation, interval math
- [ ] Frontend types updated

### Files Touched

- `src/career_os/services/scoring.py` — completeness and interval calculation
- `src/career_os/schemas/scoring.py` — response schema updates
- `frontend/src/api/types.ts` — TypeScript types
- `tests/test_uncertainty.py` — new test file

---

## Epic 11: Bayesian Preference Learning

### Why This Matters

After Epic 6 (feedback loop) has accumulated user corrections and implicit signals, the system
has data to learn from. Bayesian preference learning updates scoring weights based on what the
user actually values — not what they initially configured.

This is the capstone epic that makes Kestrel's scoring genuinely personalized and improving
over time.

### Research Context

- **BAL-PM (NeurIPS 2024):** 33-68% reduction in required feedback via active learning
- **BISTRO (KDD 2024):** Session-based preference drift detection
- **Thompson Sampling:** Standard approach for learning from sparse feedback — sample from
  posterior distribution of weights, update as feedback arrives

### What to Build

1. **Preference model** — maintain a Bayesian model of the user's true weight preferences:
   - Prior: start from configured `ScoringWeights` (user's explicit preferences)
   - Posterior: update based on feedback (direction + magnitude of correction)
   - Simple approach: per-dimension Beta distributions, updated with user corrections

2. **Weight suggestion service:**
   - After ≥15 feedback records, analyze patterns:
     - "You consistently rate technical_fit higher than the AI → suggest increasing skills_match weight"
     - "You dismiss jobs the AI scored highly on compensation_fit → suggest decreasing salary_match weight"
   - Present as suggestions, not automatic changes

3. **Active query selection** (BAL-PM inspired):
   - When scoring a borderline job, sometimes ask the user "Would you apply to this?"
   - Select queries that maximally reduce uncertainty in the preference model
   - Behind a feature flag — can be annoying if overused

### Definition of Done

- [ ] Bayesian preference model with prior/posterior updates
- [ ] Weight suggestion service analyzing feedback patterns
- [ ] Suggestions presented via API (not auto-applied)
- [ ] Minimum feedback threshold (15+ records) before suggestions
- [ ] Active query selection (optional, behind feature flag)
- [ ] Unit tests for Bayesian updates, suggestion logic
- [ ] Integration test: 20 feedback records → meaningful suggestion

### Files Touched

- `src/career_os/services/preference_learning.py` — new service
- `src/career_os/api/scoring.py` — suggestions endpoint
- `src/career_os/schemas/scoring.py` — suggestion response schema
- `tests/test_preference_learning.py` — new test file

---

## Integration & Cross-Cutting Concerns

### Shared Infrastructure

Several epics share common needs:
- **Company name normalization** — needed by Epic 2 (ghost jobs) and Epic 9 (WARN). Build once
  as a utility in `src/career_os/utils/normalization.py`, used by both.
- **Golden set fixture** — created in Epic 1, reused by Epics 5, 7 for A/B testing.
- **Profile completeness** — computed in Epic 10, could also inform Epic 4 (embedding quality
  depends on profile richness).

### Migration Strategy

Each epic adds its own Alembic migration. Migrations are independent (no cross-epic dependencies)
so they can be developed in parallel on separate branches. Merge order doesn't matter.

### Feature Flags

| Flag | Epic | Default | Purpose |
|------|------|---------|---------|
| `EMBEDDING_PREFILTER_ENABLED` | 4 | false | Enable/disable embedding pre-filter |
| `EMBEDDING_PREFILTER_THRESHOLD` | 4 | 0.65 | Cosine similarity cutoff |
| `BORDERLINE_SCORING_ENABLED` | 5 | true | Enable 2-pass for borderline scores |
| `FEEDBACK_CALIBRATION_ENABLED` | 6 | false | Inject feedback into scoring prompt |
| `DESIRE_SCORE_METHOD` | 7 | "derived" | "derived" or "ai_generated" |
| `ACTIVE_QUERY_ENABLED` | 11 | false | Ask user for feedback on borderline scores |

### Review Strategy

Each epic ships as its own PR. Review checklist:
1. Does the epic work in isolation? (no broken imports from unmerged epics)
2. Do all existing tests pass?
3. Do the new tests cover the DoD items?
4. Is the A/B testing documented with results?
5. Are feature flags properly defaulted?
6. Is the migration reversible?

### Estimated Effort

| Epic | Complexity | Estimated Agent Time | Dependencies |
|------|-----------|---------------------|--------------|
| 1. Rubric | Low | 2-3 hours | None |
| 2. Ghost Jobs | Low | 2-3 hours | None |
| 3. Percentiles | Low | 1-2 hours | None |
| 4. Embeddings | High | 6-8 hours | Phase 1 |
| 5. 2-Pass | Medium | 3-4 hours | Epic 1 |
| 6. Feedback | Medium | 4-5 hours | Phase 2 |
| 7. Dual-Score | Medium | 4-5 hours | Independent |
| 8. ESCO | High | 6-8 hours | Independent |
| 9. WARN | Medium | 3-4 hours | Independent |
| 10. Uncertainty | Low | 2-3 hours | Epic 7 |
| 11. Bayesian | High | 6-8 hours | Epic 6 |
