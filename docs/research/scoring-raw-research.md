# Scoring System Research: Raw Findings & Sources

**Researched:** 2026-04-16
**Method:** Architecture review, G-286 benchmark (120-call A/B validation), G-268 scoring evolution (11 epics), G-295 golden set expansion
**Audience:** Developers, contributors, researchers evaluating Kestrel's scoring decisions

This document presents findings without editorial filtering. For the user-friendly explanation, see `../how-scoring-works.md`. For the benchmark validation report, see `../scoring-validation-report.md`.

---

## 1. Current State: Scoring Architecture

### Dual Score System

Kestrel uses two independent scores per job, introduced via G-275:

| Score | Range | Purpose | Method |
|-------|-------|---------|--------|
| Fit Score | 0-10 | Objective alignment (skills, seniority, compensation, location) | AI-generated via provider `score()` method |
| Desire Score | 0-10 | Subjective desirability (career trajectory, company culture, compensation appeal) | Option A: derived from dimensional sub-scores + goals; Option B: AI-generated |

Desire score resolution order: AI-generated (Option B) takes priority if the provider returns one. If not, derived from three dimensional sub-scores (`career_trajectory`, `company_fit`, `compensation_fit`) weighted by the user's active goals.

Default desire weights: `career_trajectory: 0.35, company_fit: 0.35, compensation_fit: 0.30`.

Goal-keyword overrides shift these weights. For example, goals containing "leadership" shift to `career_trajectory: 0.50, company_fit: 0.25, compensation_fit: 0.25`. Goals containing "salary" or "compensation" shift to `compensation_fit: 0.55`.

**Source:** `src/career_os/services/scoring.py` (lines 438-505), `src/career_os/schemas/scoring.py` (lines 340-375).

### Six Scoring Dimensions

All six dimensions are scored 0-10 by the AI provider and stored as individual columns:

| Dimension | Column | What It Measures |
|-----------|--------|-----------------|
| `technical_fit` | `dim_technical_fit` | Skills/technology overlap |
| `seniority_alignment` | `dim_seniority_alignment` | Experience level match |
| `compensation_fit` | `dim_compensation_fit` | Salary range alignment |
| `location_fit` | `dim_location_fit` | Geography/remote policy match |
| `career_trajectory` | `dim_career_trajectory` | Growth potential alignment |
| `company_fit` | `dim_company_fit` | Culture/values/reputation match |

Dimensions are collapsed into a nested `DimensionalScoresResponse` object on the API response via a Pydantic model validator. Legacy rows with any NULL dimension leave `dimensional_scores` as None.

**Source:** `src/career_os/schemas/scoring.py` (lines 84-92, 305-332).

### Quadrant Model

Jobs are classified into 2D quadrants using a threshold of 5.0 on both axes:

| Quadrant | Fit Score | Desire Score | Interpretation |
|----------|-----------|-------------|----------------|
| Dream Job | >= 5.0 | >= 5.0 | High fit, high desire |
| Stretch Goal (Reach) | < 5.0 | >= 5.0 | Low fit, high desire |
| Safe Bet | >= 5.0 | < 5.0 | High fit, low desire |
| Skip | < 5.0 | < 5.0 | Low fit, low desire |

The `classify_quadrant()` function returns None if either score is None.

**Source:** `src/career_os/schemas/scoring.py` (lines 340-361).

### Score Bands and Letter Grades

Fit scores map to letter grades via `score_to_letter_grade()`:

| Score Range | Letter Grade | Band Label |
|-------------|-------------|------------|
| 9.0-10.0 | A | Dream fit |
| 8.0-8.9 | A- | Strong fit, top tier |
| 7.0-7.9 | B+ | Strong fit |
| 6.0-6.9 | B | Good fit |
| 5.0-5.9 | C+ | Maybe |
| 4.0-4.9 | C | Weak fit |
| 3.0-3.9 | D | Poor fit |
| 0.0-2.9 | F | No fit |

Letter grade is derived automatically via a Pydantic model validator on `ScoreResponse`.

**Source:** `src/career_os/schemas/scoring.py` (lines 22-53, 298-303).

### Scoring Rubric (v1.1)

The rubric is embedded in the scoring prompt to anchor AI scoring behavior. Band definitions:

