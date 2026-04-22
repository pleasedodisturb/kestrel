---
phase: 06-test-suite-rewrite
plan: 02
subsystem: frontend-tests
tags: [testing, vitest, renderWithProviders, test-rewrite]
dependency_graph:
  requires: [test-setup-polyfill, renderWithProviders]
  provides: [kanbanboard-tests-green, discovery-tests-green, skills-tests-green]
  affects: [frontend-test-suite]
tech_stack:
  added: []
  patterns: [shared-render-wrapper-adoption, api-level-mocking]
key_files:
  created: []
  modified:
    - frontend/src/__tests__/KanbanBoard.test.tsx
    - frontend/src/__tests__/Discovery.test.tsx
    - frontend/src/__tests__/Skills.test.tsx
decisions:
  - "Fixed stale empty state assertions in KanbanBoard and Discovery to match actual component text rather than outdated expectations"
  - "Skills empty state CTA assertion updated from 'No skills yet'/'Add manually' to 'No skills added yet'/'Add a skill' matching EmptyState component props"
metrics:
  duration: 4min
  completed: "2026-04-21T12:34:16Z"
  tasks: 2
  files: 3
---

# Phase 6 Plan 02: Pre-existing Broken Test Files Summary

Rewrote 3 pre-existing broken test files (KanbanBoard, Discovery, Skills) to use shared renderWithProviders wrapper and fixed stale assertions to match actual component text.

## What Was Done

### Task 1: Rewrite KanbanBoard.test.tsx and Discovery.test.tsx (7940f0a)

**KanbanBoard.test.tsx:**
- Replaced inline `createQueryClient()` + `renderBoard()` with `renderWithProviders(<KanbanBoard />, { route: "/" })`
- Removed imports: `render`, `QueryClient`, `QueryClientProvider`, `MemoryRouter`
- Added import: `renderWithProviders` from `@/test-utils`
- Fixed 2 stale empty state assertions: "No applications yet" -> "No jobs in your pipeline yet", "Add Application"/"kanban-add-cta" -> "Discover jobs"/"empty-state-cta"
- Kept all 29 test cases, API-level mocks (`@/api/applications`, `@/api/followUps`), and `@dnd-kit/core` external lib mock

**Discovery.test.tsx:**
- Replaced inline `createQueryClient()` + `renderDiscovery()` with `renderWithProviders(<Discovery />, { route: "/discovery" })`
- Also replaced an inline `new QueryClient` + `render()` in the "no-match message" test
- Removed imports: `render`, `QueryClient`, `QueryClientProvider`, `MemoryRouter`
- Fixed 2 stale empty state assertions: "No discovered jobs yet" -> "Ready to find your next role"
- Kept all 28 test cases and API-level mocks (`@/api/discovery`, `@/api/applications`)

### Task 2: Rewrite Skills.test.tsx (1c0de1d)

- Replaced inline `createQueryClient()` + `renderSkills()` with `renderWithProviders(<Skills />, { route: "/skills" })`
- Removed imports: `render`, `QueryClient`, `QueryClientProvider`, `MemoryRouter`
- Fixed the 1 failing empty state CTA assertion: component renders `"No skills added yet"` (not `"No skills yet"`) and `"Add a skill"` (not `"Add manually"`) -- verified by reading Skills.tsx EmptyState props
- Kept all 26 test cases and API-level mocks (`@/api/skills`, `@/api/applications`)

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 7940f0a | feat(06-02): rewrite KanbanBoard and Discovery tests to use renderWithProviders |
| 2 | 1c0de1d | feat(06-02): rewrite Skills tests to use renderWithProviders |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed stale KanbanBoard empty state assertions**
- **Found during:** Task 1
- **Issue:** Tests expected "No applications yet" and "Add Application" but component renders "No jobs in your pipeline yet" and "Discover jobs" (EmptyState component)
- **Fix:** Updated assertions to match actual rendered text and test IDs
- **Files modified:** frontend/src/__tests__/KanbanBoard.test.tsx
- **Commit:** 7940f0a

**2. [Rule 1 - Bug] Fixed stale Discovery empty state assertions**
- **Found during:** Task 1
- **Issue:** Tests expected "No discovered jobs yet" but component renders "Ready to find your next role" (EmptyState component)
- **Fix:** Updated assertions to match actual rendered text
- **Files modified:** frontend/src/__tests__/Discovery.test.tsx
- **Commit:** 7940f0a

## Verification

- `cd frontend && npx vitest run src/__tests__/KanbanBoard.test.tsx` -- 29 tests pass
- `cd frontend && npx vitest run src/__tests__/Discovery.test.tsx` -- 28 tests pass
- `cd frontend && npx vitest run src/__tests__/Skills.test.tsx` -- 26 tests pass
- All 3 files run together: 83 tests pass, 0 failures
- No `createQueryClient` function in any of the 3 files
- All 3 files import from `@/test-utils`
- API-level mocks preserved in all files (no hook mocking)

## Self-Check: PASSED

- [x] frontend/src/__tests__/KanbanBoard.test.tsx exists and imports renderWithProviders
- [x] frontend/src/__tests__/Discovery.test.tsx exists and imports renderWithProviders
- [x] frontend/src/__tests__/Skills.test.tsx exists and imports renderWithProviders
- [x] No createQueryClient in any of the 3 files
- [x] Commit 7940f0a exists in git log
- [x] Commit 1c0de1d exists in git log
- [x] All 83 tests pass green (29 + 28 + 26)
