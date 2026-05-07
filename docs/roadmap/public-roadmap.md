# Public Roadmap

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Make the project's direction visible so users can evaluate where Kestrel is headed and contributors can find meaningful work.

## What This Delivers

If you are reading this document, the Public Roadmap milestone is already working. ROADMAP.md at the repository root tells the story of what Kestrel does today and where it is going. Each milestone in the roadmap has a companion deep dive (like this one) that goes further into the details: what the feature does, what decisions shaped it, and what questions are still open.

The roadmap is written for three audiences at once. If you are evaluating Kestrel for your own job search, the shipped section shows you what exists and the planned section shows you what is coming. If you are a developer looking to contribute, the deep dives point you toward open questions and unresolved design choices. If you are the maintainer working across sessions and machines, the planning hierarchy keeps development coherent over time.

## Design Considerations

A good project roadmap balances two forces: keeping the top-level document scannable for casual visitors while providing enough depth for contributors who want to build something. Kestrel handles this by keeping ROADMAP.md short (one paragraph per milestone) and linking to deep dives for the full picture. The question of how often to refresh the roadmap matters too. Stale roadmaps erode trust faster than no roadmap at all. Each milestone update, release, or status change should flow through the same document hierarchy so the public view stays current.

## Current Status

*Status: In Progress*

ROADMAP.md is live with all shipped milestones described, all planned milestones outlined, and deep-dive documents covering the full set. The planning hierarchy (ROADMAP.md to deep dives to PRDs to Linear tickets) is established and documented.

## Related Milestones

- **[Infrastructure](infrastructure.md)** -- CI/CD and release automation keep the documentation pipeline reliable
- **[Desktop App](desktop-app.md)** -- The roadmap helps communicate priority and progress on Kestrel's most important next step

---

*For Contributors*

## Open Questions

- How should roadmap freshness be monitored? A documentation cadence (per-release updates, quarterly reviews) would prevent staleness, but the right interval depends on release frequency
- Should the roadmap include estimated timelines or stay timeline-free? The current gantt chart uses positioning dates, not commitments. Visitors may interpret them differently
- What format works best for communicating status changes? GitHub releases, CHANGELOG entries, and ROADMAP.md updates could be synchronized or kept independent
- Should deep dives for shipped milestones be updated when significant changes land, or frozen at the version they describe?

## Research Needed

The Public Roadmap milestone is self-referential: this deep dive and the documents it links to are the research output. For the broader documentation strategy:

- [ROADMAP.md](../../ROADMAP.md) -- The master document this milestone produces and maintains
- [Feature Inventory](inventory.md) -- Index page listing all deep dives with the planning hierarchy explanation

## BMAD Integration

**PRD Status:** Not started

A PRD would define documentation standards, content freshness monitoring cadence, the criteria for promoting a milestone from Considering to Planned, and the review process for keeping the roadmap synchronized with actual development.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
