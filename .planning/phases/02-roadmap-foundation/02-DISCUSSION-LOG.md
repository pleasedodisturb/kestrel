# Phase 2: Roadmap Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 02-roadmap-foundation
**Areas discussed:** Document structure & audience framing, Status system & horizon mapping, Tech debt & honesty framing, Mermaid timeline design

---

## Document Structure & Audience Framing

### Primary Audience

| Option | Description | Selected |
|--------|-------------|----------|
| Product evaluator | Someone hitting the repo cold — "what does this do, is it for me?" Clean product doc. Builder-credential lives elsewhere. | ✓ |
| Dual audience | Product evaluators AND builder/employer audience. Weave in judgment signals. Richer but risks satisfying neither. | |
| Contributor magnet | Optimize for "I want to help." Product context secondary to actionability. | |

**User's choice:** Product evaluator
**Notes:** Builder-credential story lives in blog posts and README, not in the roadmap.

### Shipped Content Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Condensed summary + link | ~500 words shipped section + link to docs/roadmap/inventory.md. Keeps roadmap scannable. | ✓ |
| Inline domain sections | Pull 8 domain clusters directly. ~1,500 words. Self-contained but long. | |
| Milestone-grouped shipped | Group by version milestones. Chronological story. Different grouping than inventory. | |

**User's choice:** Condensed summary + link

### Section Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Vision-first | Hero pitch → Shipped → What's Next → Timeline → Known Limitations → About → How to Help | ✓ |
| Story-first | Evolution narrative → Shipped → Forward vision → Timeline → Honesty corner | |
| Forward-first | What's Next → Timeline → What is Kestrel → Shipped → Limitations | |

**User's choice:** Vision-first

### Hero Pitch Positioning

| Option | Description | Selected |
|--------|-------------|----------|
| Privacy-led | Lead with self-hosted, data stays local, BYOK AI. EU/privacy wedge as differentiator. | ✓ |
| Capability-led | Lead with what it does: AI scoring, discovery, tracking. Broader but less differentiated. | |
| Problem-led | Lead with the pain: AI slop, ATS black holes. More emotional. | |

**User's choice:** Privacy-led

### Philosophy Section

| Option | Description | Selected |
|--------|-------------|----------|
| Skip it | Roadmap stays purely functional. | |
| One paragraph max | 2-3 sentences after hero. Adds soul without bloating. | ✓ |
| Dedicated section | Full "Why Kestrel" section. Risk: marketing copy on a 3-star repo. | |

**User's choice:** One paragraph max
**Notes:** User raised strategic questions about open-source positioning and AGPL — captured as deferred items. Key insight: "open source isn't the selling point." Roadmap should frame as privacy-first/self-hosted, not lead with license.

### Disclaimers Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Footnote-style | "About This Project" at bottom. Matter-of-fact, honest without apologetic. | ✓ |
| Inline callouts | Woven into relevant sections. More organic but scattered. | |
| Prominent banner | GitHub admonition near top. Very visible but leads with caveats. | |

**User's choice:** Footnote-style

### Contributing Section

| Option | Description | Selected |
|--------|-------------|----------|
| Stub placeholder | Simple "See CONTRIBUTING.md" line. Phase 5 builds the real version. | ✓ |
| Skip until Phase 5 | No contributor section until Phase 5. | |
| Lightweight per-milestone hooks | Pull Phase 5 work forward. More work now but immediately actionable. | |

**User's choice:** Stub placeholder

---

## Status System & Horizon Mapping

### Status Display

| Option | Description | Selected |
|--------|-------------|----------|
| Emoji badges | Simple emoji prefix. Universally readable, renders everywhere. Standard OSS pattern. | ✓ |
| Text labels in table | Milestone summary table with Status column. Clean and scannable. | |
| GitHub admonition blocks | Colored NOTE/TIP/WARNING blocks. Visually distinct but heavy/noisy. | |

**User's choice:** Emoji badges

### Horizon Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Version-anchored horizons | Now (v0.12), Next (v0.13-v0.15), Later (v1.0+). Concrete without dates. | ✓ |
| Priority-ordered flat list | Skip horizon labels. Just priority order + status badges. | |
| Time-relative horizons | Now/Coming Up/On the Horizon. No versions. Risk: goes stale. | |

**User's choice:** Version-anchored horizons

### Forward Section Scaffolding

