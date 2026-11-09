# Project Research Summary

**Project:** Kestrel, milestone v2.0 "Lean Kestrel" (subsequent milestone on an existing app)
**Domain:** Self-hosted, local-first AI job-search tooling (find, triage, write in your voice, learn from outcomes), Python/FastAPI/SQLAlchemy/SQLite/Typer
**Researched:** 2026-10-24
**Confidence:** MEDIUM-HIGH (repo and registry facts are HIGH; vendor rate limits and non-verified provider error bodies are LOW to MEDIUM)

Detail lives in `STACK.md`, `FEATURES.md`, `ARCHITECTURE.md` and `PITFALLS.md` in this directory. This file reconciles them and picks positions where they disagree.

## Executive Summary

Kestrel v2.0 is a CUT-and-ADD milestone. It removes a large surface (planning scaffolding, Cloudflare worker and dashboard, TickTick/calendar/OAuth/WARN, unused deploy and release plumbing) and adds one loop a technical stranger can run in 15 minutes: a headless `kestrel scan` that persists every arrival, one pure `assess()` eligibility function used by every surface, a daily digest with an overturnable audit sample of excluded jobs, a Textual TUI, a dossier with deterministic fact and voice gates, and an MCP server so coding agents draft through Kestrel state. The comparable tool that has already walked this path (career-ops) is the best design reference; its defects (each surface building its own filter subset, a private copy of the outcome vocabulary, a fact gate applied to one output path but not the others) are the specific traps v2.0 should avoid by construction.

The recommended approach is "one pipeline, one service layer, many thin adapters". `services/discovery.py::run_discovery` stays the single sequencer (`kestrel scan` is a wrapper, not a second orchestrator). `assess()` is pure, `dedup`, `fact_gate` and `voice_gate` are pure, and CLI, TUI and MCP are leaf adapters over `services/`. The stack adds almost nothing: `textual` (core), the official `mcp` 2.x SDK (optional extra), and two already-imported but undeclared packages (`platformdirs`, `pyyaml`). Everything else (ATS adapters, scheduling, spend halt, digest, gates, dedup) is built on `httpx`, `rapidfuzz`, SQLAlchemy and the stdlib. The install path is `uv tool install`, verified on a fresh-image matrix.

The main risks are not new libraries. They are: (1) deleting things or running an unattended paid job before safety nets exist, (2) a spend halt that can be bypassed or a "429 = wait" rule that loops on a spend cap, (3) cron/TUI/MCP processes opening the wrong or an unmigrated SQLite file, (4) ports that look verified because the replay shares code or a regenerated golden file, and (5) gates that pass vacuously and give false confidence. The mitigation is ordering: one Foundation phase that lands the safety nets AND the cost guard before any deletion or unattended scan, then a deliberately split cut (cheap deletions early, `tools/` deletion last after a shadow run).

## Key Findings

### Recommended Stack

One new runtime dependency, one replaced optional extra, two declared-but-already-imported packages, three removals. Details and versions in `STACK.md`.

**Core technologies:**
- `textual` (`>=8.2,<9`), core dependency: the TUI; only maintained Python library with a keyboard-first event loop, DataTable and headless `Pilot` tests. Raise `rich` floor to `>=14.2` in the same PR.
- `mcp` 2.x (`>=2.3,<3`), optional extra `kestrel-app[mcp]`: official SDK, `MCPServer` class, in-memory test client. The v1 floor in `pyproject.toml` is already broken (see Gaps). The `<3` upper bound also satisfies the CVE-2025-66416 floor (`>=1.23.0`) that PITFALLS asks for.
- `platformdirs` and `pyyaml`: declare directly. `platformdirs` backs a single resolver for data/config dirs (the current cwd-relative `data/` and `.env` break under cron). `pyyaml` is already imported.
- `uv tool install kestrel-app`: the one supported install path (downloads a managed Python on a bare machine). pipx documented but not tested.
- Stdlib and existing deps for everything else: `httpx` (+ `MockTransport`) for ATS clients and tests, `rapidfuzz` for dedup, `smtplib` only if email ships, OS schedulers (launchd, cron, systemd timer, schtasks) for unattended runs. No APScheduler, Celery, FTS5, tenacity, spaCy, Jinja2, keyring, or second install path.
- Dependency changes: remove `aiosqlite` (never imported) and `icalendar`; drop the `warn` extra; move `python-jobspy` from the hidden `dev` extra to an explicit `[indeed]` extra and keep it `<1.2` until a replay proves a bump; keep `slowapi`, `cryptography`, `uvicorn[standard]`.

### Expected Features

