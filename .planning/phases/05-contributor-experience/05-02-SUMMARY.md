---
phase: 05-contributor-experience
plan: 02
subsystem: contributor-docs
tags: [contributing, devcontainer, codespaces, onboarding]
dependency_graph:
  requires: []
  provides: [finding-work-section, codespaces-badge, full-stack-devcontainer]
  affects: [CONTRIBUTING.md, .devcontainer/devcontainer.json]
tech_stack:
  added: []
  patterns: [codespaces-one-click, dual-server-devcontainer]
key_files:
  created: []
  modified:
    - CONTRIBUTING.md
    - .devcontainer/devcontainer.json
decisions:
  - "Finding Work section placed before Development Setup per D-14"
  - "Codespaces badge uses codespaces.new/pleasedodisturb/kestrel (verified against git remote)"
  - "Python image pinned to 3.11 matching CI and Docker base image per D-10"
  - "Both servers use bash -c wrapper with & backgrounding per D-11"
  - "Port 8100 label renamed from Dashboard to API since frontend runs separately"
metrics:
  duration_seconds: 133
  completed: "2026-04-28T08:29:00Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 5 Plan 02: CONTRIBUTING.md + Devcontainer Updates Summary

**One-liner:** Finding Work section linking to ROADMAP.md milestones, Codespaces one-click badge, and full-stack devcontainer with Python 3.11 + dual servers + ESLint/Tailwind extensions.

## What Was Done

### Task 1: Add "Finding Work" section and Codespaces mention to CONTRIBUTING.md
- Added `## Finding Work` section immediately after intro paragraph (line 15), before `## Development Setup` (line 19)
- Section links to ROADMAP.md and references "Want to help?" callouts and deep dives
- Added `### Quick Start with Codespaces` subsection with badge linking to `codespaces.new/pleasedodisturb/kestrel?quickstart=1`
- Includes first-run timing note (1-2 minutes)
- Wrapped existing manual setup steps under `### Manual Setup` subsection
- No changes to Running Tests, Making Changes, Code Style, or any content below Development Setup
- **Commit:** `c391f3b`

### Task 2: Update .devcontainer/devcontainer.json for full-stack one-click experience
- Pinned Python image from 3.14 to 3.11 (matches CI workflow and Docker base image)
- Updated `postStartCommand` with `bash -c` wrapper to start both servers backgrounded with `&`
- Both servers bind to `0.0.0.0` for Codespaces port forwarding
- Backend: uvicorn on port 8100, Frontend: npm run dev on port 8101
- Added port 8101 to `forwardPorts` array
- Added `portsAttributes` entries: "Kestrel API" (8100) and "Kestrel Frontend" (8101)
- Added `dbaeumer.vscode-eslint` and `bradlc.vscode-tailwindcss` extensions
- Preserved: Node 22 feature, `AI_PROVIDER=mock`, `postCreateCommand`, Python + Ruff extensions
- **Commit:** `9d76f19`

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Codespaces URL verified against `git remote get-url origin` | Confirmed `pleasedodisturb/kestrel` matches remote |
| Port 8100 label changed from "Dashboard" to "API" | Frontend now runs on separate port 8101, so 8100 is purely the API |

## Verification Results

All 11 plan verifications passed:
1. Valid JSON (devcontainer.json parseable)
2. Python 3.11 in image
3. bash -c wrapper in postStartCommand
4. npm run dev in postStartCommand
5. 0.0.0.0 binding for both servers
6. Port 8101 in forwardPorts and portsAttributes
7. ESLint extension present
8. Tailwind CSS extension present
9. "Finding Work" heading in CONTRIBUTING.md
10. Correct Codespaces URL in CONTRIBUTING.md
11. Finding Work (line 15) appears before Development Setup (line 19)

## Known Stubs

None. Both files are fully wired with no placeholders or TODOs.

## Self-Check: PASSED

- FOUND: CONTRIBUTING.md
- FOUND: .devcontainer/devcontainer.json
- FOUND: .planning/phases/05-contributor-experience/05-02-SUMMARY.md
- FOUND: c391f3b (Task 1 commit)
- FOUND: 9d76f19 (Task 2 commit)
