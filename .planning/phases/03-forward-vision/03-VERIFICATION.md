---
phase: 03-forward-vision
verified: 2026-04-26T21:15:00Z
status: human_needed
score: 17/17
overrides_applied: 0
must_haves:
  truths:
    - "Shipped Now items (Cost Control, Onboarding, PII Safety) appear in What's Shipped, not in Now"
    - "Provider count reads 'Eleven providers' with Mistral and Hugging Face in the list"
    - "Each milestone in What's Shipped, Now, and Next uses #### heading format with bird codename and version"
    - "Each milestone has a *Status: ...* line below the heading, no emoji prefixes on headings"
    - "Desktop App milestone has full workshopped copy describing native download-and-use experience"
    - "Browser Extension milestone has full description focused on one-click save"
    - "Mobile App milestone has full description focused on future vision"
    - "Later section contains five milestones in order: Profile and Skills, Know Me, Gap Analysis and Coaching, Voice Mode, Hosted Version"
    - "Know Me milestone exists as a new addition (was not in Phase 2 ROADMAP.md)"
    - "Writing Style Flywheel has been replaced by Know Me and Voice Mode as separate milestones"
    - "Feature Flags does NOT appear anywhere in What's Next section"
    - "ROAD-15 (Feature Flags) is explicitly addressed: an HTML comment in ROADMAP.md records that feature flags are internal infrastructure"
    - "Each Later milestone has a full description paragraph (no 'Details coming in next update' remains)"
    - "Narrative transition phrases between Later milestones are exactly one sentence each, no longer than 20 words"
    - "Profile and Skills description mentions visualization styles (RPG character sheet, baseball card, etc.)"
    - "Know Me description covers values, motivations, professional identity, and pipeline alignment"
    - "Gap Analysis description mentions target role selection and concrete steps"
  artifacts:
    - path: "ROADMAP.md"
      provides: "Complete forward vision with all milestones described and narrative thread"
      contains: "#### Know Me"
  key_links:
    - from: "ROADMAP.md Now section"
      to: "ROADMAP.md What's Shipped section"
      via: "Moved shipped items"
      pattern: "Status: Shipped"
    - from: "Profile and Skills milestone"
      to: "Know Me milestone"
      via: "Narrative thread transition phrase"
      pattern: "#### Know Me"
    - from: "Know Me milestone"
      to: "Gap Analysis and Coaching milestone"
      via: "Narrative thread transition phrase"
      pattern: "#### Gap Analysis"
deferred:
  - truth: "The deployment/packaging milestone charts a clear progressive path (PWA as fast interim win, then native desktop app)"
    addressed_in: "Phase 4"
    evidence: "Context decision D-11: 'End state only. Do NOT mention the PWA interim step (implementation detail for Phase 4 deep dives)'. Phase 4 goal: 'Each milestone has a detailed companion document in docs/roadmap/ that provides depth without cluttering the master roadmap'"
  - truth: "The app packaging milestone specifically describes the PWA-to-native progressive path (Phase A: PWA, Phase B: Electron/Tauri)"
    addressed_in: "Phase 4"
    evidence: "Context decision D-12: 'No Electron, Tauri, or PWA brand names.' D-11 explicitly defers PWA implementation details to Phase 4 deep dives. ROAD-16 progressive path detail belongs in docs/roadmap/ per user decisions"
  - truth: "Feature flags documented as a distinct planned milestone in ROADMAP.md"
    addressed_in: "Phase 4"
    evidence: "Context decision D-29: 'NOT in ROADMAP.md. Feature flags are internal infrastructure with no direct user benefit. ROAD-15 satisfied in Phase 4 deep-dive docs.' HTML comment in ROADMAP.md line 115 documents this decision for traceability"
human_verification:
  - test: "Open ROADMAP.md on GitHub and verify all 19 #### headings render as proper heading elements with anchor links"
    expected: "Each milestone heading is clickable and creates a correct anchor URL"
    why_human: "GitHub heading rendering depends on their Markdown parser; cannot verify programmatically without rendering"
  - test: "Read the Later section (Profile and Skills through Hosted Version) as a first-time user and verify the narrative flow makes sense"
    expected: "The three transition sentences (lines 123, 131, 139) guide the reader through a coherent vision story without feeling forced"
    why_human: "Narrative coherence and tone consistency require subjective human judgment"
  - test: "Verify that the two Mermaid diagrams still render on GitHub despite the HTML staleness comments added above them"
    expected: "Both gantt and flowchart render normally; HTML comments do not interfere with Mermaid parsing"
    why_human: "Mermaid rendering depends on GitHub's parser; HTML comment proximity to code blocks could theoretically break rendering"
