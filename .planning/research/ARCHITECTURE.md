# Architecture Research: Kestrel v2.0 "Lean Kestrel"

**Domain:** Self-hosted job-search engine (headless scan + triage + drafting), integrated into an existing layered FastAPI/SQLAlchemy/SQLite app
**Researched:** 2026-10-24
**Confidence:** HIGH for integration points and file/function references (read from the code at branch `G-2013/v2-lean-milestone`). MEDIUM for provider-specific HTTP semantics (402 vs 429 per vendor, not verified against vendor docs) and for Textual/MCP threading details (library behaviour, not re-verified here). Versions belong to STACK.md.

Scope note: this document covers only the eleven v2.0 features. It does not redesign the existing layers (api -> services -> models -> database, `ai/` factory + fallback, `discovery/`, `services/geo/`, Typer CLI, WXT extension, parked React app). Every item is marked **new** or **modified**.

---

## 1. Key architectural decisions (read this first)

1. **One pipeline, sequenced in one place.** `services/discovery.py::run_discovery` is already the single sequencer (called by `POST /api/discover`, CLI `kestrel discover`, and the scheduler via `run_scheduled_discovery`). `kestrel scan` is a thin CLI wrapper around the same function, not a second orchestrator. Do not create `services/scan.py` next to it. The new stages (dedup, assess, preflight, spend guard) are modules `run_discovery` calls.
2. **`assess()` is a pure function in a new `services/assess.py`.** `discovery/prefilter.py::run_prefilter` becomes a loop over `assess()` (same signature, same `PrefilterMetrics`), so the existing prefilter tests are the regression net for the refactor. Geo wiring is a later, separate step.
3. **Persist every arrival, including excluded ones.** Today `run_discovery` filters with `run_prefilter` and then rebuilds `dedup_groups` from only the survivors (lines ~511-522), so excluded jobs are never written and cannot be audited. v2.0 inverts this: write the row first, attach the verdict, then gate scoring and pipeline promotion on the verdict.
4. **Never promote an excluded job into `applications`.** `_create_discovered_job` unconditionally calls `promote_discovered_job_to_application(...)` for every new row. With persisted exclusions that would flood the pipeline. Promotion becomes conditional on `assess_verdict != "exclude"` (and, for scan, on shortlist score; see open decision D1).
5. **Spend safety lives at the one true choke point: `get_ai_provider()`.** It has 12+ production callers (scoring, discovery, extension_capture, goals, embeddings, voice, interview_prep, company_research, role_intelligence, batch API, shadow scoring). A `SpendGuardProvider` wrapper returned from both branches of `get_ai_provider()` makes the halt an invariant instead of a convention.
6. **402 and 429 are separated by exception class, added to the existing hierarchy.** Today `ProviderQuotaError` is raised for `status_code in (402, 429)` at 13 sites across 9 provider files (anthropic, openai, openrouter, together, groq, xai, mistral, huggingface, gemini). New subclasses keep every current `except ProviderQuotaError` compiling, while the three sites that must behave differently are updated.
7. **CLI, TUI and MCP are three leaf adapters over `services/`.** Today `cli/main.py` embeds ORM queries and business logic (`pipeline_list`, `pipeline_stats`, `_compute_pipeline_stats`, `pipeline_follow_ups`, `_validate_status_transition`, `_apply_notes_update`). That logic moves into `services/` first; the TUI and MCP never import from `cli/`.
8. **Outcome states are a separate axis, not new `ApplicationStatus` values.** `ApplicationStatus`/`VALID_TRANSITIONS` (in `schemas/applications.py`) drive the Kanban board, analytics funnel, startup normalisation and the extension. Add `Application.submission_state` plus an `application_outcomes` event table instead.
9. **The dossier is files on disk (human-readable, git-able) with a DB version index.** A draft records the `dossier_version_id` it was checked against. Gates are deterministic and LLM-free, so the MCP server can offer `check_draft` at zero spend.
10. **"Port, replay-verify, delete" is a per-script ledger with a differential test and a frozen golden file**, modelled on the geo precedent already in the repo (`tests/eval/geo/`: frozen `reference_assignments.json`, `replay.py`, 277/277 gate). Deletion is a separate PR from the port.

---

## 2. Standard Architecture

### System overview

```
 ENTRY POINTS (leaf adapters, no business logic)
 ┌───────────────┬───────────────┬───────────────┬───────────────┬───────────────┐
 │ kestrel scan  │ kestrel CLI   │ kestrel tui   │ kestrel mcp   │ FastAPI app   │
 │ (cron/launchd)│ cli/*.py      │ tui/ (new)    │ mcp_server.py │ main.py + api/│
 │ cli/scan.py   │ Rich output   │ Textual       │ stdio, FastMCP│ + scheduler   │
 └───────┬───────┴───────┬───────┴───────┬───────┴───────┬───────┴───────┬───────┘
         │               │               │               │               │
         ▼               ▼               ▼               ▼               ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ bootstrap.py (new): ensure_schema() [moved from main._auto_migrate],        │
 │ open_session(), resolve_profile_id(), config/dossier dir resolution         │
 └───────────────────────────────────┬─────────────────────────────────────────┘
                                     ▼
 SERVICE LAYER (module-level functions + domain exceptions; the only place logic lives)
 ┌────────────────────────────────────────────────────────────────────────────┐
 │ discovery.run_discovery  (sequencer, modified)                             │
 │   ├─ discovery/ats.py (new) + adapters.py (modified)  FETCH                │
 │   ├─ dedup.py (new)                                   DEDUP                │
 │   ├─ assess.py (new) -> services/geo/* (unchanged)    ASSESS               │
 │   ├─ ai_health.preflight + ai/spend_guard.py          SAFE TO SPEND?       │
 │   ├─ scoring.batch_score_discovery (modified)         SCORE                │
 │   └─ triage.py (new) + audit.py (new)                 SHORTLIST/DIGEST     │
 │ applications.py / follow_ups.py (modified) + outcomes.py (new)  TRACK      │
 │ dossier.py + gates.py + drafting.py (new)                       WRITE      │
 └───────┬───────────────────────────────┬──────────────────────────┬─────────┘
         ▼                               ▼                          ▼
 ┌──────────────────┐         ┌────────────────────────┐  ┌──────────────────────┐
 │ ai/ factory ->   │         │ models/ + Alembic      │  │ files on disk        │
 │ SpendGuard ->    │         │ SQLite WAL (data/)     │  │ config/*.yaml        │
 │ Fallback ->      │         │ discovered_jobs, ...   │  │ data/dossier/*       │
 │ providers        │         └────────────────────────┘  └──────────────────────┘
 └──────────────────┘
```

### Component responsibilities

| Component | Status | Responsibility | Lives in |
|-----------|--------|----------------|----------|
| Process bootstrap | **new** | Run migrations, open a session, pick the profile, find config/dossier dirs. The same for scan, TUI, MCP. | `src/career_os/bootstrap.py` |
| Sequencer | **modified** | Fetch -> dedup -> persist -> assess -> preflight -> score -> promote. One code path for API, scheduler, cron. | `services/discovery.py::run_discovery`, `run_scheduled_discovery` |
| ATS adapters + liveness | **new** | Greenhouse/Lever/Ashby fetch, authoritative offices, URL -> ATS re-resolution, liveness check. | `discovery/ats.py` |
| Scan config | **new** | Load `companies`, `geo`, `sources` (floors/enabled), `blocklist` YAML into typed objects; build `GeoProfile`. | `discovery/scan_config.py` |
| Eligibility engine | **new** | `assess(job, ctx) -> Assessment`. Pure. Composes blocklist, keyword/role signals, industry blacklist, geo (`geo_eligibility`), dream-tier flags. | `services/assess.py` |
| Geo engine | unchanged | 7-way classifier, `GeoProfile`, presets. | `services/geo/` |
| Dedup | **new** | Normalisation, fuzzy match, repost fingerprint, in-batch and history matching. Pure plus one indexed lookup. | `services/dedup.py` |
| Cost safety | **modified + new** | 402/429 taxonomy in `ai/base.py`; wait-on-429 in `ai/fallback.py`; `SpendGuardProvider`; preflight in `services/ai_health.py`. | `ai/base.py`, `ai/fallback.py`, `ai/spend_guard.py` (new), `services/ai_health.py` |
| Triage + digest | **new** | Shortlist query, dismiss, due follow-ups, digest build/render. Shared by CLI, TUI, MCP. | `services/triage.py` |
| Exclusion audit | **new** | Stratified sample of excluded jobs with recorded inclusion probabilities, judge/overturn, export regression fixture. | `services/audit.py` |
| Outcomes | **new** | Submission state machine, outcome events, ingestion, feeds `scoring.record_implicit_feedback`. | `services/outcomes.py` |
| Dossier | **new** | Load facts/preferences/samples from files, hash, version, expose to drafting. | `services/dossier.py` |
| Gates | **new** | `fact_gate`, `voice_gate`: deterministic checks of draft text. | `services/gates.py` |
| Drafting | **new** | Build context pack, call provider, loop through gates, persist draft. | `services/drafting.py` |
| TUI | **new** | Textual screens over services. | `src/career_os/tui/` |
| MCP server | **new** | Stdio MCP tools over services. | `src/career_os/mcp_server.py` |

