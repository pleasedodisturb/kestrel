---
phase: 05-interactive-tour-feedback-polish
plan: 03
subsystem: frontend-tour
tags: [tour, onboarding, accessibility, wcag, react-context]
dependency_graph:
  requires: [05-02]
  provides: [TourProvider, useTour, TourTooltip, TourOverlay]
  affects: [Layout.tsx, FeedbackButton.tsx]
tech_stack:
  added: []
  patterns: [react-context-provider, css-clip-path, focus-trap, aria-live, requestAnimationFrame-retry]
key_files:
  created:
    - frontend/src/components/TourProvider.tsx
    - frontend/src/components/TourTooltip.tsx
    - frontend/src/components/TourOverlay.tsx
  modified:
    - frontend/src/components/Layout.tsx
    - frontend/src/components/FeedbackButton.tsx
decisions:
  - "useTour() returns default inactive state when outside provider (no null checks needed)"
  - "TourProvider wraps both Outlet and FeedbackButton in Layout so FeedbackButton can consume tour context"
  - "aria-live announcement skips initial mount to avoid Pitfall 5 (premature screen reader announcements)"
metrics:
  duration: 188s
  completed: 2026-04-21
  tasks: 2
  files_created: 3
  files_modified: 2
---

# Phase 05 Plan 03: Interactive Tour System Summary

Custom 5-step guided tour with CSS clip-path spotlight, WCAG 2.1 AA keyboard/screen-reader accessibility, cross-page navigation between Pipeline and Discovery, and backend persistence via tour_completed_at field.

## Task Results

| Task | Name | Commit | Status |
|------|------|--------|--------|
| 1 | Create TourProvider, TourTooltip, and TourOverlay | 313c7ba | Done |
| 2 | Wire TourProvider into Layout and hide FeedbackButton during tour | e9be1e2 | Done |

## What Was Built

### TourProvider (frontend/src/components/TourProvider.tsx)
- React Context provider managing tour state (isActive, currentStep, targetRect)
- Auto-launch: detects `welcome_completed_at && !tour_completed_at` and starts tour after 500ms delay (D-01)
- 5 hardcoded tour steps: Pipeline board, job card, Discovery search, grade badge, back to Pipeline
- Cross-page navigation via `useNavigate()` (steps 2->3 navigate to /discovery, steps 4->5 back to /)
- Target element discovery via `requestAnimationFrame` retry loop (max 10 attempts, 100ms intervals) -- mitigates T-05-05
- Recalculates target rect on scroll/resize (throttled via `requestAnimationFrame`)
- Completion persisted to backend via `patchOnboardingStep("tour_completed")`
- Exports `useTour()` hook with safe default (returns inactive state outside provider)

### TourOverlay (frontend/src/components/TourOverlay.tsx)
- Fixed full-viewport overlay at z-40 with `rgba(0, 0, 0, 0.4)` scrim
- CSS `clip-path: polygon()` creates rectangular cutout with 4px padding around target
- 2px primary-colored highlight ring around target element
- Click-to-advance behavior (clicking overlay calls `next()`)

### TourTooltip (frontend/src/components/TourTooltip.tsx)
- Positioned tooltip (below target, falls back to above if not enough space)
- Heading (14px semibold), body (14px normal), step counter, Skip/Next/Done buttons
- WCAG 2.1 AA accessibility (D-05):
  - Focus trap: Tab cycles between Skip and Next/Done buttons
  - Escape key skips entire tour
  - `aria-live="polite"` region announces step transitions (skips mount announcement)
  - Focus management: Skip button receives focus on each step change
  - 44px minimum touch targets on all buttons
  - `focus-visible:ring-2` indicators on all interactive elements
- Fade-in animation (150ms opacity transition)

### Integration
- Layout.tsx: TourProvider wraps both `<main><Outlet/></main>` and `<FeedbackButton/>`
- FeedbackButton.tsx: consumes `useTour()` and returns null when `isActive` (prevents z-index conflict)

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None. All tour steps are hardcoded with final copy from UI-SPEC. Backend integration uses existing `patchOnboardingStep` API. No placeholder data.

## Pre-existing Issues (Out of Scope)

- `npm run build` fails on pre-existing `WelcomePage.tsx:117` TypeScript error (`ProfileResponse` not assignable to `Record<string, unknown>`). This error exists on the base commit before any tour changes. `tsc --noEmit` passes cleanly. Logged for awareness but not fixed per deviation scope rules.

## Self-Check: PASSED

- [x] frontend/src/components/TourProvider.tsx exists
- [x] frontend/src/components/TourTooltip.tsx exists
- [x] frontend/src/components/TourOverlay.tsx exists
- [x] Commit 313c7ba exists (Task 1)
- [x] Commit e9be1e2 exists (Task 2)
- [x] TypeScript compiles without errors (tsc --noEmit)