---

# Phase 3: Forward Vision Verification Report

**Phase Goal:** Every planned milestone is documented through the end-user lens -- what the user gains, not what gets built -- with the deployment/packaging path given highest priority as THE gap between "dev tool" and "real product"
**Verified:** 2026-04-26T21:15:00Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Shipped Now items (Cost Control, Onboarding, PII Safety) appear in What's Shipped, not in Now | VERIFIED | Lines 37-77: All three in What's Shipped with `*Status: Shipped*`. Now section (lines 83-89) contains only Public Roadmap |
| 2 | Provider count reads 'Eleven providers' with Mistral and Hugging Face in the list | VERIFIED | Line 35: "Eleven providers to choose from: OpenRouter, Anthropic, OpenAI, Together, Groq, xAI, Gemini, Ollama, Mistral, Hugging Face, and a mock provider for testing." "Nine providers" returns zero matches |
| 3 | Each milestone uses #### heading format with bird codename and version | VERIFIED | 19 `####` headings found, all follow `#### Name (vX.Y Codename)` pattern. Codenames: Peregrine, Osprey, Starling, Merlin, Swift, Wren, Shrike, Raven, Finch, Harrier, Wagtail, Falcon, Kingfisher, Sparrowhawk, Nightjar, Robin, Woodpecker, Lark, Albatross |
| 4 | Each milestone has a Status line, no emoji prefixes on headings | VERIFIED | 19 `*Status:` lines found matching 19 headings. Statuses: 10 Shipped, 1 In Progress, 3 Planned, 5 Considering. Zero emoji characters on any `####` line |
| 5 | Desktop App has full workshopped copy | VERIFIED | Line 97: Exact D-16 copy verbatim: "Download Kestrel, double-click, and start scoring jobs. No terminal, no Docker, no configuration files. A native application with signed installers for macOS and Windows, your data stored locally just like today. This is the most important step toward making Kestrel usable for everyone." No PWA/Electron/Tauri mentions (per D-11/D-12). No "Hosted" mention (per D-15) |
| 6 | Browser Extension has full description focused on one-click save | VERIFIED | Lines 103: "add any posting to your Kestrel scoring queue with one click." Mentions Chrome and Firefox. No quick-score preview or page enrichment (per D-17) |
| 7 | Mobile App has full description focused on future vision | VERIFIED | Lines 109: "Check your pipeline, review scores, and respond to opportunities from your phone." Does NOT open with "You will be able to" (per D-06). Mentions "The web experience comes first" (per D-18) |
| 8 | Later section contains five milestones in correct order | VERIFIED | Lines 117-151: Profile and Skills, Know Me, Gap Analysis and Coaching, Voice Mode, Hosted Version. Exact order matches D-31 |
| 9 | Know Me milestone exists as new addition | VERIFIED | Line 125: `#### Know Me (v1.0 Robin)` -- not present in Phase 2 ROADMAP.md. Replaces Writing Style Flywheel per D-21 |
| 10 | Writing Style Flywheel replaced by Know Me and Voice Mode | VERIFIED | "Writing Style Flywheel" appears ONLY inside Mermaid code blocks (lines 187, 204) and HTML comments (lines 162, 193). Zero appearances in prose headings or descriptions. HTML staleness comments explicitly note the diagram divergence |
| 11 | Feature Flags does NOT appear in What's Next section | VERIFIED | "Feature Flags" appears only in HTML comments (lines 115, 162, 193). Zero appearances as a heading or in prose content. No `#### Feature Flags` heading exists |
| 12 | ROAD-15 addressed via HTML comment | VERIFIED | Line 115: `<!-- Feature Flags (ROAD-15) is internal infrastructure documented in docs/roadmap/ deep dives, not the user-facing roadmap. See D-29 in 03-CONTEXT.md. -->` |
| 13 | Each Later milestone has full description (no stubs) | VERIFIED | Zero occurrences of "Details coming in next update" in entire file. All 5 Later milestones have substantive description paragraphs (Profile and Skills: 52 words, Know Me: 60 words, Gap Analysis: 39 words, Voice Mode: 31 words, Hosted Version: 35 words) |
| 14 | Narrative transitions one sentence each, max 20 words | VERIFIED | Three transitions: "With your skills mapped..." (12 words), "Once Kestrel understands..." (15 words), "Sometimes the best way..." (14 words). Each is exactly one sentence with one terminal period. All under 20 word limit |
| 15 | Profile and Skills mentions visualization styles | VERIFIED | Line 121: "RPG character sheet, baseball card, LinkedIn-style stats, spiderweb diagram, or a simple scorecard. Same data, your preferred lens." Exact D-20 workshopped copy |
| 16 | Know Me covers values, motivations, professional identity, pipeline alignment | VERIFIED | Line 129: "values, motivations, and professional identity" plus "scoring weighs what matters to you personally, generated text sounds like you, and opportunities that clash with your values stop showing up." Exact D-24 workshopped copy |
| 17 | Gap Analysis mentions target role selection and concrete steps | VERIFIED | Line 137: "Pick a target role and see exactly what's missing" and "suggests concrete steps to close it, from free resources to structured learning paths." Exact D-26 workshopped copy |