| Band | Score | Rubric Description |
|------|-------|--------------------|
| Dream | 9-10 | Role, skills, seniority, domain, location all align. Top-5% applicant AND role precisely matches career goals and target job family. Prestigious company alone does not make a 9. |
| Strong | 7-8 | Most dimensions match. Minor gaps (one missing tool, slight seniority stretch) but clearly competitive. |
| Moderate | 5-6 | Partial overlap. Some skills transfer but meaningful gaps in domain, seniority, or core requirements. |
| Weak | 3-4 | Few dimensions align. Major gaps in multiple areas. Significant retraining needed. |
| Poor | 1-2 | Near-total mismatch on role type, skills, domain. |

The rubric includes 4 calibration examples at scores 2.0, 5.0, 7.5, and 8.5 (the 7.5 example was added via G-296 to sharpen the dream boundary).

**Source:** `src/career_os/services/scoring.py` (lines 122-174), `RUBRIC_VERSION = "v1.1"`.

### Profile-Aware Scoring Wrapper

Scoring prompts include full user profile context:

1. **Profile data:** name, location, job family, up to 20 skills (name/category/proficiency), up to 5 active goals, market positioning data
2. **Scoring weights:** JSON-serialized weight configuration specific to the profile's job family
3. **Job-family weight modifiers:** Dynamic rubric modifiers highlighting which dimensions carry more or less weight (e.g., "For SWE: skills match is weighted higher (35% vs default 25%)")
4. **Calibration examples:** When `feedback_calibration_enabled` is true and the profile has >= 10 explicit feedback records, the top 5 most informative user corrections (largest deviation) are injected into the prompt

The prompt is assembled in `_build_scoring_prompt()` which combines job description, candidate profile, rubric, job-family modifiers, weights, and calibration examples.

**Source:** `src/career_os/services/scoring.py` (lines 839-936).

---

## 2. AI Provider Abstraction

### Factory Pattern

The `get_ai_provider()` factory selects a provider via resolution order:

1. Explicit `provider_name` argument
2. `AI_PROVIDER` environment variable
3. Default: `"mock"`

**Source:** `src/career_os/ai/factory.py` (lines 104-123).

### Provider Registry

| Provider | Class | Key Config | Use Case |
|----------|-------|-----------|----------|
| `mock` / `demo` | `MockProvider` | None | Testing, development, demos |
| `openrouter` | `OpenRouterProvider` | `OPENROUTER_API_KEY`, model default: `anthropic/claude-sonnet-4` | Production (multi-model router) |
| `anthropic` | `AnthropicProvider` | `ANTHROPIC_API_KEY`, model default: `claude-sonnet-4-20250514` | Direct Anthropic API |
| `ollama` | `OllamaProvider` | `OLLAMA_BASE_URL` (localhost:11434), model default: `llama3.3` | Local/self-hosted inference |

`"demo"` is a user-facing alias for `"mock"` so non-technical users don't think "mock" means broken.

API keys are resolved via `_resolve_api_key()`: environment variable first, then DB-stored credential from the `integration_configs` table.

**Source:** `src/career_os/ai/factory.py` (lines 70-85).

### Abstract Interface

All providers implement the `AIProvider` ABC with three methods:

| Method | Signature | Purpose |
|--------|-----------|---------|
| `complete()` | `async def complete(prompt, *, feature, context, **kwargs) -> AIResponse` | General text completion |
| `score()` | `async def score(job_description, profile_data, **kwargs) -> AIResponse` | Job-vs-profile scoring |
| `embed()` | `async def embed(text, **kwargs) -> list[float]` | Embedding generation (optional, raises `NotImplementedError` by default) |

Additional properties: `name` (provider identifier), `privacy_tier` (default: "yellow").

`MockProvider` returns deterministic scores for testing using a hash-based seed derived from the job description text. It produces valid schema responses for all AI features (scoring, coaching, interview prep, etc.).

**Source:** `src/career_os/ai/base.py` (lines 20-97), `src/career_os/ai/mock_provider.py`.

---

## 3. G-286 Benchmark Results (120-Call A/B Validation)

### Configuration

