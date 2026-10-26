# Phase 11: Map - Context

**Gathered:** 2026-10-26 (from the maintainer's phase review of 2026-10-25/26; see `.planning/STATE.md`, "v2.0 review position")
**Status:** Ready for planning

<domain>
## Phase Boundary

Map freezes what exists before anything is built or cut. Two tracks. **Track A** (in Kestrel) freezes today's live outputs: a script ledger, golden fixtures with source hashes, input-to-output mapping tables for every later phase encoded as strict-xfail tests, per-source arrival counts, and one protective golden for the shared `integration_configs` table. **Track B** (in the private pipeline's repository) is a June-to-October 2026 flow retrospective with a verdict per flow and per feature. The Cut A and Retire cut lists derive from those verdicts.

Map is read-only on the product: no changes under `src/career_os/`, no paid LLM calls, no scan or scoring runs. Requirements: MAP-01..MAP-09.

</domain>

<decisions>
## Implementation Decisions

### Privacy boundary (binding for every plan and agent in this phase)
- **D-01:** The raw retrospective (session transcripts, application rows, company names, person names, dates, stall and recovery narrative, moods, cost lines) is written ONLY inside the private pipeline's repository, as a session doc. Nothing of it is written under Kestrel's `.planning/`, `docs/` or `tests/`.
- **D-02:** What enters Kestrel from Track B is one anonymised verdict list per flow and per feature: kept / trimmed / parked / cut, with counts and reasons. No company names, no person names, no dates finer than a month, no quotes from transcripts. The CI PII scan is the second net, not the first.
- **D-03:** Track A fixtures are synthetic or scrubbed. Scrubbing replaces identity fields (company, URLs, recruiter and person names, emails, requisition IDs) with synthetic values and keeps the fields a verdict depends on (location text, title, remote policy, salary band, posting age) so the golden still exercises the same branch.
- **D-04:** Track A agents never read `private/`, `.env`, or Claude Code transcript directories. Track B agents may read transcripts and private data; they write only inside the private repository. The private paths live in the gitignored `private/retrospective/README.md`, never in a committed file.
- **D-05:** Committed files refer to the private side as "the private pipeline" or "the private pipeline's repository", never by name or path.

