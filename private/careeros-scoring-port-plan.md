---
title: "CareerOS Scoring Port Plan"
date: 2026-04-16
ticket: G-303
---

# CareerOS Scoring Port Plan

## 1. Current State — What CareerOS Has Today

CareerOS (`~/Projects/CareerOS/`) has a functional scoring engine that shares the
same early architecture as Kestrel's M3 (Milestone 3) baseline. Both codebases
share the `career_os` package name and the same layered architecture.

### Scoring Service (`services/scoring.py`)

- **Single-job scoring** via `score_job()` — sends JD + profile context to AI, gets `ScoreResult`
- **Batch scoring** via `batch_score_discovery()` — iterates discovered jobs, calls `score_job` per job
- **Scoring weights** — 7 configurable weight factors (skills_match, career_alignment, culture_fit, salary_match, location_match, growth_potential, remote_preference) stored per-profile in `ScoringWeights` model
- **Job-family weight presets** — same 5 presets as Kestrel (TPM, SWE, Product Engineer, DevRel, AI Program Lead)
- **Stale score flagging** — `flag_stale_scores()` marks scores stale when weights/profile change
- **Market positioning data** injected into scoring prompt (VAL-CROSS-010)

### AI Schema (`schemas/ai.py`)

- `ScoreResult` with: fit_score, reasoning, estimated_salary, effort_flag, prep_level, prep_notes, readiness_score, career_alignment, score_breakdown (3+ factors)
- **No** DimensionalScores, ATSKeyword, desire_score, or desire_reasoning fields

### Data Model (`models/scoring.py`)

- `ScoringWeights` — identical to Kestrel's base version (7 weight columns)
- `ScoredJob` — stores fit_score, readiness_score, career_alignment, reasoning, estimated_salary, effort_flag, prep_level, prep_notes, score_breakdown (JSON), is_stale, weights_snapshot
- **No** ScoringFeedback model
- **No** columns for: red_flags, ats_keywords, desire_score, desire_score_method, desire_reasoning, dim_* (dimensional scores), scoring_passes

### API (`api/scoring.py`)

- `POST /api/score` — single job scoring
- `GET /api/scoring-weights` / `PUT /api/scoring-weights`
- `POST /api/score/batch`
- `GET /api/score/job/{id}` / `GET /api/score/application/{id}`
- `POST /api/scoring/flag-stale`
- **No** feedback endpoints, no score context/percentile endpoints

### AI Provider (`ai/openrouter_provider.py`)

- Uses OpenRouter API with Claude Sonnet 4 default
- Basic JSON parsing (code-fence stripping) — **no** retry logic on structured parse failure
- **No** `CreditsExhaustedError` handling
- **No** `_extract_first_json_object()` brace-depth parser
- Score prompt requests only basic fields (no dimensional_scores, no ats_keywords, no desire_score)

### CLI (`cli/main.py`)

- `career score <url>` command — scores a single URL against profile
- Pipeline listing shows fit_score column
- Discovery ranking by fit_score
- JSON and table output modes for score results
- **No** red flags, dimensional scores, or desire score in output

### What CareerOS Does NOT Have

| Feature | Kestrel Status | CareerOS Status |
|---------|---------------|-----------------|
| Scoring rubric (SCORING_RUBRIC, calibration examples) | Shipped (G-269) | Missing |
| 6 dimensional sub-scores (technical_fit, seniority_alignment, etc.) | Shipped (G-269) | Missing |
| ATS keyword extraction (10-15 keywords, categorized, matched) | Shipped (G-269) | Missing |
| Dual-score architecture (fit_score + desire_score) | Shipped (G-275) | Missing |
| Red flag detection (10 rule-based rules) | Shipped (G-270) | Missing |
| Ghost job detection (DB-driven) | Shipped (G-270) | Missing |
| Multi-city blast detection | Shipped (G-270) | Missing |
| WARN Act layoff integration | Shipped (G-277) | Missing |
| User feedback loop (explicit + implicit) | Shipped (G-274) | Missing |
| Feedback calibration (injected into prompt) | Shipped (G-274) | Missing |
| Score context & percentiles | Shipped (G-271) | Missing |
| Profile completeness scoring | Shipped (G-278) | Missing |
| Borderline 2-pass scoring | Shipped (G-273) | Missing |
| Embedding pre-filter (batch scoring) | Shipped (G-272) | Missing |
| AI provider retry logic (structured parse) | Shipped | Missing |
| CreditsExhaustedError handling | Shipped | Missing |
| ProfileIncompleteError guard | Shipped | Missing |
| ESCO skill taxonomy normalization | Shipped (G-276) | Missing |

