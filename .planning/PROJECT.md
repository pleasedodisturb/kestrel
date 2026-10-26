# Kestrel

## Current State

**roadmap-m1 (Public Roadmap) shipped 2026-05-07.** Since then the codebase moved on outside GSD: Scoring Engine v2 (G-1335..G-1338, July), the browser extension "the eye" (v0.24.0, August), the generic 7-way geo engine (G-1474, `src/career_os/services/geo/`, August), an evidence-bound pre-push review gate (G-1725/G-1726, September) and a Dependabot/CodeQL intake (September). Main is at v0.28.x with 0 open security alerts.

## Current Milestone: v2.0 Lean Kestrel

**Linear epic:** G-2013. v1.1 closed at phase 6 (G-1382/G-1383 shipped 2026-10-23); its unstarted phases 7–10 (geo gate wiring, over-admission rule, single geo authority, provider preflight) fold into this milestone.

**Goal:** Turn Kestrel from a do-everything platform into one loop a real person can run: it finds and triages jobs, helps you write in your own voice, and learns from every outcome. The maintainer runs his own daily search on it, and a technical stranger gets from clone to a first useful job list in 15 minutes.

**Thesis:** Kestrel tried to wear every hat at once and served no one. What proved itself in daily use and in the field: find jobs, take the dread out of the process, automate the non-human parts (searching, filtering, opening applications), assist the human parts (writing in your voice, preparing, deciding), and learn the person over time.

**Target features (v2.0):**
- Cut the sprawl: planning-framework scaffolding, the Cloudflare worker and dashboard, TickTick/calendar/OAuth/WARN integrations, unused deploy and release surface. Park the web app behind the TUI (kept working, since it is the start of the 15-minute path). Fix the default `0.0.0.0` bind (G-2009). Script logic is deleted only after it is ported and replay-verified.
- One engine: port the proven pipeline logic that today lives in scripts into `src/` (ATS-API sources, single eligibility engine with the geo gate, dedup within batch and against history, liveness with ATS re-resolution, canaries and floors, cost safety: preflight, spend halt, 429 = wait). A headless `kestrel scan` on cron that persists every arrival.
- Filter & Score: one `assess()` used by prefilter, scorer, triage and alerts; calibrated scoring; a daily digest with a recurring audit of excluded jobs the user can overturn.
- Track: a Textual TUI over the existing CLI; shortlist; outcome states (prepared / submit attempted / submission confirmed).
- Know you & Write: a readable, versioned profile dossier (verified facts, preferences, writing samples kept distinct); voice gate and fact gate; drafting in the user's voice; extension prefill built on the ATS lessons.
- Connect: an MCP server so the user's coding agents (Claude Code, Codex, Pi) draft through Kestrel's state; the private pipeline shrinks to config, data and private plugins.
- 15-minute install for a technical stranger, tested on a fresh machine; README rewritten around the thesis, leading with "learns you".

**Deferred to v2.1:** non-technical (no-terminal) path, richer person model with a kill criterion, automated learning from edits and outcomes, Firefox target, opt-in auto-submit.

**Key context:** Cross-AI review (Codex CLI and Mistral Vibe CLI, 2026-10-23) shaped this scope: make the maintainer's own daily use the acceptance test, keep one install path, treat the person model as a hypothesis, audit what the filters exclude, verify every port by replay. Every phase is a PR on its own `<ticket>/<slug>` branch, commits carry `review-push` trailers after a Codex review, merged only on green CI. Phase and feature names are plain verbs in workflow order (Find → Filter → Score → Track → Write → Apply → Learn).

## What This Is

Kestrel is a self-hosted job-search engine for one person at a time. It finds jobs from ATS APIs and boards, keeps every arrival, triages and scores against the person's own dossier, tracks the applications, drafts in the person's voice, and learns from outcomes. The surfaces are a CLI, a Textual TUI and an MCP server for the user's coding agents; the web app is kept working but parked behind them. The Python package is `career_os`, the PyPI name is `kestrel-app`.

## Core Value

