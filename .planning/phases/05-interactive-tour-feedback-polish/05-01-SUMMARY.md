---
phase: 05-interactive-tour-feedback-polish
plan: 01
subsystem: frontend-empty-states
tags: [empty-state, coaching, ui-component, pipeline, discovery, contacts, skills]
dependency_graph:
  requires: []
  provides: [EmptyState-component]
  affects: [KanbanBoard, Discovery, ContactsPage, Skills]
tech_stack:
  added: []
  patterns: [shared-coaching-component, css-variable-theming]
key_files:
  created:
    - frontend/src/components/EmptyState.tsx
  modified:
    - frontend/src/components/KanbanBoard.tsx
    - frontend/src/pages/Discovery.tsx
    - frontend/src/pages/ContactsPage.tsx
    - frontend/src/pages/Skills.tsx
decisions:
  - "EmptyState uses hsl(var(--...)) CSS variables instead of gray-N classes for theme consistency"
  - "Discovery empty state split into two paths: 'no data yet' (EmptyState) vs 'no results for query' (inline message kept)"
  - "Skills page keeps CV/assessment import buttons below EmptyState as secondary actions"
  - "KanbanBoard CTA points to /discovery instead of opening CreateApplicationDialog (coaching flow)"
metrics:
  duration: 170s
  completed: 2026-04-21T10:16:29Z
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 4
---

# Phase 05 Plan 01: Empty State Coaching Components Summary

Shared EmptyState component with CSS variable theming, integrated into Pipeline, Discovery, Contacts, and Skills pages with coaching-tone messaging per D-07/D-08.

## Commits

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create shared EmptyState component | f5de00f | frontend/src/components/EmptyState.tsx |
| 2 | Integrate EmptyState into all four pages | 31ba86b | KanbanBoard.tsx, Discovery.tsx, ContactsPage.tsx, Skills.tsx |

## What Was Built

### EmptyState Component (Task 1)
- Shared component with `icon`, `heading`, `description`, `ctaLabel` props
- Supports both `ctaHref` (navigation link) and `onCtaClick` (button action) patterns
- Themed with `hsl(var(--primary))`, `--muted-foreground`, `--foreground` CSS variables
- Accessible: `aria-hidden="true"` on decorative icons, `data-testid` markers for testing

### Page Integrations (Task 2)
- **Pipeline (KanbanBoard)**: "No jobs in your pipeline yet" with "Discover jobs" CTA linking to `/discovery`
- **Discovery**: Split into two states -- "Ready to find your next role" (EmptyState, focuses search input) vs "No jobs match your search" (kept as inline message for filtered results)
- **Contacts**: "No contacts yet" with "Add a contact" CTA opening the existing create dialog
- **Skills**: "No skills added yet" with "Add a skill" CTA opening add dialog, CV/assessment import buttons preserved below as secondary actions

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- TypeScript compiles clean (`tsc --noEmit` passes)
- Full build has a pre-existing error in WelcomePage.tsx (line 117, unrelated to this plan)
- No file deletions, no untracked generated files

## Known Stubs

None -- all EmptyState instances are wired to real actions (navigation, dialog opens, input focus).

## Self-Check: PASSED
