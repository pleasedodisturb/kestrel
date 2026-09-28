---
phase: 05-contributor-experience
plan: 01
subsystem: documentation
tags: [contributor-experience, roadmap, callouts, planning-hierarchy]
dependency_graph:
  requires: [04-milestone-deep-dives]
  provides: [contributor-callouts, planning-hierarchy-docs]
  affects: [ROADMAP.md, docs/roadmap/inventory.md]
tech_stack:
  added: []
  patterns: [blockquote-callouts, ascii-tree-diagram]
key_files:
  created: []
  modified:
    - ROADMAP.md
    - docs/roadmap/inventory.md
decisions:
  - "Used blockquote format (> **Want to help?**) for all 19 callouts per D-05"
  - "Shipped milestones use improvement framing; planned/considering use building/researching framing per D-04"
  - "Each callout links only to its deep dive doc, no CONTRIBUTING.md links per D-06"
  - "Replaced 'Linear' with 'task tracker' in inventory.md per D-09"
  - "Expanded BMAD acronym (Build More, Architect Dreams) for external contributors per review concern"
metrics:
  duration: 5m
  completed: 2026-04-28T08:31:36Z
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 5 Plan 01: Contributor Callouts and Planning Hierarchy Summary

Blockquote contribution callouts on all 19 milestones in ROADMAP.md with expanded planning hierarchy documentation in docs/roadmap/inventory.md including ASCII tree diagram and BMAD definition for external contributors.

## Task Results

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add "Want to help?" callouts to all 19 milestones in ROADMAP.md | d24d560 | ROADMAP.md |
| 2 | Expand "How Planning Works" section in docs/roadmap/inventory.md | 662a2fb | docs/roadmap/inventory.md |

## What Was Done

### Task 1: Contribution Callouts in ROADMAP.md

Added 19 `> **Want to help?**` blockquote callouts, one per milestone section:

- **10 shipped milestones** (Scoring Engine through PII Safety Boundary): improvement framing pointing to concrete areas like new adapters, better accuracy, edge case testing, and accessibility fixes
- **1 in-progress milestone** (Public Roadmap): improvement framing for documentation and link fixes
- **3 planned milestones** (Desktop App, Browser Extension, Mobile App): building/researching framing for technology research and UX prototyping
- **5 considering milestones** (Profile and Skills through Hosted Version): building/researching framing for research directions and design exploration

Each callout links to its corresponding `docs/roadmap/*.md` deep dive. All 19 deep dive files verified to exist on disk. No em dashes, no AI slop words, no CONTRIBUTING.md links. Varied openers across callouts (not starting every one the same way).

### Task 2: Planning Hierarchy in inventory.md

Expanded the "How Planning Works" section from 3 paragraphs to a comprehensive hierarchy explanation:

- **ASCII tree diagram** showing the full chain: ROADMAP.md -> docs/roadmap/ -> BMAD PRDs -> Milestones -> Epics -> Tickets
- **BMAD acronym expansion**: "Build More, Architect Dreams" with brief explanation that external contributors do not need to understand BMAD internals
- **Layer descriptions**: 1-2 sentences per layer explaining purpose and audience
- **Contributor entry point paragraph**: directs readers to start at the deep dive level and look for open questions
- **"Linear" replaced with "task tracker"**: external contributors cannot access the internal task tracker

Shipped, Planned, and Internal tables left unchanged.

## Deviations from Plan

None. Plan executed exactly as written.

## Verification Results

| Check | Expected | Actual |
|-------|----------|--------|
| Callout count | 19 | 19 |
| All callouts have deep dive link | 19 | 19 |
| Missing deep dive files | 0 | 0 |
| Em dashes in callouts | 0 | 0 |
| CONTRIBUTING.md links in callouts | 0 | 0 |
| AI slop words in callouts | 0 | 0 |
| "Linear" in inventory.md | 0 | 0 |
| "task tracker" in inventory.md | >= 1 | 1 |
| "Build More, Architect Dreams" in inventory.md | >= 1 | 1 |
| ASCII tree present | yes | yes |
| Contributor entry paragraph | yes | yes |

## Known Stubs

None. All content is complete and wired to existing deep dive documents.

## Self-Check: PASSED

- ROADMAP.md: exists
- docs/roadmap/inventory.md: exists
- 05-01-SUMMARY.md: exists
- Commit d24d560 (Task 1): found
- Commit 662a2fb (Task 2): found
