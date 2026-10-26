# Kestrel Milestones

Historical record of shipped milestones. Each entry archives to `.planning/milestones/v[X.Y]-ROADMAP.md` and `.planning/milestones/v[X.Y]-REQUIREMENTS.md` for full details.

## roadmap-m1 (Public Roadmap) — Shipped 2026-05-07

**Goal:** Transform Kestrel's organic development history into a visible, structured public roadmap. Make the project legible to non-technical users evaluating the product, contributors picking meaningful work, and the maintainer planning across sessions.

**Phases:** 5 (1 deliberately skipped, 4 executed)
**Plans:** 8/9 complete
**Tasks:** 17 commits affecting milestone files
**LOC delta:** +1,761 / −6 across 25 files
**Timeline:** 2026-04-21 → 2026-05-07 (16 days, editorial work)

### Key Accomplishments

1. **ROADMAP.md at repo root** — single canonical roadmap with 19 milestones (10 shipped + 9 planned/considering), Mermaid timeline + dependency diagrams, Now/Next/Later horizons, public statement of non-commercial intent
2. **Forward vision documented** — every planned milestone (Desktop App, Browser Extension, Mobile, Profile & Skills, Know Me, Gap Analysis, Voice Mode, Hosted Version) framed through end-user benefit, not developer tasks
3. **20 milestone deep dives in `docs/roadmap/`** — per-milestone detail covering goal, technical approach, status, research links, BMAD integration; bidirectionally wired to ROADMAP.md
4. **Contributor experience layer** — 19 "Want to help?" callouts in ROADMAP.md, planning hierarchy explained in inventory.md (ROADMAP → BMAD PRDs → milestones → epics → tickets), Finding Work section in CONTRIBUTING.md
5. **One-click dev environment** — Codespaces badge + devcontainer pinned to Python 3.11 + VS Code tasks auto-start backend (8100) and frontend (8101) on workspace open; verified live in UAT

### Known Deferred Items

- **INV-01 through INV-08** (Phase 1 Feature Inventory) — deliberately skipped during execution. The intent was naturally absorbed into Phase 4's deep dives and `docs/roadmap/inventory.md`. Formally deferred to v1.1 if a unified inventory.md is still wanted; otherwise can be retired. See `.planning/roadmap-m1-MILESTONE-AUDIT.md`.

### Audit

`.planning/roadmap-m1-MILESTONE-AUDIT.md` — final status `gaps_found` due to INV-* deferrals (intentional). All 3 cross-phase wiring gaps were fixed inline before close (commit `8be5b12`).

### Archives

- `.planning/milestones/roadmap-m1-ROADMAP.md` — full milestone roadmap with phase details
- `.planning/milestones/roadmap-m1-REQUIREMENTS.md` — final requirements status with outcomes

## v1.1 (Geo gate to production) — Closed early 2026-10-23

**Goal:** Make the shipped geo engine actually decide something in production, with one classifier, honest tests and provider failures told apart. Linear epic G-1790.

**Phases:** 5 planned (6-10), 1 executed (Phase 6 Test honesty, 2/2 plans, shipped 2026-09-30, merged 2026-10-23 in #572/#573)
**Requirements:** 4/20 satisfied (TEST-01..04)
**Timeline:** 2026-09-28 → 2026-10-23

### Why it closed early

The maintainer reset direction on 2026-10-23 toward a lean rebuild (v2.0 Lean Kestrel, G-2013). Phases 7-10 (wire the geo gate, over-admission rule, single geo authority, provider preflight) were folded into v2.0 rather than executed as written: the geo work lands inside the one `assess()` engine (Filter), the provider work inside the Foundation cost guard with a status+code+Retry-After classifier.

### Key Accomplishments

1. **Honest test suite** — AST guard fails collection on import-masking module-level skips (incl. flag-variable skipif and unittest.SkipTest); the dead parser suite was deleted with a 19-case ledger and 10 live behaviours re-pinned
2. **One ruff** — ruff==0.16.9 pinned in pyproject and pre-commit with a drift guard and force-exclude for `_alembic`

### Archives

- `.planning/milestones/v1.1-ROADMAP.md` — roadmap as written at close
- `.planning/milestones/v1.1-REQUIREMENTS.md` — requirements with final status
- `.planning/milestones/v1.1-phases/` — phase directories (06-test-honesty, plus the extension phases 00/01 that ran outside the v1.1 roadmap)