**Must have (table stakes):**
- ATS-API sources (Greenhouse, Lever, Ashby) driven by a user-owned companies file; keyless, so the first useful list needs no LLM key.
- Headless `kestrel scan` that persists every arrival (including excluded ones) with stable, versioned reason codes, meaningful exit codes, idempotent, no paid scoring by default.
- Dedup within batch and against history before any paid call; mark, never delete.
- Liveness via the ATS API (tri-state `live / expired / unknown`, `unknown` never removes anything); per-source canaries and floors.
- One `assess()` returning decision, ordered reason codes, `geo_class`, `rule_version`; every surface calls it; parity test across call sites; `kestrel why <job>`.
- Cost safety: error classifier on status plus error code plus `Retry-After`, bounded 429 waits, spend halt as a code invariant at the provider factory, preflight, default cap ON.
- Digest (file, terminal, TUI) with funnel counts, source-canary banner, spend line, and a seeded, stratified audit sample of excluded jobs; overturn and confirm become regression fixtures; `verify-fixtures`.
- Textual TUI over the service layer (shortlist, detail with decision trail, status change through the existing state machine, follow-ups due, audit screen); outcome states as a separate submission axis plus an append-only ledger.
- Dossier as plain files (verified facts, preferences, writing samples kept distinct, content-hash versioned), deterministic fact gate (fail closed) and voice gate, drafting with traceability; MCP server with a small scoped tool set; 15-minute install tested on fresh images; README that makes only true "learns you" claims.

**Should have (competitive):**
- Overturn-to-fixture audit loop (no comparable tool ships it); company resolver for `companies.yml`; repost flag with career-ops' four false-positive rules; paste-a-reply outcome proposals with human accept; `kestrel calibrate` advisory report with sample floors; knock-out pre-scan and duplicate-application warning in prefill; extension prefill for the three ATSs (never submits).

**Defer (v2.1+ or v2.0.x):**
- No-terminal path, richer person model with kill criterion, automated learning from edits and outcomes, Firefox, opt-in auto-submit; browser-based liveness, Workday and long-tail ATSs, tailored CV/PDF generation, mailbox connector, LLM entailment and "sounds like you" judges (advisory, only after TPR/TNR validation), SimHash near-duplicate column, email delivery (see Open Questions).

**Park (keep working, hide from default surfaces, do not extend):** React web app, interview prep/STAR/coaching, gap analysis, company research, salary tools, Bayesian preference learning, cascade router, embeddings prefilter, chat-session `voice` service (rename or leave to avoid collision with the voice gate).

### Architecture Approach

Layered app stays as is (api to services to models to database). New work is additive: nullable columns and new tables, one Alembic migration per schema-touching phase, flags defaulting to today's behaviour, verdicts recorded before they gate anything. `run_discovery` is re-sequenced to fetch, dedup, PERSIST ARRIVALS, assess, liveness, select for scoring, spend-guard, score, promote, digest; promotion to `applications` becomes conditional on `assess_verdict != "exclude"`. The spend guard wraps the single choke point `get_ai_provider()` and its halt is a separate exception that does not subclass `ProviderQuotaError`. Port-replay-delete is tracked in a per-script ledger with differential tests and frozen golden files, following the existing geo precedent.

**Major components:**
1. `bootstrap.py` (new): `ensure_schema()`, session, profile resolution, `KESTREL_HOME` path resolver, shared by scan, TUI, MCP and the API.
2. `services/assess.py`, `services/dedup.py` (new, pure), `discovery/ats.py`, `discovery/scan_config.py` (new): the eligibility engine, history/batch dedup, ATS adapters with liveness and URL re-resolution, YAML config loaders and source-health classification.
3. `ai/base.py` taxonomy plus `ai/spend_guard.py` and `ai/fallback.py` changes (modified/new): 402/429 classes, bounded waits, persisted spend ledger, preflight in `services/ai_health.py`.
4. `services/triage.py`, `services/audit.py`, `services/outcomes.py` (new): digest, stratified audit with recorded inclusion probabilities and rater-anchoring rule, submission state machine and outcome events.
5. `services/dossier.py`, `services/gates.py`, `services/drafting.py` (new): files-on-disk dossier with DB version index, pure deterministic gates, a single `gate_draft()` choke point enumerating every draft producer.
6. `tui/` and `mcp_server.py` (new): leaf adapters; no imports from `cli/`; session per interaction; MCP calls services in-process over stdio, never the REST API.

### Critical Pitfalls

