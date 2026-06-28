---
phase: 4
slug: milestone-deep-dives
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual review (documentation-only phase, no code changes) |
| **Config file** | None |
| **Quick run command** | `find docs/roadmap/ -name "*.md" \| wc -l` |
| **Full suite command** | `for f in scoring-engine discovery-engine ai-provider-system cost-control application-pipeline web-frontend cli infrastructure onboarding-flow pii-safety-boundary public-roadmap desktop-app browser-extension mobile-app profile-and-skills know-me gap-analysis-coaching voice-mode hosted-version feature-flags; do test -f "docs/roadmap/$f.md" && echo "OK: $f" \|\| echo "MISSING: $f"; done` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** `find docs/roadmap/ -name "*.md" | wc -l` (file count)
- **After every plan wave:** Manual review of 2-3 randomly selected deep dives for template compliance
- **Before `/gsd-verify-work`:** All 19 deep dives exist, index updated, ROADMAP.md links working, Mermaid diagrams fixed
- **Max feedback latency:** 1 second

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | DEEP-01, DEEP-02, DEEP-03, DEEP-04 | manual | `ls docs/roadmap/*.md \| wc -l` (should be 20) | N/A | ⬜ pending |
| 04-02-01 | 02 | 2 | DEEP-01, DEEP-02, DEEP-03, DEEP-04 | manual | `grep -c "docs/research\|docs/reference" docs/roadmap/*.md` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No test framework needed — this is a documentation-only phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Template consistency across 19 docs | DEEP-01 | Editorial quality cannot be automated | Spot-check 3 shipped + 2 planned docs for section order, separator, word count |
| Research link annotations | DEEP-03 | Annotation quality is subjective | Verify 3-8 annotated links per shipped deep dive |
| BMAD integration uniqueness | DEEP-04 | Boilerplate detection needs human judgment | Check 3 random BMAD sections are milestone-specific, not copy-paste |
| Mermaid diagrams render on GitHub | D-18/D-21 | GitHub renderer differs from local tools | Push to branch and preview both diagrams on GitHub |
| Cross-links between deep dives | D-05 | Semantic correctness of relationships | Verify Related Milestones sections reference logical connections |

---

## Validation Sign-Off

- [ ] All tasks have manual verify instructions
- [ ] File count: 20 files in docs/roadmap/ (19 deep dives + 1 index)
- [ ] BMAD Integration section in all 19 deep dives (grep check)
- [ ] ROADMAP.md has "Deep dive" links for all 19 milestones
- [ ] Mermaid diagrams updated and rendered on GitHub
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
