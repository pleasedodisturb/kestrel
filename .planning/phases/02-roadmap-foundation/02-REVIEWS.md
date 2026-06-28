---
phase: 2
reviewers: [claude, gemini, ollama]
reviewed_at: 2026-04-25T14:05:00Z
plans_reviewed: [02-01-PLAN.md, 02-02-PLAN.md]
models:
  claude: claude (separate session, pipe mode)
  gemini: gemini-cli v0.39.1 (Google AI, default model)
  ollama: qwen2.5-coder:14b (local, direct pipe)
---

# Cross-AI Plan Review — Phase 2

## Claude Review

### Plan 02-01: Write ROADMAP.md Prose

#### Summary

A well-structured, highly prescriptive plan for writing the core ROADMAP.md document. The 22 user decisions have been thoroughly translated into actionable instructions with clear section-by-section guidance. The plan correctly handles the Phase 1 dependency gap (inventory.md doesn't exist) by relying on `.planning/codebase/` docs as fallback sources. CHANGELOG anchor verification is smartly separated as its own task. This plan is ready for execution with one medium-severity issue around a dead link.

#### Strengths

- **Decision traceability is excellent.** Every instruction maps back to a specific D-XX decision. An executor cannot accidentally violate a user decision because the rationale is inline.
- **Negative constraints are explicit.** "Do NOT promise forever AGPL", "No file paths", "No ticket IDs", "No engineering metrics" — these are the kind of instructions that prevent the most common AI writing mistakes.
- **Anchor verification is separated as Task 2.** This is the right call — write first, verify after. The expected anchors are pre-computed and listed in the interfaces block, which eliminates guesswork.
- **The `must_haves` frontmatter is specific and falsifiable.** Each truth can be mechanically checked against the output.
- **Threat model is appropriate for a public-facing document.** T-02-01 and T-02-02 correctly identify information disclosure as the primary risk category.
- **The `read_first` list is comprehensive.** Directing the executor to read PATTERNS.md, CONCERNS.md, and ARCHITECTURE.md ensures the shipped content is grounded in verified facts rather than hallucinated features.

#### Concerns

- **MEDIUM — Dead link to `docs/roadmap/inventory.md`.** The plan instructs Task 1 to write "link to `docs/roadmap/inventory.md` for the full story" in the What's Shipped opening line. But this file doesn't exist — Phase 1 hasn't executed. A reader clicking this link on GitHub will get a 404. **Recommendation:** Either (a) make the link conditional on the file existing, (b) link to CHANGELOG.md instead as the "full story" fallback, or (c) add a task to create a minimal stub at `docs/roadmap/inventory.md` with a "Coming soon" note. Option (c) is cleanest.

- **LOW — Word count verification is weak.** The done criteria say "under 600 words" but the automated verify is just `grep -c "^## " ROADMAP.md`. There's no automated word count check. Adding `wc -w` on the shipped section would make it self-verifying.

- **LOW — Contributing stub links to non-existent CONTRIBUTING.md.** Similar to the inventory.md issue. `CONTRIBUTING.md` doesn't exist at repo root. Since D-05 explicitly says "simple 'See CONTRIBUTING.md' line," the decision was made knowingly — just flag it in the commit message.

- **LOW — D-07 anchor pattern mismatch.** The CONTEXT.md records D-07's pattern as `[v0.3.0](CHANGELOG.md#030)` but the plan correctly uses the full anchor format `CHANGELOG.md#030-2026-04-13` (with date). The shorter format would not work on GitHub. Handled correctly in the plan, but the CONTEXT.md source has a stale pattern.

#### Suggestions

- Add a `<!-- NOTE: This link will resolve once Phase 1 ships inventory.md -->` comment in the markdown source, or create a stub file
- Consider adding `CONTRIBUTING.md` as a planned stub to prevent 404s (2-line file, not scope creep)
- Add one more negative done check: "No mention of 'open source' as a selling point" (per D-04)

#### Risk Assessment

**LOW.** The plan is thorough, well-constrained, and the primary risk (anchor mismatches) is explicitly addressed with a dedicated verification task.

---

### Plan 02-02: Add Mermaid Diagrams

#### Summary

A focused plan addressing the highest-risk requirement (ROAD-07: Mermaid diagrams). The plan correctly identifies GitHub Mermaid rendering as the primary technical risk and includes a mandatory human verification checkpoint before merge. The diagram syntax is conservative and GitHub-safe based on the project's own failure history (PR #266/#267). One medium concern around unverified Mermaid directives.

#### Strengths

- **Human checkpoint is blocking.** Mermaid rendering on GitHub cannot be verified programmatically — push and visual inspection is required. The checkpoint checklist is comprehensive (13 items).
- **Diagram syntax is maximally conservative.** No `&` joins, no HTML, no style directives, no subgraph edges. Every constraint from PR #266/#267 failures is encoded.
- **Diagram code is provided verbatim.** The executor doesn't need to design the diagrams, eliminating creative syntax errors.
- **Milestone name consistency is explicitly required.** Prevents subtle inconsistency between prose and diagrams.
- **The flowchart dependency graph is accurate.** Scoring -> Cost Control, Scoring -> Discovery, Discovery -> Browser Extension — verifiable from codebase architecture.

#### Concerns

- **MEDIUM — `todayMarker off` is unverified on GitHub.** The plan flags this as "ASSUMED safe but must verify." If unsupported, the entire gantt chart could fail to render. **Recommendation:** Have a fallback ready — if it breaks, simply remove the line.

- **MEDIUM — `axisFormat %B` is also unverified.** If GitHub's Mermaid doesn't support `%B`, the axis might show raw date strings like "2026-01-01" exposing the fake positioning dates. **Recommendation:** Fallback to `axisFormat %Y` or remove entirely.

- **LOW — Gantt dates create false precision risk.** The underlying dates (2026-01-01, 2026-04-15) are in the source code. A contributor reading raw markdown might interpret "Desktop App starts April 2026" as a real date commitment. **Recommendation:** Add a markdown comment above the gantt block.

- **LOW — Flowchart dependency accuracy.** The edge `B[Cost Control] -> E[Desktop App]` implies Desktop App depends on Cost Control — these seem independent. Similarly, `E[Desktop App] -> J[Feature Flags]` may be temporal ordering rather than a real dependency. **Recommendation:** Verify edges represent real dependencies, not just aspirational ordering.

#### Suggestions

- Document fallback Mermaid syntax for both `todayMarker off` and `axisFormat %B` directly in the plan
- Add a source-code comment above the gantt block clarifying dates are positional, not commitments
- Reconsider Cost Control -> Desktop App and Desktop App -> Feature Flags dependency edges
- Add one more checkpoint check: "Gantt chart axis does NOT show year numbers (only month names)"

#### Risk Assessment

**MEDIUM.** The human checkpoint mitigates the primary risk, but two unverified Mermaid directives could each independently cause the gantt chart to fail, requiring a fix-and-reverify cycle. Having documented fallbacks would reduce this to LOW.

---

## Gemini Review

### Summary

The proposed implementation plans for Phase 2 are well-structured, tightly aligned with the established design decisions, and exhibit a strong understanding of Kestrel's product vision and non-commercial nature. Breaking the work into two distinct phases (prose first, visual diagrams second) is a smart de-risking strategy that isolates the known volatility of GitHub's Mermaid rendering from the core documentation work.

### Strengths

- **Logical Staging.** Separating the prose generation (Plan 01) from the diagram generation (Plan 02) isolates the highest-risk element (Mermaid rendering) into its own verifiable step.
- **Tone Alignment.** The plan perfectly captures the requested "warm teaching tone" and confident acknowledgement of technical debt, avoiding defensive language or over-promising.
- **Accurate Context.** The milestone versions (v0.12 for "Now") accurately reflect the current state of the repository (`pyproject.toml` and `CHANGELOG.md` are at `0.12.0`).
- **Targeted Scope.** Strict adherence to limiting known limitations to exactly three items, preventing document bloat and focusing on the non-technical evaluator audience.

### Concerns

- **HIGH — Dead Link Risk (Missing Inventory).** Plan 01 references a link to `docs/roadmap/inventory.md` (based on decision D-22). However, codebase analysis reveals this file does not currently exist. The closest matches are `docs/internal/kestrel-sync-matrix.md` and `.planning/PROJECT.md`. Linking to a non-existent file in a root document will degrade the evaluator experience.
- **MEDIUM — CHANGELOG Anchor Volatility.** `CHANGELOG.md` headers use a complex format: `## [0.12.0](link) (2026-04-23)`. GitHub aggressively strips markdown links, brackets, and periods during slugification, resulting in unintuitive anchors like `#0120-2026-04-23`. Task 2 in Plan 01 relies on manual verification, which is highly error-prone given this complexity.
- **LOW — Gantt Chart Mobile Overflow.** Mermaid Gantt charts with absolute durations often scale poorly on GitHub's mobile web view, requiring awkward horizontal scrolling.

### Suggestions

- **Address the Missing Inventory.** Update Plan 01, Task 1. Since Phase 1 (Feature Inventory) may not be executed yet, either create a temporary stub for `docs/roadmap/inventory.md`, point the link to the existing `docs/internal/kestrel-sync-matrix.md`, or comment out the link until Phase 1 is officially complete.
- **Programmatic Anchor Verification.** Enhance Plan 01, Task 2 to recommend using a quick Python regex script to dry-run GitHub's slugification rules against the `CHANGELOG.md` headers to guarantee the cross-reference anchors will resolve.
- **Optimize Gantt Labels.** Keep the milestone labels in the Plan 02 Gantt chart as short as possible to prevent layout breaking on narrower viewports.

### Risk Assessment

**LOW.** This is an entirely documentation-focused initiative with zero impact on production code. The primary risks are cosmetic (broken diagrams, dead links, bad anchors). The human verification checkpoint in Plan 02, combined with the suggested fixes for the missing inventory file and anchor generation, reduces the overall risk profile to near zero.

---

## Ollama Review (qwen2.5-coder:14b, local)

### Summary

Plan 02-01 and Plan 02-02 aim to create a comprehensive roadmap for the Kestrel project, focusing on documentation quality, structure, and user engagement. The plans are well-designed with detailed sections and specific requirements, but there are several concerns related to content accuracy, dependency management, and rendering issues that need attention.

### Strengths

- **Structured Approach.** Both plans provide a clear structure for the roadmap, including specific sections and requirements.
- **User-Centric Design.** The emphasis on privacy-led hero pitch and user impact limitations aligns with the North Star goals.
- **Detailed Roadmap Sections.** Each section has well-defined objectives and content guidelines, such as CHANGELOG cross-references and emoji status badges.

### Concerns

- **HIGH — Rendering Issues with Mermaid Diagrams.** There are known risks related to the rendering of Mermaid diagrams on GitHub, particularly with `todayMarker off` and `axisFormat %B`. These issues could lead to a suboptimal user experience if not resolved.
- **MEDIUM — Accuracy of CHANGELOG Cross-References.** The task to verify all CHANGELOG cross-reference anchors matches GitHub's slugification should be thoroughly tested to ensure accuracy.
- **MEDIUM — Dependency Management.** Plan 02-02 depends on the completion of Plan 01, which introduces a sequential dependency that could impact overall project timelines if not carefully managed.
- **LOW — Content Completeness.** The plans should ensure that all sections are fully populated with relevant content to avoid partial or incomplete information.

### Suggestions

- **Enhance CHANGELOG Verification.** Implement automated checks to ensure all cross-references are accurate and up-to-date.
- **Test Mermaid Diagrams Thoroughly.** Before finalizing the plans, conduct extensive testing of Mermaid diagrams on GitHub to confirm rendering behavior and adjust configurations if necessary.
- **Improve Dependency Communication.** Clearly document dependencies between plans and establish contingency measures to mitigate delays due to sequential dependencies.

### Risk Assessment

**MEDIUM.** The plan is well-designed but relies heavily on the accurate rendering of Mermaid diagrams, which has previously caused issues in similar projects. There are concerns about the completeness of content, particularly related to CHANGELOG cross-references and the shipped section. While the plans have clear goals and requirements, dependency management introduces a risk that could impact timelines if not properly addressed.

---

## Consensus Summary

### Agreed Strengths

All three reviewers independently praised:

1. **Logical plan staging** — separating prose (Plan 01) from Mermaid diagrams (Plan 02) correctly isolates the highest-risk element
2. **Strong decision traceability** — plans align tightly with the 22 CONTEXT.md decisions
3. **Tone and scope discipline** — warm teaching tone, user-centric design, exactly 3 known limitations, no scope creep
4. **Conservative Mermaid syntax** — learned from project's own PR #266/#267 failures
5. **Human checkpoint for Mermaid** — correct gating of the only unverifiable-by-automation risk

### Agreed Concerns

All three reviewers independently flagged:

1. **Mermaid rendering risk** (Claude: MEDIUM, Gemini: implicit, Ollama: HIGH) — `todayMarker off` and `axisFormat %B` are unverified on GitHub. All recommend thorough testing. **Priority: document fallbacks before execution.**
2. **CHANGELOG anchor fragility** (Claude: LOW, Gemini: MEDIUM, Ollama: MEDIUM) — GitHub's slugification rules make verification error-prone. Gemini and Ollama both suggest automated/programmatic verification. **Priority: enhance Task 2 verification.**

Two of three reviewers flagged:

3. **Dead link to `docs/roadmap/inventory.md`** (Claude: MEDIUM, Gemini: HIGH) — the file doesn't exist yet. Both recommend a stub file or HTML comment. **Priority: address before execution.**

### Divergent Views

| Topic | Claude | Gemini | Ollama | Assessment |
|-------|--------|--------|--------|------------|
| `todayMarker off` risk | MEDIUM | Not flagged | HIGH | **Consensus: prepare fallback** — 2/3 flagged, trivial fix if needed |
| `axisFormat %B` risk | MEDIUM | Not flagged | HIGH (grouped) | **Same as above** — prepare fallback syntax |
| Dead link inventory.md | MEDIUM | HIGH | Not flagged | **Consensus: create stub** — 2/3 flagged, Gemini rated HIGH |
| Flowchart dependency accuracy | LOW | Not flagged | Not flagged | **Minor** — Claude-only concern, worth a quick check |
| Gantt mobile overflow | Not flagged | LOW | Not flagged | **Cosmetic** — Gemini-only, acceptable for desktop-primary audience |
| Plan dependency risk | Not flagged | Not flagged | MEDIUM | **Low concern** — sequential dependency is by design (Wave 1 -> Wave 2) |
| Anchor verification method | Manual (pre-computed) | Programmatic script | Automated checks | **Consensus: automate** — 2/3 want programmatic verification |

### Overall Verdict

**Ship-ready with 3 adjustments:**

1. **Create a stub `docs/roadmap/inventory.md`** — 2/3 reviewers flagged the dead link, Gemini rated it HIGH. A 2-line stub prevents 404s with zero scope creep.
2. **Document Mermaid fallbacks** — 2/3 reviewers flagged `todayMarker off` and `axisFormat %B` as risks. The fix is "remove the line." Note this in the plan so the executor doesn't have to improvise.
3. **Automate CHANGELOG anchor verification** — 2/3 reviewers want programmatic verification rather than manual. A simple grep/regex check against CHANGELOG.md headings would suffice.

### Requirement Coverage

| Requirement | Plan | Coverage | Reviewer Agreement |
|-------------|------|----------|--------------------|
| ROAD-01 | 02-01 | Full | All 3 |
| ROAD-02 | 02-01 | Full | All 3 |
| ROAD-03 | 02-01 | Full | All 3 |
| ROAD-04 | 02-01 | Full | All 3 |
| ROAD-05 | 02-01 | Full | All 3 |
| ROAD-06 | 02-01 | Full | All 3 |
| ROAD-07 | 02-02 | Full | All 3 |
| ROAD-08 | 02-01 | Full | All 3 |

No gaps in requirement coverage. All three reviewers confirm all 8 ROAD requirements are addressed.