1. **Deleting before safety nets exist (CUT-1/2/3/4)** — Hidden deferred imports (Pushover is referenced from six places, three non-import-time), CI-critical scripts living in `tools/`, and an aggregator check that fails open. Land import-all and OpenAPI tests, relocate `check_review_trailers`, harden `CI Complete` to an allow-list, add a wheel-content test, introduce a `notify()` seam, then delete leaf-first, one integration per PR.
2. **Spend halt bypass and 402/429 conflation (COST-1/2)** — All 9 providers treat `(402, 429)` as quota; Anthropic's spend-cap 429 has no `retry-after`, OpenAI billing exhaustion arrives as 429 `insufficient_quota`, OpenRouter can fail inside a 200. Use a classifier over status, body code and `Retry-After` with recorded fixtures per provider; bounded waits; guard at `get_ai_provider()` outside the fallback chain; unknown model price fails closed; persisted ledger; landed before any unattended scan.
3. **Headless process in the wrong place (ADD-1/2/3, MIG-1)** — Cron has a different cwd, no `.env`, default `mock` provider, an unmigrated DB, and two schedulers can double-scan. One `KESTREL_HOME` resolver for all entry points, `ensure_schema()` fail-fast before paid work, `busy_timeout` plus short transactions plus a two-process contention test, a single run lease row, scan refuses `mock` without a flag.
4. **Port-by-replay that proves nothing (REPLAY-1, CUT-7)** — Shared imports, injected-clock gaps, hash-order dependence, regenerated golden files, and deleting the maintainer's live pipeline before parity. Ledger plus differential tests that fail under mutation, captured real inputs, a shadow window with an explained-diff ledger, tag the last script revision, delete only in a late Retire phase.
5. **Persist-then-gate and gates that give false confidence (DIGEST-1, GATE-1, SEC-1/2)** — Excluded arrivals must be persisted before any audit exists; gates must fail closed on an empty dossier, be measured with planted fabrications, and run at one choke point for CLI, TUI, MCP and extension; MCP must be stdio-only, read-first, no dossier dump, JD text labelled untrusted, no submit tool.

## Implications for Roadmap

### Reconciled build order (ONE order)

The four researchers proposed different orders (ARCHITECTURE: Cut, Spend, Filter, Find, Scan, Track, Triage, Surfaces, Know you, Connect, Sweep. PITFALLS: Foundation, Cut-A, Cost, Find, Filter, Score+Digest, Track, Write, Connect, Install, Retire. FEATURES: cost safety and persisted arrivals first, assess before everything that filters, gates before drafting before agents). Resolution below.

### Phase 1: Foundation (safety nets and cost guard)
**Rationale:** All four files agree nothing may be deleted and no unattended paid job may run until this exists. Merges PITFALLS "Foundation" with ARCHITECTURE "Spend safely" (the cost guard must be in the first phase) and the `bootstrap` extraction from ARCHITECTURE's Cut phase. Two internal waves, separately mergeable PRs: 1a safety nets, 1b spend guard.
**Delivers:** 1a: relocate `check_review_trailers` out of `tools/` and repoint CI; `CI Complete` allow-list plus workflow-lint test; wheel-content and fresh-venv job (fixes the stale bundled frontend, G-2015); import-all and OpenAPI tests; `bootstrap.py` with `ensure_schema()` and one `KESTREL_HOME` path/config resolver; `busy_timeout`, short-transaction rule and two-process contention test; `notify()` seam; bind default to `127.0.0.1` with an explicit Docker override and non-loopback refusal. 1b: 402/429/400 classifier with recorded per-provider fixtures, `SpendGuardProvider` at `get_ai_provider()` with a separate non-catchable halt exception and persisted ledger, bounded 429 wait, `ai_health.preflight`, pricing-table fix, AST guard that providers are constructed only in the factory.
**Addresses:** cost safety (FEATURES section 6), install prerequisites.
**Avoids:** CUT-1, CUT-2, CUT-3, CUT-4, ADD-1, ADD-2, MIG-1, COST-1, COST-2, BIND-1.

### Phase 2: Cut (sprawl removal, part A)
**Rationale:** Shrink the surface the new code must coexist with, but only things with no port dependency. Pushover removed only now that the `notify()` seam exists. `tools/` and `daily-scan.yml` stay (they are the live pipeline and the porting source).
**Delivers:** leaf-first, one integration per PR: Pushover decoupling (callers in `api/scoring.py`, `drift_canary`, `analytics`, `cli/scoring.py`, registry, config, `main.py`), TickTick/calendar/WARN, OAuth (after moving `limiter` out of `api/oauth.py`), worker, dashboard, BMAD scaffolding, unused workflows, npm/homebrew/GHCR deprecation notices. Forward-only Alembic revisions (old revisions byte-identical, `integration_configs` data-deleted only for cut names, orphan tables left in place). Frontend pages and API clients deleted in the same PR as their backend. Docs and secrets inventory with keep/remove per item.
**Avoids:** CUT-1, CUT-5, CUT-6, FE-1, DOC-1, PROC-1.

