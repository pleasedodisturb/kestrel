# Requirements: Kestrel Public Roadmap

**Defined:** 2026-04-21
**Core Value:** Make Kestrel's direction visible and structured so users can evaluate the product, contributors can pick meaningful work, and development stays coherent across sessions and milestones.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Inventory

- [ ] **INV-01**: All shipped backend features (27 routes, 36 services, 5+ AI providers, scoring engine, discovery engine, CLI) are catalogued into a coherent feature list
- [ ] **INV-02**: All shipped infrastructure work (CI/CD, test infrastructure, token optimization, docs audit, privacy layer) is catalogued
- [ ] **INV-03**: Working web frontend (React 19, 11 pages, Kanban board, analytics, discovery UI) is catalogued as shipped with current capabilities
- [ ] **INV-04**: Parked mobile app (React Native/Expo scaffold) is catalogued with status and context for why it's paused
- [ ] **INV-05**: Voice mode is catalogued honestly — code exists (api/voice.py, voice integration registered) but untested, status unknown, needs audit before roadmapping next steps
- [ ] **INV-06**: Current deployment/packaging options (clone+uvicorn, Docker compose, pip install) are documented honestly with their UX gaps
- [ ] **INV-07**: Shipped features are grouped into logical retrospective milestones with clear boundaries
- [ ] **INV-08**: An evolution narrative tells the story of how Kestrel grew from initial tool to current state

### Master Roadmap

- [ ] **ROAD-01**: ROADMAP.md exists at repo root and renders correctly on GitHub
- [ ] **ROAD-02**: Every roadmap item has a status indicator (shipped/in-progress/planned/considering)
- [ ] **ROAD-03**: Milestones are structured as Now/Next/Later horizons tied to version numbers (v0.6, v0.7, v1.0+)
- [ ] **ROAD-04**: A forward-looking disclaimer states plans may change
- [ ] **ROAD-05**: An open-source statement clarifies this repo is non-commercial; commercial SaaS forks off to separate repo
- [ ] **ROAD-06**: A tech debt section publicly acknowledges known debt (scoring monolith, mock provider, no lockfile, sync clients, frontend type drift, SQLite-only)
- [ ] **ROAD-07**: A Mermaid timeline diagram visualizes milestone structure (GitHub-compatible subset only: gantt or flowchart, no quadrantChart/HTML/color:#fff)
- [ ] **ROAD-08**: Shipped roadmap items cross-reference CHANGELOG.md entries and release tags
- [ ] **ROAD-09**: Deployment/packaging milestone charts the path from "3 techy install methods" to "usable entirely via interface"
- [ ] **ROAD-10**: Browser extension (Chrome/Firefox) is documented as a planned milestone — one-click add any job to scoring DB
- [ ] **ROAD-11**: Mobile app resumption is documented as a planned milestone with context on why it was paused
- [ ] **ROAD-12**: Profile & Skills vision is documented as a major planned milestone — RPG-style character sheet (not gamified), Dalio baseball card concept, honest skill mapping with levels
- [ ] **ROAD-13**: Gap analysis & coaching roadmap is documented as a planned milestone — select target role/path, continuous gap analysis, personal development stepping stones, progressive coaching depth (skill maps → MOOCs → AI-assisted learning)
- [ ] **ROAD-14**: Voice mode vision is documented as a planned milestone — native superwhisper-to-claude style voice interaction, building on existing (untested) implementation
- [ ] **ROAD-15**: Feature flag system is documented as a planned milestone — comprehensive flags covering all features and UI elements, enabling different app flavors/editions, hiding incomplete/broken features, adjusting capabilities per deployment
- [ ] **ROAD-16**: App packaging is documented as a planned milestone with progressive path — Phase A: PWA (installable from browser, service worker, offline-capable, fast interim win) → Phase B: native desktop app (Electron/Tauri, .dmg/.exe, Apple dev cert, Obsidian-style "download, open, use" with embedded backend and local data)

### Milestone Deep Dives

- [ ] **DEEP-01**: docs/roadmap/ directory exists with a consistent template for milestone documents
- [ ] **DEEP-02**: Each shipped milestone has a deep dive document (goal, context, features, technical approach, status, related docs)
- [ ] **DEEP-03**: Milestone documents link to relevant research and decision docs in docs/ and docs/research/
- [ ] **DEEP-04**: Milestone documents show where BMAD PRDs plug in (integration pattern defined, even if PRDs incomplete)

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
| ROAD-01 | Phase 2 | Pending |
| ROAD-02 | Phase 2 | Pending |
| ROAD-03 | Phase 2 | Pending |
| ROAD-04 | Phase 2 | Pending |
| ROAD-05 | Phase 2 | Pending |
| ROAD-06 | Phase 2 | Pending |
| ROAD-07 | Phase 2 | Pending |
| ROAD-08 | Phase 2 | Pending |
| ROAD-09 | Phase 3 | Pending |
| ROAD-10 | Phase 3 | Pending |
| ROAD-11 | Phase 3 | Pending |
| ROAD-12 | Phase 3 | Pending |
| ROAD-13 | Phase 3 | Pending |
| ROAD-14 | Phase 3 | Pending |
| ROAD-15 | Phase 3 | Pending |
| ROAD-16 | Phase 3 | Pending |
| DEEP-01 | Phase 4 | Pending |
| DEEP-02 | Phase 4 | Pending |
| DEEP-03 | Phase 4 | Pending |
| DEEP-04 | Phase 4 | Pending |
| CONT-01 | Phase 5 | Pending |
| CONT-02 | Phase 5 | Pending |
| CONT-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0

---
*Requirements defined: 2026-04-21*
*Last updated: 2026-04-21 after roadmap creation*
