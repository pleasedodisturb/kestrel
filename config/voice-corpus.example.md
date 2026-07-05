<!--
Kestrel Voice Corpus — starter template.

Copy to config/voice-corpus.md and fill in:
    cp config/voice-corpus.example.md config/voice-corpus.md

This file is the single source of truth for YOUR writing voice. Tools that
draft or review prose (including the anti-slop-frontier workflow's 5th angle)
read it to calibrate against how you actually write, instead of the generic
AI assistant register.

Organize your material into three layers by how much you trust each one to
DEFINE your voice. See docs/guides/voice-corpus-architecture.md for the full
method (the Ground -> Review -> Capture -> Distill flywheel and the
"outputs are not inputs" firewall).

Two rules that keep this file honest:
  1. Only genuine writing goes in Layer 1 (GOLD) — things you wrote, dictated,
     or rewrote substantially in your own words. Never add AI-drafted output.
  2. Capture new genuine artifacts the SAME DAY you produce them, or they are
     invisible to your next draft.
-->

# Voice Corpus

_A curated library of my real writing, so an assistant helps me sound like myself._

---

## Layer 1 — GOLD: my pure, unedited voice (highest calibration weight)

<!--
The strongest signal. Pieces you wrote or dictated yourself, grammar-cleanup at
most. Calibrate on these FIRST. Never let a tool rewrite anything here.
For each entry: a path or link, a one-line note on what it captures, and how
much editing it received ("grammar-only" or "fully mine").
List your single strongest sample first and anchor every voice check to it.
-->

- `path/to/strongest-sample.md` — [what it captures; why it's your anchor] — grammar-only
- `path/to/voice-memo-YYYY-MM-DD.md` — [topic; a raw unfiltered dictation] — grammar-only
- `path/to/letter-you-wrote-yourself.md` — [a piece you rewrote entirely in your own words] — fully mine
- _(add more as you capture them)_

## Layer 2 — IDENTITY & RULES: what the voice IS

<!--
Explicit rules distilled FROM Layer 1. What you skim before writing when you
don't have time to re-read all of GOLD. Re-distill these periodically as GOLD
grows (see the DISTILL stage of the flywheel).
-->

- **Register:** [describe your baseline tone in one line — e.g. "precise, a little
  self-deprecating, never salesy"]
- **Rhythm:** [e.g. "jagged — long run-ons next to short fragments; never uniform"]
- **Signature moves:** [e.g. "parentheticals that undercut the sentence; a win
  always ships with its cost attached; deflating closers, never a pitch"]
- **Hard avoids:** [words/moves that are never you — e.g. "no adjective
  self-claims, no fit-assertion closers, no three-item lists"]
- `path/to/voice-rules.md` — [link to a fuller distilled ruleset if you keep one]

## Layer 3 — BACKGROUND FACTS: ground claims (NOT voice samples)

<!--
Facts and dates only. Answers "is that claim true?" — NEVER "does that sound
like me?". Do not calibrate tone on anything here (CV phrasing is optimized for
scanning, not voice).
-->

- `path/to/facts.yaml` — the source of truth for dates, titles, metrics
- `path/to/background-notes.md` — roles, projects, and context to ground claims
- _(assessments, timelines, and other fact sources)_

## NOT corpus — outputs to judge, never inputs

<!--
The firewall. AI-drafted pieces (even ones you lightly edited and sent) are
OUTPUTS. They are judged against Layer 1, never calibrated on. Calibrating on
them launders the assistant register back into your voice over time.
-->

- `path/to/assistant-drafts/` — treat as outputs to review against GOLD, not inputs

---

## CAPTURE checklist (run at every session end)

- [ ] Did I write or dictate something genuine? → save it under Layer 1 and note the editing level.
- [ ] Did I rewrite an assistant draft substantially in my own words? → save the parts that are truly mine to Layer 1.
- [ ] New facts, dates, or assessment results? → Layer 3.
- [ ] Do the new samples shift my voice rules? → queue a DISTILL pass into Layer 2.
- [ ] Commit it. Keep the corpus in plain text under version control so it travels across machines and tools.
