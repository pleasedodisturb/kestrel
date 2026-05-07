# v1.0 Requirements — ARCHIVED

> **Shipped:** 2026-05-07
> **Defined:** 2026-04-21
> **Core Value:** Make Kestrel's direction visible and structured so users can evaluate the product, contributors can pick meaningful work, and development stays coherent across sessions and milestones.
> **Outcome:** 23/31 satisfied (74%). 8 INV requirements deferred to v1.1.
> This is a frozen archive. The active requirements file lives at `.planning/REQUIREMENTS.md` (regenerated for next milestone).

## v1 Requirements (final status)

### Inventory — DEFERRED to v1.1

Phase 1 was deliberately not executed. The intent (visible inventory of shipped work) was naturally absorbed into `docs/roadmap/inventory.md` (Phase 4) and the 10 shipped deep dives. The formal INV requirements move to v1.1 if a unified standalone inventory is still wanted.

- [ ] **INV-01**: All shipped backend features (27 routes, 36 services, 5+ AI providers, scoring engine, discovery engine, CLI) are catalogued into a coherent feature list — *deferred*
- [ ] **INV-02**: All shipped infrastructure work (CI/CD, test infrastructure, token optimization, docs audit, privacy layer) is catalogued — *deferred*
- [ ] **INV-03**: Working web frontend (React 19, 11 pages, Kanban board, analytics, discovery UI) is catalogued as shipped with current capabilities — *deferred*
- [ ] **INV-04**: Parked mobile app (React Native/Expo scaffold) is catalogued with status and context for why it's paused — *deferred*
- [ ] **INV-05**: Voice mode is catalogued honestly — code exists (api/voice.py, voice integration registered) but untested, status unknown, needs audit before roadmapping next steps — *deferred*
- [ ] **INV-06**: Current deployment/packaging options (clone+uvicorn, Docker compose, pip install) are documented honestly with their UX gaps — *deferred*
- [ ] **INV-07**: Shipped features are grouped into logical retrospective milestones with clear boundaries — *deferred*
- [ ] **INV-08**: An evolution narrative tells the story of how Kestrel grew from initial tool to current state — *deferred*

### Master Roadmap

