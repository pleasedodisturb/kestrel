---
phase: 03-forward-vision
plan: 01
subsystem: roadmap
tags: [documentation, roadmap, editorial, milestones]
dependency_graph:
  requires: [02-01, 02-02]
  provides: [heading-format, bird-codenames, next-milestone-descriptions]
  affects: [ROADMAP.md]
tech_stack:
  added: []
  patterns: [heading-based-milestones, bird-codenames, status-lines]
key_files:
  created: []
  modified: [ROADMAP.md]
decisions:
  - "Bird codenames assigned to all 18 milestones (Peregrine, Osprey, Starling, Merlin, Swift, Wren, Shrike, Raven, Finch, Harrier, Wagtail, Falcon, Kingfisher, Sparrowhawk, Nightjar, Woodpecker, Lark, Albatross)"
  - "Shipped items (Cost Control, Onboarding, PII Safety) moved from Now to What's Shipped"
  - "Provider count updated from 9 to 11 with Mistral and Hugging Face added"
  - "Desktop App uses exact workshopped copy from D-16"
  - "Browser Extension copy focuses on one-click save, Chrome and Firefox"
  - "Mobile App copy leads with pipeline access from phone, mentions web-first priority"
metrics:
  duration: 174s
  completed: "2026-04-26T18:40:32Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 3 Plan 01: Structural Overhaul and Next Milestones Summary

Heading-based milestone format with bird codenames, status lines, shipped item cleanup, and full Next milestone descriptions for Desktop App, Browser Extension, and Mobile App.

## What Was Done

### Task 1: Structural overhaul and Now/Shipped cleanup
**Commit:** `45c3e3d`

Converted all 18 milestones in ROADMAP.md from the Phase 2 emoji-bullet format to heading-based format with `####` headings, bird codenames in parentheses, and explicit `*Status:*` lines. Moved three shipped items (Cost Control, Onboarding Flow, PII Safety Boundary) from the Now section to What's Shipped. Updated the AI Provider System description from nine to eleven providers, adding Mistral and Hugging Face to the list. Cleaned up the Now section to contain only the Public Roadmap milestone (in progress). Created heading stubs with placeholder text in Next and Later sections for Task 2 and Plan 02 to fill in.

**Key changes:**
- 18 milestones converted to `#### Name (vX.Y Codename)` format
- 18 `*Status:*` lines added (Shipped, In Progress, Planned, Considering)
- 3 items moved from Now to What's Shipped
- Provider count: 9 to 11 (Mistral, Hugging Face)
- All emoji prefixes removed from headings

### Task 2: Write Next milestone descriptions
**Commit:** `190ae04`

Replaced "Details coming in next update" placeholders for all three Next milestones with full user-facing descriptions. Desktop App uses the exact workshopped copy from the context decisions (D-16). Browser Extension and Mobile App descriptions written following the prose style rules (no em dashes, no AI slop, natural variation in openers, warm second-person tone).

**Key changes:**
- Desktop App: download-and-use experience, signed installers, most important step for usability
- Browser Extension: one-click save from any job page, Chrome and Firefox
- Mobile App: pipeline and scores from phone, web experience comes first
- 4 remaining placeholders are in Later section (Plan 02 fills these)

## Deviations from Plan

None. Plan executed exactly as written.

## Verification Results

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| `####` heading count | >= 14 | 18 | PASS |
| "Details coming" count | <= 4 | 4 | PASS |
| "Nine providers" absent | 0 matches | 0 | PASS |
| "Eleven providers" present | 1+ matches | 1 | PASS |
| Emoji on headings | 0 matches | 0 | PASS |
| `*Status:` line count | >= 14 | 18 | PASS |

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | `45c3e3d` | docs(03-01): structural overhaul of ROADMAP.md with heading format and bird codenames |
| 2 | `190ae04` | docs(03-01): write full descriptions for Next milestones in ROADMAP.md |

## Self-Check: PASSED

- ROADMAP.md: exists
- 03-01-SUMMARY.md: exists
- Commit 45c3e3d: found in git log
- Commit 190ae04: found in git log
