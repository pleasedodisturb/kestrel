# Roadmap: Kestrel Public Roadmap

## Overview

This milestone transforms Kestrel's organic development history into a visible, structured public roadmap. No code changes — pure editorial work. The journey: first catalogue everything shipped (the "bag of cats" problem), then assemble the master ROADMAP.md with both retrospective and forward-looking content, then document all planned milestones through the end-user lens, then create deep-dive documents for each milestone, and finally make the whole thing contributor-friendly. The output becomes the backbone for BMAD PRDs, milestones, epics, and Linear tickets going forward.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Feature Inventory** - Catalogue all shipped work into a coherent, verifiable feature list organized by retrospective milestones
- [ ] **Phase 2: Roadmap Foundation** - Assemble the master ROADMAP.md with shipped content, status indicators, Mermaid timeline, and structural elements
- [ ] **Phase 3: Forward Vision** - Document all planned milestones through the end-user lens (deployment, browser extension, mobile, profiles, coaching, voice, feature flags, app packaging)
- [ ] **Phase 4: Milestone Deep Dives** - Create docs/roadmap/ with per-milestone detail documents, research links, and BMAD integration points
- [ ] **Phase 5: Contributor Experience** - Add contribution paths, planning hierarchy documentation, and one-click dev environment

## Phase Details

### Phase 1: Feature Inventory
**Goal**: Every piece of shipped work is catalogued, honestly assessed, and grouped into coherent retrospective milestones that tell the story of how Kestrel evolved
**Depends on**: Nothing (first phase)
**Requirements**: INV-01, INV-02, INV-03, INV-04, INV-05, INV-06, INV-07, INV-08
**Success Criteria** (what must be TRUE):
  1. A reader can see every shipped backend capability (routes, services, AI providers, scoring, discovery, CLI) in one organized list without reading source code
  2. Infrastructure work (CI/CD, tests, token optimization, docs audit, privacy layer) is visible as shipped product investment, not hidden plumbing
  3. The web frontend is documented as a shipped, working interface with specific page-level capabilities — not just "React app exists"
  4. Deployment options are documented honestly, including the UX gaps that make each option developer-only
  5. Shipped features are grouped into retrospective milestones with a narrative that explains how Kestrel grew from initial tool to current state
**Plans**: TBD

### Phase 2: Roadmap Foundation
**Goal**: ROADMAP.md exists at repo root as a well-structured, GitHub-rendered document with shipped content, status system, timeline visualization, and all structural scaffolding
**Depends on**: Phase 1
**Requirements**: ROAD-01, ROAD-02, ROAD-03, ROAD-04, ROAD-05, ROAD-06, ROAD-07, ROAD-08
**Success Criteria** (what must be TRUE):
  1. A non-technical user visiting the GitHub repo can open ROADMAP.md and understand what Kestrel does, what is shipped, and what is planned — without reading any code or docs
  2. Every roadmap item has a clear status (shipped/in-progress/planned/considering) and shipped items cross-reference CHANGELOG.md entries and release tags
  3. Milestones are organized as Now/Next/Later horizons tied to version numbers so readers understand relative priority
  4. A Mermaid timeline diagram renders correctly on GitHub and visualizes the milestone structure at a glance
  5. The document states openly that this repo is non-commercial, plans may change, and known tech debt exists — honesty builds trust
**Plans**: TBD

### Phase 3: Forward Vision
**Goal**: Every planned milestone is documented through the end-user lens — what the user gains, not what gets built — with the deployment/packaging path given highest priority as THE gap between "dev tool" and "real product"
**Depends on**: Phase 2
**Requirements**: ROAD-09, ROAD-10, ROAD-11, ROAD-12, ROAD-13, ROAD-14, ROAD-15, ROAD-16
**Success Criteria** (what must be TRUE):
  1. The deployment/packaging milestone charts a clear progressive path (PWA as fast interim win, then native desktop app with Obsidian-style "download, open, use" experience) and a reader understands why this is the highest-priority forward milestone
  2. Browser extension, mobile app, profile/skills, gap analysis/coaching, voice mode, and feature flags are each documented as distinct planned milestones with enough context that a reader understands the vision without implementation details
  3. Each planned milestone is framed through end-user benefit ("you will be able to...") not developer tasks ("we will build...") — consistent with the user-first north star
  4. The app packaging milestone specifically describes the PWA-to-native progressive path (Phase A: PWA installable from browser, Phase B: Electron/Tauri with .dmg/.exe and Apple dev cert)
**Plans**: TBD

### Phase 4: Milestone Deep Dives
**Goal**: Each milestone has a detailed companion document in docs/roadmap/ that provides depth without cluttering the master roadmap, and these documents show how BMAD PRDs integrate into the planning hierarchy
**Depends on**: Phase 2, Phase 3
**Requirements**: DEEP-01, DEEP-02, DEEP-03, DEEP-04
**Success Criteria** (what must be TRUE):
  1. docs/roadmap/ exists with a consistent template that any future milestone document can follow
  2. Each shipped milestone has a deep-dive document covering goal, context, features delivered, technical approach, current status, and links to relevant research and decision docs
  3. Deep-dive documents show where BMAD PRDs plug into the planning hierarchy — the integration pattern is defined even though PRDs are incomplete
**Plans**: TBD

### Phase 5: Contributor Experience
**Goal**: A potential contributor can find meaningful work, understand the planning hierarchy, and spin up a development environment without reading source code or asking for help
**Depends on**: Phase 2, Phase 3
**Requirements**: CONT-01, CONT-02, CONT-03
**Success Criteria** (what must be TRUE):
  1. Each milestone section in ROADMAP.md has a "Want to help?" callout that links to concrete contribution paths — not a generic "PRs welcome"
  2. A planning hierarchy document explains the full chain from ROADMAP.md through BMAD PRDs, milestones, epics, to Linear tickets — so contributors understand how work gets defined and tracked
  3. A .devcontainer/ config enables one-click GitHub Codespaces dev environment with Python, Node, and SQLite ready to go
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Feature Inventory | 0/0 | Not started | - |
| 2. Roadmap Foundation | 0/0 | Not started | - |
| 3. Forward Vision | 0/0 | Not started | - |
| 4. Milestone Deep Dives | 0/0 | Not started | - |
| 5. Contributor Experience | 0/0 | Not started | - |
