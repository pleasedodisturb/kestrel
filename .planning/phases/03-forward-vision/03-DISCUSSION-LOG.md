# Phase 3: Forward Vision - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md. This log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 03-forward-vision
**Areas discussed:** Description depth & format, Desktop App / Packaging path, Feature Flags gap, Writing Style Flywheel naming, Hosted Version framing, Mobile App resumption story, Profile & Skills / Gap Analysis vision, Now section cleanup, Specific milestone wording, What's Shipped updates, Version numbers / codenames, Tone / voice consistency

---

## Description Depth & Format

| Option | Description | Selected |
|--------|-------------|----------|
| Short paragraph | 2-4 sentences per milestone, keeps ROADMAP.md scannable | ✓ |
| Structured block | Mini-template: What you get + Why it matters + How it works | |
| Feature list | Intro + bullet list of sub-features | |

**User's choice:** Short paragraph
**Notes:** Phase 4 deep dives handle overflow

| Option | Description | Selected |
|--------|-------------|----------|
| Equal depth | All milestones get same 2-4 sentences | ✓ |
| Desktop App gets extra | Desktop App 4-6 sentences, others 2-3 | |
| Tiered by horizon | Next milestones longer, Later milestones shorter | |

**User's choice:** Equal depth

| Option | Description | Selected |
|--------|-------------|----------|
| Natural variation | Each milestone opens differently | ✓ |
| Consistent opener | Each starts with "You will be able to..." | |

**User's choice:** Natural variation

| Option | Description | Selected |
|--------|-------------|----------|
| Replace bullets with paragraphs | Each milestone as own heading with paragraph | ✓ |
| Keep bullets, add body | Emoji + bold bullet as anchor, body below | |

**User's choice:** Replace bullets with paragraphs

| Option | Description | Selected |
|--------|-------------|----------|
| On heading line | Emoji next to milestone name | |
| Drop emojis from headings | Rely on grouping for status | |
| Status line | *Status: Planned* line below heading | ✓ |

**User's choice:** Initially selected "On heading line," then switched to status line. User explicitly requested: "can we switch to status line option"

---

## Desktop App / Packaging Path

| Option | Description | Selected |
|--------|-------------|----------|
| Abstract only | No technology brand names | ✓ |
| Name the technologies | Mention PWA, Electron, Tauri | |
| Parenthetical hint | User-friendly with tech in parentheses | |

**User's choice:** Abstract only

| Option | Description | Selected |
|--------|-------------|----------|
| Mention both phases | Installable web app first, native download second | |
| End state only | Just describe the native app experience | ✓ |

**User's choice:** End state only. Note: ROAD-16 requires progressive path description, satisfied at high level with detail in Phase 4

| Option | Description | Selected |
|--------|-------------|----------|
| Brief callback | One phrase connecting to Known Limitations | ✓ |
| Let readers connect it | Don't reference the limitation | |

**User's choice:** Brief callback

| Option | Description | Selected |
|--------|-------------|----------|
| Mention code signing | Signals seriousness | ✓ |
| Don't mention signing | Product evaluators don't care | |

**User's choice:** Mention as commitment

| Option | Description | Selected |
|--------|-------------|----------|
| Independent | Don't contrast with Hosted Version | ✓ |
| Brief contrast | Mention hosted option as alternative | |

**User's choice:** Independent

---

## Feature Flags Gap

| Option | Description | Selected |
|--------|-------------|----------|
| Add as Later milestone | New entry under Later with Considering status | Initially selected |
| Fold into Hosted Version | Mention as part of Hosted Version | |
| Drop ROAD-15 | Remove from public roadmap entirely | |

**Initial choice:** Add as Later milestone
**Revised during word count discussion:** User said "I don't see value in feature flags in the roadmap, as its a technical milestone, it should be either in some gray backgraph or separate place, it has no direct value to users." Feature Flags removed from ROADMAP.md. ROAD-15 satisfied via Phase 4 deep-dive docs.

| Option | Description | Selected |
|--------|-------------|----------|
| Keep technical name | Call it "Feature Flags" | ✓ (moot: removed from roadmap) |
| User benefit framing | Rename to "App Editions" | |

| Option | Description | Selected |
|--------|-------------|----------|
| Skip diagram update | Phase 3 focuses on prose | ✓ |
| Add to flowchart | Add Feature Flags back to diagram | |

---

## Writing Style Flywheel Naming

| Option | Description | Selected |
|--------|-------------|----------|
| Voice input (speech) | Superwhisper-style voice interface | |
| Writing style learning | Kestrel learns your writing voice | |
| Both, one milestone | Voice + writing as one milestone | |
| Both, separate milestones | Split into Voice Mode and Writing Style | ✓ |

**User's choice:** Both as separate milestones

| Option | Description | Selected |
|--------|-------------|----------|
| Voice Mode + Writing Style | Clear, distinct names | ✓ |
| Voice Input + Writing Flywheel | More descriptive names | |

**Additional user input:** "I want writing style flywheel more important than voice, as voice is currently not as popular as writing with LLM." Writing Style appears before Voice Mode in Later section.

**Major vision expansion:** User expanded Writing Style into "Know Me" milestone encompassing:
- Writing voice + professional identity + personal values + motivations + triggers
- Pipeline alignment: scoring reflects values (no oil drilling if environmentally conscious)
- Reflective essay prompts on existential and value-oriented questions
- "Not only mechanics, but vision alignment"

