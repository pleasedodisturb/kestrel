# Know Me

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Have Kestrel understand who you are as a person, not just your resume.

## What This Delivers

Skills tell Kestrel what you can do. Know Me tells it who you are. Through reflective prompts, your writing, and everyday choices you make in the app, Kestrel builds an understanding of your values, motivations, and professional identity. This is not a personality quiz. It is an ongoing conversation between you and the system that deepens over time.

The payoff touches the entire pipeline. Scoring starts to weigh what matters to you personally, not just what matches on paper. If you care about environmental impact, roles at fossil fuel companies stop surfacing. If financial stability is your current priority, cause-oriented roles with below-market compensation get deprioritized. Generated text (cover letters, interview talking points) starts to sound like you rather than a generic template. The system learns your voice from what you write and reflects it back. Over time, Kestrel stops being a tool you configure and becomes something that genuinely understands your direction.

## Design Considerations

Collecting deeply personal information requires careful thought about how it is stored, used, and protected. Reflective essay prompts (questions about your values, what kind of work environment you thrive in, what you would do with unlimited resources) are the primary input mechanism. These prompts need to be thoughtful and open-ended, not checkbox surveys. Extracting values and motivations from natural language text and representing them computationally is a hard problem. The system needs to handle ambiguity, contradiction, and change over time. You are allowed to evolve.

Privacy matters more here than anywhere else in Kestrel. Reflections about your values and motivations are the most personal data the system would hold. This data should never leave your machine by default, even if you have an AI provider configured for other tasks. Users need to see exactly what Kestrel thinks it knows about them and be able to correct or delete any of it.

## Current Status

*Status: Considering -- not yet started*

No implementation exists. This is a vision-stage milestone. The concept builds on top of the Profile and Skills foundation.

## Related Milestones

- **[Profile and Skills](profile-and-skills.md)** -- Builds on the skills map to understand values and motivations
- **[Gap Analysis and Coaching](gap-analysis-coaching.md)** -- Personal understanding shapes coaching recommendations
- **[Voice Mode](voice-mode.md)** -- Understanding who you are makes voice interaction more personal

---

*For Contributors*

## Open Questions

- How should values and motivations be represented computationally? Embedding vectors, structured tags, weighted preference lists, or something else?
- What is the right set of reflective prompts? How many, how often, and how should they adapt based on previous responses?
- How does the system handle contradictions? People's values shift with context and over time. The model needs to accommodate this without treating change as error
- How should users verify that Kestrel "understands" them correctly? A summary view, a set of predictions they can confirm or reject, or something interactive?
- What feedback loop lets users correct the system when it gets something wrong?
- How should this deeply personal data be encrypted and isolated from the rest of the application data?
- Can everyday usage signals (which jobs you bookmark, which you dismiss, how you edit generated text) contribute to understanding without explicit reflection?

## Research Needed

No existing research documents cover this topic directly. It is a new concept for Kestrel. Research areas include:

- Computational personality and value modeling approaches
- Reflective journaling UX patterns and prompt design
- Natural language understanding for extracting values and motivations from open-ended text
- Privacy architectures for sensitive personal data in local-first applications
- Feedback mechanisms for AI systems that model user preferences (reinforcement learning from human feedback, preference learning)

## BMAD Integration

**PRD Status:** Not started

A PRD would define the reflective essay prompt library, the value and motivation extraction methodology, pipeline integration points where personal understanding influences scoring and text generation, and the privacy model for deeply personal reflections.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
