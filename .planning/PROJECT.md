# Kestrel

## Current State

**v1.0 Public Roadmap shipped 2026-05-07.** The repo now has a public roadmap at root, 20 milestone deep dives in `docs/roadmap/`, contributor callouts pointing to concrete contribution areas, a Finding Work section in CONTRIBUTING.md, and a Codespaces one-click dev environment. Phase 1 (Feature Inventory) was deferred to v1.1 — its intent was naturally absorbed into deep dives + `docs/roadmap/inventory.md`.

## Next Milestone Goals

To be defined via `/gsd-new-milestone`. Carry-over candidates:
- **Feature Inventory deferred (INV-01..08)** — only worth picking up if a unified standalone inventory.md is wanted
- **Deployment/packaging milestone** — highest-priority forward work per Phase 3 (PWA → native desktop app)
- **BMAD PRD process** — 5/13 steps complete from earlier work, could be picked back up

## What This Is

A public, demo-ready roadmap for Kestrel — the AI-powered, self-hosted job search platform — that lives on GitHub as the single source of truth for where the product is and where it's going. The roadmap documents everything shipped, lays out the forward vision, and becomes the backbone of a structured planning hierarchy: roadmap → BMAD PRDs → milestones → epics → Linear tickets.

## Core Value

Make Kestrel's direction visible and structured so users can evaluate the product, contributors can pick meaningful work, and development stays coherent across sessions and milestones.

## Requirements

### Validated

- ✓ Backend API with 27 routes, 36 services, layered architecture — existing
- ✓ Web frontend (React 19, Vite, TanStack Query, Tailwind CSS) — existing
- ✓ AI provider abstraction (5 providers: Mock, OpenRouter, Anthropic, Ollama, Together) — existing
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

### Active

- [ ] Define epic structure within milestones that links to Linear tickets

### Validated in v1.0 Public Roadmap (2026-05-07)

- ✓ Write comprehensive ROADMAP.md at repo root documenting shipped progress and forward vision — Phase 2 (ROAD-01..08)
- ✓ Document forward milestones through end-user lens — Phase 3 (ROAD-09..16)
- ✓ Create docs/roadmap/ structure for per-milestone deep dives (20 files) — Phase 4 (DEEP-01..04)
- ✓ Add "Want to help?" callouts to every milestone, planning hierarchy in inventory.md — Phase 5 (CONT-01)
- ✓ Finding Work section in CONTRIBUTING.md pointing back to ROADMAP.md — Phase 5 (CONT-02 partial — formal hierarchy doc lives in inventory.md)
- ✓ Codespaces one-click dev environment with auto-starting backend + frontend servers — Phase 5 (CONT-03)

### Deferred to v1.1

- INV-01..08 — Feature Inventory was deliberately not executed; intent absorbed into deep dives + inventory.md. Picks back up only if a unified standalone inventory artifact is desired.

### Out of Scope

- Implementing any new Kestrel features — this milestone is roadmap/planning infrastructure only
- Building the actual SaaS platform (hosting, billing, auth tiers) — commercial forks off to separate repo later
- Mobile app development — parked, documented in roadmap as future milestone
- Browser extension development — documented as planned feature in roadmap, not built this milestone
- Career roadmapping user feature — future product feature
- Changing any existing code or architecture — read-only analysis of current state

## Context

**NORTH STAR: Web-first, user-first — NOT developer-first.**
Kestrel is a web application for job seekers, not a dev tool that happens to have a UI. Every roadmap milestone must be framed through the lens of end-user experience. The web frontend is the primary interface. CLI and self-hosting are advanced options, not the default path. Moving to real end-user experience is the highest priority after this roadmap milestone.

Kestrel has shipped substantial functionality across backend, frontend, AI, and infrastructure — but development has been organic and the full picture isn't captured anywhere. The codebase analysis (`.planning/codebase/`) documents the technical state. Memory files track individual epics and decisions. But there's no single document that tells the story: "here's what Kestrel is, here's what's done, here's what's next."

**Deployment/packaging gap (CRITICAL — highest priority forward milestone):**
Currently 3 techy ways to run Kestrel: (1) clone + set env vars + uvicorn, (2) Docker compose, (3) pip install + manual config. ALL of these are developer-oriented. None are acceptable for real end users. The roadmap must chart the path from "dev self-help tool" to "download, open, use" — this is THE most important forward-looking milestone, not just one of many.