| Parameter | Value |
|-----------|-------|
| Runs per job | 3 |
| Total jobs | 20 |
| Total API calls attempted | 120 (60 baseline + 60 rubric) |
| AI provider | OpenRouter |
| Model | anthropic/claude-sonnet-4 (default) |
| Profile | Benchmark TPM: Berlin, Germany; Python/AI/ML/PM skills |
| Baseline | Rubric monkey-patched to empty string |
| Rubric | v1.0 (later updated to v1.1 via G-296) |

### Baseline Analysis

| Metric | Value |
|--------|-------|
| Total runs | 47 |
| Errors (JSON parse failures) | 13 (21.7% error rate) |
| Mean standard deviation across jobs | 0.364 |

**Baseline by category:**

| Category | Mean | Std Dev | Min | Max | In-Band % | Jobs | Runs |
|----------|------|---------|-----|-----|-----------|------|------|
| reject | 2.26 | 0.207 | 2.1 | 2.5 | 100.0% | 4 | 10 |
| mediocre | 5.29 | 0.831 | 4.2 | 6.2 | 63.6% | 6 | 11 |
| strong | 8.03 | 1.288 | 5.5 | 9.2 | 20.0% | 6 | 15 |
| dream | 8.57 | 1.057 | 6.2 | 9.2 | 54.5% | 4 | 11 |

**Baseline dimensional consistency (std dev per dimension):**

| Dimension | Std Dev |
|-----------|---------|
| technical_fit | 0.339 |
| seniority_alignment | 0.480 |
| compensation_fit | 0.428 |
| location_fit | 0.876 |
| career_trajectory | 0.333 |
| company_fit | 0.261 |

### Rubric Analysis (v1.1)

| Metric | Value |
|--------|-------|
| Total runs | 54 |
| Errors (JSON parse failures) | 6 (10.0% error rate) |
| Mean standard deviation across jobs | 0.307 |

**Rubric by category:**

| Category | Mean | Std Dev | Min | Max | In-Band % | Jobs | Runs |
|----------|------|---------|-----|-----|-----------|------|------|
| reject | 2.14 | 0.452 | 1.5 | 2.5 | 100.0% | 4 | 11 |
| mediocre | 4.16 | 0.413 | 3.5 | 4.5 | 75.0% | 6 | 16 |
| strong | 7.76 | 1.580 | 4.2 | 9.2 | 11.8% | 6 | 17 |
| dream | 8.55 | 1.445 | 4.5 | 9.2 | 60.0% | 4 | 10 |

**Rubric dimensional consistency (std dev per dimension):**

| Dimension | Std Dev |
|-----------|---------|
| technical_fit | 0.548 |
| seniority_alignment | 0.513 |
| compensation_fit | 0.491 |
| location_fit | 0.683 |
| career_trajectory | 0.362 |
| company_fit | 0.459 |

### Comparison: Baseline vs Rubric

| Metric | Baseline | Rubric | Change |
|--------|----------|--------|--------|
| Mean std across jobs | 0.364 | 0.307 | -15.7% (improvement) |
| Error rate | 21.7% (13/60) | 10.0% (6/60) | -53.8% (improvement) |
| Reject in-band | 100.0% | 100.0% | No change |
| Mediocre in-band | 63.6% | 75.0% | +11.4pp improvement |
| Strong in-band | 20.0% | 11.8% | -8.2pp regression |
| Dream in-band | 54.5% | 60.0% | +5.5pp improvement |

**Key finding:** The rubric improved reject/mediocre/dream categories but degraded strong-category accuracy. The validation report attributes this to the model consistently over-scoring TPM-adjacent roles into dream territory (8.5-9.2 vs expected 7-8), plus 2 likely miscategorized golden-set jobs (VP Engineering, Product Engineer) inflating error rates.

### Category Separation (Score Ranges)

| Category | Baseline Range | Rubric Range |
|----------|---------------|--------------|
| reject | [2.1, 2.5] | [1.5, 2.5] |
| mediocre | [4.2, 6.2] | [3.5, 4.5] |
| strong | [5.5, 9.2] | [4.2, 9.2] |
| dream | [6.2, 9.2] | [4.5, 9.2] |

**Observation:** The rubric tightened the mediocre range significantly (2.0-point spread down to 1.0) but widened the strong range. Overlap between strong and dream categories persists in both modes.

### Dimensional Consistency Comparison