### Phase 3: Find (sources, arrivals, dedup, liveness, canaries)
**Rationale:** Persisted arrivals with reason codes is the most load-bearing data decision (dedup, canaries, audit, fixtures and calibration all read it), so it lands before anything that filters. Assess verdict columns exist but are nullable here.
**Delivers:** `discovery/ats.py` (Greenhouse, Lever with `region`, Ashby), `companies.yml` plus example file with fictional companies, `external_id`/`ats`/`ats_slug` columns, `job_arrivals` disposition and reason model, dedup L0 to L2 (exact identity certain; fuzzy only proposes `duplicate_of` with company, location and level guards; use `token_sort_ratio`, never `token_set_ratio`), `normalize.py` port, ATS-API liveness with quarantine-before-close and re-resolution, per-run source verdicts, 50% drift and global floor, JD normalization at ingest (strip hidden text, cap length), keyless first scan. Replay tests with recorded payloads.
**Uses:** `httpx`, `rapidfuzz`, `MockTransport`. **Implements:** ATS adapters, dedup, scan_config, migrations C/D.
**Avoids:** DEDUP-1, ATS-1, SEC-2 (normalize), MIN-2, MIN-3.

### Phase 4: Filter (`assess()` and the geo gate)
**Rationale:** One engine for prefilter, scorer, triage, alerts, extension and MCP, built as a behaviour-identical refactor first so existing prefilter tests are the regression net. Geo wiring follows.
**Delivers:** pure `services/assess.py` with stable versioned reason codes and `rule_version`; `run_prefilter` delegating to it; parity test across call sites; geo gate resolved per `SearchProfile` with `geo_class` persisted and visible everywhere; no geo config means no gate and class `unknown` (never an example-file fallback); multi-office evaluation using authoritative ATS office arrays; over-admission rule with a distinct `multi_office_partial` class; `kestrel why`; scoring excludes `exclude`/duplicate/closed rows; promotion conditional on verdict.
**Avoids:** GEO-1, GEO-2 (held-out split before designing the rule; report counts with intervals; differential gate kept separate from quality gate).

### Phase 5: Scan (headless run on cron; maintainer daily use begins)
**Rationale:** Needs cost guard (1), arrivals and dedup (3), assess (4). This is where the maintainer's own daily use becomes the acceptance test.
**Delivers:** `kestrel scan` as a thin wrapper over `run_scheduled_discovery(force=True)`; run lease row with heartbeat; exit codes (0 ok, 1 partial, 2 spend-halted, 3 preflight failed, 75 lease held); `--dry-run --json`, `--company`; prints resolved DB path and provider and refuses `mock`; in-lifespan scheduler off by default; `--print-schedule` snippets (launchd preferred on macOS); bounded scoring selection under the guard; `daily_pipeline` logic ported (old script still present); shadow-run window opens.
**Avoids:** ADD-1, ADD-3, REPLAY-1 (shadow plan starts).

### Phase 6: Score (digest, audit, overturn)
**Rationale:** Needs persisted reason codes (3), assess and `rule_version` (4), and a scan to feed it (5). Delivered CLI-first so it does not wait on the TUI.
**Delivers:** `triage.build_digest` (funnel, canary banner, spend line, shortlist); `audit.draw` stratified by reason code and near-miss slice with seed and inclusion probability recorded; rater sees job facts before filter-derived fields; overturn admits the job and exports a profile-free JSONL fixture with confirm fixtures as opposite polarity; `kestrel verify-fixtures` (warn first, block later); fixtures stay in the user data dir, never committed; label tools ported.
**Avoids:** DIGEST-1.

### Phase 7: Track (service extraction, TUI, outcomes, calibrate)
**Rationale:** Extraction of CLI logic into services precedes the TUI and MCP so neither reimplements it. Outcomes follow digest here (disagreement noted below).
**Delivers:** extraction PR first (no behaviour change; keep `_get_session` test seam), then `tui/` (list, detail with decision trail, status picker via `VALID_TRANSITIONS`, follow-ups, audit screen, undo); `submission_state` axis (prepared, submit_attempted, submission_confirmed) separate from `ApplicationStatus`, append-only `application_outcomes` ledger, one shared vocabulary module with a coverage test; `kestrel outcome`; paste-a-reply proposals with human accept; `kestrel calibrate` advisory report with sample floors (stretch, P2).
**Avoids:** TUI-1, OUT-1.

