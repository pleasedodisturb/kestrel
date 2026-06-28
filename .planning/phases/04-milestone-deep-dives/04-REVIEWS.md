---
phase: 4
reviewers: [gemini, codex]
reviewed_at: 2026-04-27T16:34:00.000Z
plans_reviewed: [04-01-PLAN.md, 04-02-PLAN.md]
attempted_reviewers: [gemini, codex, cursor]
failed_reviewers:
  cursor: "macOS login keychain locked — needs `security unlock-keychain`"
reviewer_models:
  gemini: "gemini-2.5-pro (default)"
  codex: "o4-mini"
---

# Cross-AI Plan Review — Phase 4

## Gemini Review

This review evaluates implementation plans **04-01 (Shipped Deep Dives)** and **04-02 (Planned Deep Dives + Mermaid Fixes)** for the Kestrel Public Roadmap project.

### Summary
The Phase 4 plans provide a robust and logical structure for translating high-level roadmap items into technical depth. By splitting the work into "Shipped" and "Planned" waves, the plans appropriately handle the varying levels of detail available (narrative vs. speculative) and ensure that the foundational `inventory.md` is built iteratively. The templates are well-aligned with the dual-audience decision (D-01), balancing business value with architectural transparency. However, the sheer volume of high-quality content required (19 documents, ~15k words) poses a significant risk to consistency and "AI slop" prevention (D-23).

### Strengths
*   **Logical Decomposition**: Grouping milestones by status (Shipped vs. Planned) allows for distinct templates that acknowledge different levels of certainty and technical detail.
*   **Strong Documentation Hierarchy**: Leveraging `inventory.md` (D-07) as a central registry prevents `ROADMAP.md` from becoming cluttered while ensuring all deep dives are discoverable even if they aren't explicitly linked in the main prose (e.g., Feature Flags).
*   **Traceability**: The explicit requirement to link 3-8 research and decision docs per document satisfies DEEP-03 and anchors the roadmap in historical technical reality.
*   **Future-Proofing**: Including "BMAD Integration" sections (DEEP-04) even for incomplete PRDs establishes the planning hierarchy early, making it easier for future contributors to understand the workflow.

### Concerns
*   **Volume vs. Quality (HIGH Severity)**: Writing 19 deep-dive documents at 500-1200 words each is a massive undertaking. Maintaining the "warm tone" (D-22) and avoiding "AI slop" (D-23) across ~15,000 words of technical documentation requires extreme discipline. There is a risk that later documents (in Wave 2) will feel rushed or repetitive compared to Wave 1.
*   **Relative Path Complexity (MEDIUM Severity)**: Docs located in `docs/roadmap/*.md` linking to `docs/research/*.md`, `docs/*.md`, and `ROADMAP.md` (root or `docs/` depending on final location) create significant surface area for broken links.
*   **Diagram Edit Latency (LOW Severity)**: Plan 04-02 handles critical Mermaid diagram fixes (renaming, adding "Know Me"). If Phase 4 is a "deep dive" phase, it is slightly counter-intuitive to wait until the final task of the final wave to fix the primary visual of the roadmap foundation.
*   **Cross-Plan Contradiction on "Feature Flags" (LOW Severity)**: Plan 02 includes "Feature Flags" as the 19th doc but notes it is excluded from `ROADMAP.md` prose. This is a subtle edge case; if a user finds it via `inventory.md`, they might be confused why it lacks a "parent" in the narrative roadmap.

### Suggestions
*   **Implement a Link Validation Script**: Before concluding Phase 4, run a local markdown link checker (e.g., `mlc` or a simple grep/find script) specifically targeting the `docs/roadmap/` directory to ensure all relative paths to the research vault are valid.
*   **Consolidate Mermaid Fixes**: Move the Mermaid diagram updates from Plan 04-02 to the beginning of Plan 04-01. Fixing the high-level visual "Flywheel" before writing the deep dives ensures that the terminology in the documents (e.g., "Voice Mode" vs. "Writing Style") is consistent with the latest visual vision.
*   **Content Parity Check**: Ensure that the "Related Milestones" section in the deep-dive documents uses the same naming conventions as the `ROADMAP.md` headers to avoid cognitive load for the reader.
*   **Standardize "BMAD Integration" Language**: Since PRDs are incomplete, create a "Standard Integration Statement" or boilerplate for this section to ensure consistency across all 19 files while still allowing for the "unique content" requested in the plan.

### Risk Assessment: MEDIUM
The overall risk level is **MEDIUM**.

**Justification**: The technical implementation is low-risk (markdown files and Mermaid strings), but the **editorial risk** is high. The success of this phase depends entirely on the ability to generate a high volume of technical prose that is both accurate to the codebase and accessible to users. If the links to the research vault break or the "BMAD integration" logic is hand-waved, the roadmap loses its value as a "truth-seeking" document and becomes mere marketing material. Strict adherence to the provided source materials (CHANGELOG, Research docs) is required to mitigate this.

---

## Codex Review (o4-mini)

### Summary
Both Plan 04-01 and Plan 04-02 present a clear two-wave strategy for authoring deep-dive roadmap documents. Wave 1 ("Shipped Deep Dives") establishes the template, creates ten shipped-milestone write-ups, and updates the master ROADMAP with inline links. Wave 2 ("Planned Deep Dives + Mermaid Fixes") fills in the planned-milestone documents, completes the inventory tables, adds nine additional links, and corrects two Mermaid diagrams. The split aligns with dependencies (shipped then planned) and reflects the phase goals, but coordination, quality consistency, and link accuracy warrant close attention.

