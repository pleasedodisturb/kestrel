---
phase: 2
slug: roadmap-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual verification (documentation-only phase — no code tests) |
| **Config file** | none |
| **Quick run command** | `grep -c "^##\|^###" ROADMAP.md` (verify section structure) |
| **Full suite command** | `cat ROADMAP.md \| head -5 && wc -l ROADMAP.md && grep -c "mermaid" ROADMAP.md` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick section structure check
- **After every plan wave:** Verify full document structure and Mermaid block count
- **Before `/gsd-verify-work`:** Full manual review of GitHub rendering
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ROAD-01 | — | N/A | manual | `test -f ROADMAP.md && echo "EXISTS"` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | ROAD-02 | — | N/A | manual | `grep -cE "✅\|🔨\|📋\|💭" ROADMAP.md` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | ROAD-03 | — | N/A | manual | `grep -c "Now\|Next\|Later" ROADMAP.md` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | ROAD-04 | — | N/A | manual | `grep -c "plans may change\|evolve\|subject to change" ROADMAP.md` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | ROAD-05 | — | N/A | manual | `grep -c "non-commercial\|not commercial" ROADMAP.md` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 1 | ROAD-06 | — | N/A | manual | `grep -ci "limitation\|tech debt\|known" ROADMAP.md` | ❌ W0 | ⬜ pending |
| 02-01-07 | 01 | 1 | ROAD-07 | — | N/A | manual | `grep -c "mermaid" ROADMAP.md` | ❌ W0 | ⬜ pending |
| 02-01-08 | 01 | 1 | ROAD-08 | — | N/A | manual | `grep -c "CHANGELOG.md" ROADMAP.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* This is a documentation-only phase — no test framework installation needed. Verification is file-existence and content-grep checks.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Mermaid diagrams render on GitHub | ROAD-07 | GitHub renderer differs from live editor | Push branch, open ROADMAP.md on GitHub, verify both gantt and flowchart render without errors |
| CHANGELOG cross-reference links resolve | ROAD-08 | GitHub anchor generation strips special chars | Click each `CHANGELOG.md#anchor` link in rendered ROADMAP.md on GitHub |
| Non-technical readability | ROAD-01 | Subjective quality — requires human judgment | Read ROADMAP.md as if discovering the project cold; verify no jargon, clear story arc |
| Status badges display correctly | ROAD-02 | Emoji rendering varies by platform | View on GitHub desktop and mobile |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