### Phase 8: Write (dossier, gates, drafting)
**Rationale:** Needs the spend guard and privacy boundary; independent of Phases 5 to 7 technically but sequenced after Track because drafts hang off shortlisted jobs and the `prepared` state.
**Delivers:** dossier under `KESTREL_HOME` as YAML/Markdown files (verified facts with provenance, preferences, samples) with content-hash `dossier_versions`; `fact_gate` (numbers, employers, titles, tools, tenure recompute, ownership verbs; fail closed) and `voice_gate` (lexical layer, style deltas, user style beats generic rules) as pure functions behind one `gate_draft()`; a test enumerating every draft producer; `drafting` with bounded revise loop, `final_text` captured; injection-corpus tests; planted-fabrication measurement of gate recall.
**Avoids:** GATE-1, SEC-2, DOS-1.

### Phase 9: Connect (MCP server)
**Rationale:** Depends on read services (7) and gates (8). Read tools could ship earlier, but one phase keeps the tool manifest reviewable.
**Delivers:** `kestrel mcp` over stdio, `mcp>=2.3,<3` extra, in-process service calls, roughly a dozen tools, read-only by default with `--allow-write` and a config allow-list for dossier exposure, `get_drafting_context` / `check_draft` / `save_draft`, JD text marked untrusted and length-capped, no submit/send/delete/raw SQL tools, golden manifest test, every tool has a CLI twin with `--json` (CLI is the contract for agents without MCP), stdout kept clean, lazy imports for the 10 s client startup budget, tool-call audit log. Replaces `tools/kestrel-mcp`.
**Avoids:** SEC-1, SEC-2, DEP-1.

### Phase 10: Apply (extension prefill) — schedule risk, may slip to v2.0.x
**Rationale:** Highest cost and the riskiest external dependency (per-ATS DOM stability, Chrome Web Store review). Sequenced late and behind a per-ATS spike so it cannot hold the milestone.
**Delivers:** prefill for Greenhouse, Lever, Ashby from verified dossier facts only; never submits, never solves captchas, lists skipped fields; free-text answers through `gate_draft()` with per-field accept; sets `prepared`; liveness re-check at fill time; duplicate-application warning; optional knock-out pre-scan; narrow host permissions, no telemetry.
**Avoids:** GATE-1 (every producer gated), SEC-2 (answers never derived from JD text).

### Phase 11: Retire (sprawl removal, part B)
**Rationale:** Only now is it safe to delete the live pipeline and its source scripts.
**Delivers:** per-script `PORT_LEDGER.yaml` with a test that keeps it honest; differential tests converted to golden-only; shadow-run diff ledger with zero unexplained differences; git tag of the last script revision; separate delete PRs; remove `tools/` CI steps, `daily-scan.yml`, `sonar` excludes, `conftest.py` path hacks; rewrite billing-safety invariant to target the new scan surface (and assert non-vacuous); define the private-plugin seam (versioned config schema, contract test with a fake plugin).
**Avoids:** CUT-7, REPLAY-1, PLUG-1, CUT-2.

### Phase 12: Install (15-minute stranger path and README)
**Rationale:** Last, because the README must describe the product that exists and claim only what is true. The wheel-install skeleton is already in Phase 1.
**Delivers:** `kestrel init` (data dir, `companies.yml` starter, dossier skeleton), `kestrel doctor` per-stage checks; required deterministic CI job (wheel built in the same run, clean HOME and `KESTREL_HOME`, ATS served from fixtures, `--no-browser`, free port, step budget) on the OS matrix with `uv` managed Python, plus a bare-container no-Python job; non-blocking nightly canary installing from PyPI with an unconstrained resolve and live canary boards; README commands extracted from one tested file; README leads with "learns you" limited to v2.0 truths and states what Kestrel will not do (no auto-submit, no sending, no telemetry); version story decided.
**Avoids:** INSTALL-1, DEP-1, DOC-1.

### Phase Ordering Rationale

- Foundation (with cost guard) first because every other phase either deletes, spends or opens the DB from a new entry point.
- Cut-A before the engine work shrinks CI and the coexistence surface; Cut-B is last because `tools/` holds the code being ported and the maintainer's live pipeline.
- Find before Filter: persisted arrivals and ATS office data feed `assess()`, and DEDUP-1 notes Filter depends on normalized locations. `assess` columns exist but are nullable in Find.
- Digest before Track: the digest and audit are CLI-first, so the TUI audit screen is an interactive view of something that already works.
- Gates before drafting before agents: MCP and prefill call the same `gate_draft()`.
- Each port keeps the old script until Retire (PITFALLS) rather than deleting per phase (ARCHITECTURE).