### Strengths
- Well-defined templates for each wave, ensuring consistent structure across all documents.
- Explicit task breakdowns (write docs vs. update links/fix diagrams) simplify assignment and tracking.
- Clear dependency ordering: Wave 2 depends on Wave 1 output, minimizing premature cross-references.
- Inclusion of research links, BMAD integration notes, and "Related Milestones" promotes traceability.
- Mermaid diagram fixes scoped separately, reducing distraction from core documentation tasks.

### Concerns
- **HIGH -- Volume & Quality**: Authoring 19 deep-dive docs (~800-1200 words each) at uniform quality is ambitious and risks uneven depth or style drift.
- **MEDIUM -- Coordination Risk**: Two-wave split requires tight communication (e.g., inventory.md placeholders must align precisely between waves) or broken index tables.
- **MEDIUM -- Link Accuracy**: Relative paths from `docs/roadmap/...` to `docs/...`, `docs/research/...`, CHANGELOG.md, and BMAD PRDs must be validated; manual link edits across 19 files invite typos.
- **LOW -- Scope Creep**: Integration pattern for BMAD PRDs is defined but PRDs themselves remain incomplete; teams may be tempted to expand docs with draft PRD content beyond "integration notes."
- **LOW -- Template Evolution**: Any late template tweaks after Wave 1 (e.g., renaming headings) will force mass updates, delaying Wave 2.

### Suggestions
- Pilot one full deep-dive doc (including links and BMAD section) early in Wave 1 to lock down template and linking conventions.
- Create a lightweight QA checklist or automated link-checker script to validate all relative hyperlinks and Mermaid syntax across the new files.
- Establish a review cadence (e.g., peer review of two docs per week) to surface style drift or content gaps before scaling to all 19.
- Document the BMAD integration pattern separately (e.g., `docs/roadmap/INTEGRATION_GUIDELINE.md`) and reference it, reducing per-doc duplication and preserving consistency.
- Buffer time between waves for any template adjustments, index table corrections, or lessons learned from Wave 1 rollout.

### Risk Assessment: MEDIUM
While the plans cover all requirements and respect dependency ordering, the sheer volume of deliverables and manual linking steps pose a moderate risk to quality and schedule. Mitigation via early piloting, automated checks, and structured reviews should keep the milestone on track.

---

## Cursor Review

*Review failed: macOS login keychain locked. Run `security unlock-keychain` to fix.*

---

## Consensus Summary

Two reviewers (Gemini, Codex/o4-mini). Both rated overall risk as **MEDIUM**.

### Agreed Strengths (mentioned by both)
- Logical two-wave decomposition matching shipped vs. planned content depth
- Clear dependency ordering (Wave 2 depends on Wave 1)
- Strong traceability via research links and BMAD integration sections
- Well-defined templates ensuring consistent document structure

### Agreed Concerns (raised by both)
1. **Volume vs. Quality (HIGH)**: Both flagged 19 docs at ~15k total words as the top risk. Consistency fatigue, style drift, and uneven depth across documents
2. **Link Accuracy (MEDIUM)**: Both highlighted relative path complexity from `docs/roadmap/` to multiple target directories as a significant broken-link risk
3. **Coordination Risk (MEDIUM, Codex)** / **Diagram Edit Timing (LOW, Gemini)**: Both noted the two-wave split creates coordination surface area, though they weighted it differently

### Divergent Views
- **Mermaid timing**: Gemini suggested moving diagram fixes to Plan 01. Codex accepted the Wave 2 placement as reducing distraction from core docs. Neither rated it higher than LOW
- **BMAD boilerplate**: Gemini suggested standardizing BMAD language. Codex suggested extracting a separate INTEGRATION_GUIDELINE.md. Different approaches to the same consistency concern
- **Feature Flags discoverability**: Only Gemini flagged this (LOW). Codex did not mention it
- **Template evolution risk**: Only Codex flagged the risk of late template tweaks forcing mass updates (LOW)

### Actionable Suggestions (merged)
1. Run a link validation pass after each wave (both reviewers)
2. Pilot one full deep-dive doc early in Wave 1 to lock template conventions (Codex)
3. Ensure Related Milestones naming matches ROADMAP.md headings exactly (Gemini)
4. Create a shared BMAD Integration skeleton or guideline to prevent drift (both, different approaches)

### Orchestrator Assessment

Both reviewers agree the plans are well-structured and cover all requirements. The shared HIGH concern (volume vs. quality) is already mitigated by:
- Word count targets in plans (800-1200 shipped, 500-800 planned)
- Automated slop detection in verify commands
- The natural two-wave split (shipped docs have richer source material, planned docs are lighter by design)

The shared MEDIUM concern (link accuracy) is mitigated by:
- Verified path table in RESEARCH.md
- Verify commands that grep for `.planning/` links and count research references
- Consistent relative path patterns documented in plan context blocks

**Verdict**: No plan changes recommended. Both reviewers validated the approach. The suggestions for link validation and early piloting are good execution practices but don't require plan modifications.
