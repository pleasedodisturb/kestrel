---
phase: 04-milestone-deep-dives
plan: 01
subsystem: docs
tags: [markdown, roadmap, deep-dives, milestone-docs, bmad]

# Dependency graph
requires:
  - phase: 02-roadmap-foundation
    provides: ROADMAP.md with shipped milestone descriptions and status lines
  - phase: 03-forward-vision
    provides: ROADMAP.md with planned milestone descriptions and Mermaid diagrams
provides:
  - 10 shipped milestone deep-dive documents in docs/roadmap/
  - inventory.md rewritten as index page with How Planning Works section
  - ROADMAP.md inline Deep dive links on all 10 shipped milestone status lines
  - Dual-audience template pattern (user-facing top / contributor bottom) established
affects: [04-02-PLAN, phase-05]

# Tech tracking
tech-stack:
  added: []
  patterns: [dual-audience-template, annotated-research-links, bmad-integration-hook]

key-files:
  created:
    - docs/roadmap/scoring-engine.md
    - docs/roadmap/discovery-engine.md
    - docs/roadmap/ai-provider-system.md
    - docs/roadmap/cost-control.md
    - docs/roadmap/application-pipeline.md
    - docs/roadmap/web-frontend.md
    - docs/roadmap/cli.md
    - docs/roadmap/infrastructure.md
    - docs/roadmap/onboarding-flow.md
    - docs/roadmap/pii-safety-boundary.md
  modified:
    - docs/roadmap/inventory.md
    - ROADMAP.md

key-decisions:
  - "Pilot-first approach: scoring-engine.md written and validated before remaining 9 docs"
  - "Word counts below 800 accepted for thinner milestones (CLI, Discovery) to honor D-23 every-word-earns-its-place"
  - "Related Milestones use 2-4 entries per doc from cross-link map, not exhaustive dependency graph"

patterns-established:
  - "Dual-audience template: Goal, What This Delivers, How It Works, Current Status, Related Milestones, ---, Architecture, Research & Decisions, BMAD Integration"
  - "Annotated research links: [Title](../research/file.md) -- one-sentence factual annotation"
  - "BMAD Integration hook: PRD Status line + unique what-a-PRD-would-cover paragraph + call-to-action"
  - "ROADMAP.md inline link pattern: *Status: Shipped* | [Deep dive](docs/roadmap/slug.md)"

requirements-completed: [DEEP-01, DEEP-02, DEEP-03, DEEP-04]

# Metrics
duration: 9min
completed: 2026-04-27
---

# Phase 4 Plan 01: Shipped Milestone Deep Dives Summary

**10 shipped milestone deep-dive documents with dual-audience template, 28 verified research links, unique BMAD integration content, and inventory.md index page with How Planning Works hierarchy**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-27T16:54:46Z
- **Completed:** 2026-04-27T17:04:20Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Wrote 10 shipped milestone deep dives following dual-audience template (user-facing top half, contributor bottom half)
- Rewrote inventory.md as directory index with How Planning Works section explaining full planning hierarchy
- Added inline "Deep dive" links to all 10 shipped milestone status lines in ROADMAP.md
- Validated all 28 unique research/reference/guide link targets exist on disk (zero broken links)
- Each BMAD Integration section has unique content specifying what a PRD would cover for that specific milestone

## Task Commits

Each task was committed atomically:

1. **Task 1: Write inventory.md index page and all 10 shipped deep-dive documents** - `6e9603f` (docs)
2. **Task 2: Add inline "Deep dive" links to ROADMAP.md for all 10 shipped milestones** - `92fbf0c` (docs)

## Files Created/Modified
- `docs/roadmap/inventory.md` - Index page with How Planning Works, Shipped table, Planned/Internal placeholders
- `docs/roadmap/scoring-engine.md` - Scoring Engine shipped deep dive (pilot document)
- `docs/roadmap/discovery-engine.md` - Discovery Engine shipped deep dive
- `docs/roadmap/ai-provider-system.md` - AI Provider System shipped deep dive
- `docs/roadmap/cost-control.md` - Cost Control shipped deep dive
- `docs/roadmap/application-pipeline.md` - Application Pipeline shipped deep dive
- `docs/roadmap/web-frontend.md` - Web Frontend shipped deep dive
- `docs/roadmap/cli.md` - CLI shipped deep dive
- `docs/roadmap/infrastructure.md` - Infrastructure shipped deep dive
- `docs/roadmap/onboarding-flow.md` - Onboarding Flow shipped deep dive
- `docs/roadmap/pii-safety-boundary.md` - PII Safety Boundary shipped deep dive
- `ROADMAP.md` - Added 10 inline Deep dive links on shipped milestone status lines

## Decisions Made
- Pilot-first approach: wrote scoring-engine.md first, validated against all acceptance criteria, then used it as the concrete reference for remaining 9 docs
- Accepted word counts below 800 for CLI (573 words) and Discovery Engine (642 words) because padding would violate D-23 (every word earns its place). These milestones have less depth to cover.
- Used 2-4 Related Milestones per doc from the cross-link map in 04-RESEARCH.md, selecting the most meaningful connections rather than listing all dependencies

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 04-02 is ready to execute: 9 planned deep dives (8 planned + Feature Flags), ROADMAP.md inline links for planned milestones, Mermaid diagram fixes, and final index update
- inventory.md has placeholder rows for Planned and Internal sections awaiting Plan 04-02
- The dual-audience template is established and can be adapted for planned milestones (How It Works -> Design Considerations, Architecture -> Open Questions)

## Self-Check: PASSED

All 12 created/modified files verified present on disk. Both task commits (6e9603f, 92fbf0c) verified in git log.

---
*Phase: 04-milestone-deep-dives*
*Completed: 2026-04-27*