### Where the researchers disagreed, and the position taken

| Topic | Disagreement | Position and reason |
|-------|--------------|---------------------|
| Cut vs Foundation first | ARCHITECTURE puts Cut first; PITFALLS puts Foundation first | Foundation first. Cut needs the import-all test, hardened `CI Complete` and `notify()` seam to be safe. |
| Delete scripts per port vs at the end | ARCHITECTURE: each port phase deletes; PITFALLS: delete only after shadow period | Delete at the end (Retire). The live pipeline is the acceptance test, and replay needs the old code present. |
| Filter vs Find order | ARCHITECTURE: assess and dedup before ATS; PITFALLS/FEATURES: arrivals and sources feed assess | Find then Filter, with nullable verdict columns so persistence does not wait for assess. |
| Outcomes before or after digest | ARCHITECTURE: outcomes (6) before digest (7) | Digest first. Outcome display in the digest is not required for the audit loop; calibrate needs data later anyway. |
| 402/429 rule | Original requirement is status-only | Classifier on status, body code and `Retry-After` (three files agree; reconciles ARCHITECTURE's exception-class design with STACK/PITFALLS' body inspection). |
| Dedup fuzziness | STACK/ARCHITECTURE merge fuzzily in a company bucket; FEATURES lists fuzzy merge as an anti-feature; PITFALLS says fuzzy proposes only | Exact identity is certain; fuzzy only proposes `duplicate_of` and suppresses paid scoring only when company, location set and level tokens all agree. Repost flag uses title identity, not similarity. |
| Config format | STACK: TOML; FEATURES/ARCHITECTURE: YAML | YAML. Example YAML configs already exist and are the contract with the private pipeline; `pyyaml` is being declared anyway. |
| Textual as core or extra | ARCHITECTURE: core; PITFALLS DEP-1: extra | Core. The TUI is the front door once the web app is parked. Still listed under Open Questions. |
| `mcp` floor | PITFALLS: `>=1.23.0`; STACK: `>=2.3,<3` | `>=2.3,<3`: v1 import path is gone on fresh installs, and 2.x is past the CVE floor. |
| Scan lock | STACK: `scan_lease` table; ARCHITECTURE: `DiscoveryRun` heartbeat; PITFALLS: table or file lock | Heartbeat row in the DB (reuse `DiscoveryRun`); no lock-file library; stale detection by heartbeat age. |
| Existing unique constraint | STACK: replace `uq_discovered_job_dedup` (it collapses distinct requisitions); ARCHITECTURE: keep it untouched | Unresolved; see Open Questions. STACK's data-loss argument is sound for ATS data, ARCHITECTURE's cost argument (table rebuild) is real. |
| Email digest | STACK: optional stdlib `smtplib` sink; FEATURES: anti-feature in v2.0 | File, terminal and TUI by default; email is not on the 15-minute path. See Open Questions. |
| Pushover | Not named in the milestone cut list; ARCHITECTURE/PITFALLS delete it; STACK keeps it "if kept" | Decouple behind `notify()` in Phase 1; final keep/remove is an Open Question. |

### Research Flags

Phases likely needing `/gsd-plan-phase --research-phase <N>`:
- **Phase 1b (spend guard):** capture real 402/429/400 bodies for all 10 providers (only Anthropic, OpenAI, OpenRouter verified from docs); ledger design (reserve/settle under `BEGIN IMMEDIATE`); batch-API cost accounting.
- **Phase 2 (Cut):** spike generating a real v0.28.2 database and running the upgrade with FK enforcement on and off; confirm `integration_configs` handling.
- **Phase 3 (Find):** live probing of each ATS for rate limits, 404 board, empty board, EU host, Ashby `id` and `isListed`; whether the Greenhouse list endpoint can return offices without per-job fetches.
- **Phase 4 (Filter):** whether `assess()` can wrap the roughly 4,000-line scoring service at a clean seam; held-out split decision for the 277-item set.
- **Phase 8 (Write):** measurement spike for fact-gate recall on planted fabrications and voice-gate minimum sample counts.
- **Phase 10 (Apply):** per-ATS DOM spike and Chrome Web Store form-filling policy before planning.
- **Phase 9 (Connect):** light check of async tool and stdio behaviour in the pinned `mcp` version and current spec security guidance.

