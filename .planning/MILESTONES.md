# Kestrel Milestones

Historical record of shipped milestones. Each entry archives to `.planning/milestones/v[X.Y]-ROADMAP.md` and `.planning/milestones/v[X.Y]-REQUIREMENTS.md` for full details.

## v1.0 Public Roadmap — Shipped 2026-05-07

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

- **INV-01 through INV-08** (Phase 1 Feature Inventory) — deliberately skipped during execution. The intent was naturally absorbed into Phase 4's deep dives and `docs/roadmap/inventory.md`. Formally deferred to v1.1 if a unified inventory.md is still wanted; otherwise can be retired. See `.planning/v1.0-MILESTONE-AUDIT.md`.

### Audit

`.planning/v1.0-MILESTONE-AUDIT.md` — final status `gaps_found` due to INV-* deferrals (intentional). All 3 cross-phase wiring gaps were fixed inline before close (commit `8be5b12`).

### Archives

- `.planning/milestones/v1.0-ROADMAP.md` — full milestone roadmap with phase details
- `.planning/milestones/v1.0-REQUIREMENTS.md` — final requirements status with outcomes