---

## 3. Integration points: existing modules that change

All paths relative to `src/career_os/`. "Phase" refers to section 12.

| Module | Status | Change | Why (grounding) |
|--------|--------|--------|-----------------|
| `main.py` | modified | Move `_auto_migrate`, `_resolve_alembic_ini`, `_alembic_ini_candidates` to `bootstrap.py`; import them back. Gate `start_scheduler()` on `settings.scheduler_enabled`. Remove routers/imports for pushover, ticktick, calendar, (integrations/oauth: see D3). Remove `start_ticktick_scheduler`. | `_auto_migrate` is private to `main.py`; a cron process has no FastAPI lifespan, so `kestrel scan` would run on an unmigrated DB. |
| `config.py` | modified | `host` default `0.0.0.0` -> `127.0.0.1` (G-2009; also `cli/main.py::start` option and `Dockerfile` CMD). Add: `scheduler_enabled`, `daily_spend_limit_usd`, `scoring_max_failure_rate`, `config_dir`, `dossier_dir`, `scan_lock_ttl_seconds`, `audit_sample_size`, `shortlist_min_score`. Remove pushover/ticktick settings. | Settings is the existing flag mechanism (all new behaviour ships behind `Settings` flags). `database_url = "sqlite:///data/career_os.db"` and `env_file=".env"` are CWD-relative: see pitfall in section 5.3. |
| `database.py` | modified | Add `PRAGMA busy_timeout` to `_set_sqlite_pragmas`. | Cron scan and API server write the same SQLite file; WAL allows concurrent readers but not writers. |
| `discovery/adapters.py` | modified | `RawJobResult` gains `external_id`, `ats`, `ats_slug`, `offices: list[str]` (all defaulted). Register ATS adapters in `ADAPTER_REGISTRY`. | `RawJobResult` has no id/offices fields today; `ADAPTER_REGISTRY` is the extension point (`arbeitsagentur`, `arbeitnow`, `jobspy`). |
| `discovery/prefilter.py` | modified | `run_prefilter` delegates per job to `assess()`; the inline `geo_eligibility` block is deleted; docstring NOTE ("annotation does not currently reach DiscoveredJob persistence") is resolved. | Single authority; this is the "prefilter" consumer of `assess()`. |
| `discovery/scheduler.py` | modified | `_run_sweep` keeps calling `run_scheduled_discovery`; add run-lock check and `scheduler_enabled`. | Already the same function the CLI/API reach; only lifecycle changes. |
| `services/discovery.py` | modified | Restructure `run_discovery`: persist all arrivals; replace `_dedup_key`/`_dedup_and_filter` with `dedup.py`; `_build_prefilter_config` resolves a `GeoProfile` per `SearchProfile`; `_create_discovered_job` writes `geo_class`/verdict; promote only non-excluded; call preflight before `_auto_score_and_refresh`. Expose a public `persist_arrival()` (see next row). `run_scheduled_discovery(..., force=False)` so `kestrel scan` can bypass `next_run` gating. | `_build_prefilter_config` never sets `geo_profile`, so the gate is dead code in production today. |
| `services/extension_capture.py` | modified | `_find_or_create_discovered_job` calls the shared `persist_arrival()` instead of its own insert. | Second creator of `DiscoveredJob`; without this, captured jobs bypass dedup and assess. |
| `models/discovery.py` | modified | New columns on `DiscoveredJob`; new `DiscoveryRun` columns (section 8). Keep `uq_discovered_job_dedup` untouched. | Changing a SQLite unique constraint needs a table rebuild and buys nothing. |
| `schemas/discovery.py` | modified | `DiscoveredJobResponse` adds `geo_class`, `assess_verdict`, `duplicate_of_id`, `liveness`. | Frontend/extension get the verdict for free; additive. |
| `services/scoring.py` | modified | `_query_jobs_to_score`: exclude `assess_verdict == "exclude"`, `duplicate_of_id IS NOT NULL`, `liveness == "closed"`. `batch_score_discovery` (the `except (CreditsExhaustedError, ProviderQuotaError)` at ~3937 currently sets `credits_exhausted=True; break`): split into 402 -> halt batch, 429 -> bounded wait and retry the job. | A 429 currently aborts the whole batch and is reported as "credits exhausted". |
| `services/scoring_calibration.py` | modified | In `apply_calibration_and_gate` (the "gate has the last word" tail) cap fit for `geo_class == "foreign"` jobs and set a review flag. | Matches the existing role-fit gate placement; avoids reordering the scoring pipeline. Cap rule must follow RULE-01 (over-admission) when that is decided. |
| `ai/base.py` | modified | Add `ProviderCreditsExhaustedError(ProviderQuotaError)` (402) and `ProviderRateLimitedError(ProviderQuotaError)` (429, `retry_after`). Add `AIProvider._raise_for_quota(response)` helper. | One helper replaces 13 inline `if status in (402, 429)` blocks. |
| `ai/*_provider.py` (9 files) | modified | Replace inline 402/429 blocks (anthropic x3, openai x3, openrouter, together, groq, xai, mistral, huggingface; gemini handles only 429 and raises `ProviderUnavailableError` for other >=400) with `self._raise_for_quota(response)`. | Mechanical; one commit per few providers. |
| `ai/openrouter_provider.py` | modified | `CreditsExhaustedError` re-parented onto `ProviderCreditsExhaustedError` (name kept so `api/scoring.py`, `api/extension.py`, `services/scoring.py` imports survive). | Avoids a name collision with the new base-class error. |
| `ai/fallback.py` | modified | `_try_chain`: on `ProviderRateLimitedError` wait `min(retry_after, cap)` and retry the same leg up to N times before moving on; on `ProviderCreditsExhaustedError` mark the leg exhausted for the process and move on; never swallow `SpendLimitExceededError` (it must not subclass `ProviderQuotaError`). | Today the chain treats 402 and 429 identically and escalates immediately. |
| `ai/factory.py` | modified | Wrap the result of `get_ai_provider()` in `SpendGuardProvider` on both branches (fallback chain and single provider). `mock` is exempt. | Choke point. |
| `ai/observability.py` | modified | Expose a process-local running spend total next to `log_usage`; extend `_MODEL_PRICING` (Mistral models fall to the Sonnet-class default today, which over-estimates and makes a halt trip early). | `log_usage` writes `ai_usage_log` fire-and-forget in an executor, so the DB sum lags; the guard needs an in-process counter plus the DB sum at start. |
| `services/ai_health.py` | modified | Add `preflight(required: list[str]) -> PreflightReport` over `check_single_provider`; providers without a cheap probe report `unverified (key present)` rather than a fake OK. | `check_all_providers` exists but only probes mock/openrouter/anthropic/ollama. |
| `schemas/applications.py` + `services/applications.py` | modified | Add `SUBMISSION_STATES`/`SUBMISSION_TRANSITIONS`; `update_application` unchanged for `status`. Guard: moving `status` to `applied` via MCP/TUI requires a confirmed submission or an explicit override flag. | Keeps `VALID_TRANSITIONS` and the Kanban untouched. |
| `services/follow_ups.py`, `services/applications.py`, `services/goals.py` | modified | Remove `try_auto_push_*` (TickTick) and calendar-event hooks. `goals.py` line 10 imports `ticktick_sync` at module top level; the others are lazy imports inside functions. | Must be removed before TickTick modules are deleted (import errors otherwise). |
| `services/analytics.py` | modified | Delete `_compute_notification_metrics` (lazy-imports `models.pushover.NotificationLog`) and `NotificationMetrics` from `schemas/analytics.py`; frontend `Analytics.tsx`/types need the field made optional first. | Hidden Pushover coupling. |
| `services/drift_canary.py`, `cli/scoring.py` | modified | Remove `send_drift_alert` call and `--notify`; result already carries `alert`/`reason`; surface in digest and exit code. | Pushover decoupling. |
| `api/scoring.py` | modified | Remove `send_credits_exhausted_alert` import and call; `BatchScoreResponse` already returns `credits_exhausted`. | Pushover decoupling. |
| `api/extension.py` | modified | `from career_os.api.oauth import limiter` -> import from a neutral module (`middleware.py`); later: prefill route calls `drafting`/`gates`. | Deleting/trimming `api/oauth.py` would otherwise break the extension router. |
| `cli/main.py` | modified | Replace direct `db.query(Application|FollowUp)` in `pipeline_list`/`pipeline_stats`/`pipeline_follow_ups` and the helper logic with service calls; `_get_default_profile` (hardcoded `Profile.id == 1`) -> `bootstrap.resolve_profile_id`. Keep `_get_session()` as the test patch seam (tests patch it). Register `scan`, `digest`, `assess`, `tui`, `mcp`, `dossier`, `draft`, `outcome` commands from new modules. | The TUI cannot reuse code that prints with Rich. |
| `models/__init__.py`, `schemas/integrations.py` | modified | Drop pushover/ticktick/calendar exports and the Pushover entry in the integration catalogue. **Keep `IntegrationConfig`** (see D3). | `ai/factory.py::_read_credential_from_db` reads `integration_configs` (`name="ai_providers"`) directly via sqlite3; `services/ai_health.py` also reads it. |
| `pyproject.toml` | modified | Add `textual` (core or extra, see D4), declare `pyyaml` explicitly (tools import `yaml`; today it is only a transitive of `uvicorn[standard]`, to be verified). Remove `icalendar` (calendar only) once calendar is deleted. Keep `mcp` extra. | Declared-dependency hygiene for the 15-minute install. |
| `.github/workflows/ci.yml` | modified | The "Run tool-script tests" step (`pip install -e ".[mcp]"; pytest tools/tests/`) shrinks with each deletion and is removed at the end. | tools/ tests are a separate CI gate today. |