One loop a real person runs every day: find, triage, apply, learn. The maintainer's own daily search is the acceptance test, and a technical stranger gets from clone to a first useful job list in 15 minutes.

## Requirements

### Validated

- ✓ Backend API with 31 routers (150 endpoints), 50 service modules plus the geo package, layered architecture — existing (counts as of 2026-09-28)
- ✓ Web frontend (React 19, Vite, TanStack Query, Tailwind CSS) — existing
- ✓ AI provider abstraction (10 real providers plus mock: OpenRouter, Anthropic, OpenAI, Together, Groq, xAI, Gemini, Ollama, Mistral, Hugging Face) — existing
- ✓ AI-powered job scoring with multi-factor rubric, borderline re-scoring, feedback calibration — existing
- ✓ Job discovery engine with scraper adapters and background scheduling — existing
- ✓ Application state machine with enforced transitions — existing
- ✓ Token optimization (complexity routing, caching, batch scoring) — existing
- ✓ Test infrastructure (pytest + Vitest + CI pipeline) — existing
- ✓ CI/CD (GitHub Actions: lint, test, audit, SonarCloud, PII scan) — existing
- ✓ Documentation audit and restructure (40+ docs) — existing
- ✓ Privacy layer (PII masking, provider privacy registry, GDPR metadata) — existing
- ✓ Self-calibrating scoring (288 job family presets, fuzzy matching, 18 sectors) — existing
- ✓ CLI (Typer-based: pipeline, skills, goals, interview-prep, contacts) — existing
- ✓ Docker packaging (dev + prod, single-container production mode) — existing
- ✓ PyPI distribution (`kestrel-app` package) — existing
- ✓ Cloudflare Worker (Linear↔TickTick sync, calendar feed) — existing
- ✓ Integration system (TickTick, Pushover, Calendar, AI providers, OAuth PKCE) — existing
- ✓ Web frontend (React 19, 11 pages, Kanban board, analytics, discovery — works locally) — existing
- ⏸ Mobile app (React Native/Expo scaffold, paused for web v1 priority) — parked
- ✓ Test suite is honest: AST guard fails collection on import-masking module skips (incl. flag-variable skipif and unittest.SkipTest), dead parser suite deleted with its 19 cases ledgered, ruff==0.16.9 pinned in pyproject and pre-commit with a drift guard and force-exclude for `_alembic` — Phase 6 (2026-09-30)

### Active

- [ ] A technical stranger gets from clone to a first triaged job list in 15 minutes on a fresh machine (v2.0)
- [ ] The maintainer runs his daily job search on Kestrel's engine, with his private repo reduced to config and data (v2.0)
- [ ] `kestrel scan` runs headless on cron, persists every arrival, and dedups within the batch and against history before any paid scoring (v2.0)
- [ ] One eligibility engine (`assess()`) decides for prefilter, scorer, triage and alerts, including the geo gate per search profile with `geo_class` visible in results (v2.0, absorbs v1.1 phases 7–9)
- [ ] Providers tell "no credits" (402) from "rate limited" (429); 429 waits instead of escalating; a preflight reports readiness and a spend halt is a code invariant (v2.0, absorbs v1.1 phase 10)
- [ ] The daily digest includes an audit sample of excluded jobs that the user can overturn, and every overturn becomes a regression fixture (v2.0)
- [ ] A Textual TUI shows the shortlist, follow-ups due and outcome states, over the same service layer the CLI uses (v2.0)
- [ ] Drafts are written in the user's voice from a readable dossier and pass a fact gate against verified facts (v2.0)
- [ ] The user's coding agents draft through a Kestrel MCP server (v2.0)
- [ ] Define epic structure within milestones that links to Linear tickets — done in practice: each GSD milestone is a Linear epic with phase tickets as children (G-1790)

### Validated in roadmap-m1 (Public Roadmap) (2026-05-07)

