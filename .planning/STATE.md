# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-19)

**Core value:** A user who has never seen Kestrel finishes onboarding understanding what it does, has their profile populated, has seen scored results, and knows where to go next -- all in under 10 minutes.
**Current focus:** Phase 1: Onboarding State Foundation

## Current Position

Phase: 1 of 5 (Onboarding State Foundation)
Plan: 0 of 0 in current phase
Status: Context gathered, ready to plan
Last activity: 2026-04-20 -- Phase 1 context gathered

Progress: [..........] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- CV file parsing deferred to v2; v1 uses guided questions + paste-text regex extraction only
- Shepherd.js chosen over react-joyride for interactive tour (maintenance, Tailwind compat, accessibility)
- Onboarding state persisted in backend DB (not localStorage) to sync CLI and web

### Pending Todos

None yet.

### Blockers/Concerns

- Shepherd.js + React 19 concurrent mode compatibility is unverified (affects Phase 5)
- Non-developer usability validation needed before flow is considered validated

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| CV Import | File upload parsing (PDF/DOCX) | v2 | Roadmap creation |
| CV Import | spaCy NER extraction | v2 | Roadmap creation |
| CLI | --explain flag for verbose guidance | v2 | Roadmap creation |
| CLI | LinkedIn URL import | v2 | Roadmap creation |

## Session Continuity

Last session: 2026-04-20
Stopped at: Phase 1 context gathered
Resume file: .planning/phases/01-onboarding-state-foundation/01-CONTEXT.md