---

## 4. New components (and why each is a new file)

| Path (under `src/career_os/`) | Kind | Purpose | Why not an existing module |
|-------------------------------|------|---------|----------------------------|
| `bootstrap.py` | module | `ensure_schema()`, `open_session()`, `resolve_profile_id()`, `config_dir()` | Three non-API entry points (scan, TUI, MCP) need identical startup; today it is stranded in `main.py` and `cli/main.py::_get_default_profile`. |
| `discovery/ats.py` | module (~400-500 lines) | Greenhouse/Lever/Ashby adapters, `parse_greenhouse_url`/`parse_ashby_url`, `fetch_*_offices`, `resolve_posting(url)`, `check_liveness(job)` | `adapters.py` is already 781 lines and its adapters are keyword-search scrapers; ATS boards are company-list fetchers with per-job office lookups. Ports `tools/tier0_ats_poller.py` + the fetch half of `tools/batch_probe.py`. |
| `discovery/scan_config.py` | module | Typed loaders for `companies.yaml`, `geo.yaml`, `scan-sources.yaml`, `blocklist.yaml`; source classification (`ok/DISABLED/BLOCKED/BELOW-FLOOR/ZERO`) | The four YAML files already exist as `config/*.example.yaml` and are the contract with the maintainer's private repo ("config, data, private plugins"). Ports `tools/source_registry.py` + `tools/blocklist.py` loaders. |
| `services/assess.py` | module (pure) | `assess()`; `Assessment`, `Reason` | The one eligibility engine. Must not import SQLAlchemy. |
| `services/dedup.py` | module | `normalize_company/title`, `job_key`, `fuzzy_ratio`, `repost_fingerprint`, `dedup_batch`, `match_history` | Ports `tools/normalize.py`; replaces `services/discovery.py::_normalize/_dedup_key`. `rapidfuzz` is already a dependency, so use it instead of the script's `difflib`. |
| `ai/spend_guard.py` | module | `SpendGuardProvider`, `SpendLimitExceededError` | Wrapper around `AIProvider`; keeps `factory.py` small. |
| `services/triage.py` | module | `shortlist()`, `dismiss()`, `due_followups()`, `build_digest()`, `render_digest()` | The query behind the digest is exactly the TUI shortlist; one home for "what needs my attention". |
| `services/audit.py` | module | Stratified audit sampling with recorded inclusion probabilities, `judge()`, `overturn()`, `export_fixture()` | Statistical logic ported from `tools/build_label_set.py` (strata, repeat items, hidden filter fields) and `tools/calibrate.py` (weighted precision/recall). |
| `services/outcomes.py` | module | `advance_submission()`, `record_outcome()`, `ingest_outcomes()` | New table plus a state machine; do not bloat the 340-line `services/applications.py`. |
| `services/dossier.py` | module | Load dossier files, hash, snapshot to `dossier_versions` | New concept. |
| `services/gates.py` | module (pure) | `fact_gate(text, dossier)`, `voice_gate(text, dossier)` | Pure and shared by drafting, extension prefill and MCP `check_draft`. |
| `services/drafting.py` | module | `build_context()`, `draft()`, `answer_question()` | `services/voice.py` is chat-session code (modes `cover_letter`/`coaching`/`job_evaluation`); leave it alone. Naming warning: "voice" already means chat sessions; the new gate is `voice_gate` in `gates.py`. |
| `tui/` | package (`__init__.py`, `app.py`, `screens.py`) | Textual app | Must be isolated so `import career_os` never imports Textual. |
| `mcp_server.py` | module | FastMCP stdio server | Not named `mcp/` on purpose: a sub-package called `mcp` shadows the PyPI `mcp` import when run as a script. Replaces `tools/kestrel-mcp/server.py` (which proxies the REST API; the new one calls services in-process). |
| `cli/scan.py`, `cli/write.py` | CLI modules | `scan`, `digest`, `assess replay/backfill/probe`, `overturn`; `dossier`, `draft`, `outcome` | Follows the existing pattern (`cli/doctor.py`, `cli/init.py`, `cli/extension.py`). `cli/main.py` is already 2,384 lines. |

Considered and rejected as new packages: a `usecases/` layer (services already are it); a `scan.py` orchestrator (duplicates `run_discovery`); a plugin framework for sources (the `ADAPTER_REGISTRY` dict is enough); a notification subsystem to replace Pushover (the digest plus process exit code is the alert channel).

---

## 5. Data flow

### 5.1 The pipeline: scan -> dedup -> assess -> score -> digest -> TUI

```
 kestrel scan (cron)  ──┐                       API scheduler (_run_sweep) ──┐
                        ▼                                                    ▼
              bootstrap.ensure_schema ── acquire run lock (DiscoveryRun status=running, heartbeat_at)
                        │
                        ▼
              services.discovery.run_scheduled_discovery(force=...)  ->  run_discovery(...)  [per SearchProfile]
                        │
   1 PREFLIGHT          │  ai_health.preflight(chain)   fail -> run continues in "fetch+assess only", exit code 3
   2 FETCH              │  adapters (jobspy, arbeitsagentur, arbeitnow, ats)  -> RawJobResult[] + SourceReport per source
                        │  scan_config floors: BELOW-FLOOR / ZERO surfaced in DiscoveryRun.source_report
   3 IN-BATCH DEDUP     │  dedup.dedup_batch: exact key + fuzzy company/title merge (keeps _merge_raw_jobs semantics)
   4 HISTORY DEDUP      │  dedup.match_history: exact -> _update_existing_job (+last_seen_at, seen_count)
                        │                       fuzzy/repost -> new row with duplicate_of_id, dedup_reason
   5 PERSIST ARRIVALS   │  INSERT DiscoveredJob rows, assess_verdict NULL, commit   (crash-safe: arrivals are durable)
   6 ASSESS             │  for survivors lacking authoritative offices: ats.resolve_posting (bounded HTTP)
                        │  assess(job, ctx) -> Assessment ; UPDATE geo_class, assess_verdict, assess_reasons, assess_hash
   7 LIVENESS           │  ats.check_liveness for rows due a recheck -> liveness live|closed|unknown
   8 SELECT FOR SCORING │  verdict in (pass, review), duplicate_of_id NULL, liveness != closed, unscored,
                        │  ordered by source priority, capped by budget (port of effective_scoring_cap)
   9 SPEND GUARD        │  SpendGuardProvider inside get_ai_provider(): halt at daily_spend_limit_usd
  10 SCORE              │  batch_score_discovery (batch_scoring 10/prompt, async_batch for Anthropic/OpenAI)
  11 PROMOTE            │  Application rows for non-excluded jobs (or shortlist-only, D1)
  12 DIGEST             │  triage.build_digest(since=last_digest): shortlist, review queue, source health,
                        │  spend, audit sample (audit.draw), alerts (drift, preflight, halts)
                        ▼
              stdout / file / (later) email; exit code 0 ok, 2 partial, 3 preflight, 4 spend halt, 1 fatal

 TUI / CLI / MCP read the same tables: shortlist = DiscoveredJob JOIN ScoredJob WHERE verdict != exclude
```

Steps 3-6 reorder today's `_dedup_and_filter` -> `run_prefilter` -> upsert, so that nothing is dropped before it is written.

### 5.2 Where the API server and cron share code