- ✓ Write comprehensive ROADMAP.md at repo root documenting shipped progress and forward vision — Phase 2 (ROAD-01..08)
- ✓ Document forward milestones through end-user lens — Phase 3 (ROAD-09..16)
- ✓ Create docs/roadmap/ structure for per-milestone deep dives (20 files) — Phase 4 (DEEP-01..04)
- ✓ Add "Want to help?" callouts to every milestone, planning hierarchy in inventory.md — Phase 5 (CONT-01)
- ✓ Finding Work section in CONTRIBUTING.md pointing back to ROADMAP.md — Phase 5 (CONT-02 partial — formal hierarchy doc lives in inventory.md)
- ✓ Codespaces one-click dev environment with auto-starting backend + frontend servers — Phase 5 (CONT-03)

### Deferred to v1.1

- INV-01..08 — Feature Inventory was deliberately not executed; intent absorbed into deep dives + inventory.md. Picks back up only if a unified standalone inventory artifact is desired.

### Out of Scope

- A non-technical (no-terminal) install path, a richer person model, automated learning from edits and outcomes, Firefox, opt-in auto-submit — v2.1
- Onboarding other people's profiles (the friends' profiles are the v2.1 test); v2.0 only guarantees nothing hard-codes the maintainer's profile
- Cutting AI providers, writing, prefill or voice — they are the product
- A private clone of the repo for v2.0 work — declined; the private retrospective runs inside the private pipeline's repository and only an anonymised verdict list enters this repo
- Email digest as a delivery channel — Pushover stays until Retire
- A hosted SaaS (hosting, billing, auth tiers) — a separate repo if ever
- Mobile app — parked
- Rewriting history: scripts and integrations are deleted only after their logic is ported and replay-verified against Map goldens

## Context

**North star for v2.0: lean, engine-first, one person at a time.** The web-first framing of the 2026-04 roadmap milestone is superseded. The CLI, the TUI and the MCP server are the primary surfaces; the web app is kept working but parked; "download, open, use" packaging is a later milestone. Agents planning any v2.0 phase must read the "Current Milestone" section above and `.planning/STATE.md` ("v2.0 review position") as ground truth, not the history below.

**How v2.0 is built.** The maintainer reviews each phase of the reconciled build order one by one (idea / process / results), and phases are added to the roadmap only after their review closes: Map → Foundation → Cut A → Find → Filter → Scan → Score → Track → Write → Connect → Apply → Retire → Install. Map is the milestone-level instance of "tests and output mapping first": it freezes a script ledger, goldens with source hashes, strict-xfail mapping tables and per-source arrival counts before anything is built or cut. Every port is verified by replay against those goldens; the old script stays until Retire.

**Where the evidence comes from.** The maintainer's private pipeline (a separate, private repository) ran the full loop daily from June to October 2026 with 21 configured sources and roughly ten thousand lines of scripts. That pipeline is the source of the ported logic and of the Track B flow retrospective. Its raw material never enters this repository: committed files carry only anonymised verdicts, synthetic or scrubbed fixtures and aggregate counts, and the CI PII scan is the second net, not the first. See `docs/coe/2026-07-09_initial-commit-pii-exposure.md` for why.

**Cross-AI review shaped the scope** (Codex CLI and Mistral Vibe CLI, 2026-10-23): make the maintainer's own daily use the acceptance test, keep one install path, treat the person model as a hypothesis, audit what the filters exclude, verify every port by replay.

**Business model (unchanged):** this repo stays non-commercial, public, always free and self-deployable. A commercial offering, if ever, forks off into a separate repo.

**Existing planning infrastructure:** GSD (`.planning/`, committed), Linear team G (one epic per milestone, G-2013 for v2.0, phase tickets as children), the `review-push` evidence-bound pre-push review gate, memory files across sessions. BMAD is removed in Cut A.

**Technical debt that v2.0 addresses directly:** scoring and discovery logic split between `src/` and `tools/` scripts; a shared `integration_configs` table where AI credentials sit next to third-party tokens and a silent-fail credential read; `0.0.0.0` default bind (G-2009); no pip lockfile; consumer-less workflows and packaging targets (npm, Homebrew, GHCR).

<details>
<summary>History: context of the 2026-04 Public Roadmap milestone (roadmap-m1, shipped 2026-05-07)</summary>