### Track A: what to freeze
- **D-06:** The script ledger covers every script in Kestrel `tools/` and every private-pipeline script that v2.0 ports, one row each: status (scheduled / by hand / dead), inputs, outputs, disposition (port / keep until Retire / delete). It is the seed of Retire's `PORT_LEDGER`; Retire's test that keeps the ledger honest is designed here.
- **D-07:** Goldens come from recorded outputs already on disk (scan outputs, digests, verdict logs), never from re-running the pipeline. Each golden records the git hash of the script revision that produced it.
- **D-08:** Mapping tables for later phases (Find, Filter, Scan, Score, Track, Write, Connect, Apply) are encoded as tests marked `xfail(strict=True, reason="v2.0 Phase <N>")`, collected by CI today. A phase turns them green by removing the marker; a strict xfail that passes early fails CI, so the ledger of pending behaviour stays honest.
- **D-09:** Per-source arrival counts are aggregates by month: arrived, survived prefilter, scored, shortlisted, applied. They are committed so Find decides source ports and cuts on evidence (the maintainer's rule: all sources are ported and judged on evidence, none cut up front).
- **D-10:** The protective golden for MAP-05 seeds an `ai_providers` row in `integration_configs`, runs `alembic upgrade head`, and reads the key back through the factory path (`career_os.ai.factory._read_credential_from_db`). It exists because Cut A deletes rows from that table by name and the factory's read is a silent `except Exception: return ""` today.

### Track B: the flow retrospective
- **D-11:** The unit of analysis is the FLOW, not the artefact: what it produces, how often it ran, where it stalled, where the maintainer pushed through, his energy on it (up or down), what it cost. Window: June to October 2026. Evidence from this machine only: the private repository's git history and session handoffs, its application tracker and outcome records, its logs and data folders, Claude Code session transcripts for that repository, Linear tickets, screenpipe activity where useful.
- **D-12:** Verdict per flow and per feature: KEEP (efficient, productive) / SCOPE-AND-PLAN (under-realised but wanted) / PARK (with a product-map entry) / REMOVE (exists for the sake of existing). Under-use alone is never a reason to remove.
- **D-13:** Every verdict carries two tags: profile-specific vs generic (the maintainer's own TPM/product profile vs any job seeker), and a "works for a non-technical profile" column, because v2.0 carries a per-profile constraint and v2.1 onboards other people's profiles.
- **D-14:** The verdict list is the input the maintainer reviews before Cut A is planned. Cuts are his decision; Map only supplies the evidence.

### Claude's Discretion
- File layout for ledger, goldens, counts and xfail tests under `tests/` and `docs/` (follow `tests/eval/geo/` as the golden precedent).
- How transcripts are parsed and summarised for Track B, as long as D-01..D-05 hold.
- Whether Track A and Track B run as parallel plans (they share no files, so they should).

</decisions>

<specifics>
## Specific Ideas

- The maintainer's framing: "leave the efficient and productive, remove what exists for the sake of existing", but features that were never fully realised get scoped and planned or parked, not removed.
- Map must tag what is his profile versus generic, because the friends' profiles (banker, art curator, QA engineer, hardware lead, ops manager) are the v2.1 test.
- Tests and output mapping come first at every scale: Map is the milestone-level instance of that rule.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Decisions and requirements
- `.planning/STATE.md` § "v2.0 review position (2026-10-25)" — the binding privacy rule and the settled Phase 0 to 2 decisions
- `.planning/REQUIREMENTS.md` § Map (MAP-01..MAP-09) and § "Decisions carried into later phases"
- `.planning/research/SUMMARY.md` § "Implications for Roadmap" — the reconciled build order the mapping tables target
- `.planning/research/PITFALLS.md` — CUT-*, REPLAY-1 and MIG-1 pitfalls that Track A's goldens and ledger exist to prevent

### Precedents in this repo
- `tests/eval/geo/` — golden fixture set with a generation log and scrubbed items; the pattern for Track A fixtures
- `src/career_os/_alembic/versions/` revision `d2e5a7f1b9c3` — the row-scoped `DELETE FROM integration_configs WHERE name = ...` precedent that MAP-05 protects
- `src/career_os/ai/factory.py` (`_read_credential_from_db`) — the silent-fail credential read
- `docs/coe/2026-07-09_initial-commit-pii-exposure.md` — why the privacy boundary is file-placement first, scan second

### Private side
- `private/retrospective/README.md` (gitignored) — private paths for Track B; never copy into committed files

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/eval/geo/` fixtures, `GENERATION_LOG.md` and differential gate: the shape for goldens with provenance
- `tests/test_no_import_masking_skips.py`: AST-guard style for a test that keeps a ledger honest
- `tools/check_review_trailers.py` and the PII scan workflow: the second net for Track B's verdict list

### Established Patterns
- Alembic revisions are forward-only and byte-identical once merged; CI round-trips upgrade/downgrade
- `integration_configs` is one shared table for ticktick, calendar, pushover, voice and `ai_providers`

### Integration Points
- Track A writes only under `tests/`, `docs/` and `.planning/phases/11-map/`
- Track B writes only inside the private pipeline's repository; its anonymised verdict list lands in `.planning/phases/11-map/`

</code_context>

<deferred>
## Deferred Ideas

- The `notify()` seam and any Pushover work: Retire, after everything else is verified
- Moving AI credentials out of `integration_configs`: Connect
- Source cuts (WARN, board scrapers): Find, on Map's counts
- Calendar sinks (Apple Calendar/Reminders default on a Mac, agent MCP recipes): Track

</deferred>

---

*Phase: 11-map*
*Context gathered: 2026-10-26*
