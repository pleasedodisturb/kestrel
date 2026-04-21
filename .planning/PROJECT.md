# Kestrel Public Roadmap

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

### Active

- [ ] Write comprehensive ROADMAP.md at repo root documenting shipped progress and forward vision
- [ ] Create docs/roadmap/ structure for per-milestone deep dives
- [ ] Map all existing shipped work into coherent product narrative
- [ ] Define milestone structure that BMAD PRDs can plug into
- [ ] Define epic structure within milestones that links to Linear tickets
- [ ] Establish the open-source core vs. SaaS tier boundary
- [ ] Chart the evolution path: open-source tool → commercial SaaS platform

### Out of Scope

- Implementing any new Kestrel features — this milestone is roadmap/planning infrastructure only
- Building the actual SaaS platform (hosting, billing, auth tiers) — that's a future milestone informed by this roadmap
- Mobile app development — paused, preserved for future release
- Career roadmapping user feature — future product feature, not part of this planning milestone
- Changing any existing code or architecture — read-only analysis of current state

## Context

Kestrel has shipped substantial functionality across backend, frontend, AI, and infrastructure — but development has been organic and the full picture isn't captured anywhere. The codebase analysis (`.planning/codebase/`) documents the technical state. Memory files track individual epics and decisions. But there's no single document that tells the story: "here's what Kestrel is, here's what's done, here's what's next."

**Business model (decided):**
- Open-source core: always free, self-deployable, full-featured
- Hosted SaaS: paid subscription tiers with refined UI/UX, managed infrastructure, GDPR compliance, zero-access privacy option
- Model reference: GitLab/Supabase approach — open-source base + commercial hosted offering

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
*Last updated: 2026-04-21 after initialization*
