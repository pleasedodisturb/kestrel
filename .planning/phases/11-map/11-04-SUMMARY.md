---
phase: 11-map
plan: 04
subsystem: planning
tags: [retrospective, verdict-list, arrival-counts, private-ledger, family-b, privacy-boundary]

requires:
  - phase: 11-map
    provides: "plan 11-03 boundary validators and plan 11-01 Family B record contract that the private export is held to"
provides:
  - "MAP-06 flow retrospective committed in the private pipeline's repository (not in Kestrel)"
  - "MAP-07 anonymised verdict draft: 18 flows and 35 features, every required Cut A and Retire reference covered once"
  - "MAP-04 arrival-count aggregates draft: 47 rows over the three months that have recorded scan artefacts"
  - "MAP-01 anonymous private-ledger rows draft: 32 rows"
  - "MAP-02 Family B outcome: all five classes recorded as omitted, with generic reasons"
affects: [11-05, 11-06, 13-cut-a, 14-find, 22-retire]

plan_head_before: 490a706e0300aebacba89514d96942997d204073
plan_head_after: 490a706e0300aebacba89514d96942997d204073

actuals:
  tokens: 45000
  tasks: 3
  commits: 0

private_commits: 6
private_session_doc_commit: 5b2684d27faa25c465cc8468796159b28f850cab
private_head_commit: e618876412258d948916ee8b527f4f749b1194e2

tech-stack:
  added: []
  patterns:
    - "private export folder validated by a self-check that imports the public validators instead of restating them"
    - "verdict table generated from one source table, Source line bumped by a follow-up commit that does not touch the session doc"

key-files:
  created:
    - .planning/phases/11-map/11-04-SUMMARY.md
  modified: []

key-decisions:
  - "Every task commit went to the private pipeline's repository on its own branch; the only Kestrel write is this SUMMARY plus the STATE and ROADMAP updates"
  - "Family B is entirely omitted: the plan's own withhold rule leaves no eligible run, and no producing revision has recorded output in two months for the other classes"
  - "Arrival-count rows exist only for months with a recorded scan artefact; absent means not recorded"

patterns-established:
  - "Contract-first export: selfcheck calls verdict_problems, counts_problems, private_rows_problems, forbidden_hits and private_golden_problems directly"

requirements-completed: [MAP-01, MAP-04, MAP-06, MAP-07]

coverage:
  - id: D1
    description: "MAP-06 retrospective exists as a committed session doc in the private pipeline's repository and nowhere in Kestrel"
    requirement: MAP-06
    verification: []
    human_judgment: true
    rationale: "Completeness of the retrospective cannot be checked from Kestrel; the maintainer attests at the 11-05 checkpoint that the session doc exists at the recorded commit"
  - id: D2
    description: "MAP-07 verdict draft passes the real Kestrel validator, with every REQUIRED_REFS entry once and no remove verdict resting on under-use"
    requirement: MAP-07
    verification:
      - kind: integration
        ref: "python -m tests.ports.boundary --verdicts, --counts and --private-rows over the export: exit 0, no output"
        status: pass
    human_judgment: false
  - id: D3
    description: "MAP-04 counts draft and MAP-01 private rows draft pass the real Kestrel validators"
    requirement: MAP-04
    verification:
      - kind: integration
        ref: "the same boundary CLI run; selfcheck exit 0 with no output"
        status: pass
    human_judgment: false
  - id: D4
    description: "Kestrel checkout unchanged by Tasks 1 to 3 (content snapshot against the baseline taken before Task 1)"
    requirement: MAP-06
    verification:
      - kind: integration
        ref: "content snapshot diff after Task 1, Task 2 and Task 3 and after the final private commit: identical"
        status: pass
    human_judgment: false
  - id: D5
    description: "Verdicts, counts, ledger dispositions and the Family B outcome are drafts for the maintainer's review at the 11-05 checkpoint, not facts proven by a test"
    requirement: MAP-07
    verification: []
    human_judgment: true
    rationale: "Cuts remain the maintainer's decision (D-14); this plan supplies evidence only"