| Dimension | Baseline Std | Rubric Std | More Consistent? |
|-----------|-------------|-----------|-----------------|
| technical_fit | 0.339 | 0.548 | No (worse) |
| seniority_alignment | 0.480 | 0.513 | No (slightly worse) |
| compensation_fit | 0.428 | 0.491 | No (slightly worse) |
| location_fit | 0.876 | 0.683 | Yes (improved) |
| career_trajectory | 0.333 | 0.362 | No (slightly worse) |
| company_fit | 0.261 | 0.459 | No (worse) |

**Finding:** `location_fit` was the most consistent dimension across both modes (0.683-0.876 std). `company_fit` was the least consistent in baseline (0.261) but worsened with the rubric (0.459). The rubric improved overall variance at the aggregate level but increased dimensional variance — suggesting the rubric guides the AI to more consistent *total* scores while redistributing dimensional variance.

### Red Flag Analysis

| Metric | Value |
|--------|-------|
| Total flags triggered | 18 |
| Flag types triggered | `vague_responsibilities` only |
| False positives | 10 (55.6%) |

The 10 false positives in `vague_responsibilities` led to G-297 raising the character threshold from 200 to 400 characters.

### Dual Score Quadrant Distribution

| Quadrant | Count |
|----------|-------|
| Dream Job | 8 |
| Reach | 2 |
| Skip | 8 |
| Safe Bet | 0 |

No jobs landed in the Safe Bet quadrant (high fit, low desire). This suggests the desire derivation formula correlates strongly with fit — when fit is high, the dimensional sub-scores feeding desire are also high.

### Embedding Analysis

| Parameter | Value |
|-----------|-------|
| Model | nomic-embed-text |
| Max reject similarity | 0.6475 |
| Min strong/dream similarity | 0.6066 |
| Clean threshold exists | **No** |

**Finding:** The maximum cosine similarity for reject-category jobs (0.6475) exceeds the minimum similarity for strong/dream-category jobs (0.6066). No clean similarity threshold exists that separates reject from non-reject jobs. This means embedding pre-filtering cannot reliably exclude bad fits without also excluding some good fits. The embedding pre-filter (G-272) operates in shadow mode by default for this reason.

**Source:** `docs/research/benchmark-results-summary.json`, `docs/scoring-validation-report.md`.

---

## 4. G-268 Scoring Evolution (11 Epics)

All 11 epics merged 2026-04-15:

### Epic 1: Scoring Rubric Calibration (G-269)

- Added `SCORING_RUBRIC` constant with band definitions and calibration examples
- Introduced `RUBRIC_VERSION` tracking (currently "v1.1")
- Rubric embedded in every scoring prompt via `_build_scoring_prompt()`
- Job-family weight modifiers dynamically adjust rubric text per profile

**Source:** `src/career_os/services/scoring.py` (lines 122-210).

### Epic 2: Ghost Job Detection (G-270)

- `_detect_ghost_job_signals()`: counts repeated company+title occurrences in discovery history within 90-day window
- Thresholds: >= 3 occurrences = "caution", >= 5 occurrences = "warning"
- `_detect_multi_city_blast()`: detects same company+description across 3+ locations
- Normalization functions: `normalize_job_title()` strips seniority tokens, `normalize_company_name()` strips legal suffixes

**Source:** `src/career_os/services/red_flags.py` (lines 310-464).

### Epic 3: Score Context Percentiles (G-271)

- `compute_score_context()` returns percentile, rank, total_scored, avg_score, and score_band_count
- Requires minimum 5 non-stale scored jobs before context is populated
- Computed dynamically on GET endpoints (not stored in DB)

**Source:** `src/career_os/services/scoring.py` (lines 1172-1261).

### Epic 4: Embedding Pre-Filter (G-272)

- Computes cosine similarity between profile and job embeddings before full LLM scoring
- Shadow mode (default): logs similarities but scores all jobs. When enabled: skips jobs below threshold.
- Uses `compute_job_similarities()` from `src/career_os/services/embeddings.py`
- Graceful degradation: if embedding fails, all jobs proceed to full scoring

**Source:** `src/career_os/services/scoring.py` (lines 1018-1065).

### Epic 5: Borderline 2-Pass Scoring (G-273)

