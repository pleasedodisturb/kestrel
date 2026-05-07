# Voice Mode

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Talk to Kestrel instead of typing for pipeline updates, interview rehearsal, and career thinking.

## What This Delivers

Sometimes typing is not the most natural way to interact with your job search tools. Voice Mode adds speech as an input method across everything Kestrel already does. Dictate a pipeline update while cooking dinner. Rehearse interview answers out loud and get feedback on your delivery. Think through a career decision by talking it out rather than writing it down.

Voice is not a separate feature. It is another way to reach the same capabilities. Everything you can do by clicking or typing, you will also be able to do by speaking. The interface adapts to whichever input mode you are using. The pipeline view, scoring results, and coaching interactions all work the same way whether your input comes from a keyboard or a microphone.

## Design Considerations

The fundamental choice is between local and cloud speech-to-text processing. Running a model like Whisper locally keeps all audio on your machine, which aligns with Kestrel's privacy-first approach. But local processing requires meaningful compute resources and may be slower than cloud alternatives. Cloud speech-to-text services (Google, OpenAI, Deepgram) offer better accuracy and speed but mean your voice recordings leave your machine. The right answer may be a choice, just like Kestrel handles AI providers: you pick the tradeoff that fits you.

Latency matters. Voice interaction feels natural when responses come within a second or two. Delays longer than that break the conversational flow. Real-time streaming (transcribing as you speak) feels much better than batch processing (waiting until you stop talking). The existing codebase includes an API endpoint and frontend route for voice functionality, but they are untested prototypes rather than production-ready implementations.

## Current Status

*Status: Considering -- not yet started*

An API endpoint (`api/voice.py`) and a frontend route exist in the codebase but are untested. No speech-to-text integration is implemented. This milestone depends on the core product experience being solid first.

## Related Milestones

- **[Know Me](know-me.md)** -- Understanding who you are makes voice interaction more personal
- **[Gap Analysis and Coaching](gap-analysis-coaching.md)** -- Voice is a natural fit for coaching conversations

---

*For Contributors*

## Open Questions

- Which speech-to-text approach: local Whisper (privacy, compute cost) or cloud APIs (accuracy, latency)? Should both be available as provider choices?
- Real-time streaming transcription or batch processing? Streaming feels more natural but is technically harder
- How does voice interact with the existing UI? Overlay panel, dedicated voice mode screen, or inline within existing pages?
- Should the system support voice output (text-to-speech for responses) or only voice input?
- Privacy of voice recordings: are recordings stored, or transcribed and immediately discarded?
- How should voice handle structured input (selecting from a list, confirming an action) versus freeform input (describing a job preference)?
- What is the existing state of `api/voice.py` and the frontend voice route? How much of it is salvageable versus starting fresh?

## Research Needed

- [Validation Contract: Integrations](../reference/validation-contract-m5-integrations.md) -- Includes voice integration validation assertions (draft status)

No dedicated voice research exists yet. Research areas include: speech-to-text provider comparison (Whisper local, OpenAI Whisper API, Deepgram, Google Speech), real-time transcription architectures, voice UX patterns for productivity tools, and privacy-preserving voice processing.

## BMAD Integration

**PRD Status:** Not started

A PRD would define the voice interaction model and supported commands, speech-to-text provider selection criteria and fallback chain, UI integration patterns for voice-alongside-keyboard workflows, and privacy controls for voice recording storage and processing.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