Phases with standard patterns (skip research-phase; acceptance criteria in PITFALLS are enough): Phase 1a, Phase 5, Phase 6, Phase 7, Phase 11, Phase 12.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Versions read from registries on 2026-10-24 (HIGH). ATS rate limits are undocumented (LOW). Provider error semantics MEDIUM (vendor docs for Anthropic and OpenRouter, secondary sources for OpenAI and Gemini). Context7 was unavailable to the researcher; official docs were used instead. |
| Features | MEDIUM-HIGH | Closest comparable tool read at the source level (HIGH for what it does); market figures are secondary and no requirement depends on them. Several design choices (audit sampling, over-admission labelling) are researcher judgment. |
| Architecture | HIGH for integration points | Read from the code on the milestone branch. MEDIUM for Textual/MCP runtime behaviour and per-vendor HTTP semantics, which were not re-verified. Script dispositions were chosen from headers and function inventories only. |
| Pitfalls | HIGH for repo-specific findings, MEDIUM for external services | Wheel contents, branch protection and workflow behaviour were observed first-hand; some SQLite BUSY_SNAPSHOT and search-summary claims are MEDIUM/LOW and flagged in the file. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **VERIFIED (orchestrator, 2026-10-24): stale frontend in the published wheel.** The published 0.28.2 wheel contains the committed April frontend at `_frontend_dist/` root and the fresh build nested under `_frontend_dist/dist/`; `main.py` serves the stale root. Root cause is `publish.yml` running `cp -r` into a git-tracked target. Filed as **G-2015** (fix on main now: `git rm` the tracked copy, replace-not-nest copy step, wheel-content CI check). Phase 1a inherits the CI guard.
- **VERIFIED (orchestrator, 2026-10-24): `CI Complete` fails open.** The aggregator only fails on `failure`/`cancelled`, so a skipped job, or a job removed from `needs`, reads as green. Harden to a success allow-list in Phase 1a before any workflow deletion.
- **`mcp` extra and `python-jobspy`:** STACK reports a fresh `kestrel-app[mcp]` resolves to 2.x, which removes the `FastMCP` import path used by `tools/kestrel-mcp/server.py`, and that `python-jobspy` is only in the dev extra so a clean install has no Indeed adapter. Both are repo-readable; confirm in Phase 1a and fix in Phases 3 and 9 (or earlier if the nightly canary is red).
- **Provider coverage beyond three vendors:** fixtures must be captured per provider; until then, providers without fixtures should default to the conservative classification and not be advertised as safe.
- **ATS behaviour:** Ashby `id` is absent from the docs but read by the existing poller; Greenhouse `offices` need `content=true`; no vendor publishes GET rate limits. Set explicit pacing defaults and verify on live responses.
- **"Calibrated scoring" scope** is not defined beyond shipped Scoring Engine v2; research assumed the outcome-calibration report plus `assess()` integration.
- **Multi-office over-admission rule** must be copied from the v1.1 geo design notes, not from this research; the 277-item set is no longer blind.
- **Not verified:** whether `uvicorn[standard]` provides `pyyaml` transitively, Pi's lack of MCP (secondary sources only), Textual behaviour on legacy Windows conhost, and the 3.14 matrix row (allowed to fail).
- **Release/version story:** with `bump-minor-pre-major`, a mass-deletion `feat!` commit yields 0.29.0, not 2.0.0; the package version and milestone name will diverge unless a `Release-As` footer is used deliberately.

## Open Questions (decisions for the requirements step)

