# Phase 3: Forward Vision - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Expand every planned milestone in ROADMAP.md's What's Next section from placeholder ("Details coming in next update") to a full user-facing description. Also: add the "Know Me" milestone, update the Now section (move shipped items to What's Shipped), update provider count to 11, and assign bird codenames to all milestones. No code changes, editorial only.

Output: Updated ROADMAP.md with fully described milestones across Next (Desktop App, Browser Extension, Mobile App) and Later (Profile & Skills, Know Me, Gap Analysis & Coaching, Voice Mode, Hosted Version), plus Now section cleanup.

</domain>

<decisions>
## Implementation Decisions

### Document Structure
- **D-01:** **Short paragraph per milestone** (2-4 sentences). Keeps ROADMAP.md scannable. Deep dives go in docs/roadmap/ in Phase 4
- **D-02:** **Equal depth for all milestones.** Desktop App's importance is already clear from position (first in Next) and Known Limitations callback. No milestone gets extra space
- **D-03:** **Replace bullet format with headings.** Each milestone becomes its own `####` heading with a paragraph below, replacing the current emoji + bullet format
- **D-04:** **Status line below heading.** Use `*Status: Shipped/In Progress/Planned/Considering*` on a line below the heading, NOT emoji on the heading line. Cleaner headings, explicit status
- **D-05:** **Bird codenames in headings.** Each milestone gets a bird codename in the heading: `#### Desktop App (v0.13 Falcon)`. Claude picks the specific birds. Real species, memorable, not too obscure

### Prose Style
- **D-06:** **Natural variation in openers.** No consistent "You will be able to..." template. Each milestone opens differently based on what fits
- **D-07:** **Same tone throughout.** Shipped and planned milestones feel like the same voice. Warm, second-person, factual, no hype. Only difference is tense
- **D-08:** **No em dashes anywhere in copy.** Use periods, commas, or restructure sentences instead
- **D-09:** **No AI slop.** Avoid: "seamlessly," "leverage," "revolutionize," "cutting-edge," "game-changer," "delve," "robust," "streamline," "harness," and similar hollow filler. Write like a human who cares. Einstein's razor: as simple as possible, but no simpler
- **D-10:** **Light narrative thread between Later milestones.** Brief connecting phrases ("With your profile mapped, the next step is...") to guide readers through the vision. Each milestone still makes sense in isolation

### Desktop App (v0.13)
- **D-11:** **End state only.** Describe the native app experience. Do NOT mention the PWA interim step (implementation detail for Phase 4 deep dives)
- **D-12:** **Abstract technology.** No Electron, Tauri, or PWA brand names. Just "native application" and "signed installers"
- **D-13:** **Mention Apple code signing.** Signals seriousness to technical evaluators. "Signed installers for macOS and Windows"
- **D-14:** **Brief callback to Known Limitations.** "This is the most important step toward making Kestrel usable for everyone" connects to the developer-only install limitation
- **D-15:** **Independent from Hosted Version.** Don't contrast with the hosted option. Each milestone stands alone
- **D-16:** **Workshopped copy:** "Download Kestrel, double-click, and start scoring jobs. No terminal, no Docker, no configuration files. A native application with signed installers for macOS and Windows, your data stored locally just like today. This is the most important step toward making Kestrel usable for everyone."

### Browser Extension (v0.14)
- **D-17:** **Just one-click save.** Core value: save any job from any site to scoring queue. No quick-score preview, no page enrichment. Keep it simple

### Mobile App (v0.15)
- **D-18:** **Future-focused framing.** Don't dwell on "paused" status. Focus on what it will be. Brief mention that web comes first

### Profile & Skills
- **D-19:** **Customizable visualization styles.** Users pick how to see their profile: RPG character sheet, baseball card, LinkedIn-style stats, spiderweb diagram, or simple scorecard. Same data, preferred lens
- **D-20:** **Workshopped copy:** "An honest map of where you stand professionally. Your strengths, gaps, and skill levels across the areas that matter for your target roles. Pick how you want to see it: RPG character sheet, baseball card, LinkedIn-style stats, spiderweb diagram, or a simple scorecard. Same data, your preferred lens."

### Know Me (NEW milestone, replaces "Writing Style Flywheel")
- **D-21:** **Deep personal understanding.** Not just writing voice. Kestrel learns values, motivations, likes, dislikes, triggers, professional identity. Feeds back into the entire pipeline: scoring reflects what matters personally, generated text sounds like you, misaligned opportunities stop showing up
- **D-22:** **Reflective essay prompts.** Propose users write essays on existential, value-oriented, and work-related questions to align the vision, not just mechanics
- **D-23:** **Examples of pipeline alignment.** No oil drilling jobs if you care about the environment. No low-salary cause-oriented roles if money is the current priority. The system understands context, not just keywords
- **D-24:** **Workshopped copy:** "Kestrel learns who you are, not just what you can do. Through your writing, reflective prompts, and everyday choices, it builds an understanding of your values, motivations, and professional identity. Over time the entire pipeline tunes to you: scoring weighs what matters to you personally, generated text sounds like you, and opportunities that clash with your values stop showing up."

### Gap Analysis & Coaching
- **D-25:** **End benefit only.** Don't describe the progressive depth (skill maps, MOOCs, AI coaching). Just the outcome: pick a target role, see what's missing, get steps to close the gap
- **D-26:** **Workshopped copy:** "Pick a target role and see exactly what's missing. Kestrel maps the gap between where you are and where you want to be, then suggests concrete steps to close it, from free resources to structured learning paths."