**Score:** 17/17 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases per user context decisions.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | PWA-to-native progressive path detail in ROADMAP.md (RSC-1 partial) | Phase 4 | D-11: "End state only. Do NOT mention the PWA interim step (implementation detail for Phase 4 deep dives)" |
| 2 | Specific technology names (Electron/Tauri/PWA) in deployment milestone (RSC-4) | Phase 4 | D-12: "No Electron, Tauri, or PWA brand names. Just 'native application' and 'signed installers'" |
| 3 | Feature Flags as distinct user-facing milestone (RSC-2 partial) | Phase 4 | D-29: "NOT in ROADMAP.md. Feature flags are internal infrastructure. ROAD-15 satisfied in Phase 4 deep-dive docs" |

**Context:** These three items reflect a deliberate refinement of the original roadmap success criteria during the Phase 3 discuss phase. The user decided (through 35 documented decisions in 03-CONTEXT.md) that ROADMAP.md should describe user benefits and end states only, deferring implementation details and internal infrastructure to Phase 4 deep-dive documents. Both cross-AI reviewers (Gemini, Ollama) approved this approach.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `ROADMAP.md` | Complete forward vision with all milestones described | VERIFIED | 231 lines. 19 `####` milestone headings. 19 `*Status:` lines. 10 shipped milestones in What's Shipped. 1 in-progress (Now). 3 planned (Next). 5 considering (Later). Zero stubs. Zero placeholders |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| ROADMAP.md Now section | ROADMAP.md What's Shipped section | Moved shipped items | WIRED | Cost Control (line 37), Onboarding Flow (line 67), PII Safety Boundary (line 73) all in What's Shipped with `*Status: Shipped*`. Now section has only Public Roadmap |
| Profile and Skills milestone | Know Me milestone | Narrative transition phrase | WIRED | Line 123: "With your skills mapped, the next step is understanding what drives you." immediately precedes `#### Know Me` on line 125 |
| Know Me milestone | Gap Analysis and Coaching | Narrative transition phrase | WIRED | Line 131: "Once Kestrel understands what matters to you, it can show you what to work on." immediately precedes `#### Gap Analysis` on line 133 |
| ROADMAP.md | CHANGELOG.md | Anchor cross-references | WIRED | 10 CHANGELOG anchor links (up from 6 in Phase 2 -- added links for Cost Control, Onboarding, PII Safety, Infrastructure). All anchors verified present in earlier verification |
| ROADMAP.md | docs/roadmap/inventory.md | Relative link | WIRED | Line 17: `[feature inventory](docs/roadmap/inventory.md)` link intact from Phase 2 |

### Data-Flow Trace (Level 4)

Not applicable -- this phase produces static documentation files with no dynamic data rendering.

### Behavioral Spot-Checks