1. **Promotion policy.** Today every new discovered job becomes an application at ingest. Options: (a) keep that for the manual and API path and promote only shortlisted jobs for `scan` (ARCHITECTURE's recommendation); (b) promote everything non-excluded; (c) promote nothing automatically. Which one, given it changes pipeline counts?
2. **Replace the existing dedup unique constraint?** Options: (a) replace `uq_discovered_job_dedup` with `(profile_id, source, external_id)` as the strong key and enforce the normalized triple in the dedup service via a batch-rebuild migration (STACK); (b) keep the constraint and add the new key alongside it (ARCHITECTURE); (c) keep it and accept that same-title same-location requisitions collapse. Which?
3. **Integrations and OAuth.** The milestone lists OAuth for removal, but OpenRouter OAuth and the `integration_configs` `ai_providers` subset carry AI keys for the web start path. Options: (a) keep the AI-provider subset and OpenRouter OAuth; (b) move to `.env` written by `kestrel init` only and delete web key entry.
4. **Is Pushover cut or kept?** It is not on the milestone's cut list. Options: (a) cut it behind the `notify()` seam (ARCHITECTURE/PITFALLS assume this); (b) keep it as the optional push sink for digest and halt alerts (STACK).
5. **Textual: core dependency or `[tui]` extra?** Options: (a) core (STACK, ARCHITECTURE); (b) extra, with `pip-audit` installing it in CI (PITFALLS DEP-1).
6. **Email digest.** Options: (a) none in v2.0, file plus terminal plus TUI only (FEATURES); (b) optional stdlib `smtplib` sink with an app password (STACK).
7. **Geo configuration keys and the over-admission rule.** What are the documented keys on `SearchProfile.filters`, and what exactly does a multi-office posting do (admit when any office qualifies and label it `multi_office_partial`, cap the fit score for foreign class, or exclude)? Options offered: copy the v1.1 definition (FEATURES, ARCHITECTURE); over-admit then label (FEATURES' recommendation).
8. **What does "calibrated scoring" add in v2.0?** Options: (a) the outcome-calibration report (`kestrel calibrate`) plus `assess()` integration (assumed); (b) additional scoring changes not yet specified.
9. **Scraper long tail.** Which of the roughly 3,500 lines of board scrapers survive? Options: (a) only sources the maintainer's scan config shows as productive (ARCHITECTURE); (b) none beyond the three ATSs plus the existing adapters; (c) more.
10. **Is fixture export ever shared publicly?** Options: (a) never, fixtures stay in the user data dir (default); (b) an opt-in "contribute a scrubbed case" path through the PII scrub gate.
11. **15-minute path: CLI-first or web onboarding?** Options: (a) `kestrel init` primary, web onboarding optional (FEATURES); (b) keep the web wizard as the start of the path (milestone text), which requires the API server and conflicts with "one install path".
12. **Version story.** Options: (a) a `Release-As: 2.0.0` footer at milestone close; (b) stay on 0.x and name the milestone separately; (c) accept 0.29.0.
13. **Alembic for cut tables.** Options: (a) leave orphan tables in place and stop using them (ARCHITECTURE, PITFALLS' safest option); (b) one forward drop revision whose `downgrade()` recreates the tables or change the CI roundtrip to a named floor.
14. **Name collision.** The chat-session `voice` service is unrelated to the voice gate. Options: (a) leave in place and name the new code `voice_gate` (ARCHITECTURE D6); (b) rename or park it now (FEATURES).
15. **Extension prefill schedule.** Options: (a) keep Phase 10 inside v2.0 behind per-ATS spikes; (b) pre-agree to slip it to v2.0.x if a spike fails or store review stalls.
16. **MCP dossier exposure.** Options: (a) expose dossier sections only through an explicit config allow-list (ARCHITECTURE); (b) read-only by default with a write flag and per-session acknowledgement that the connected agent is a third party (FEATURES, PITFALLS). These can be combined.

## Sources

### Primary (HIGH confidence)
- Repository state on the milestone branch: `src/career_os/` (config, database, main, discovery, services, ai providers, cli), `pyproject.toml`, `.github/workflows/`, `tests/` (billing-safety, import-masking guard, geo eval), `tools/` headers and function inventories (via ARCHITECTURE and PITFALLS).
- Registry and release data queried 2026-10-24: PyPI JSON API and GitHub releases API (via STACK).
- Published `kestrel-app` 0.28.2 wheel contents (via PITFALLS, re-verified by the orchestrator); branch protection and ruleset read through the GitHub API (via PITFALLS).
- Vendor docs: Greenhouse Job Board API, Lever Postings API, Ashby public job-posting API, Anthropic API errors and rate limits, OpenRouter errors and key endpoint, MCP specification (Tools, Security Best Practices), Textual guides (workers, testing, DataTable), SQLite WAL and DROP TABLE docs, Alembic batch docs, PyPI trusted publisher docs, GitHub required-status-check docs, RapidFuzz `fuzz` docs, uv docs (via STACK, FEATURES, PITFALLS).
- Comparable tool source read directly: career-ops scanner, admission gate, listing fingerprint, repost detector, liveness, canary audit, calibrate, fact gate, reply proposals and TUI (via FEATURES).

### Secondary (MEDIUM confidence)
- OpenAI 429 `insufficient_quota` behaviour from help-center articles and cookbook; Claude Code and Codex MCP configuration docs; launchd versus cron behaviour from Apple documentation and developer forums; JobOps and JobSync READMEs; Simplify Copilot help article; Hamel Husain evals FAQ; Wikipedia "Signs of AI writing".

### Tertiary (LOW confidence, needs validation)
- Gemini 429 daily-quota behaviour from forum threads; Pi's lack of built-in MCP from secondary write-ups; ghost-job and AI-resume survey figures (market color only); SQLite BUSY_SNAPSHOT mechanics and stale-`build/` wheel behaviour from search summaries; hidden-prompt-injection prevalence from secondary coverage of a study the researcher did not open.

---
*Research completed: 2026-10-24*
*Ready for roadmap: yes*