**Target deployment vision:** Native desktop app experience (Electron/Tauri wrapper or similar). Download a `.dmg`/`.exe`, install, open, use. Data stays local, experience is polished. Think Obsidian — self-hosted but feels like a real app. Apple Developer Certificate budget approved for proper macOS signing/notarization. The web frontend IS the app — just packaged as a desktop application with embedded backend.

**Planned features for roadmap (not built this milestone, but documented):**
- Browser extension (Chrome/Firefox) — one-click "add this job to scoring DB" from any job page, even beyond scraper reach
- Mobile app — parked scaffold, resumes when web v1 is solid
- Profile & Skills — RPG-style character sheet (not gamified/cringe), inspired by Ray Dalio's baseball cards but techier. Honest skill mapping with levels, strengths, gaps
- Gap Analysis & Coaching — select target role/path, continuous gap analysis, personal development stepping stones. Progressive depth: skill maps → awesome-learn-anything lists → MOOCs → AI-assisted learning/coaching. "Can't coach you to Apple CEO, but can coach you to better specialist, communicator, professional, human"
- Codespaces one-click setup — `.devcontainer/` for instant dev environment

**Business model (decided):**
- This repo stays **non-commercial and public**. Always free, always self-deployable, full-featured
- Commercial SaaS product **forks off separately** later — different repo, different deployment, paid subscription tiers with refined UI/UX, managed infrastructure, GDPR compliance, zero-access privacy
- Model reference: screenpi.pe approach — open-source repo is the product, commercial offering forks off independently
- **Codespaces-friendly**: target one-click dev environment via `.devcontainer/` (free tier: 60 hours/month on 2-core)

**Planning hierarchy (target):**
```
ROADMAP.md (master, repo root)
  └── docs/roadmap/ (per-milestone detail)
       └── BMAD PRDs (product requirements)
            └── Milestones (scoped deliverables)
                 └── Epics (feature groupings)
                      └── Linear tickets (granular tasks)
```

**Existing planning infrastructure:**
- GSD workflow system (`.planning/`, phases, plans, execution)
- BMAD product planning (`_bmad/`, PRD creation in progress — 5/13 steps done)
- Linear for task tracking (team: G)
- Memory system tracking decisions, research, feedback across sessions

**Key shipped epics (from memory):**
- Scoring evolution: 11 epics, self-calibrating with 288 job family presets
- Token optimization: full stack cost control shipped
- Test infrastructure: 6 phases shipped
- CI/CD: 4-phase roadmap researched, 22 tickets created
- Docs audit: 40+ docs restructured
- AI providers: Wave 1 shipped (6 providers/middleware), Waves 2-4 planned
- Cost control: 17 tickets, research in docs/research/

**Technical debt highlights (from codebase analysis):**
- Scoring service monolith (4,262 lines)
- Mock provider maintenance burden (1,844 lines)
- No pip lockfile for reproducible builds
- Synchronous external API clients blocking event loop
- Frontend types manually maintained (drift risk)
- SQLite-only (Supabase migration researched but unimplemented)

## Constraints

- **Format**: ROADMAP.md at repo root (GitHub-rendered Markdown), docs/roadmap/ for depth
- **Audience**: Must be readable by non-technical users evaluating the product, developers wanting to contribute, and the maintainer for cross-session planning
- **Accuracy**: Every claim about shipped features must be verifiable against codebase
- **Structure**: Must support future BMAD PRD integration — milestones and epics as plug-in points
- **No code changes**: This milestone is documentation and planning only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ROADMAP.md at repo root + docs/roadmap/ for depth | GitHub renders root markdown prominently; depth docs keep master clean | — Pending |
| Open-source core + hosted SaaS business model | GitLab/Supabase model proven; aligns with self-hosted ethos while enabling sustainability | — Pending |
| BMAD PRDs feed into milestone structure | PRD process already in progress (5/13 steps); roadmap should receive its output | — Pending |
| Linear remains single source for task tracking | Already established (team G, 100+ tickets); GitHub Issues not used | — Pending |
| Map existing progress before forward planning | "Bag of cats" — can't plan forward without knowing what's built | — Pending |

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
*Last updated: 2026-05-07 after v1.0 Public Roadmap milestone completion*