- When first-pass score falls in the borderline zone (`borderline_low_threshold` to `borderline_high_threshold`), a second scoring pass runs
- Results are averaged via `_average_score_results()`: numeric fields averaged, qualitative fields taken from higher-scoring result, ATS keywords from longer list, score_breakdown factors deduplicated and averaged
- `scoring_passes` column tracks whether 1 or 2 passes were used

**Source:** `src/career_os/services/scoring.py` (lines 530-616, 696-737).

### Epic 6: User Feedback Loop (G-274)

- `submit_feedback()`: explicit user corrections (too_high, too_low, correct) with optional user_score and reason
- `record_implicit_feedback()`: implicit signals (implicit_positive, implicit_negative, implicit_strong_positive) from application state transitions
- `get_feedback_stats()`: summary statistics (total, explicit, implicit counts, avg deviation, direction counts)
- `get_feedback_calibration()`: returns top 5 most informative corrections (largest deviation) for injection into scoring prompts
- Calibration requires minimum 10 explicit feedback records (`CALIBRATION_MIN_FEEDBACK`)

**Source:** `src/career_os/services/scoring.py` (lines 1436-1687).

### Epic 7: Dual-Score Architecture (G-275)

- Added `desire_score`, `desire_score_method` ("derived" or "ai_generated"), and `desire_reasoning` fields
- Option A (derived): weighted average of career_trajectory, company_fit, compensation_fit dimensional scores
- Option B (AI-generated): provider returns desire_score directly (takes priority)
- `classify_quadrant()`: maps (fit, desire) to dream_job/stretch_goal/safe_bet/skip

**Source:** `src/career_os/schemas/scoring.py` (lines 340-375), `src/career_os/services/scoring.py` (lines 434-506, 783-803).

### Epic 8: Skill Normalization — ESCO Taxonomy (G-276)

- ESCO (European Skills, Competences, Qualifications and Occupations) taxonomy tables added
- `src/career_os/services/skill_normalizer.py`: normalizes user-entered skill names to ESCO canonical forms
- `src/career_os/models/esco.py`: ESCO taxonomy ORM model
- Alembic migration: `l3g4h5i6j7k8_add_esco_tables.py`

**Source:** `src/career_os/services/skill_normalizer.py`, `src/career_os/models/esco.py`.

### Epic 9: WARN Act Layoff Integration (G-277)

- `_detect_recent_layoffs()`: queries `warn_filings` table for WARN Act notices
- Filing within 60 days = "warning" (layoffs imminent or in progress)
- Filing within 180 days = "caution" (recent layoffs, risk signal)
- US-only; silently returns None for non-US roles or when company cannot be matched
- Lazy import of `warn_data` module to avoid circular dependencies

**Source:** `src/career_os/services/red_flags.py` (lines 467-540).

### Epic 10: Uncertainty Ranges (G-278)

- `compute_profile_completeness()`: scores profile richness 0-100% across 7 components
- Components: job_family (15%), location (15%), skills >= 5 (20%), goals >= 1 (15%), market_positioning (10%), experiences (15%), dream_companies (10%)
- Confidence interval formula: `half_width = 3.0 * (1 - completeness / 100) + 0.3`
  - At 100% completeness: +/- 0.3
  - At 50% completeness: +/- 1.8
  - At 25% completeness: +/- 3.075
- Improvement hints shown when completeness < 50%

**Source:** `src/career_os/services/scoring.py` (lines 1265-1396).

### Epic 11: Bayesian Preference Learning (G-279)

- `src/career_os/services/preference_learning.py`: generates weight adjustment suggestions based on feedback patterns
- `WeightSuggestionResponse`: per-dimension suggestion with current weight, suggested weight, confidence (0-1), and reason
- `SuggestionsResponse`: list of suggestions + readiness flag (enough feedback exists)
- `ActiveQueryResponse`: uncertainty-based prompts asking user for feedback on dimensions with highest uncertainty

**Source:** `src/career_os/services/preference_learning.py`, `src/career_os/schemas/scoring.py` (lines 530-568).

---

## 5. Job-Family-Aware Scoring Weights

### Default Weights

| Dimension | Default Weight |
|-----------|---------------|
| skills_match | 0.25 |
| career_alignment | 0.20 |
| culture_fit | 0.15 |
| salary_match | 0.15 |
| location_match | 0.10 |
| growth_potential | 0.10 |
| remote_preference | 0.05 |