### Voice Mode
- **D-27:** **Separate from Know Me.** Voice Mode is speech input (dictation, voice interaction). Know Me is deep personal understanding. Different technical challenges, different user benefits
- **D-28:** **Writing Style > Voice Mode in priority.** Know Me appears before Voice Mode in Later section. Writing with LLMs is current mainstream; voice is still niche

### Feature Flags
- **D-29:** **NOT in ROADMAP.md.** Feature flags are internal infrastructure with no direct user benefit. ROAD-15 satisfied in Phase 4 deep-dive docs, not the user-facing roadmap

### Hosted Version
- **D-30:** **User benefit framing only.** "Subscription option for users who don't want to install anything." No pricing, no tiers, no business model discussion. Zero-setup, encrypted, deletable

### Milestone Ordering
- **D-31:** **Later section order (user journey):** Profile & Skills, Know Me, Gap Analysis & Coaching, Voice Mode, Hosted Version. Know who you are (skills) -> know who you ARE (values) -> improve -> communicate -> infrastructure
- **D-32:** **Next section order unchanged:** Desktop App (v0.13), Browser Extension (v0.14), Mobile App (v0.15)

### Now Section Cleanup
- **D-33:** **Move shipped Now items to What's Shipped.** Cost Control, Onboarding, PII Safety are shipped and belong in the shipped section, not cluttering Now. Now should only have in-progress/planned items

### What's Shipped Updates
- **D-34:** **Update provider count to 11.** Mistral and Hugging Face providers added on this branch. Bump "Nine providers" to "Eleven providers" and update the provider list

### Diagrams
- **D-35:** **Defer all diagram updates.** Mermaid gantt and flowchart changes (new milestones, renamed milestones, Feature Flags removal) deferred to Phase 4 or cleanup task. Phase 3 focuses on prose content only

### Claude's Discretion
- Bird codename assignments for all milestones (real species, memorable, on-brand)
- Exact wording for Browser Extension, Mobile App, Voice Mode, Hosted Version descriptions
- How to word the connecting phrases in the narrative thread between Later milestones
- Exact phrasing when moving shipped items from Now to What's Shipped
- Whether "Public Roadmap" in-progress item stays in Now or gets updated

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 Output (primary input)
- `ROADMAP.md` (repo root) -- Current state from Phase 2. Phase 3 modifies this file
- `.planning/phases/02-roadmap-foundation/02-CONTEXT.md` -- Phase 2 decisions that carry forward (D-02, D-03, D-04, D-08, D-09, D-13, D-19, D-20)
- `.planning/phases/02-roadmap-foundation/02-01-SUMMARY.md` -- What Plan 01 built
- `.planning/phases/02-roadmap-foundation/02-02-SUMMARY.md` -- What Plan 02 built

### Project Context
- `.planning/PROJECT.md` -- North star (web-first, user-first), business model, milestone vision details
- `.planning/REQUIREMENTS.md` -- ROAD-09 through ROAD-16 requirements this phase covers
- `CHANGELOG.md` -- For any new cross-reference links needed

### Codebase Analysis
- `.planning/codebase/CONCERNS.md` -- Known tech debt context (for Known Limitations if touched)
- `.planning/codebase/ARCHITECTURE.md` -- Shipped capabilities reference

### Strategic Context (private, do not commit content to public files)
- `private/kestrel-gtm-conversation.md` -- GTM analysis informs tone and framing. Use insights, not citations

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **ROADMAP.md** -- 140-line document with established structure, tone, and formatting patterns
- **CHANGELOG.md** -- Cross-reference pattern established: `[v0.X.0](CHANGELOG.md#anchor)`
- **Phase 2 CONTEXT.md** -- 22 decisions providing tone, formatting, and structural precedent

### Established Patterns
- Status line format: `*Status: Shipped/In Progress/Planned/Considering*` (new, replacing emojis)
- Heading format: `#### Milestone Name (vX.Y Codename)`
- Warm second-person tone: "you," "your," conversational but factual
- No file paths, no API routes, no ticket IDs in user-facing content
- `---` horizontal rules as section separators

### Integration Points
- ROADMAP.md is the single file modified
- Phase 4 extends with docs/roadmap/ deep dives that reference these milestone descriptions
- Phase 5 adds contributor paths per milestone

</code_context>

<specifics>
## Specific Ideas

- Desktop App: evoke the "download, double-click, use" simplicity. Obsidian-like experience
- Profile & Skills: the multiple visualization styles (RPG, baseball card, spiderweb, etc.) are a unique differentiator. Make it clear this isn't a boring skills matrix
- Know Me: this is the deepest, most ambitious vision piece. Kestrel as a career companion that truly understands you as a person, not just your resume. Reflective essays on existential questions. Pipeline that reflects your values, not just your keywords. Oil drilling example, salary/cause example
- Writing Style priority over Voice Mode: writing with LLMs is mainstream, voice interaction is still niche. Order reflects this
- Bird codenames: on-brand with Kestrel (a falcon). Makes milestones memorable and gives the project personality
- No AI slop: the user explicitly called this out. Every word must earn its place

</specifics>

<deferred>
## Deferred Ideas

- **Diagram updates** -- Mermaid gantt and flowchart need updating for new milestones (Know Me, removed Feature Flags, renamed milestones). Deferred to Phase 4 or cleanup task
- **ROAD-15 (Feature Flags)** -- Documented in Phase 4 deep-dive docs, not in user-facing ROADMAP.md
- **PWA-to-native progressive path** -- Implementation detail for Phase 4 Desktop App deep dive. ROADMAP.md describes end state only
- **Hosted Version business model** -- Pricing, tiers, sustainability angle deferred. ROADMAP.md describes user benefit only

### Reviewed Todos (not folded)
None -- no pending todos matched this phase

</deferred>

---

*Phase: 03-forward-vision*
*Context gathered: 2026-04-26*
