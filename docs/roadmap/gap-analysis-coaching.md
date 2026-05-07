# Gap Analysis and Coaching

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Show exactly what is missing between where you are and where you want to be, then help you close the gap.

## What This Delivers

You pick a target role. Kestrel compares your current skills and experience against what that role demands and shows you the gaps. Not in vague terms like "you need more experience," but specific, actionable gaps: which skills are below the threshold, which qualifications are missing, and which strengths already exceed the bar.

From there, the system suggests concrete steps to close each gap. The recommendations are progressive in depth. At the first level, curated lists of free resources (open-source courses, tutorials, documentation). Deeper: structured learning paths from MOOCs and certification programs. Deeper still: AI-assisted coaching that helps you build specific skills through practice exercises and feedback. Progress tracking shows you how the gaps are closing over time as you learn and grow.

## Design Considerations

Defining "target role" precisely is harder than it sounds. Job titles are inconsistent across companies. A "Senior Product Manager" at a startup and at a Fortune 500 company may require very different skill sets. The gap analysis needs a role model that captures this nuance, potentially building on the same job family presets used in the scoring engine. Learning resource curation is another challenge. The internet has infinite learning content, most of it mediocre. Recommending resources means either building a curated database (high effort, high quality) or using AI to evaluate resources on the fly (lower effort, variable quality).

Measuring skill improvement over time is important for motivation but difficult to do well. Self-reported progress is easy but unreliable. Objective measures (certifications earned, projects completed) are more credible but harder to track automatically. The coaching tone also matters. Encouragement without dishonesty. Honesty without discouragement.

## Current Status

*Status: Considering -- not yet started*

No implementation exists. This milestone depends on the Profile and Skills foundation being in place first. The existing 288 job family presets provide a starting point for understanding what different roles require.

## Related Milestones

- **[Profile and Skills](profile-and-skills.md)** -- Gap analysis requires a skills baseline to measure against
- **[Know Me](know-me.md)** -- Personal context shapes which learning paths and coaching styles resonate

---

*For Contributors*

## Open Questions

- Should the role taxonomy for gap analysis reuse the 288 job family presets or build a separate, more detailed model?
- How should learning resources be sourced and curated? A static database, AI-evaluated recommendations, community contributions, or a combination?
- What metrics should be used to track skill improvement? Self-assessment, certifications, project completion, or behavioral signals from the app?
- How granular should gap identification be? Broad categories ("improve your data analysis skills") versus specific items ("learn pandas pivot tables")?
- What coaching tone is right? Encouraging but honest? Clinical and neutral? Should it be configurable?
- How does gap analysis handle skills that are difficult to quantify (leadership, communication, creativity)?

## Research Needed

- [Validation Contract: Skills Intelligence](../reference/validation-contract-m2-skills.md) -- Includes gap analysis validation assertions that define the expected inputs, outputs, and accuracy requirements

No dedicated gap analysis research exists yet. Research areas include: competency modeling frameworks, learning resource aggregation APIs, progress tracking methodologies in educational technology, and coaching interaction design patterns.

## BMAD Integration

**PRD Status:** Not started

A PRD would specify the role-gap calculation algorithm, learning resource curation and ranking criteria, progress tracking metrics and visualization, and the coaching interaction model including tone and escalation depth.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
