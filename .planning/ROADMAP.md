# Roadmap: Kestrel Onboarding Experience

## Overview

This roadmap takes a new Kestrel user from "just installed" to "seeing scored results and knowing where to go next" in under 10 minutes. The build order follows the dependency chain: shared onboarding state first (everything reads/writes it), then the CLI wizard (first touch for pip users), then demo data (needed before web can show results), then the web welcome flow, and finally the interactive tour and feedback channel (which attach to pages that must already exist). CV file parsing is v2 -- v1 uses guided questions and paste-text extraction only.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Onboarding State Foundation** - Shared state model, API endpoints, and error infrastructure that all onboarding surfaces depend on
- [ ] **Phase 2: CLI Wizard** - Complete `kestrel init` interactive wizard with profile questions, paste-text extraction, health check, and guided next steps
- [ ] **Phase 3: Demo Data** - Pre-baked sample jobs with pre-computed scores that deliver the "aha moment" without requiring an API key
- [ ] **Phase 4: Web Welcome Flow** - First-time welcome screen, onboarding guard, web profile questions, resume/skip/complete flow, and post-onboarding AI provider nudge
- [ ] **Phase 5: Interactive Tour, Feedback, and Polish** - Shepherd.js guided tour, empty state coaching, persistent feedback button, and non-developer documentation

## Phase Details

### Phase 1: Onboarding State Foundation
**Goal**: A shared, persistent onboarding state model exists that both CLI and web can read and write, with structured error handling that never shows stack traces to users
**Depends on**: Nothing (first phase)
**Requirements**: INF-01, INF-02, INF-03
**Success Criteria** (what must be TRUE):
  1. Onboarding state is persisted per-profile in the backend DB with timestamps (not booleans) and survives server restarts
  2. `GET /api/onboarding/status` returns the current onboarding state for a profile and `PATCH /api/onboarding/status` updates it
  3. Any onboarding error raised anywhere in the codebase carries a `user_message` and `resolution` field (no raw stack traces reach the user unless --verbose)
**Plans**: 3 plans

Plans:
- [x] 01-00-PLAN.md — Wave 0 failing test stubs for INF-01, INF-02, INF-03 (TDD contract) — COMPLETE 2026-04-20
- [x] 01-01-PLAN.md — Error hierarchy, OnboardingState model, Pydantic schemas (INF-01, INF-02 foundation)
- [ ] 01-02-PLAN.md — Alembic migration registration, DB table creation, service layer business logic (INF-01, INF-02, INF-03 service)
- [ ] 01-03-PLAN.md — API routes, main.py wiring, full test suite (INF-01, INF-02, INF-03 complete)

### Phase 2: CLI Wizard
**Goal**: A user who runs `pip install kestrel-app` and types `kestrel` is guided through profile setup, sees their data confirmed, and knows exactly what to do next -- all from the terminal
**Depends on**: Phase 1
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07, CLI-08, PROF-01, PROF-02, PROF-03
**Success Criteria** (what must be TRUE):
  1. Running `kestrel` for the first time after install prints a next-steps message pointing to `kestrel init`
  2. `kestrel init` walks through 5-7 skippable profile questions (name, location, target roles, salary, skills, experience) with progress indicators, and optionally accepts pasted resume text for regex extraction
  3. Extracted/entered data is shown for user confirmation before saving to the profile
  4. `kestrel init --skip` creates a complete default profile and exits immediately; non-TTY environments get a clear message with `--non-interactive` guidance
  5. `kestrel doctor` verifies setup health (DB, config, sample data, Python version) and every error during onboarding includes what happened, why, and what to do next
**Plans**: TBD

### Phase 3: Demo Data
**Goal**: Users see realistic scored job results immediately after onboarding completes, proving the tool works without requiring any API key or external service
**Depends on**: Phase 1
**Requirements**: DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05
**Success Criteria** (what must be TRUE):
  1. Ten pre-baked sample jobs spanning 3+ job families (not just tech -- includes marketing, operations, finance) ship as fixture data in the package
  2. Demo records display relative dates (never look stale), carry an `is_demo=True` flag, and show a "Sample Results" banner in the UI
  3. The demo seeder is idempotent -- running it multiple times produces exactly the same result with no duplicate records
**Plans**: TBD

### Phase 4: Web Welcome Flow
**Goal**: A first-time web visitor is guided from an empty dashboard to a populated profile with demo results, knows what was configured and what was skipped, and sees the path to full AI-powered scoring
**Depends on**: Phase 1, Phase 3
**Requirements**: WEB-01, WEB-02, WEB-04, WEB-07, WEB-08, WEB-09, PROF-04
**Success Criteria** (what must be TRUE):
  1. First-time visitors are redirected to `/welcome` via an OnboardingGuard route wrapper; returning visitors go straight to the dashboard
  2. The welcome flow walks through setup steps including the same profile questions as the CLI (name, location, roles, salary, skills, experience), and users can resume from last completed step after closing the browser
  3. End-of-onboarding summary shows what was configured and what was skipped, with "do it later" signposting providing exact navigation paths (e.g., "Settings > Profile")
  4. After onboarding completes, an "Unlock full scoring" card shows AI provider options (OpenRouter one-click OAuth, Together.ai, Ollama) with a link to provider settings
**Plans**: TBD
**UI hint**: yes

### Phase 5: Interactive Tour, Feedback, and Polish
**Goal**: Users who completed onboarding get a contextual guided tour of the actual UI, can always reach out for help, and non-developers have a documentation safety net
**Depends on**: Phase 4
**Requirements**: WEB-03, WEB-05, WEB-06, FB-01, FB-02, FB-03, INF-04
**Success Criteria** (what must be TRUE):
  1. Shepherd.js interactive tour walks through Pipeline, Discovery, and Scoring pages with tooltips that are keyboard-navigable, have aria-live announcements, proper focus management, and a skip button
  2. Pipeline, Discovery, Contacts, and Skills pages show empty state coaching when no data exists (guiding users to populate each section)
  3. A persistent feedback button is visible on all web pages (bottom-right) that opens a pre-filled GitHub issue URL with system info (OS, Python version, Kestrel version)
  4. End-of-onboarding screen prompts for feedback with a link to GitHub issues and contact info
  5. A "Getting Started for Non-Developers" documentation page exists explaining terminal basics needed for Kestrel
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5
Note: Phases 2 and 3 can execute in parallel (both depend only on Phase 1).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Onboarding State Foundation | 2/4 | In Progress|  |
| 2. CLI Wizard | 0/0 | Not started | - |
| 3. Demo Data | 0/0 | Not started | - |
| 4. Web Welcome Flow | 0/0 | Not started | - |
| 5. Interactive Tour, Feedback, and Polish | 0/0 | Not started | - |