## 2. What to Port — Feature-by-Feature

### Phase 1: Core Scoring Upgrades (Foundation)

| # | Feature | Effort | Description |
|---|---------|--------|-------------|
| 1.1 | Scoring rubric + calibration examples | **S** | Copy `SCORING_RUBRIC` constant and `_build_job_family_modifiers()` into CareerOS scoring service. Add rubric to `_build_scoring_prompt()`. |
| 1.2 | DimensionalScores schema | **S** | Add `DimensionalScores` model to `schemas/ai.py`, add 6 `dim_*` columns to `ScoredJob` model. Alembic migration. |
| 1.3 | ATS keywords schema | **S** | Add `ATSKeyword` and `ATSKeywordCategory` to `schemas/ai.py`, add `ats_keywords` column to `ScoredJob`. Migration. |
| 1.4 | Update AI provider score prompt | **M** | Update `OpenRouterProvider.score()` and `_system_prompt_for_feature()` to request dimensional_scores, ats_keywords, desire_score. |
| 1.5 | AI provider retry logic | **M** | Port `max_retries` parameter, `_extract_first_json_object()` brace-depth parser, trailing comma stripping, retry on structured parse failure. |
| 1.6 | CreditsExhaustedError | **S** | Port `CreditsExhaustedError` class and HTTP 402/429 handling in provider. |
| 1.7 | ProfileIncompleteError guard | **S** | Add guard in `score_job()` and `batch_score_discovery()` for missing job_family/location. |

### Phase 2: Red Flags & Detection

| # | Feature | Effort | Description |
|---|---------|--------|-------------|
| 2.1 | Red flags service | **L** | Port entire `services/red_flags.py` (10 rule-based rules: stale posting, unrealistic requirements, turnover language, missing salary, staffing agency, vague responsibilities, excessive requirements). |
| 2.2 | Ghost job detection | **M** | Port `detect_data_driven_red_flags()`, `normalize_job_title()`, `normalize_company_name()`, `_detect_ghost_job_signals()`, `_detect_multi_city_blast()`. Requires `company_normalized` / `title_normalized` columns on DiscoveredJob. |
| 2.3 | WARN Act integration | **M** | Port `_detect_recent_layoffs()` + `services/warn_data.py`. Requires `warn_filings` table + model. |
| 2.4 | Red flags in scoring | **S** | Wire red flag detection into `score_job()`, add `red_flags` column to `ScoredJob`. |

### Phase 3: Dual-Score Architecture

| # | Feature | Effort | Description |
|---|---------|--------|-------------|
| 3.1 | Desire score (AI-generated + derived) | **M** | Port `compute_derived_desire_score()`, `_resolve_desire_weights()`, `DEFAULT_DESIRE_WEIGHTS`, `_GOAL_WEIGHT_ADJUSTMENTS`. Add desire_score/desire_score_method/desire_reasoning columns. |
| 3.2 | Update ScoreResult schema | **S** | Add `desire_score`, `desire_reasoning` to `ScoreResult`. |
| 3.3 | Desire score in scoring flow | **S** | Wire AI-generated (Option B) and derived (Option A fallback) into `score_job()`. |

### Phase 4: Feedback & Calibration

| # | Feature | Effort | Description |
|---|---------|--------|-------------|
| 4.1 | ScoringFeedback model | **S** | Port `ScoringFeedback` ORM model. Alembic migration. |
| 4.2 | Feedback CRUD | **M** | Port `submit_feedback()`, `record_implicit_feedback()`, `list_feedback()`, `get_feedback_stats()`. |
| 4.3 | Feedback calibration | **M** | Port `get_feedback_calibration()`, `CALIBRATION_MIN_FEEDBACK`, `CALIBRATION_MAX_EXAMPLES`, and `_format_calibration_section()`. Wire into scoring prompt. |
| 4.4 | Feedback API endpoints | **M** | Port API routes for feedback submission, listing, stats. |