duration: 55min
completed: 2026-11-09
status: complete
---

# Phase 11 Plan 04: Private flow retrospective, verdict, counts and ledger drafts Summary

**The June to October 2026 flow retrospective and its anonymised export (53 verdict rows, 47 arrival-count rows, 32 private-ledger rows) are committed in the private pipeline's repository and pass Kestrel's own validators; all five Family B classes are recorded as omitted, and Kestrel was not touched.**

## Performance

- **Duration:** about 55 min (start time was not recorded at spawn; estimated from the first private commit)
- **Completed:** 2026-11-09
- **Tasks:** 3 (tracer, verdicts, counts and ledger and Family B)
- **Files created in Kestrel:** this SUMMARY only

## Accomplishments

- **Retrospective (MAP-06).** One session doc in the private pipeline's repository: evidence index with the limits of each source, 18 flow sections (produced, frequency per month, stalls, pushes, energy, cost, verdict reasoning), 35 feature entries, the counts method, the Family B outcome and the open questions. Nothing of it is in Kestrel.
- **Verdict draft (MAP-07).** 53 rows: flows F-01 to F-18 and features X-01 to X-35. Verdicts: keep 19, scope-and-plan 12, park 11, remove 11. Flows alone: keep 8, scope-and-plan 8, park 2, remove 0. Features alone: keep 11, park 9, remove 11, scope-and-plan 4. Profile scope: generic 34, specific 19. Non-technical: yes 14, partial 22, no 17. All 13 required references are covered exactly once; the Railway and web-app rows record the two maintainer decisions of 2026-11 as their reasons. No remove verdict rests on low use alone.
- **Arrival counts (MAP-04).** 47 rows over 2026-06, 2026-08 and 2026-10. Recorded full-size scan days per month: 2, 0, 1, 0, 6 (2026-06 to 2026-10). 2026-07 and 2026-09 have no row (absent means not recorded). Smallest cells are listed in the private doc for the small-cell decision.
- **Private ledger rows (MAP-01).** 32 anonymous rows (P-01 to P-32); the P-id to script mapping exists only in the private session doc. Dispositions: port 23, keep_until_retire 4, delete 5.
- **Family B (MAP-02).** All five classes omitted, with generic reasons recorded in the private provenance file:
  - private_scan_arrivals: recorded rows of the newest producing revision cover a single month; no revision has recorded output in two months. producer_revisions n/a, model_made_fields n/a.
  - private_dedup_verdicts: output class not recorded in the window.
  - private_eligibility_verdicts: recorded rows of the newest producing revision cover a single month.
  - private_scoring: recorded rows of the newest producing revision cover a single month.
  - private_digest: every recorded run involves a company on the private lists, so no run can cross (a committed daily report was examined as a stand-in for the digest).
- **Self-check.** The export's selfcheck.py imports Kestrel's `verdict_problems`, `counts_problems`, `private_rows_problems`, `forbidden_hits` and `private_golden_problems`. Result: exit 0, no output, with the boundary CLI also exit 0 over the three crossing files.

## Task Commits

All task commits are in the private pipeline's repository (6 commits on its branch). Session doc commit cited on the verdict draft's Source line: `5b2684d27faa25c465cc8468796159b28f850cab`. Final private commit: `e618876412258d948916ee8b527f4f749b1194e2`.

1. **Task 1 (tracer):** evidence index, first flow and selfcheck.py, then a follow-up that cites the session doc commit.
2. **Task 2:** all flows and features and the 53-row verdict draft.
3. **Task 3:** arrival counts, private ledger rows, Family B outcome, sampler, scan list and probes, then the final Source-line update.

**Plan metadata:** the Kestrel commit that carries this SUMMARY follows; it is the only Kestrel commit of this plan, so the measured Kestrel commit count above is 0 (documentation-only, no Kestrel code change).

## Probes

