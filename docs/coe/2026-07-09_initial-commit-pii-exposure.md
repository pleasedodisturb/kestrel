# COE: Personal application content shipped in the repo's initial public commit

**Date:** 2026-07-09 · **Severity:** mid-major · **Area:** repository publishing / PII hygiene
**Tickets:** G-1303, G-1306, G-1305 (remediation, all Done) · G-1316, G-1317 (action items)

## Impact

Personal narrative data was publicly readable in this repository for **three months** (2026-04-08 → 2026-07-08): application form-answer essays (~200-word "why company X" texts), a de-facto personal profile (salary band, visa status, location and notice-period answers, language proficiencies, per-role screening answers), 14 CV persona summaries with career details, private workspace identifiers (Linear org/project UUIDs), and personal document IDs. No credentials were exposed (secret scanning was green throughout). Blast radius was small in practice — 0 forks, ~5 stars, content buried inside two tool files — but the exposure was real and complete.

## Timeline

- 2026-04-08 — repo published; the initial commit carries the private codebase wholesale, including `batch_apply_browser.py` (essays, answer banks) and `render_tailored_cvs.py` (personas)
- 2026-04-19 — first scrub (PR #220) removes personal data from 29 files, **file-list-driven; misses the constants inside the two tool files**
- 2026-07-05 — owner directive "companies generic, examples must not reference me" triggers an adversarial full-repo sweep; leak discovered
- 2026-07-06 — HEAD cleaned (PRs #442, #443); data preserved to gitignored local config
- 2026-07-08 — full history rewrite executed (all refs), issue/PR bodies edited; GitHub Support purge requested for orphaned SHAs and body-edit revisions

## Root cause

1. **Why was personal data public?** The repo was created by publishing the private working codebase directly — the initial commit inherited everything.
2. **Why did it contain application machinery?** The project doubled as the owner's live job-search tool; personal answers were hardcoded next to the mechanisms that used them.
3. **Why didn't the first scrub catch it?** PR #220 enumerated *files known to hold personal data*; it never ran content-marker searches, so constants inside "tool code" passed.
4. **Why did three months pass?** No automated gate: `.github/pii-patterns.txt` existed but was empty (a placeholder), making the CI PII job a permanent no-op; nothing else searched for narrative-style personal content.
5. **Root:** publishing preceded a marker-based content audit, and the only recurring gate was a no-op.

## Detection

Human directive → adversarial sweep by content category (essays, profile facts, identifiers), not by file list. Could have been detected at any time by grepping distinctive personal markers; could have been **prevented** by doing that grep before the first push.

## Resolution

HEAD genericized to config-driven mechanisms (real values in gitignored `config/personal.yaml` / `config/companies.yaml`, fictional embedded floors, floor-hygiene tests that fail CI if real markers return); full `git filter-repo` rewrite (85 redactions + path purges) verified marker-zero across 1,193 commits with byte-identical HEAD; guardrails (ruleset + branch protection) restored after the ref flips; issue/PR bodies edited; support purge requested.

## What went well / what went wrong

- ✅ Layered review caught what regex missed both ways: a plan-checker added missed employer markers to gates; an independent reviewer found the gitignore landmine and the wrangler UUIDs
- ✅ Data was preserved (personas, UUIDs) into gitignored config *before* worktree/history destruction
- ✅ Mechanisms were kept functional — genericization, not amputation
- ✗ The initial publish had no pre-push content audit
- ✗ The first scrub verified by file list, not by marker search — partial scrubs create false confidence
- ✗ The CI PII gate was an empty placeholder for months and nobody noticed a permanently-green no-op check
- ✗ During remediation, an agent briefly wiped a PR body with a bad `sed` (restored from edit history) — shell string surgery on content with special characters is fragile; use a real language

## How a future agent avoids this

- **Before the first public push of any repo split from private code, run a marker-based content audit** — grep for the owner's name variants, employers, cities, salary patterns, doc/workspace IDs, and read every string constant in tools/ — not just the obvious data dirs. The initial commit is forever (until a rewrite).
- **Scrub PRs must verify by marker search over the whole tree, never by file list.** "We cleaned the 29 files we knew about" is how this incident happened.
- **A permanently-green check is a smell.** If a gate (like a PII pattern file) has no patterns, it isn't a gate — either populate it or fail loudly when empty.
- **The strip-list is itself PII.** Gate regexes, scrub checklists, and planning artifacts that enumerate personal markers must never be committed to the public repo (see also the G-1281 lesson: files that docs instruct users to create must be gitignored in the same PR).
- **When editing issue/PR bodies programmatically, never pipe through `sed` with unescaped content** — fetch body → transform in Python → `--body-file`. GitHub keeps body-edit revisions; count them into exposure scope.
- **History rewrites don't end at the push:** orphaned SHAs and body-edit revisions stay readable until GitHub Support purges them — that request is part of the remediation, not optional cleanup.

## Action items

- [ ] G-1316 — populate `.github/pii-patterns.txt` with generic structural patterns so the CI PII gate actually bites (route/agent)
- [ ] G-1317 — submit the GitHub Support purge request and confirm orphaned SHAs + body-edit revisions are gone (route/human-only)
- [x] Layer-3 memory pointer written (`feedback_repo_split_pii_audit`)