### Phase 5: Advanced Scoring

| # | Feature | Effort | Description |
|---|---------|--------|-------------|
| 5.1 | Borderline 2-pass scoring | **M** | Port `_average_score_results()`, borderline zone detection logic, `scoring_passes` column. Add `borderline_scoring_enabled` / threshold settings. |
| 5.2 | Embedding pre-filter | **L** | Port embedding similarity pre-filter for batch scoring. Requires embeddings service integration. |
| 5.3 | Score context & percentiles | **M** | Port `compute_score_context()`, `score_to_letter_grade()`, percentile/rank computation. |
| 5.4 | Profile completeness scoring | **M** | Port `compute_profile_completeness()`, `apply_confidence_range()`, completeness weights. |

### Phase 6: CLI Integration

| # | Feature | Effort | Description |
|---|---------|--------|-------------|
| 6.1 | Red flags in CLI output | **S** | Add red flag display to `_score_output_table()` and `_score_output_json()`. |
| 6.2 | Dimensional scores in CLI | **S** | Show 6 dimensional sub-scores in score breakdown panel. |
| 6.3 | Desire score in CLI | **S** | Show desire score alongside fit score in pipeline and score views. |
| 6.4 | Score context in CLI | **S** | Show percentile/rank context when available. |

## 3. Architecture Gaps

### Data Model Differences

| Gap | Impact | Resolution |
|-----|--------|------------|
| `ScoredJob` missing 12 columns | Must add: red_flags, ats_keywords, desire_score, desire_score_method, desire_reasoning, dim_technical_fit, dim_seniority_alignment, dim_compensation_fit, dim_location_fit, dim_career_trajectory, dim_company_fit, scoring_passes | Single Alembic migration adding all nullable columns |
| No `ScoringFeedback` table | New table required | Alembic migration |
| `DiscoveredJob` missing normalized columns | Ghost job detection needs `company_normalized`, `title_normalized` | Alembic migration + backfill |
| No `warn_filings` table | WARN Act feature needs it | Alembic migration + data import service |

### AI Provider Differences

| Gap | Impact | Resolution |
|-----|--------|------------|
| No retry on structured parse failure | Scores silently return None for structured data | Port `max_retries` parameter and retry loop |
| No brace-depth JSON extractor | Provider fails on LLM responses with surrounding text | Port `_extract_first_json_object()` |
| No credits exhaustion handling | Batch scoring doesn't stop gracefully when credits run out | Port `CreditsExhaustedError` and break-on-exhaust logic |
| Score prompt much simpler | Missing dimensional, ATS, desire instructions | Update both user prompt and system prompt |

### Configuration Differences

| Gap | Impact | Resolution |
|-----|--------|------------|
| No feature flags for borderline/embedding/calibration | Features can't be toggled | Add to CareerOS config/settings |
| No `RUBRIC_VERSION` tracking | Can't track which rubric version scored a job | Add to weights_snapshot JSON |

### No Web Frontend Consideration

CareerOS is CLI-only. There are no API response schema changes needed for frontend
consumption. All new fields (dimensional scores, red flags, desire score, etc.) only need
to be surfaced in CLI output and stored in the database.

## 4. Porting Order (Recommended Sequence)

```
Phase 1: Core Scoring Upgrades          ← Foundation, everything depends on this
  ├── 1.6 CreditsExhaustedError         (standalone, quick win)
  ├── 1.7 ProfileIncompleteError        (standalone, quick win)
  ├── 1.5 AI provider retry logic       (improves reliability for all subsequent phases)
  ├── 1.2 DimensionalScores schema      (needed by Phase 3)
  ├── 1.3 ATS keywords schema           (needed by Phase 2 red flags)
  ├── 1.4 Update AI provider prompts    (depends on 1.2, 1.3)
  └── 1.1 Scoring rubric                (improves quality for all subsequent scoring)

Phase 2: Red Flags & Detection           ← High user value, no AI cost
  ├── 2.1 Red flags service             (standalone module)
  ├── 2.4 Red flags in scoring          (depends on 2.1)
  ├── 2.2 Ghost job detection           (depends on normalized columns)
  └── 2.3 WARN Act integration          (optional, US-only)

Phase 3: Dual-Score Architecture         ← Depends on Phase 1 dimensional scores
  ├── 3.2 Update ScoreResult schema
  ├── 3.1 Desire score logic
  └── 3.3 Wire into scoring flow

Phase 4: Feedback & Calibration          ← Depends on Phase 1 rubric
  ├── 4.1 ScoringFeedback model
  ├── 4.2 Feedback CRUD
  ├── 4.4 Feedback API endpoints
  └── 4.3 Feedback calibration          (depends on 4.2, needs enough data)

Phase 5: Advanced Scoring                ← Depends on all above
  ├── 5.3 Score context & percentiles   (standalone query logic)
  ├── 5.4 Profile completeness          (standalone)
  ├── 5.1 Borderline 2-pass scoring     (depends on Phase 1)
  └── 5.2 Embedding pre-filter          (most complex, defer to last)

Phase 6: CLI Integration                 ← After each phase ships
  └── 6.1–6.4 incremental CLI updates
```