### Job-Family Presets

| Family | Skills | Career | Culture | Salary | Location | Growth | Remote |
|--------|--------|--------|---------|--------|----------|--------|--------|
| SWE | **0.35** | 0.15 | 0.10 | 0.15 | 0.05 | **0.15** | 0.05 |
| TPM | 0.20 | **0.25** | 0.15 | 0.15 | 0.10 | 0.10 | 0.05 |
| Product Engineer | **0.30** | 0.20 | 0.15 | 0.10 | 0.05 | **0.15** | 0.05 |
| DevRel | 0.15 | 0.20 | **0.25** | 0.10 | 0.05 | 0.15 | **0.10** |
| AI Program Lead | 0.25 | **0.25** | 0.10 | 0.15 | 0.05 | **0.15** | 0.05 |

Key differences from default:
- SWE weights `skills_match` at 35% (vs 25% default) — technical skill gaps are more penalizing
- DevRel weights `culture_fit` at 25% (vs 15% default) — company culture matters more for advocacy roles
- DevRel weights `remote_preference` at 10% (vs 5% default) — DevRel roles are often distributed

When a profile's `job_family` changes, `regenerate_weights_for_job_family()` deletes existing weights and recreates with the new family's preset.

**Source:** `src/career_os/services/scoring.py` (lines 55-115, 277-295).

---

## 6. Red Flag Detection

### Stateless Rules (No DB Access)

