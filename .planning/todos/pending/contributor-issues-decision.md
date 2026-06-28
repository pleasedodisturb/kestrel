---
created: 2026-04-30
source: phase-05-uat
priority: low
type: design-decision
---

# Decide whether to seed GitHub Issues for "Want to help?" callouts

Phase 5 added 19 "Want to help?" callouts to ROADMAP.md, each pointing to a deep dive doc but NOT to any specific issue or ticket. This was deliberate (decision D-02: "Specific enough to act on, stable enough not to go stale").

User raised the question post-UAT: should we also create GitHub Issues so external contributors have concrete actionable items?

## The trade-off

| Option | Pros | Cons |
|--------|------|------|
| **Status quo** (no issues) | Zero maintenance, never stale | No "claim this" mechanism for contributors |
| **Reactive issues** (open when someone asks) | Issues only exist for active work | Slow first response |
| **Seeded issues** (~38 starter issues) | Visible pipeline, "good first issue" labels | Maintenance burden, stale issues if unpicked |

## Why this matters

- Linear is private — external contributors can't see it (per D-09)
- A potential contributor reading a callout has nowhere concrete to land
- But a solo maintainer adding 38 maintained issues has real upkeep cost

## Recommendation pending decision

**Option B (reactive)** is the lowest-cost path. Could be paired with a sentence in CONTRIBUTING.md like "Open an issue to discuss before starting work — we'll help shape the scope."

This is its own milestone (open-source contribution infrastructure), not a Phase 5 follow-up. Worth scoping when the project gets more inbound contributor interest.

## Stop conditions

- DONE when user makes the call (A/B/C) or defers to a future milestone
- If "C, seeded": needs its own phase to draft 38 starter issues
- If "B, reactive": needs a one-liner addition to CONTRIBUTING.md