## 5. Files to Create/Modify in CareerOS

### New Files

| File | Purpose |
|------|---------|
| `src/career_os/services/red_flags.py` | Rule-based red flag detection (port from Kestrel) |
| `src/career_os/services/warn_data.py` | WARN Act filing lookup service |
| `src/career_os/services/embeddings.py` | Embedding similarity service (Phase 5) |
| `alembic/versions/xxx_add_scoring_v2_columns.py` | Migration: add 12 columns to scored_jobs |
| `alembic/versions/xxx_add_scoring_feedback.py` | Migration: create scoring_feedback table |
| `alembic/versions/xxx_add_discovery_normalized.py` | Migration: add company_normalized, title_normalized to discovered_jobs |
| `alembic/versions/xxx_add_warn_filings.py` | Migration: create warn_filings table |
| `tests/test_red_flags.py` | Red flag detection tests |
| `tests/test_ghost_jobs.py` | Ghost job detection tests |
| `tests/test_scoring_feedback.py` | Feedback CRUD tests |
| `tests/test_scoring_v2.py` | Tests for new scoring features (rubric, dimensions, desire) |

### Modified Files

| File | Changes |
|------|---------|
| `src/career_os/schemas/ai.py` | Add DimensionalScores, ATSKeyword, ATSKeywordCategory; extend ScoreResult with desire_score, desire_reasoning, dimensional_scores, ats_keywords |
| `src/career_os/schemas/scoring.py` | Add desire_score to ScoreResponse; add score_to_letter_grade(); add feedback schemas; add score context schemas |
| `src/career_os/models/scoring.py` | Add 12 columns to ScoredJob; add ScoringFeedback model |
| `src/career_os/services/scoring.py` | Add SCORING_RUBRIC, rubric injection, red flag wiring, desire score computation, feedback CRUD, calibration, borderline 2-pass, score context, profile completeness |
| `src/career_os/ai/openrouter_provider.py` | Add retry logic, CreditsExhaustedError, brace-depth JSON extractor, updated score/system prompts |
| `src/career_os/api/scoring.py` | Add feedback endpoints, score context endpoint, profile completeness endpoint |
| `src/career_os/cli/main.py` | Update score output to show red flags, dimensional scores, desire score, percentiles |
| `src/career_os/config.py` | Add feature flags: borderline_scoring_enabled, embedding_prefilter_enabled, feedback_calibration_enabled, threshold values |
| `src/career_os/models/discovery.py` | Add company_normalized, title_normalized columns |

## 6. Estimated Total Effort

| Phase | Items | Effort |
|-------|-------|--------|
| Phase 1: Core Scoring | 7 | ~3 days |
| Phase 2: Red Flags | 4 | ~3 days |
| Phase 3: Dual-Score | 3 | ~1 day |
| Phase 4: Feedback | 4 | ~2 days |
| Phase 5: Advanced | 4 | ~3 days |
| Phase 6: CLI | 4 | ~1 day |
| **Total** | **26 items** | **~13 days** |

Notes:
- Effort assumes AI-assisted development (Claude Code).
- Each phase is independently shippable and testable.
- Phase 2.3 (WARN Act) and Phase 5.2 (embedding pre-filter) are optional/deferrable.
- Without optional items, core effort drops to ~10 days.
- All phases require corresponding test files (included in estimates).