| Rule | Flag Type | Severity | Trigger Condition |
|------|-----------|----------|------------------|
| Stale posting | `stale_posting` | warning | Posted > 60 days ago |
| Unrealistic requirements (A) | `unrealistic_requirements` | warning | 10+ years required + junior/mid title |
| Unrealistic requirements (B) | `unrealistic_requirements` | warning | > 15 distinct tech skill tokens |
| Turnover language | `turnover_language` | info | >= 2 turnover phrases, 0 work-life phrases |
| Missing salary | `missing_salary` | warning | No salary + located in pay-transparency mandate state (CO, CA, WA, NY, CT) |
| Staffing agency | `staffing_agency` | caution | Contains staffing/recruiting agency patterns |
| Vague responsibilities (short) | `vague_responsibilities` | info | Description < 400 chars (raised from 200 via G-297) |
| Vague responsibilities (phrases) | `vague_responsibilities` | info | > 50% of bullets use generic phrases |
| Excessive requirements | `excessive_requirements` | warning | > 15 distinct tech skills (only if unrealistic_requirements didn't fire) |
| Recent layoffs (imminent) | `recent_layoffs` | warning | WARN Act filing within 60 days |
| Recent layoffs (caution) | `recent_layoffs` | caution | WARN Act filing within 180 days |

Severity scale: `info < caution < warning < dealbreaker`.

### Data-Driven Rules (DB Required)

| Rule | Flag Type | Severity | Trigger Condition |
|------|-----------|----------|------------------|
| Ghost job (moderate) | `ghost_job` | caution | Same company+title >= 3 times in 90 days |
| Ghost job (strong) | `ghost_job` | warning | Same company+title >= 5 times in 90 days |
| Multi-city blast | `multi_city_blast` | info | Same company+description across >= 3 locations in 90 days |

Ghost job detection uses normalized company names (strip legal suffixes) and normalized titles (strip seniority tokens) for fuzzy matching.

Multi-city blast uses the first 200 characters of the stripped description as a fingerprint to detect copy-pasted JDs without expensive similarity calculations.

**Source:** `src/career_os/services/red_flags.py` (full file).

---

## 7. Golden Set Fixtures

### Inventory

| File | Domain | Profile | Job Count |
|------|--------|---------|-----------|
| `scoring_golden_set.json` | General tech (TPM/SWE/AI) | Benchmark TPM profile | 20+ |
| `scoring_golden_set_finance.json` | Finance | Finance profile | 20+ |
| `scoring_golden_set_design.json` | Design | Design profile | 20+ |

Created and expanded via G-295.

### Structure

Each fixture file contains:
- `profile`: object with `job_family`, `location`, and other profile fields
- `jobs`: array of 20+ hand-labeled jobs, each with:
  - `id`: unique identifier
  - `category`: one of `reject`, `mediocre`, `strong`, `dream`
  - `expected_band`: `[low, high]` score range (numeric, low <= high)
  - `title`, `company`, `description` (description >= 50 chars)

### Validation Status

| Validation Type | Status | Test File |
|-----------------|--------|-----------|
| Structural (schema validation) | Active | `tests/test_golden_set_integrity.py` |
| Functional (scoring regression) | **Not implemented** | N/A |

The golden sets have `expected_band` fields but are currently only structurally validated (schema integrity, no duplicate IDs, valid categories, minimum description length). Functional validation — running actual scoring against golden sets and comparing to expected bands — is not yet implemented.

**Constraint from G-286 benchmark:** 15.7% variance observed across 120 A/B scoring calls. Any functional golden set tests must use wide enough bands to tolerate non-deterministic AI scoring. The benchmark showed strong-category jobs ranging from 4.2-9.2, so bands narrower than ~2 points would produce excessive false failures.

**Source:** `tests/fixtures/scoring_golden_set*.json`, `tests/test_golden_set_integrity.py`.

---

## 8. Scoring Feedback & Learning

### Feedback Types

| Direction | Type | Signal |
|-----------|------|--------|
| `too_high` | Explicit | User thinks AI overscored |
| `too_low` | Explicit | User thinks AI underscored |
| `correct` | Explicit | User confirms score is accurate |
| `implicit_positive` | Implicit | User promoted job (e.g., applied) |
| `implicit_negative` | Implicit | User dismissed job |
| `implicit_strong_positive` | Implicit | User reached interview stage |

### Calibration Pipeline

1. User submits explicit feedback with optional `user_score` (0-10) and `reason`
2. Feedback is stored in `ScoringFeedback` table with `original_fit_score` snapshot
3. When profile accumulates >= 10 explicit corrections (`CALIBRATION_MIN_FEEDBACK`), the system activates
4. At scoring time, `get_feedback_calibration()` selects top 5 corrections with largest |user_score - original_fit_score| deviation
5. These calibration examples are injected into the scoring prompt under "Scoring Calibration (user corrections on past scores — adjust accordingly)"
6. The AI model sees examples like: "Staff TPM @ Google: AI scored 6.5, user corrected to 8.5 (reason: strong domain match)"

### Bayesian Preference Learning

The preference learning service (`src/career_os/services/preference_learning.py`) generates weight adjustment suggestions:

1. Analyzes patterns in feedback (which dimensions are consistently over/under-scored)
2. Produces `WeightSuggestionResponse` for each dimension: current weight, suggested weight, confidence, reason
3. `SuggestionsResponse` includes readiness flag (enough feedback) and minimum feedback required
4. Active querying: when scoring a job, the system may suggest asking the user about dimensions with highest uncertainty

**Source:** `src/career_os/services/scoring.py` (lines 1608-1687), `src/career_os/services/preference_learning.py`.

---

## 9. Follow-up Tickets from G-286 Benchmark

7 tickets (G-294 through G-300) created from benchmark findings:

| Ticket | Title | Status | Impact |
|--------|-------|--------|--------|
| G-294 | JSON parse retry for malformed AI responses | Open | 15.8% baseline error rate was entirely JSON parse failures; retry with re-prompting could recover most |
| G-295 | Golden set expansion (finance + design domains) | Merged | Expanded from 1 tech-only fixture to 3 domain-specific fixtures |
| G-296 | Rubric v1.1 — sharpen dream boundary, add 7.5 example | Merged | Added calibration example at 7.5 to help AI distinguish strong from dream |
| G-297 | Raise vague_responsibilities threshold from 200 to 400 chars | Merged | 10 false positives in benchmark were vague_responsibilities on adequate descriptions |
| G-298 | User-facing scoring explainer | Merged | Published `docs/how-scoring-works.md` |
| G-299 | Benchmark artifact publication | Merged | Published PII-scrubbed benchmark results to `docs/research/` |
| G-300 | CareerOS <-> Kestrel feature sync | Open | Systematic alignment between private CLI and public platform |

**Source:** Linear project tracker (team G), benchmark analysis session 2026-04-15.

---

## 10. Scoring Implementation Details

### Scoring Flow (Single Job)

1. **Input validation:** verify profile, discovered_job, and application exist
2. **Profile completeness guard:** profile must have `job_family` and `location` set
3. **Context gathering:** profile data (skills, goals, market positioning) + scoring weights
4. **Calibration loading:** if feature flag enabled and >= 10 corrections exist
5. **Prompt assembly:** job description + profile context + rubric + modifiers + calibration
6. **AI scoring:** `provider.score()` returns `ScoreResult` with all fields
7. **Borderline 2-pass:** if score in borderline zone, second pass + averaging
8. **Red flag detection:** stateless rules + data-driven rules (ghost jobs, multi-city blast)
9. **Desire score computation:** AI-generated (priority) or derived from dimensional scores
10. **Persistence:** ScoredJob record + propagate fit_score to linked DiscoveredJob/Application
11. **Commit**

### Batch Scoring Flow

1. Query jobs to score (specific IDs, all unscored, or include stale)
2. **Embedding pre-filter:** compute similarities, optionally skip below-threshold jobs
3. Loop: score each job individually via `score_job()`
4. **Credit exhaustion handling:** if `CreditsExhaustedError` or `ProviderQuotaError`, stop batch gracefully
5. Return scored_count, total_time, scores, errors, credits_exhausted flag

### Stale Score Management

When scoring weights change or profile is updated:
1. All existing ScoredJob records for the profile are marked `is_stale = True`
2. Cached `fit_score` on linked DiscoveredJob and Application rows is nulled
3. Frontend displays stale indicator; user can re-score

**Source:** `src/career_os/services/scoring.py` (full file).

---

## Complete Source Index

### Internal Source Files

- `src/career_os/ai/base.py` — AIProvider abstract base class
- `src/career_os/ai/factory.py` — Provider factory and registry
- `src/career_os/ai/mock_provider.py` — Deterministic mock provider for testing
- `src/career_os/ai/openrouter_provider.py` — OpenRouter production provider
- `src/career_os/ai/anthropic_provider.py` — Direct Anthropic API provider
- `src/career_os/ai/ollama_provider.py` — Local Ollama provider
- `src/career_os/services/scoring.py` — Core scoring service (rubric, weights, scoring, feedback, calibration, completeness)
- `src/career_os/services/red_flags.py` — Rule-based red flag detection
- `src/career_os/services/embeddings.py` — Embedding computation and similarity
- `src/career_os/services/preference_learning.py` — Bayesian preference learning
- `src/career_os/services/skill_normalizer.py` — ESCO taxonomy skill normalization
- `src/career_os/services/warn_data.py` — WARN Act filing data access
- `src/career_os/schemas/scoring.py` — Pydantic schemas (ScoreRequest, ScoreResponse, DimensionalScores, RedFlag, Feedback, etc.)
- `src/career_os/schemas/ai.py` — AI response schemas (ScoreResult, DimensionalScores, ScoreBreakdownFactor, ATSKeyword)
- `src/career_os/models/scoring.py` — ScoredJob and ScoringFeedback ORM models
- `src/career_os/models/esco.py` — ESCO taxonomy ORM model

### Test Files

- `tests/test_golden_set_integrity.py` — Golden set structural validation
- `tests/fixtures/scoring_golden_set.json` — General tech golden set
- `tests/fixtures/scoring_golden_set_finance.json` — Finance domain golden set
- `tests/fixtures/scoring_golden_set_design.json` — Design domain golden set

### Documentation

- `docs/how-scoring-works.md` — User-facing scoring explainer (G-298)
- `docs/scoring-validation-report.md` — G-286 benchmark validation report
- `docs/research/benchmark-results-summary.json` — Raw benchmark data (JSON)

### Linear Tickets

- G-268: Scoring Evolution parent epic
- G-269 through G-279: Individual scoring evolution epics (all merged 2026-04-15)
- G-286: Benchmark validation run
- G-294 through G-300: Follow-up tickets from benchmark findings
- G-295: Golden set expansion (current branch)
- G-296: Rubric v1.1 dream boundary sharpening
- G-297: vague_responsibilities threshold adjustment

---

*Raw research data compiled from codebase analysis, G-286 benchmark results, and G-268 scoring evolution epics, 2026-04-16. No editorial filtering applied.*