| Option | Description | Selected |
|--------|-------------|----------|
| Rename to something broader | The vision is bigger than Writing Style | ✓ |
| Keep Writing Style name | Name is entry point, description explains | |
| Split the vision | Values in Profile & Skills, writing in Writing Style | |

| Option | Description | Selected |
|--------|-------------|----------|
| Personal Alignment | Professional and values-oriented | |
| Know Me | Short, evocative, user-centric | ✓ |
| Deep Profile | Extends Profile & Skills concept | |

| Option | Description | Selected |
|--------|-------------|----------|
| Move Know Me earlier | Before Gap Analysis (values inform coaching) | ✓ |
| Keep current order | After Gap Analysis | |

---

## Hosted Version Framing

| Option | Description | Selected |
|--------|-------------|----------|
| User benefit only | Zero-setup, encrypted, deletable. No pricing/business model | ✓ |
| Acknowledge business model | Mention sustainability motivation | |
| Minimal mention | One sentence only | |

---

## Mobile App Resumption

| Option | Description | Selected |
|--------|-------------|----------|
| Future-focused | Focus on vision, brief mention web comes first | ✓ |
| Honest about status | Acknowledge scaffold exists, explain pause | |
| Minimal | "Coming after web and desktop are solid" | |

---

## Profile & Skills / Gap Analysis Vision

**Profile & Skills:**
User provided custom input instead of selecting an option. Key quote: "just be chill, mention that it can be different style depending on your preference, RPG char, baseball card, LinkedIn stats, scorecard, personality test chart or spiderweb." Emphasis on customizable visualization.

**Gap Analysis & Coaching:**

| Option | Description | Selected |
|--------|-------------|----------|
| End benefit only | Pick a role, see what's missing, get steps | ✓ |
| Mention the progression | Hint at skill maps, resources, AI coaching | |

---

## Now Section Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Move shipped items up | Cost Control, Onboarding, PII Safety to What's Shipped | ✓ |
| Leave as-is | Don't touch Now section | |
| Remove Now entirely | Collapse into Next | |

---

## Milestone Wording Workshop

**Desktop App:** Approved as-is. "Download Kestrel, double-click, and start scoring jobs. No terminal, no Docker, no configuration files. A native application with signed installers for macOS and Windows, your data stored locally just like today. This is the most important step toward making Kestrel usable for everyone."

**Profile & Skills:** Approved with em dash removal. Final: "An honest map of where you stand professionally. Your strengths, gaps, and skill levels across the areas that matter for your target roles. Pick how you want to see it: RPG character sheet, baseball card, LinkedIn-style stats, spiderweb diagram, or a simple scorecard. Same data, your preferred lens."

**Gap Analysis & Coaching:** Approved as-is. "Pick a target role and see exactly what's missing. Kestrel maps the gap between where you are and where you want to be, then suggests concrete steps to close it, from free resources to structured learning paths."

**Know Me:** Approved as-is. "Kestrel learns who you are, not just what you can do. Through your writing, reflective prompts, and everyday choices, it builds an understanding of your values, motivations, and professional identity. Over time the entire pipeline tunes to you: scoring weighs what matters to you personally, generated text sounds like you, and opportunities that clash with your values stop showing up."

---

## What's Shipped Updates

| Option | Description | Selected |
|--------|-------------|----------|
| Leave as-is | Don't update shipped section | |
| Add new providers | Bump 9 to 11 (Mistral + Hugging Face) | ✓ |
| Light refresh | Tweak wording only | |

---

## Version Numbers / Codenames

| Option | Description | Selected |
|--------|-------------|----------|
| Keep versions as-is | v0.13, v0.14, v0.15, v1.0+ | ✓ |
| Reassign versions | | |
| Drop versions from Later | | |

User additionally requested codenames:

| Option | Description | Selected |
|--------|-------------|----------|
| Birds (matches Kestrel) | Real bird species, memorable | ✓ |
| Nature/weather | Horizon, Summit, etc. | |
| Simple letters/numbers | No codenames | |

| Option | Description | Selected |
|--------|-------------|----------|
| In headings | `#### Desktop App (v0.13 Falcon)` | ✓ |
| Subtitle line | On status line | |
| Internal only | Not in public roadmap | |

| Option | Description | Selected |
|--------|-------------|----------|
| Claude picks | Executor chooses fitting bird names | ✓ |
| User assigns | User picks specific birds | |

---

## Tone / Voice Consistency

| Option | Description | Selected |
|--------|-------------|----------|
| Same tone throughout | Shipped and planned feel like same voice | ✓ |
| Slightly more aspirational | Later milestones can use vision language | |
| Match but add urgency | Gradient from concrete to aspirational | |

**Additional formatting rules from user:**
- No em dashes anywhere in copy
- No AI slop (seamlessly, leverage, revolutionize, cutting-edge, etc.)
- Research AI writing antipatterns
- Keep it simple, but no simpler than necessary (Einstein's razor)

---

## Claude's Discretion

- Bird codename assignments (real species, memorable, on-brand)
- Exact wording for Browser Extension, Mobile App, Voice Mode, Hosted Version
- Connecting phrases in narrative thread between Later milestones
- How to move shipped items from Now to What's Shipped
- Public Roadmap in-progress item handling in Now section

## Deferred Ideas

- Mermaid diagram updates for new/renamed/removed milestones (Phase 4 or cleanup)
- Feature Flags documentation in deep-dive docs (Phase 4, not ROADMAP.md)
- PWA-to-native progressive path details (Phase 4 Desktop App deep dive)
- Hosted Version business model details (future decision)