Step 7b: SKIPPED (no runnable entry points -- this phase is documentation-only, no code changes)

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ROAD-09 | 03-01 | Deployment/packaging milestone charts path from dev-only to usable via interface | SATISFIED | Desktop App (line 93-97): "Download, double-click, start scoring." Known Limitations (line 213): "This is the biggest barrier to adoption and the reason the Desktop App milestone exists." End-state framing per D-11 |
| ROAD-10 | 03-01 | Browser extension (Chrome/Firefox) documented as planned milestone with one-click add | SATISFIED | Lines 99-103: "add any posting to your Kestrel scoring queue with one click." "Available for Chrome and Firefox." |
| ROAD-11 | 03-01 | Mobile app resumption documented with context on why paused | SATISFIED | Lines 105-109: "The web experience comes first, then native iOS and Android apps." Future-focused framing per D-18 |
| ROAD-12 | 03-02 | Profile & Skills with RPG character sheet, baseball card concept | SATISFIED | Lines 117-121: Exact D-20 copy with "RPG character sheet, baseball card, LinkedIn-style stats, spiderweb diagram, or a simple scorecard" |
| ROAD-13 | 03-02 | Gap analysis & coaching with target role selection and development paths | SATISFIED | Lines 133-137: "Pick a target role and see exactly what's missing" and "from free resources to structured learning paths." Simplified from progressive depth per D-25 |
| ROAD-14 | 03-02 | Voice mode vision documented as planned milestone | SATISFIED | Lines 141-145: "Talk to Kestrel instead of typing. Dictate pipeline updates, rehearse interview answers out loud." User benefit framing, no implementation details |
| ROAD-15 | 03-02 | Feature flag system documented | PARTIALLY SATISFIED | HTML comment on line 115 documents the intentional omission with ROAD-15 reference and D-29 citation. Full satisfaction deferred to Phase 4 deep-dive docs per D-29. Not a gap -- user decision |
| ROAD-16 | 03-01 | App packaging with progressive PWA-to-native path | PARTIALLY SATISFIED | Desktop App end-state described (line 97: signed installers, native app). PWA progressive detail intentionally omitted per D-11/D-12. Full progressive path in Phase 4 deep dives |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `ROADMAP.md` | 162, 193 | HTML comments above Mermaid blocks noting Phase 4 staleness | INFO | Intentional per D-35. Explicitly names divergences (Know Me, Voice Mode, Writing Style Flywheel, Feature Flags) for Phase 4 to fix |
| `ROADMAP.md` | 187, 204 | "Writing Style Flywheel" inside Mermaid code blocks (no longer a milestone) | INFO | Diagram-prose divergence. Deferred to Phase 4 per D-35. HTML staleness comments document this |

No TODO/FIXME/PLACEHOLDER markers found. No AI slop words found. No em dashes in prose paragraphs. No private info leakage. No "we will build" developer-task framing. Zero stubs.

### Human Verification Required

### 1. GitHub Heading Rendering

**Test:** Open ROADMAP.md on GitHub and verify all 19 `####` headings render as proper heading elements with anchor links
**Expected:** Each milestone heading is clickable and creates a correct anchor URL (e.g., `#desktop-app-v013-falcon`)
**Why human:** GitHub heading rendering depends on their Markdown parser; cannot verify programmatically without rendering the page

### 2. Narrative Flow Coherence

**Test:** Read the Later section (Profile and Skills through Hosted Version) as a first-time user and verify the narrative flow makes sense
**Expected:** The three transition sentences (lines 123, 131, 139) guide the reader through a coherent vision story without feeling forced. Each milestone also makes sense when read in isolation
**Why human:** Narrative coherence, tone consistency, and reading flow require subjective human judgment

### 3. Mermaid Diagram Rendering with HTML Comments

**Test:** Verify that both Mermaid diagrams (gantt and flowchart) still render on GitHub after the HTML staleness comments were added directly above them
**Expected:** Both diagrams render normally; HTML comments do not interfere with Mermaid code block parsing
**Why human:** Mermaid rendering depends on GitHub's parser; HTML comment proximity to code fence could theoretically break rendering

### Gaps Summary

No gaps found. All 17 observable truths verified with concrete line-number evidence. All requirements accounted for (6 fully satisfied, 2 partially satisfied with intentional user-decision deferrals to Phase 4). All artifacts exist and are substantive. All key links wired. Zero anti-pattern blockers. Zero stubs.

The three roadmap success criteria items that do not literally pass (PWA progressive path in RSC-1/RSC-4, Feature Flags as user-facing milestone in RSC-2) were all intentionally refined during the discuss phase through documented user decisions (D-11, D-12, D-29). These are deferred to Phase 4 deep-dive documents, not missing.

**Recommendation:** If the developer wants to clear the deferred items from this phase's success criteria, add overrides for the three RSC items that were refined by context decisions:

```yaml
overrides:
  - must_have: "deployment/packaging milestone charts clear progressive path (PWA as fast interim win, then native desktop app)"
    reason: "User decided (D-11) to show end state only in ROADMAP.md. PWA progressive path deferred to Phase 4 deep dives."
    accepted_by: "{username}"
    accepted_at: "2026-04-26T21:15:00Z"
  - must_have: "app packaging milestone specifically describes the PWA-to-native progressive path"
    reason: "User decided (D-11, D-12) no technology brand names in user-facing roadmap. Progressive path detail in Phase 4."
    accepted_by: "{username}"
    accepted_at: "2026-04-26T21:15:00Z"
  - must_have: "feature flags documented as distinct planned milestone"
    reason: "User decided (D-29) feature flags are internal infrastructure. Documented via HTML comment for traceability. Full docs in Phase 4."
    accepted_by: "{username}"
    accepted_at: "2026-04-26T21:15:00Z"
```

---

_Verified: 2026-04-26T21:15:00Z_
_Verifier: Claude (gsd-verifier)_