| Concern | API-server path | Cron path | Shared? |
|---------|-----------------|-----------|---------|
| Entry | `discovery/scheduler.py::_run_sweep` -> `run_scheduled_discovery(db, profile_id)` | `cli/scan.py::scan` -> `run_scheduled_discovery(db, profile_id, force=True)` | The service function and everything beneath it. |
| Sequencing, dedup, assess, scoring, digest | `services/*` | `services/*` | 100% shared. |
| Migrations | `lifespan` -> `bootstrap.ensure_schema()` | `scan` -> `bootstrap.ensure_schema()` | Shared after extraction. |
| Session | `get_db` / `SessionLocal` | `bootstrap.open_session()` (`SessionLocal`) | Same engine config and pragmas. |
| Async | already inside the event loop | `asyncio.run(run_scheduled_discovery(...))` once at the top (as `cli/main.py::_run_discovery_async` does) | Service code is `async def`, awaited directly. |
| Mutual exclusion | run lock row | run lock row | Shared via `DiscoveryRun`. |
| Failure policy | log, back off, stop after 5 consecutive errors (`_handle_discovery_error`) | exit code (daily_pipeline's 0/1/2 contract plus 3/4) | Policy differs, mechanism (ScanResult) shared. |

### 5.3 Process-boundary pitfalls specific to cron

- **CWD-relative config.** `database_url` defaults to `sqlite:///data/career_os.db` and `env_file=".env"`; a cron job with a different CWD silently creates a fresh empty DB in the wrong place. `kestrel scan` must resolve an absolute data dir (`--home` / `KESTREL_HOME`), log the resolved DB path on the first line, and refuse to run when `data/` does not exist and `--init` was not passed.
- **Double runs.** The in-API scheduler and cron can both fire. The run lock (a `DiscoveryRun` row with `status="running"` and `heartbeat_at` younger than `scan_lock_ttl_seconds`) plus the existing `next_run` gating in `_should_run_profile` make the second one a no-op that exits 0 with a clear message.
- **Long write transactions.** `run_discovery` commits after the run row, then holds a session across network calls and scoring. Commit per stage and per scoring batch; combined with `busy_timeout` this keeps API requests from seeing "database is locked".
- **No ephemeral CI scanning.** `.github/workflows/daily-scan.yml` runs `tools/daily_pipeline.py` on a runner with no persistent DB, so dedup-against-history cannot work there. It is retired, not ported.

### 5.4 `assess()` contract

```python
# services/assess.py  (new, pure: no SQLAlchemy, no I/O)
@dataclass(frozen=True)
class JobFacts:
    title: str; company: str; location: str = ""
    offices: tuple[str, ...] = (); remote: bool = False
    description: str = ""; industry: str = ""; source: str = ""

@dataclass(frozen=True)
class AssessContext:                 # built once per run from SearchProfile + scan_config
    prefilter: PrefilterConfig       # existing dataclass: strategy, keywords, blacklist
    geo_profile: GeoProfile | None   # None => geo stage is a strict no-op
    geo_drop_foreign: bool = False
    blocklist: Blocklist | None = None
    dream_companies: frozenset[str] = frozenset()   # from Profile.dream_companies

@dataclass(frozen=True)
class Assessment:
    verdict: Literal["pass", "review", "exclude"]
    reasons: tuple[str, ...]          # stable codes: no_role_signal, industry_blacklisted, blocklisted, geo_foreign, ...
    geo_class: str | None             # one of services.geo.classifier.ALL_CLASSES, or None when gate off
    signals: Mapping[str, bool]       # title_match, skill_match, ... (feeds PrefilterMetrics)

def assess(job: JobFacts, ctx: AssessContext) -> Assessment: ...
def context_hash(ctx: AssessContext) -> str: ...   # stored as assess_hash; changed config => rows are stale
```

Rules that must survive from the current code:
- `PrefilterStrategy.OFF` is a full bypass (no geo classification either): `run_prefilter` documents this.
- `unknown` and the maybe classes are never excluded; `foreign` is annotated and counted, and deleted only when `geo_drop_foreign` is set (module docstring of `prefilter.py`: deletion trades the 99.5% keyword recall for the geo gate's recall).
- Absence of geo config yields byte-identical output to today (GEO-03). The regression test for this lands in the same PR as the `run_prefilter` refactor, before any wiring.
- A foreign dream-tier company is `review`, not `exclude` and not floored (the logic in `tools/job_scorer.py::apply_floors` / `classify_tier`).

### 5.5 Geo wiring per SearchProfile

Resolution precedence, evaluated in `services/discovery.py::_build_prefilter_config`:
1. `SearchProfile.filters["geo"]` (JSON, already the home of `prefilter_title_keywords` etc.): either `{"preset": "frankfurt"}` (resolved from `services/geo/presets.py`) or `{"home_tokens": [...], "allow_pan_region_remote": true, "extra_foreign_tokens": [...], "drop_foreign": false}` passed to `GeoProfile.from_home_tokens` (its docstring names these as "the user-facing geo configuration keys").
2. `config/geo.yaml` (`home_tokens`, `allow_pan_region_remote`, `extra_foreign_tokens`; the same file `tools/batch_probe.py::_load_geo_config` reads).
3. Nothing: `geo_profile=None`, no `geo_class`, output unchanged.

`GeoProfile` is compiled once per run (profiles are frozen dataclasses of compiled regexes) and put in `AssessContext`. Authoritative `offices` (from `ats.resolve_posting`) are passed as `geo_eligibility(location, offices, ...)`; the engine already documents that offices override the list-level location string. Key names are a requirements decision (D2) because v1.1's GEO-01 left them open.

### 5.6 Dedup design

Current state: exact `(title, company, location)` lowercase key (`_dedup_key`) plus the DB unique constraint `uq_discovered_job_dedup`. It misses `"Acme GmbH"` vs `"Acme"`, `"Senior PM (m/f/d)"` vs `"Senior PM"`, and the same role reposted with a new location string.

- **In batch:** `dedup_batch(raw_jobs)` groups by `job_key(company, title)` (normalised: legal suffixes, gender/work-time tags, locations in parentheses; specialisations in parentheses preserved, per `tools/normalize.py`), then merges fuzzy near-matches within the same normalised company using `rapidfuzz` at a high threshold on title only. Output keeps `_merge_raw_jobs` semantics (earliest `posted_at`, longest description, union of sources/URLs).
- **Against history:** exact normalised hit -> existing `_update_existing_job` path plus `last_seen_at`/`seen_count`. Non-exact but `dedup_key` or `repost_fingerprint` match -> insert the arrival with `duplicate_of_id` set and `dedup_reason in ("fuzzy","repost")`; it is never scored, and the UI shows the parent's score.
- **`repost_fingerprint`:** hash of `(company_norm, title_norm, sha1 of the first N normalised description tokens)`; location excluded so a changed location string does not defeat it. Window: match only parents seen in the last 90 days (config), so a genuinely re-opened role years later is new.
- Because duplicates are persisted rather than dropped, "persist every arrival" and "no paid scoring on duplicates" both hold.
- ATS rows dedup first on `(profile_id, ats, ats_slug, external_id)`; the tier0 poller's `data/tier0_state.json` "seen ids" file disappears into this index.

### 5.7 Cost safety design

```python
# ai/base.py (modified)
class ProviderQuotaError(Exception): ...                       # unchanged base, still caught everywhere
class ProviderCreditsExhaustedError(ProviderQuotaError): ...   # HTTP 402 / vendor "insufficient credits" body
class ProviderRateLimitedError(ProviderQuotaError):            # HTTP 429
    retry_after: float | None

class AIProvider(ABC):
    def _raise_for_quota(self, response: httpx.Response) -> None:
        """Single place that maps status + body to the taxonomy; per-provider hook for 429 bodies."""
```

- **Status alone is not enough for every vendor.** Some vendors return 429 for an out-of-credits condition and distinguish it only in the error body (OpenAI's `insufficient_quota` code and Gemini's `RESOURCE_EXHAUSTED` are the cases to verify). `_raise_for_quota` takes an overridable `classify_429(body)` hook defaulting to rate-limited. MEDIUM confidence: confirm each vendor in the phase research before relying on it.
- **`FallbackProvider._try_chain`:** 429 -> sleep `min(retry_after or backoff, cap)`, retry the same leg up to `rate_limit_max_waits`; only then move on. 402 -> mark the leg exhausted for this process and move on. The premium filter in `ai/factory.py` (`_filter_premium`, `AI_ALLOW_PREMIUM_FALLBACK`) stays as is, so a wait never escalates to `anthropic`.
- **`SpendGuardProvider(AIProvider)`:** before each `complete/score/batch_score/embed`, compute `spent_today = SUM(ai_usage_log.estimated_cost_usd since local midnight) + process_running_total`, raise `SpendLimitExceededError` when `>= settings.daily_spend_limit_usd`. `SpendLimitExceededError` deliberately does **not** subclass `ProviderQuotaError` or `httpx.HTTPStatusError`, so `FallbackProvider` and the scoring loop's `except Exception` per-job handler cannot convert a halt into "try the next provider" or "skip this job and continue". `batch_score_discovery` must re-raise it (add it to the explicit except list, before the generic handler) and `run_discovery` records `halt_reason="spend_limit"`.
- **Invariant test:** (a) `get_ai_provider()` for every registry name except `mock` returns a guarded instance; (b) an AST guard (same family as `tests/test_ai_isolation_guard.py` and `tests/test_billing_safety.py`) fails if any module under `src/` constructs a concrete provider class outside `ai/factory.py`.
- **Batch APIs:** Anthropic/OpenAI batch submission cost accrues later; the guard charges an estimate at submit time using `_estimate_cost` with a 0.5 factor.
- **Preflight:** `ai_health.preflight(required)` runs before fetch; "required" is the configured chain. Report states: `ready`, `no_key`, `unreachable`, `no_credits`, `unverified`. `kestrel doctor --providers` and `kestrel scan` share it. It never calls a scoring endpoint.

### 5.8 Digest, exclusion audit, overturn

- **Digest contents** (`triage.build_digest(db, profile_id, since)`): new shortlist (score >= `shortlist_min_score`, verdict pass), review queue (foreign dream-tier etc.), duplicates collapsed count, source health table from `DiscoveryRun.source_report` (every registered source appears every run: `ok/DISABLED/BLOCKED/ZERO/BELOW-FLOOR`), spend summary, alerts (drift canary result, preflight, halts), and the audit sample. Rendering is plain Markdown/text so it can go to stdout, a file, or an agent.
- **Audit sample** (`audit.draw(db, profile_id, n, seed)`): stratified over `assess_reasons` (one stratum per exclusion reason), with the **inclusion probability recorded at draw time** in `exclusion_audits.inclusion_probability`. That number cannot be reconstructed afterwards, and without it the audited false-negative rate describes the sample, not the population. This is the design principle already written into `tools/build_label_set.py` and `tools/calibrate.py`.
- **Anchoring:** the rater sees the job facts first; filter-derived fields (reason codes, geo class, scores) are shown only after the judgement. `tools/build_label_set.py` and `tools/annotate.py` already enforce this with a `_hidden` block and a test; carry both the rule and the test over.
- **Overturn:** `audit.overturn(db, audit_id, note)` sets `judgement="overturn"`, flips the job to `assess_verdict="pass"` with `assess_override=True` (so a later re-assess does not undo the human), queues it for scoring, and stores a `snapshot` (the `{id, company, title, location, remote, desc[:2500]}` shape of `tests/eval/geo/fixtures/blind_items.json`).
- **Regression fixture:** `audit.export_fixture(path)` writes snapshots plus `expected: "pass"` as JSONL for `kestrel assess replay FILE`. These live in the user's data dir (they are real postings: never committed to the public repo; the existing `scrub_patterns()` gate in `tests/eval/geo/replay.py` shows what a committed fixture must pass). The public repo keeps the mechanism and synthetic fixtures only.
- **Learning from outcomes in v2.0 is display-only.** Outcomes feed `scoring.record_implicit_feedback` (the existing preference-learning input) and a digest line; automated weight changes are v2.1.

### 5.9 Outcome states and ingestion

- `Application.submission_state` in `{prepared, submit_attempted, submission_confirmed}` with failure side-states (`submit_failed`) and `SUBMISSION_TRANSITIONS` next to `VALID_TRANSITIONS` in `schemas/applications.py`.
- `application_outcomes` is an append-only event log: `kind` in `{submission_confirmed, rejected, interview_invite, offer, ghosted, withdrawn}`, `source` in `{manual, extension, email, mcp}`, `evidence` JSON, and `fit_score_at_event` (needed later to relate score to outcome). Each event also writes an `ActivityLog` row through `services/activity.py::log_activity` (existing audit trail), but the typed table is what learning and the digest query.
- `ingest_outcomes(db, profile_id, events)` is idempotent on `(application_id, kind, occurred_at, source)` so re-running an email/CSV ingest cannot double count. Events that imply a pipeline move call the existing `update_application`, which enforces `VALID_TRANSITIONS`.
- The extension's `autolog.content.ts` posts a confirmed submission to a new route in `api/applications.py`; extension code changes are out of scope for this research beyond that route.

### 5.10 Dossier, gates, drafting

```
data/dossier/                     (path from settings.dossier_dir; a private git repo can track it)
  facts.yaml          each fact: id, claim, evidence, verified_at   (VERIFIED: the fact gate trusts only these)
  preferences.yaml    targets, dealbreakers, tone preferences        (not checked as claims)
  samples/*.md        writing samples                                 (voice gate input only)
```

- `dossier.load()` parses and validates; `dossier.snapshot(db)` hashes the three kinds separately and inserts a `dossier_versions` row only when the hash changed. Keeping facts, preferences and samples distinct is a hard rule: the fact gate never treats a preference or a sample sentence as evidence.
- `gates.fact_gate(text, dossier)` -> violations for numbers, employers, titles, dates and technologies in the draft not supported by a verified fact. Deterministic first pass (entity/number extraction and matching). An optional LLM pass can only add violations, never remove them.
- `gates.voice_gate(text, dossier)` -> report: banned-phrase list from preferences plus a cheap stylometric distance to samples (sentence length, punctuation rate). Pure, no provider.
- `drafting.draft(...)`: context pack -> provider (through the spend guard) -> both gates -> bounded regenerate loop -> `drafts` row with `dossier_version_id`, `gate_report`, `text`, and nullable `final_text` (captures the user's edit; v2.1 learning needs it and retrofitting is costly).
- Extension prefill calls `drafting.answer_question` and shows the gate report; the extension never receives unverified claims silently.

### 5.11 One service layer for CLI, TUI and MCP

Rules (enforce with an import-boundary test, like `tests/test_no_import_masking_skips.py` style AST guards):
1. `tui/` and `mcp_server.py` may import `services/`, `models/`, `schemas/`, `bootstrap`. They may not import `cli/`.
2. Services take `(db, profile_id, ...)` and return ORM objects/dataclasses; they never print and never call `typer.Exit`.
3. **Async discipline.** `cli/main.py` wraps async services with `asyncio.run` (`_run_discovery_async`, `_run_score_async`). Textual and FastMCP already run an event loop: call `await service(...)` directly (or `run_worker`), and never `asyncio.run` inside them. Blocking sync SQLAlchemy calls from Textual go through `run_worker(thread=True)`.
4. Session per interaction (open, use, close), never one session for the app lifetime (the TUI would hold a SQLite transaction open).

Extraction list (from `cli/main.py`; each becomes a tested service function, CLI keeps only Rich rendering):

| Today in CLI | Becomes |
|--------------|---------|
| `pipeline_list` query | `services/applications.list_applications(...)` (already exists; CLI just stops duplicating it) |
| `_compute_pipeline_stats` | `services/analytics` (or `triage.pipeline_stats`) |
| `pipeline_follow_ups` query | `services/follow_ups.list_follow_ups(..., due_only=True)` (add parameter) |
| `_validate_status_transition`, `_apply_notes_update` | `services/applications.update_application` (already validates; CLI raised its own errors) |
| `discover` post-sweep job listing | `services/discovery.list_discovered(...)` |

MCP tool set (read-mostly, no outbound submit): `shortlist`, `job_detail`, `pipeline`, `follow_ups_due`, `digest`, `get_draft_context`, `check_draft` (gates only, zero spend), `save_draft`, `record_outcome`, `overturn`. The agent writes the text by default; `draft` (server-side LLM) is optional and subject to the spend guard. Dossier content leaves the machine to the agent's model provider, so expose it only through an explicit `mcp_expose` allow-list in config. Transport is stdio only; no network listener (consistent with G-2009).

---

## 6. Recommended project structure (additions only)

```
src/career_os/
├── bootstrap.py                  NEW
├── mcp_server.py                 NEW
├── discovery/
│   ├── ats.py                    NEW  adapters + resolve_posting + check_liveness
│   ├── scan_config.py            NEW  YAML loaders + source health classification
│   ├── adapters.py               MOD
│   ├── prefilter.py              MOD  delegates to assess()
│   └── scheduler.py              MOD
├── services/
│   ├── assess.py                 NEW
│   ├── dedup.py                  NEW
│   ├── triage.py                 NEW
│   ├── audit.py                  NEW
│   ├── outcomes.py               NEW
│   ├── dossier.py                NEW
│   ├── gates.py                  NEW
│   ├── drafting.py               NEW
│   └── (discovery, scoring, scoring_calibration, ai_health, applications, follow_ups, analytics: MOD)
├── ai/
│   ├── spend_guard.py            NEW
│   └── (base, fallback, factory, observability, 9 providers: MOD)
├── tui/                          NEW  __init__.py, app.py, screens.py
├── cli/
│   ├── scan.py                   NEW
│   ├── write.py                  NEW
│   └── (main, scoring: MOD)
├── models/   discovery.py MOD; outcomes.py, dossier.py, audit.py NEW (or one models/v2.py)
├── schemas/  discovery.py, applications.py MOD; outcomes.py, triage.py NEW
└── _alembic/versions/            one migration per phase that touches schema
```

Deleted: see section 9.

---

## 7. Patterns to follow

### Pattern 1: Pure decision core, thin persistence shell
`assess()`, `dedup_batch()`, `fact_gate()`, `voice_gate()` take plain data and return plain data. DB reads/writes are in `services/discovery.py` and `triage.py`. This is what made the geo engine replayable against a frozen blind set ("pure and total: no file I/O, no network" in `classifier.py`), and it is what makes the port-verify mechanism in section 10 possible.

### Pattern 2: Flags default to today's behaviour; verdicts are recorded, not applied silently
Follow the existing `Settings` flag pattern (`cascade_shadow_enabled`, `embedding_prefilter_enabled`). New exclusion behaviour ships as: record the verdict, show it, and only then let it gate scoring. The cascade router (`services/cascade_router.py`) is the in-repo example; it stays a separate, shadow-first signal consumer of scoring and is **not** folded into `assess()`.

### Pattern 3: One shared Alembic step per phase, additive only
Add nullable columns and new tables; never alter or drop constraints. `env.py` already sets `render_as_batch=True` and several migrations use `batch_alter_table`, so a self-referencing FK (`duplicate_of_id`) is feasible, but prefer a plain indexed integer if the batch rewrite of `discovered_jobs` is not worth it.

### Pattern 4: Reporting every source, every run
Port the `tools/source_registry.py` rule: a disabled or empty source is reported as such, never as absence. Stored as `DiscoveryRun.source_report` JSON and rendered in the digest.

---

## 8. Schema changes and migration notes

Current head: `w5x6y7z8a9b0` (single linear chain of 38 files in `src/career_os/_alembic/versions/`; `18b5326c3da3_merge_parallel_migration_branches.py` is evidence of what parallel migration branches cost). Rule: one migration per phase, written against the head at merge time; phases that touch schema do not run in parallel.

### `discovered_jobs` (modified)

| Column | Type | Phase | Notes |
|--------|------|-------|-------|
| `geo_class` | String(32) null, indexed | C | NULL = gate off or never assessed |
| `assess_verdict` | String(16) null, indexed | C | `pass`/`review`/`exclude`; NULL = never assessed (legacy rows) |
| `assess_reasons` | Text null | C | JSON list of codes |
| `assess_hash` | String(16) null | C | `context_hash(ctx)`; mismatch = stale, re-assess |
| `assess_override` | Boolean not null default false | F | human overturn; re-assess skips |
| `assessed_at` | DateTime null | C | |
| `offices` | Text null | D | JSON; authoritative offices from ATS |
| `dedup_key` | String(255) null, indexed | C | from `dedup.job_key` |
| `repost_fingerprint` | String(32) null, indexed | C | |
| `duplicate_of_id` | Integer null (self FK, ondelete SET NULL) | C | batch_alter_table |
| `dedup_reason` | String(16) null | C | `exact`/`fuzzy`/`repost` |
| `last_seen_at` | DateTime null | C | |
| `seen_count` | Integer not null default 1 | C | |
| `ats`, `ats_slug`, `external_id` | String null; composite index `(profile_id, ats, ats_slug, external_id)` | D | replaces `data/tier0_state.json` |
| `liveness`, `liveness_checked_at` | String(16) null, DateTime null | D | |

Existing unique constraint `uq_discovered_job_dedup (profile_id, title_normalized, company_normalized, location_normalized)` is kept as is.

### `discovery_runs` (modified)
`source_report` Text, `heartbeat_at` DateTime, `scored_count` Integer, `spend_usd` Float, `halt_reason` String(32), `exit_status` Integer. (`trigger` already allows `manual|scheduled|cli`.)

### `applications` (modified)
`submission_state` String(32) null, `submission_updated_at` DateTime null.

### New tables

| Table | Columns (summary) | Phase |
|-------|-------------------|-------|
| `exclusion_audits` | id, profile_id, discovered_job_id FK, drawn_at, stratum, inclusion_probability Float, snapshot Text JSON, assess_hash, judgement (`agree_exclude`/`overturn`/NULL), judged_at, note, exported_at | F |
| `application_outcomes` | id, profile_id, application_id FK, kind, occurred_at, source, evidence Text JSON, fit_score_at_event Float, created_at; index `(application_id, occurred_at)`; unique `(application_id, kind, occurred_at, source)` | F |
| `dossier_versions` | id, profile_id, content_hash (unique per profile), manifest JSON, snapshot Text, created_at | H |
| `drafts` | id, profile_id, application_id null, discovered_job_id null, kind, text, final_text null, dossier_version_id FK, gate_report JSON, provider, model, status, created_at | H |

### Migration notes
- Backfill is optional and LLM-free: `kestrel assess backfill` computes `dedup_key`, `geo_class`, `assess_*` for legacy rows in batches. NULL means "never assessed" and the scoring query treats NULL as scorable, so old data keeps behaving.
- Orphaned tables from removed features (`notification_*`, `ticktick_sync_tasks`, `calendar_events`, `warn_filings`, `time_sessions` already dropped by `d2e5a7f1b9c3`) stay in place in v2.0. Deleting the model classes does not affect old migrations (they use `op.create_table`). A drop migration is a separate, optional, late decision; a downgrade path matters more than 10 empty tables.
- `Application.status` normalisation in `lifespan` (lowercasing at startup) is unrelated and stays.

---

## 9. Decoupling and deletion order

Rule: callers first, then providers of the callee, then the callee. Each step leaves `pytest tests/ -v` and the frontend build green.

### Pushover (hidden couplings found)
1. `api/scoring.py`: drop `send_credits_exhausted_alert` (the response already carries `credits_exhausted`).
2. `services/drift_canary.py::run_drift_canary` and `cli/scoring.py --notify`: drop the alert send; the returned dict already has `alert`/`reason`.
3. `services/analytics.py::_compute_notification_metrics` plus `NotificationMetrics`; make the field optional in `frontend/src/api/analytics.ts` / `types.ts` first, then remove.
4. `schemas/integrations.py` Pushover catalogue entry; `config.py` pushover settings.
5. `main.py` router include and import.
6. Delete `api/pushover.py`, `services/pushover.py`, `services/pushover_client.py`, `schemas/pushover.py`, `models/pushover.py`, `models/__init__.py` exports, and their tests. Leave the tables (section 8).
7. `.github/workflows/daily-scan.yml` references `PUSHOVER_*` secrets; it is retired with the workflow.

### TickTick / calendar / WARN
1. Remove callers: `services/applications.py` (two lazy `try_auto_push_pipeline_action` imports), `services/follow_ups.py` (`try_auto_push_follow_up`, `create_follow_up_calendar_event`), `services/goals.py` (module-level `try_auto_push_learning_goal` import: this one breaks import of `goals` if the module is deleted first).
2. Remove `start/stop_ticktick_scheduler` from `main.py`; remove routers; delete services/api/schemas/models; frontend `ticktick.ts`, `calendar.ts`, `CalendarSection.tsx`.
3. `services/red_flags.py` lazily imports `warn_data` and already tolerates its absence; `cli/warn.py` goes with it.
4. Remove `icalendar` dependency last.

### Integrations / OAuth: do not delete wholesale (D3)
`api/oauth.py` is OpenRouter OAuth PKCE (`/api/auth/openrouter/*`), used by `frontend/src/components/OpenRouterConnect.tsx` and `OpenRouterConnect`'s API module; it writes the key into `integration_configs` through `services/integrations.py`. `ai/factory.py::_read_credential_from_db` and `services/ai_health.py` read `IntegrationConfig(name="ai_providers")`. The web app is "the start of the install path", so either keep `integrations` (AI-provider subset) and OpenRouter OAuth, or consciously drop web key entry in favour of `kestrel init` writing `.env`. Whatever is chosen, move `limiter` out of `api/oauth.py` first (imported by `main.py` and `api/extension.py`).

### Non-code removals
`worker/`, `dashboard/`, `_bmad/` and `.claude/skills/bmad-*`, unused workflows (`daily-scan.yml`, and the release/deploy surface the milestone names): independent of the Python work; do them in the first deletion phase to shrink CI. `.github/workflows/ci.yml` and any path filters that reference removed directories must be updated in the same PR.

---

## 10. Port, replay-verify, delete: the mechanism

### Precedent in the repo
- `tests/eval/geo/`: frozen `reference_assignments.json` (outputs of the source engine), `replay.py::classify` reproducing the original call shape, `test_blindset_regression.py` asserting 277/277 equality, `generate_reference.py` (one-shot, needs the original; not run by CI), a scrub gate (`scrub_patterns`) over the committed fixture.
- `tools/tests/test_daily_pipeline_port.py`, `tests/test_tier0_ats_poller.py`: behaviour specs for scripts that already exist.
- Phase 6 precedent (v1.1): delete a dead suite only with its cases ledgered (19 cases: 7 covered, 10 re-pinned, 2 out of contract).

### The ledger
`tools/PORT_LEDGER.yaml` (committed, reviewed with every PR that touches tools/). One entry per file in `tools/` (45 entries today, including `kestrel-mcp/` and `sonarcloud-mcp/`).

```yaml
- script: tools/normalize.py
  disposition: PORT            # PORT | FOLD | DROP | KEEP
  target: src/career_os/services/dedup.py
  proof: tests/ports/test_port_normalize.py
  golden: tests/ports/golden/normalize.jsonl
  allowed_divergences: tests/ports/test_port_normalize.py::ALLOWED_DIVERGENCES
  status: pending              # pending -> ported -> verified -> deleted
  verified_at: null            # git sha of the verifying commit
  dependents: [tools/tests/test_normalize.py, tools/daily_pipeline.py]
  notes: ""
```
A test (`tests/test_port_ledger.py`) fails when: a file in `tools/` has no entry; an entry is `deleted` but the file exists (or the reverse); a `verified/deleted` entry's `proof` or `golden` file is missing; an `allowed_divergence` has no reason string.

### The steps (per script)
1. **Capture before touching anything.** Run the old script's pure functions over a corpus and freeze `(input, output)` into `tests/ports/golden/<script>.jsonl`; the header records the script's SHA-256 and the git SHA. Corpus tiers:
   - committed and PII-scrubbed (the 277-item blind set for geo; synthetic titles/companies for normalisation), passing `scrub_patterns()`;
   - property-based inputs via Hypothesis (already a dev dependency: `tests/property/`, `tests/geo/`) for pure functions (`normalize_*`, `job_key`, geo tokens);
   - **private shadow replay** in the maintainer's environment on real data (not committed): `kestrel scan --dry-run --json` versus the old pipeline's output for N days; compare the set of arrivals and verdicts; the PR records counts and explained diffs only.
2. **Differential test while both exist.** `tests/ports/test_port_<script>.py` imports the old module (tools/ is already on `sys.path` via `tests/conftest.py`) and the new one, runs the corpus through both, and asserts equality except for `ALLOWED_DIVERGENCES`: an explicit list, each with a reason, reviewed like code (UNIF-02 in the v1.1 requirements uses the same device).
   - Network scripts: inject recorded payloads through `httpx.MockTransport`. `tools/tier0_ats_poller.py::fetch_greenhouse/lever/ashby(slug, *, company_key, client)` already take a `client`, so the same transport feeds the old function and the new adapter; compare a field map (`Tier0Job` -> `RawJobResult`: title, company, location, url, job_id/external_id, remote, posted).
   - LLM-bound scripts (`job_scorer.score_job`, `local_scorer`): no behavioural equivalence claim. Port only the deterministic parts (`apply_floors`, `classify_tier`, `is_dream_tier`, `is_api_submittable`, `pre_filter_job`); the LLM scorer is superseded by `services/scoring.py` whose proof is the existing golden-set eval (`tests/eval/test_golden_agreement.py`, `tests/eval/baseline_metrics.json`).
3. **Prove the test can fail.** Mutate the port (flip one comparison, drop one normalisation rule) and show the differential goes red, with a loud assertion that the mutation was applied. A differential that cannot fail is the silent-green failure this repo has already hit.
4. **Port PR merges with the old script still present**, ledger `status: ported`, CI running the live differential.
5. **Shadow acceptance** (only for pipeline-level scripts: `daily_pipeline.py`, `tier0_ats_poller.py`): maintainer runs both for a defined window; zero unexplained diffs recorded in the PR body. `status: verified`.
6. **Delete PR (separate).** Preconditions, checked by the reviewer and by `tests/test_port_ledger.py`: golden file committed; the differential converted to golden-only (the import of the old module removed, so the test survives the deletion); no importers (`rg "import (normalize|batch_probe|...)|from (normalize|...) import"` over `src/`, `tests/`, `tools/`, workflows); the same PR updates `tests/conftest.py`/`tests/test_scoring_rescore.py`/`tests/test_tier0_ats_poller.py` style `sys.path.insert(... "tools")` users, `.github/workflows/*.yml`, `pyproject.toml` comments, docs. `status: deleted`.

### Proposed dispositions (confirm each by reading the script in its phase; headers only were read here)

| Script(s) | Disposition | Target | Proof |
|-----------|-------------|--------|-------|
| `normalize.py` | PORT | `services/dedup.py` | Hypothesis differential + existing `tools/tests/test_normalize.py` as golden |
| `batch_probe.py` (geo half) | PORT (delegate) | `services/geo` already; legacy tri-state shim for old callers, then delete | location-corpus differential with allow-list (v1.1 UNIF-01/02); 277-item gate |
| `batch_probe.py` (ATS offices half: `parse_*_url`, `fetch_greenhouse_offices`, `fetch_ashby_location`, `probe_role`, `validate_manifest`) | PORT | `discovery/ats.py::resolve_posting`, `kestrel assess probe` | recorded-payload differential |
| `tier0_ats_poller.py` | PORT | `discovery/ats.py` + `external_id` index | `tests/test_tier0_ats_poller.py` as spec; MockTransport differential; shadow run |
| `source_registry.py`, `blocklist.py` | PORT | `discovery/scan_config.py`, `services/assess.py` | `tools/tests/test_source_registry.py`, `test_blocklist.py` as golden |
| `job_scorer.py` (floors/tiers/ATS-host helpers) | PORT | `services/assess.py` flags (dream list from `Profile.dream_companies`) and `triage` | golden over synthetic job dicts |
| `job_scorer.py`, `local_scorer.py` (LLM/legacy scoring) | DROP (superseded) | `services/scoring.py` | golden-set eval |
| `daily_pipeline.py` | PORT then retire | `run_discovery` + `cli/scan.py` + `triage.build_digest`; `effective_scoring_cap` and `_source_priority` move into the scoring-selection step | `tools/tests/test_daily_pipeline_port.py` cases carried over; shadow run |
| `build_label_set.py`, `annotate.py`, `calibrate.py` | PORT | `services/audit.py`, `kestrel assess label/report` | their existing tests (`test_build_label_set.py`, `test_annotate.py`, `test_calibrate.py`, `test_label_pipeline_integration.py`) become the golden |
| `snapshot_db.py` | KEEP until shadow runs finish, then port as `kestrel db snapshot` or drop | n/a | `tests/test_snapshot_db.py` |
| `kestrel-mcp/server.py` | PORT | `mcp_server.py` (4 existing tools: `list_pipeline`, `pipeline_stats`, `score_job`, `discover_jobs`) | `tools/tests/test_kestrel_mcp.py` moved to `tests/` |
| `scrape_resilient.py`, `scrape_new_sources.py`, `germany_jobs.py`, `scraper.py`, `scrape_remotely.py`, `research_*`, `specific_hunt.py`, `_filter_jobs.py` (about 3,500 lines) | DROP unless a source is on the maintainer's productive list (D5) | at most one adapter each in `discovery/adapters.py` | recorded-payload differential for any kept source |
| `auto_apply.py`, `batch_apply_browser.py`, `captcha_solver.py`, `scrape_form_questions.py`, `open_question_probe.py`, `t3_lane.py`, `kit_builder.py`, `render_*`, `md_to_pdf_cover_letter.py`, `generate_batch_*` | FOLD or DROP: auto-submit is v2.1; v2.0 lessons (open-question detection, guardrails) inform extension prefill and `fact_gate` seeds | extension + `services/gates.py` | ledgered cases, no behavioural claim |
| `update_sheet.py`, `validate_sheet.py` | DROP | n/a | ledger reason |
| `spike_prefilter.py`, `spike_batch_quality.py` (+ results md) | DROP after moving results into `docs/research/` | n/a | the spike results are the record |
| `check_review_trailers.py` | KEEP (CI gate, not pipeline) | n/a | `tests/test_check_review_trailers.py` |
| `sonarcloud-mcp/` | KEEP or decide separately (dev tooling) | n/a | n/a |

Note that `tools/job_scorer.py::geo_eligibility` already delegates to the package engine, and `tools/batch_probe.py` still owns an independent token-list classifier; that duplicate is the one real divergence to resolve by differential test, not by inspection.

---

## 11. Anti-patterns to avoid

### A second orchestrator
**What people do:** write `services/scan.py` with its own fetch->score loop because the CLI is "headless".
**Why it's wrong:** two sequencers drift (the daily_pipeline vs `run_discovery` split is exactly how the current duplication arose).
**Do this instead:** `kestrel scan` calls `run_scheduled_discovery(force=True)`.

### Dropping before persisting
**What people do:** keep `run_prefilter` ahead of the upsert.
**Why it's wrong:** nothing excluded can be audited or overturned, and "persist every arrival" is false.
**Do this instead:** persist, assess, then gate scoring/promotion on the verdict.

### Letting the spend halt be catchable
**What people do:** raise a subclass of `ProviderQuotaError` for the limit.
**Why it's wrong:** `FallbackProvider` and `batch_score_discovery` treat that class as "try the next one / stop this batch" and the cap becomes a speed bump.
**Do this instead:** a separate exception, re-raised explicitly, and the guard at `get_ai_provider()`.

### New values in `ApplicationStatus` for outcomes
**Why it's wrong:** ripples through `VALID_TRANSITIONS`, Kanban columns, analytics funnel, `lifespan` normalisation, extension, frontend types (manually maintained).
**Do this instead:** separate axis (`submission_state`) plus an event table.

### Folding `cascade_router` into `assess()`
**Why it's wrong:** the cascade needs embeddings, a DB, and a shadow-first false-skip measurement; `assess()` must stay pure and cheap.
**Do this instead:** `assess()` is the deterministic pre-LLM gate; the cascade remains a scoring-time signal.

### Importing CLI helpers into the TUI
`cli/main.py` mixes queries with Rich printing and uses `asyncio.run`. Extract to services first.

### Blocking calls on the Textual event loop / `asyncio.run` inside it
Use `await` on async services and `run_worker(thread=True)` for sync SQLAlchemy.

---

## 12. Suggested build order

Dependencies drive the order. Each row is a candidate roadmap phase (a PR on its own branch). "Needs" lists hard prerequisites.

| # | Phase (plain verb) | Delivers | Needs | Notes |
|---|--------------------|----------|-------|-------|
| 1 | **Cut** | Pushover decoupled then deleted; TickTick/calendar/WARN removed; worker/, dashboard/, BMAD, unused workflows; `limiter` moved; G-2009 host default; `bootstrap.py` extraction; `busy_timeout` | none | Deletion-only plus two tiny refactors. Shrinks CI before the engine work. Keep `integration_configs` and decide D3 here. |
| 2 | **Spend safely** | 402/429 taxonomy, fallback wait, `SpendGuardProvider`, preflight, pricing table fix | 1 (bootstrap for `doctor --providers`) | Must precede any unattended scan. Research flag: vendor status/body semantics. |
| 3 | **Filter** (engine core) | `assess.py` + prefilter refactor (behaviour-identical, regression test first); `dedup.py`; `scan_config.py`; migration C; persist-all-arrivals; geo wired per SearchProfile with `geo_class` persisted; `batch_probe` geo half delegated; `normalize.py` ported | 1 | Order inside: assess (pure) -> dedup (pure) -> migration -> geo wiring -> `run_discovery` restructure. "assess before geo wiring; dedup before scan" is satisfied here. |
| 4 | **Find** (sources) | `discovery/ats.py`, `companies.yaml`, `external_id`, authoritative offices into assess, liveness, source floors; `tier0` and `batch_probe` ATS half ported | 3 | Migration D. Research flag: ATS API behaviours (Greenhouse list vs per-job endpoints, Lever/Ashby field names, rate limits). |
| 5 | **Scan** | `kestrel scan`, run lock, exit codes, `scheduler_enabled`, scoring selection/cap, `daily_pipeline` ported; `daily-scan.yml` retired; shadow-run window opens | 2, 3, 4 | The maintainer's own daily use starts here. |
| 6 | **Track** (outcomes) | `submission_state`, `application_outcomes`, ingestion, route for extension autolog; `exclusion_audits` table lands with phase 7 | 3 | Before digest display of outcomes. Migration F. |
| 7 | **Triage** (digest + audit) | `triage.py`, `audit.py`, digest render, overturn -> fixture, `kestrel assess replay`; label tools ported | 3, 5, 6 | Rater-anchoring rule and recorded inclusion probabilities are acceptance criteria. |
| 8 | **Surfaces** (service layer + TUI) | CLI logic extracted to services (tests pin the `_get_session` seam), then `tui/` | 6, 7 | Extraction PR first (no behaviour change), TUI PR second. |
| 9 | **Know you** (dossier + gates + drafting) | `dossier.py`, `gates.py`, `drafting.py`, migration H, extension prefill route | 2 | Independent of 5-8; can run in parallel with them if migrations are sequenced. |
| 10 | **Connect** (MCP) | `mcp_server.py`, `kestrel mcp`, `mcp_expose` allow-list; `tools/kestrel-mcp` retired | 7, 8 (read tools), 9 (draft tools) | Read tools may ship earlier than draft tools. |
| 11 | **Sweep** | Remaining ledger entries (DROP/FOLD), CI step removal, 15-minute install test, README | all | Each earlier phase already deletes what it ported; this phase handles the leftovers only. |

Why this order:
- `bootstrap` and the deletions are prerequisites for everything because every later entry point depends on a migration-safe startup, and removing Pushover callers first avoids deleting a thing the scorer's error path still calls.
- Cost safety (2) precedes scan (5) and drafting (9) because both spend money unattended.
- `assess` (3) precedes geo wiring because the wiring needs one function to call; dedup precedes scan because paid scoring must never see duplicates.
- Outcomes (6) precede digest (7) so the digest's outcome section and the `record_implicit_feedback` link exist; automated learning stays v2.1.
- Service extraction (8) precedes TUI and MCP so neither re-implements CLI logic.

### Research flags for phases
- Phase 2: needs deeper research (per-vendor 402/429 body semantics; `batch_score` cost accounting).
- Phase 4: needs deeper research (ATS API shapes and rate limits; whether the Greenhouse board list endpoint can return offices in one call instead of per-job fetches, which changes the HTTP budget).
- Phase 9: needs deeper research (fact-gate extraction quality; false-positive rate on real drafts).
- Phase 10: needs light research (FastMCP async tool and stdio behaviour in the pinned `mcp` version).
- Phases 1, 3, 5, 6, 7, 8, 11: standard patterns in this codebase; existing tests are the guide.

---

## 13. Scaling considerations

Single-user, single-file SQLite; the realistic limits are API budgets and SQLite writers, not users.

| Scale | Concern | Approach |
|-------|---------|----------|
| One scan/day, 10^3-10^4 new arrivals | Write contention with the API | WAL + `busy_timeout`, commit per stage, run lock |
| 10^5 `discovered_jobs` rows | `match_history` lookups, `batch_alter_table` rewrite time | Indexed `dedup_key`/`repost_fingerprint`; fingerprint window of 90 days; run migration once at startup |
| ATS companies list of 100+ | HTTP budget and politeness | Per-host delay (the poller uses 1.5 s between companies), fetch offices only for survivors of the cheap keyword gate |
| Multi-profile in one instance | Isolation | Keep `profile_id` on every new table (done above); scan loops profiles as `_run_sweep` does |

## 14. Open decisions for requirements (flagged, not decided here)

- **D1 Promotion policy.** Today every new `DiscoveredJob` becomes an `Application` at ingest. Recommend: keep for the manual/API path (byte-identical), promote only shortlisted jobs for scan. Needs a product call because it changes pipeline counts.
- **D2 Geo config key names** on `SearchProfile.filters` (v1.1 GEO-01 left them "documented names"); also the over-admission rule (RULE-01) that decides the foreign-cap behaviour in the scorer.
- **D3 Integrations/OAuth:** keep the AI-provider credential subset and OpenRouter OAuth, or move to `.env` only. The milestone text lists "integrations, OAuth" for removal, but they currently carry AI keys for the web start path.
- **D4 Textual as core dependency or `[tui]` extra.** Recommendation: core, because the TUI is the front door once the web app is parked; `mcp` stays an extra. Versions in STACK.md.
- **D5 Scraper long tail:** which of the roughly 3,500 lines of board scrapers survive. Recommend only sources the maintainer's own `scan-sources` config shows as productive.
- **D6 `services/voice.py` / `api/voice.py` / `models/voice.py`** (chat sessions) are not on the removal list but collide in name with the voice gate. Leave in place for v2.0; revisit in v2.1.
- **D7 Liveness has no script to port** (grep of `tools/` finds none beyond `batch_probe.probe_role` re-resolution). It is new behaviour, verified by recorded-payload contract tests rather than replay.

## Sources

Read from the repo (all HIGH confidence): `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/codebase/ARCHITECTURE.md`, `CLAUDE.md`; `src/career_os/main.py`, `config.py`, `database.py`, `discovery/{adapters,prefilter,scheduler}.py`, `services/discovery.py`, `services/scoring.py` (`_query_jobs_to_score`, `batch_score_discovery`), `services/cascade_router.py`, `services/extension_capture.py`, `services/geo/{classifier,profile,presets}.py`, `ai/{base,factory,fallback,observability}.py` and the provider 402/429 sites (grep), `services/ai_health.py`, `services/{applications,follow_ups,analytics,drift_canary,pushover}.py`, `schemas/applications.py`, `models/{discovery,models,scoring,ai_usage,voice}.py`, `api/{discovery,oauth,scoring,integrations,extension}.py`, `cli/{main,doctor}.py`, `_alembic/env.py` and version list; `tools/{tier0_ats_poller,batch_probe,job_scorer,daily_pipeline,normalize,source_registry,build_label_set,calibrate,kestrel-mcp/server}.py` (headers and function inventories only); `tests/eval/geo/{replay.py,test_blindset_regression.py,fixtures/README.md}`, `tools/tests/test_daily_pipeline_port.py`; `.github/workflows/{ci,daily-scan}.yml`; `pyproject.toml`; `frontend/src/api/` listing.

Not verified here (LOW/MEDIUM): vendor-specific 402/429 semantics; Greenhouse/Lever/Ashby API details beyond what the existing scripts use; Textual and FastMCP runtime behaviour; that `uvicorn[standard]` provides `PyYAML` transitively.

---
*Architecture research for: Kestrel v2.0 Lean Kestrel (subsequent milestone)*
*Researched: 2026-10-24*
