# Profile and Skills

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Give you an honest, visual map of where you stand professionally.

## What This Delivers

Knowing what you are good at and where you have gaps is the foundation for everything else in your job search. Profile and Skills builds that foundation. You map out your strengths, skill levels, and experience across the areas that matter for your target roles. The system does not inflate or sugarcoat: it gives you an honest picture of where you stand so you can make informed decisions about which roles to pursue and where to invest in growth.

How you see that picture is up to you. The same underlying data can be displayed as an RPG character sheet (stats and attributes), a baseball card (key numbers at a glance), LinkedIn-style stats (familiar format), a spiderweb diagram (visual shape of your profile), or a simple scorecard (clean and minimal). Same data, your preferred lens. With your skills mapped, the scoring engine becomes smarter too. Your profile shapes what counts as a good fit, so scores reflect your actual qualifications rather than generic assumptions.

## Design Considerations

The core challenge is skill taxonomy. How do you represent "Python" or "project management" or "leadership" in a way that is specific enough to be useful but flexible enough to work across industries? A rigid standard taxonomy risks being too broad or missing niche skills. Pure freeform input risks inconsistency and duplication. The likely approach is a curated taxonomy with the ability to add custom entries.

Proficiency levels need a clear scale. Self-assessed levels are easy to collect but unreliable. Evidence-based assessment (certifications, years of experience, project history) is more accurate but harder to automate. Some combination of self-assessment with calibration signals will be needed. The integration with the scoring engine is bidirectional: your profile shapes scoring weights, and scoring results can surface skill gaps you had not considered.

## Current Status

*Status: Considering -- not yet started*

No implementation exists. The existing profile model stores basic information (target role, preferences, experience level) but not a structured skills inventory. The 288 job family presets in the scoring engine provide a starting taxonomy of relevant skills per role.

## Related Milestones

- **[Know Me](know-me.md)** -- Skills map feeds into deeper personal understanding
- **[Gap Analysis and Coaching](gap-analysis-coaching.md)** -- A skills baseline enables gap identification
- **[Scoring Engine](scoring-engine.md)** -- Profile data improves scoring accuracy

---

*For Contributors*

## Open Questions

- Skill ontology: should Kestrel use a standard taxonomy (ESCO, O*NET), build its own, or allow freeform entry with normalization?
- Proficiency level scale: how many levels, what do they mean, and how are they assessed?
- How should skills stay current over time? Automatic decay, periodic prompts to review, or manual updates only?
- What is the data model for a skill entry? Name, level, evidence, last updated, source (self-assessed vs inferred)?
- How do skills integrate with the existing 288 job family presets? Should presets define expected skills per role, enabling automatic gap detection?
- Which visualization framework handles the five display styles? A single charting library or purpose-built components per style?

## Research Needed

- [Validation Contract: Skills Intelligence](../reference/validation-contract-m2-skills.md) -- Defines the validation assertions for skills data model, skill normalization, and the integration contract between profile and scoring

No dedicated skills research exists yet. Research areas include: skill taxonomy standards (ESCO, O*NET, LinkedIn Skills Graph), proficiency assessment methodologies, visualization libraries for multi-format display, and how other tools (LinkedIn, Pluralsight, SkillShare) represent skill profiles.

## BMAD Integration

**PRD Status:** Not started

A PRD would define the skill data model and taxonomy, proficiency assessment methodology, visualization component specifications for each display style, and the integration rules connecting profile data to scoring weights.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