- [x] **ROAD-01**: ROADMAP.md exists at repo root and renders correctly on GitHub
- [x] **ROAD-02**: Every roadmap item has a status indicator (shipped/in-progress/planned/considering)
- [x] **ROAD-03**: Milestones are structured as Now/Next/Later horizons tied to version numbers (v0.6, v0.7, v1.0+)
- [x] **ROAD-04**: A forward-looking disclaimer states plans may change
- [x] **ROAD-05**: An open-source statement clarifies this repo is non-commercial; commercial SaaS forks off to separate repo
- [x] **ROAD-06**: A tech debt section publicly acknowledges known debt (scoring monolith, mock provider, no lockfile, sync clients, frontend type drift, SQLite-only)
- [x] **ROAD-07**: A Mermaid timeline diagram visualizes milestone structure (GitHub-compatible subset only: gantt or flowchart, no quadrantChart/HTML/color:#fff)
- [x] **ROAD-08**: Shipped roadmap items cross-reference CHANGELOG.md entries and release tags
- [x] **ROAD-09**: Deployment/packaging milestone charts the path from "3 techy install methods" to "usable entirely via interface"
- [x] **ROAD-10**: Browser extension (Chrome/Firefox) is documented as a planned milestone — one-click add any job to scoring DB
- [x] **ROAD-11**: Mobile app resumption is documented as a planned milestone with context on why it was paused
- [x] **ROAD-12**: Profile & Skills vision is documented as a major planned milestone — RPG-style character sheet (not gamified), Dalio baseball card concept, honest skill mapping with levels
- [x] **ROAD-13**: Gap analysis & coaching roadmap is documented as a planned milestone — select target role/path, continuous gap analysis, personal development stepping stones, progressive coaching depth (skill maps → MOOCs → AI-assisted learning)
- [x] **ROAD-14**: Voice mode vision is documented as a planned milestone — native superwhisper-to-claude style voice interaction, building on existing (untested) implementation
- [x] **ROAD-15**: Feature flag system is documented as a planned milestone — comprehensive flags covering all features and UI elements, enabling different app flavors/editions, hiding incomplete/broken features, adjusting capabilities per deployment
- [x] **ROAD-16**: App packaging is documented as a planned milestone with progressive path — Phase A: PWA (installable from browser, service worker, offline-capable, fast interim win) → Phase B: native desktop app (Electron/Tauri, .dmg/.exe, Apple dev cert, Obsidian-style "download, open, use" with embedded backend and local data)

### Milestone Deep Dives

- [x] **DEEP-01**: docs/roadmap/ directory exists with a consistent template for milestone documents
- [x] **DEEP-02**: Each shipped milestone has a deep dive document (goal, context, features, technical approach, status, related docs)
- [x] **DEEP-03**: Milestone documents link to relevant research and decision docs in docs/ and docs/research/
- [x] **DEEP-04**: Milestone documents show where BMAD PRDs plug in (integration pattern defined, even if PRDs incomplete)

### Contributor Experience

- [ ] **CONT-01**: Each milestone section in ROADMAP.md has a "Want to help?" callout linking to contribution paths
- [ ] **CONT-02**: A planning hierarchy document explains the full chain: ROADMAP.md → BMAD PRDs → milestones → epics → Linear tickets
- [ ] **CONT-03**: A .devcontainer/ config enables one-click GitHub Codespaces dev environment (Python + Node + SQLite)

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Community Engagement

- **COMM-01**: GitHub Discussions enabled for structured community feature requests and feedback
- **COMM-02**: Monthly developer update posts (Supabase-style) summarizing progress
- **COMM-03**: Contributor spotlight section recognizing external contributions

### Advanced Visuals

- **VIS-01**: Shields.io badges on ROADMAP.md (CI status, version, license, coverage)
- **VIS-02**: Dependency graph between milestones as Mermaid diagram
- **VIS-03**: Per-milestone progress indicators beyond binary status

## Out of Scope

| Feature | Reason |
|---------|--------|
| Specific dates/deadlines on roadmap items | Solo maintainer — dates create false accountability and make roadmap feel stale when missed |
| GitHub Issues for tracking | Linear is the single source of truth for tasks; duplicating creates sync burden |
| Community voting on features | Creates delivery expectations; maintainer curates, community informs |
| Interactive roadmap tool (Plane, Notion, etc.) | External tools aren't git-versioned, fragment source of truth; markdown in repo is permanent |
| Percentage-complete tracking | Misleading (% of tickets ≠ % of effort), requires constant updates, goes stale immediately |
| Separate roadmap website | Scope creep — ROADMAP.md renders well on GitHub; upgrade only at 1000+ stars |
| SaaS tier boundary matrix in this repo | This repo is non-commercial; tier boundaries belong in the future commercial fork |
| Any code changes to Kestrel | This milestone is documentation and planning infrastructure only |
| Building the browser extension | Documented as planned milestone in roadmap, not built this milestone |
| Building profile/skills/coaching features | Documented as vision milestones in roadmap, not built this milestone |
| Building the devcontainer beyond basic config | Simple working config only; no CI integration or advanced features |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INV-01 | Phase 1 | Pending |
| INV-02 | Phase 1 | Pending |
| INV-03 | Phase 1 | Pending |
| INV-04 | Phase 1 | Pending |
| INV-05 | Phase 1 | Pending |
| INV-06 | Phase 1 | Pending |
| INV-07 | Phase 1 | Pending |
| INV-08 | Phase 1 | Pending |
| ROAD-01 | Phase 2 | Complete (02-01) |
| ROAD-02 | Phase 2 | Complete (02-01) |
| ROAD-03 | Phase 2 | Complete (02-01) |
| ROAD-04 | Phase 2 | Complete (02-01) |
| ROAD-05 | Phase 2 | Complete (02-01) |
| ROAD-06 | Phase 2 | Complete (02-01) |
| ROAD-07 | Phase 2 | Pending |
| ROAD-08 | Phase 2 | Complete (02-01) |
| ROAD-09 | Phase 3 | Complete (03-01) |
| ROAD-10 | Phase 3 | Complete (03-01) |
| ROAD-11 | Phase 3 | Complete (03-01) |
| ROAD-12 | Phase 3 | Complete (03-02) |
| ROAD-13 | Phase 3 | Complete (03-02) |
| ROAD-14 | Phase 3 | Complete (03-02) |
| ROAD-15 | Phase 3 | Complete (03-02, omitted per D-29, documented via HTML comment) |
| ROAD-16 | Phase 3 | Complete (03-01) |
| DEEP-01 | Phase 4, Plans 01+02 | Complete |
| DEEP-02 | Phase 4, Plans 01+02 | Complete |
| DEEP-03 | Phase 4, Plans 01+02 | Complete |
| DEEP-04 | Phase 4, Plans 01+02 | Complete |
| CONT-01 | Phase 5 | Complete (05-01) |
| CONT-02 | Phase 5 | Complete (05-01) |
| CONT-03 | Phase 5 | Complete (05-02) |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0

---
*Requirements defined: 2026-04-21*
*Last updated: 2026-04-28 after Phase 5 Contributor Experience completion*