| Option | Description | Selected |
|--------|-------------|----------|
| Empty scaffolding with headings | Section headers + "Details coming" placeholders. Phase 3 fills in. | ✓ |
| Brief placeholders with names | Milestone names + one-sentence teasers under each horizon. | |
| Skip forward sections entirely | Phase 3 adds them wholesale. | |

**User's choice:** Empty scaffolding

### Cross-references

| Option | Description | Selected |
|--------|-------------|----------|
| Shipped only | CHANGELOG + release tag links on shipped items. Forward milestones have none yet. | ✓ |
| Shipped + planning links | Also link forward milestones to deep dives (some dead until Phase 4). | |
| Minimal - no inline links | Status badges are enough. Keep roadmap link-light. | |

**User's choice:** Shipped only

### Status Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| 4 statuses (Shipped/In Progress/Planned/Considering) | Clear, low-maintenance. Maps cleanly to horizons. | ✓ |
| Add "Researched" | Signals serious thought. One more thing to maintain. | |
| Add "Paused" | Honest for mobile/voice. Distinct from "Considering." | |

**User's choice:** 4 statuses is enough

### Version Numbering for Forward Milestones

**User's choice:** Claude's discretion — assign reasonable version numbers based on scope and existing pattern.

---

## Tech Debt & Honesty Framing

### Disclosure Level

| Option | Description | Selected |
|--------|-------------|----------|
| User-impact debt only | Developer-only install, SQLite-only, no lockfile. Skip internal architecture debt. | ✓ |
| Full transparency | Everything from CONCERNS.md. Maximum honesty. Risk: reads like bug tracker. | |
| Minimal acknowledgment | One paragraph, no specifics. Technically meets ROAD-06. | |

**User's choice:** User-impact debt only
**Notes:** User reframed the entire section: "The real limitation is that it's user-first product with developer-only install — a mutant without clear audience." This became the lead item (D-12).

### Tone

| Option | Description | Selected |
|--------|-------------|----------|
| Confident acknowledgment | Frame as known tradeoffs, not apologies. Shows awareness and intentionality. | ✓ |
| Humble and direct | No spin. "Here is what is rough." | |
| Roadmap-integrated | Each debt links to fixing milestone. | |

**User's choice:** Confident acknowledgment

### Docker G-488

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, briefly | Mention the known regression honestly. | |
| No - too granular | Specific bugs don't belong in roadmap. | |
| Fold into deployment framing | Frame all deployment options with current state. | |

**User's choice:** Initially selected "Yes, briefly" but then corrected: "if Docker is fixed we don't care about it." Decision changed to: **Don't immortalize bugs in the roadmap. Bugs come and go, structural limitations stay.** Led to the D-15 decision.

---

## Mermaid Timeline Design

### Diagram Type

| Option | Description | Selected |
|--------|-------------|----------|
| Gantt chart | Horizontal timeline. Natural fit for roadmap. | |
| Flowchart | Boxes and arrows. Good for dependencies. | |
| Both | Gantt for timeline, flowchart for dependencies. | ✓ |

**User's choice:** Both diagrams

### Gantt Date Format

| Option | Description | Selected |
|--------|-------------|----------|
| Quarters without years | Relative ordering without specific date commitments. Won't go stale. | ✓ |
| Real quarters with years | More concrete and professional. Goes stale fast for solo project. | |
| No dates at all | Ordering only, no time axis. Unconventional. | |

**User's choice:** Quarters without years

### Detail Level

**User's choice:** Claude's discretion — choose detail level based on what renders cleanly on GitHub and what's readable at a glance.

---

## Claude's Discretion

- Version-to-milestone mapping for forward milestones
- Mermaid diagram detail level
- Exact hero pitch and philosophy paragraph wording
- How to condense shipped section into ~500 words
- Section heading phrasing

## Deferred Ideas

### Strategic (user raised during discussion)
- **Commercialization path research** — market, product vision, promotion strategy
- **Recruiter-oriented spin-off** — scoring engine inverted for B2B recruiter tool
- **License strategy review** — AGPL vs dual-license vs fork model
- **CLA addition** — prerequisite for future dual-licensing, easy now
- **Open-source positioning rethink** — privacy-first may be better pitch than "open source"
- **Grant applications** — Prototype Fund, NLnet (parked until after July 23 kill criterion)