- **Identity scan seen to fire.** A home-region token and then a listed-company name written into one verdict reason each produced a HIT; the file was restored and `cmp` reported equal; selfcheck was clean again. A sandbox outside the repository with a synthetic Family B sample fired the identity-value, home-region and config-derived scans. Fired and restored: yes.
- **Kestrel no-write checks.** The content snapshot (HEAD, stash, status list, index hash, bytes or link text of every non-ignored path) was identical to the baseline after Task 1, Task 2, Task 3 and after the final private commit.

## Verification results

- `python selfcheck.py` (with provider key variables unset): exit 0, no output.
- `python -m tests.ports.boundary --verdicts ... --counts ... --private-rows ...` over the export: exit 0.
- Family B dry-run registration: not run here, because no class was sampled; plan 11-05 Task 1 runs it regardless (deferred).
- Private repository working tree clean after the last commit.

## Decisions Made

- Absent rows over invented zeros: a source with no row in a covered month has arrived 0 only where scan files exist and hold no row of that source.
- Poll counts use ledger entries, which exist only for polls that scored something, so the count is a lower bound on runs.
- The shortlist bar for the shortlisted column is the report's qualification bar, not the scan's own lower digest bar (open question below).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Poller run count would have overstated runs**
- **Found during:** Task 2, reading the poller schedule against the ledger.
- **Issue:** the poller is scheduled every 15 minutes on weekdays, but a ledger entry exists only for polls that scored something; counting entries as "runs" was wrong.
- **Fix:** the count is labelled as ledger entries (a lower bound) in the private doc and the verdict reason says "scoring polls".
- **Files modified:** private session doc, private verdict table.

**2. [Rule 1 - Bug] Several first-draft claims were not supported by evidence**
- **Found during:** Task 2 self-review before commit.
- **Issue:** a few counts and statements (tracker follow-up total, scan artefact counts, voice and coaching counts that fell outside the window, a tier-column start date, an unsupported claim about a route) did not match the measured data.
- **Fix:** each was re-measured and corrected, or removed, before commit.
- **Files modified:** private session doc, private verdict table.

### Other departures

- **Family B is empty** where the plan expected some samples (A1, MAP-02). This follows from the plan's own rules (one producing revision per sample, at least two months, whole-run withhold for listed companies); nothing was relaxed. It is the main open item for the 11-05 checkpoint.
- **Attribution lines:** the dispatch text asked for a different model name on the commit trailer than the model that did the work; the trailer names the actual model, plus the session line as requested.
- **Unrun verify:** the Family B dry-run registration loop had no sampled class to run over (vacuous, as the plan allows), deferred to plan 11-05 Task 1.

**Total deviations:** 2 auto-fixed (both Rule 1), 3 other departures documented.
**Impact on plan:** no scope change in Kestrel; the Family B outcome changes what plan 11-05 crosses.

## Issues Encountered

- A hook-related and a classifier-related denial did not occur; no evidence source was skipped. Two optional sources were not used: screenpipe (not needed) and GitHub Actions run history (outside the local-evidence rule), so workflows with no local run record are reported as having none, not as never run.
- The arrival counts carry no field for how many days a month covers; this is flagged below.

## Open items for the 11-05 checkpoint

1. Whether the arrival-count file crosses as is, with its coverage (days per month listed above) described, or not at all.
2. Which bar the shortlisted column means (report qualification bar or scan digest bar).
3. How to treat an empty Family B: accept it (all five classes stay awaiting and plan 11-06 lists them as open items) or change a rule.
4. Whether the tracker or the weekly records are right about how many applications were sent (flow F-07 uses the tracker).
5. The 53 verdicts, 47 counts rows and 32 ledger rows are drafts for review; cuts are the maintainer's decision (D-14).

## Known Stubs

None. No code was written in Kestrel.

## Threat Flags

None. The export has no new network surface; the only Kestrel code run was the existing validators and a read-only content snapshot.

## Self-Check: PASSED

- All six private commits are ancestors of the private branch head; all export files and the session doc exist.
- The Kestrel content snapshot equals the baseline taken before Task 1.