**NORTH STAR at the time: Web-first, user-first — NOT developer-first.** Kestrel was framed as a web application for job seekers with the web frontend as the primary interface and CLI/self-hosting as advanced options. The "deployment/packaging gap" (three developer-oriented ways to run Kestrel, none acceptable for end users) was named the highest-priority forward milestone, with a native desktop wrapper (Electron/Tauri, signed `.dmg`/`.exe`, Obsidian-like) as the target vision. Planned features documented then: browser extension (since shipped as "the eye", v0.24.0), mobile app (parked), RPG-style profile and skills sheet, gap analysis and coaching, Codespaces one-click setup (shipped). Planning hierarchy target: ROADMAP.md → docs/roadmap/ → BMAD PRDs → milestones → epics → Linear tickets. Technical debt noted then: scoring service monolith (4,262 lines), mock provider burden (1,844 lines), no pip lockfile, synchronous external clients, hand-maintained frontend types, SQLite-only.

v2.0 reverses the web-first framing on the evidence of six months of daily use: the engine and the terminal surfaces are what got used; the web app did not.

</details>

## Constraints

- **Privacy boundary**: `.planning/`, `docs/` and `tests/` are public. No company names, person names, dates finer than a month, transcript quotes or private paths. Raw retrospective material lives only in the private pipeline's repository, referred to here only as "the private pipeline".
- **Port before cut**: no script or integration is deleted before its logic is ported into `src/` and replay-verified against the Map goldens; old scripts stay until Retire.
- **Map is read-only**: no changes under `src/career_os/`, no paid LLM calls, no scan or scoring runs during Phase 11.
- **Cost**: no bulk paid LLM operation without an estimate and the maintainer's go; the spend guard is a code invariant from Foundation on.
- **Delivery**: every phase is a PR on its own `<ticket>/<slug>` branch, commits carry `review-push` trailers after an independent review, CI green before merge, forward-only Alembic migrations with row-scoped deletes.
- **Per-profile**: nothing new hard-codes the maintainer's profile; Map tags every verdict profile-specific vs generic.
- **Surfaces**: CLI and TUI first, MCP server for agents; the web app stays working but receives no new features in v2.0.
- **Release**: v2.0 ships as `2.0.0` (Release-As) once Install passes on a fresh machine.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ROADMAP.md at repo root + docs/roadmap/ for depth | GitHub renders root markdown prominently; depth docs keep master clean | — Pending |
| Open-source core + hosted SaaS business model | GitLab/Supabase model proven; aligns with self-hosted ethos while enabling sustainability | — Pending |
| BMAD PRDs feed into milestone structure | PRD process already in progress (5/13 steps); roadmap should receive its output | — Pending |
| Linear remains single source for task tracking | Already established (team G, 100+ tickets); GitHub Issues not used | — Pending |
| Map existing progress before forward planning | "Bag of cats" — can't plan forward without knowing what's built | — Pending |
| Resolve the ruff pin from the newest green main CI run at execution time, never from research notes | Research, venv and pre-commit each held a different version; only CI's resolution is the contract | Done — 0.16.9 pinned in both files (G-1383) |
| Keep `force-exclude = true` even though the pre-commit ruff hooks already pass `--force-exclude` | Belt and braces for bare and editor invocations; the RESEARCH claim that pre-commit bypassed the `_alembic` exclude was wrong | Done (Phase 6) |
| Delete the dead `test_parse_scoring_response.py` and ledger all 19 cases (7 covered, 10 re-pinned, 2 out of contract) instead of relocating it | Its subject has zero live callers; a ledger keeps the deletion auditable | Done (G-1382) |
| Import-masking guard is AST-based with no allowlist, and fails loudly on unparseable files | An exemption mechanism would recreate the silent-skip class it exists to remove | Done; extended after code review to flag-variable skipif and unittest.SkipTest (WR-01) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-26 — What This Is, Core Value, Out of Scope, Context and Constraints refreshed to the v2.0 frame (G-2013)*
