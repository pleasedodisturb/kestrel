---
phase: 03-forward-vision
plan: 02
subsystem: roadmap
tags: [documentation, roadmap, editorial, milestones, forward-vision]
dependency_graph:
  requires: [03-01]
  provides: [later-milestone-descriptions, know-me-milestone, voice-mode-milestone, narrative-thread, feature-flags-traceability]
  affects: [ROADMAP.md]
tech_stack:
  added: []
  patterns: [narrative-thread-transitions, html-comment-traceability, mermaid-staleness-notes]
key_files:
  created: []
  modified: [ROADMAP.md]
decisions:
  - "Five Later milestones ordered by user journey: Profile and Skills, Know Me, Gap Analysis and Coaching, Voice Mode, Hosted Version"
  - "Know Me (v1.0 Robin) replaces Writing Style Flywheel as a broader personal understanding milestone"
  - "Voice Mode (v1.0 Lark) split from Know Me as separate speech-input milestone"
  - "Feature Flags omission documented via HTML comment for ROAD-15 traceability rather than silent exclusion"
  - "Mermaid diagram staleness explicitly noted with HTML comments naming exact divergences for Phase 4"
  - "Three narrative transition sentences (12, 15, 14 words) connect Later milestones without bloating"
metrics:
  duration: 166s
  completed: "2026-04-26T18:45:02Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 3 Plan 02: Later Milestones and Editorial Quality Summary

Full descriptions for all five Later vision milestones (Profile and Skills, Know Me, Gap Analysis and Coaching, Voice Mode, Hosted Version) with narrative thread, Feature Flags traceability, and Mermaid diagram staleness notes.

## What Was Done

### Task 1: Restructure Later section, write all five milestone descriptions, and document Feature Flags omission
**Commit:** `b9153e3`

Replaced the entire Later (v1.0+) subsection content. Removed the Writing Style Flywheel milestone and replaced it with two separate milestones: Know Me (v1.0 Robin) for deep personal understanding, and Voice Mode (v1.0 Lark) for speech input. Added the HTML comment documenting that Feature Flags (ROAD-15) is internal infrastructure excluded from the user-facing roadmap per D-29. Used exact workshopped copy from context decisions for Profile and Skills (D-20), Know Me (D-24), and Gap Analysis and Coaching (D-26). Wrote original copy for Voice Mode and Hosted Version following the prose style rules (no em dashes, no AI slop, varied openers, warm second-person). Added three narrative transition sentences between milestones, each a single sentence under 20 words.

**Key changes:**
- 5 milestones with full descriptions replace 4 placeholder stubs
- Know Me (v1.0 Robin) is a new milestone not in Phase 2
- Voice Mode replaces Writing Style Flywheel (speech input, not personal understanding)
- Feature Flags documented as intentional omission via HTML comment
- 3 narrative transitions weave a light story through the vision
- Zero "Details coming in next update" stubs remain

### Task 2: Final prose quality pass and Mermaid diagram consistency note
**Commit:** `0b323ed`

Full editorial pass across the entire ROADMAP.md. Em dash sweep found no prose em dashes (the heading range separator "Next (v0.13 -- v0.15)" is acceptable). AI slop sweep found zero matches across all 13 flagged words. Tone consistency verified: shipped sections use past/present tense, planned sections use present/future, all use warm second-person voice. Added HTML staleness comments above both Mermaid code blocks (gantt and flowchart), explicitly naming the divergences Phase 4 needs to fix: Know Me and Voice Mode replace Writing Style Flywheel, Feature Flags removed. Confirmed Feature Flags ROAD-15 traceability comment is present.

**Key changes:**
- 2 HTML comments added above Mermaid blocks with explicit divergence list
- Editorial sweep confirmed: no em dashes, no AI slop, consistent tone
- Narrative transitions confirmed: 12, 15, 14 words (all under 20 max)

## Deviations from Plan

None. Plan executed exactly as written.

## Verification Results

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| "Details coming" stubs | 0 | 0 | PASS |
| Writing Style Flywheel outside Mermaid/comments | 0 matches | 0 | PASS |
| `####` heading count | >= 15 | 19 | PASS |
| Know Me heading exists | present | present | PASS |
| Voice Mode heading exists | present | present | PASS |
| Feature Flags only in HTML comments | true | true | PASS |
| Phase 4 staleness comments | 2 | 2 | PASS |
| ROAD-15 traceability | present | present | PASS |
| Em dashes in prose | 0 | 0 | PASS |
| AI slop words | 0 | 0 | PASS |
| Transition word counts | all <= 20 | 12, 15, 14 | PASS |
| Later milestones with Considering status | 5 | 5 | PASS |

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | `b9153e3` | docs(03-02): write all five Later milestone descriptions and document Feature Flags omission |
| 2 | `0b323ed` | docs(03-02): editorial quality pass and Mermaid diagram staleness notes |

## Self-Check: PASSED

- ROADMAP.md: exists
- 03-02-SUMMARY.md: exists
- Commit b9153e3: found in git log
- Commit 0b323ed: found in git log
