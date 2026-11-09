# Golden outputs (MAP-02)

These files freeze what today's deterministic scripts in `tools/` produce, with
provenance, so that a later phase that ports a script can prove it reproduces
today's behaviour (PITFALLS REPLAY-1). They are the regression net for the
Find, Filter, Scan, Score and Retire phases of v2.0.

`tests/replay/test_golden.py` replays every golden on each CI run and checks
`MANIFEST.json`; `tests/replay/generate_golden.py` is the one-shot generator and
is never run by CI.

## What a golden is (decision A1 of Phase 11, reading D-07)

D-07 says goldens come from recorded outputs, never from re-running the
pipeline. Kestrel holds no recorded live outputs: the one tracked
`tracking/scraped_scored_*.json` is a one-row placeholder and the daily scan
workflow has no successful run. So a Family A golden is made by calling the
current deterministic `tools/` function, in-process, over **synthetic inputs**
(D-03), at a pinned producer blob. That is a pure function replay: no scan, no
network request, no database read, no LLM call, no money spent.

A golden line is one JSON object with exactly `id`, `input` and `output`. Each
class lives in `{class}.jsonl` and is listed in `MANIFEST.json`.

## Synthetic input rules (D-03)

- Fictional companies and people only; generic job titles.
- URLs only on `example.com` or `.invalid` hosts, with no query string.
- Any date uses the year 2000.
- Nothing is copied or paraphrased from `tests/fixtures` recorded payloads,
  `tracking/`, `data/`, gitignored `config/*.yaml` or the private pipeline.
- Every file passes `scrub_patterns()` from `tests/eval/geo/replay.py`; the test
  rescans every file under this folder on each run.

The private side is only ever called "the private pipeline" (D-05). The 277-item
geo set stays at `tests/eval/geo` and is referenced, not copied.

## Determinism pins

Importing a `tools/` module can read the maintainer's gitignored config. CI holds
only the example config, so any local-config leak into an output would turn CI
red. `pinned()` in `_support.py` therefore fixes every machine-dependent input
while a producer runs, and each class records what it pinned in the MANIFEST
`pins` list: the geo config (`batch_probe._CONFIG`), the environment
(`GITHUB_STEP_SUMMARY` and `PIPELINE_*`), and, for the classes that need them, the
blocklist floor, the clock and the transport. The replay passes under
`PYTHONHASHSEED=0` and `PYTHONHASHSEED=4242`, which is the order-independence
proof when the Python minor version differs from CI's.

## Provenance and the hash recipe

Each class entry records the golden file and its sha256, every producer path with
its git blob (`git hash-object <path>` at generation), `producer_commit`, the
Python version, `generated` (month only), `inputs` and `pins`. The blob works in
CI's shallow checkout; `producer_commit` is recorded but never checked in CI.
The test fails when a golden byte changes or when a producer file changes.

## Regeneration rule (OQ-6)

Goldens are append-only by default. Changing a producer under `tools/` makes the
replay fail on purpose: regenerate with
`python tests/replay/generate_golden.py --class NAME`, and say in the PR which
producer changed and why the new output is right. A regeneration with any PII
hit, schema error or duplicate writes nothing.

## Encoding

Goldens are JSON Lines: sorted keys, compact separators, UTF-8, LF endings and
one trailing newline with no trailing spaces, so the rewriting pre-commit hooks
(end-of-file-fixer, trailing-whitespace, mixed-line-ending) never change a
golden's bytes. A digest or any other Markdown output is stored as a JSON string,
never as a Markdown file.

## Two golden families

`MANIFEST.json` holds two families of golden behind one schema.

**Family A** is the synthetic replay above: Kestrel's own `tools/` functions at
pinned blobs, recomputed on every CI run. Together with the mapping tables of
plan 11-02 (synthetic profiles only) it is the **generic target**: what any job
seeker's pipeline should reproduce (D-13).

**Family B** is one scrubbed, **output-only** sample per output class of the
maintainer's real recorded runs in the private pipeline: `private_scan_arrivals`,
`private_dedup_verdicts`, `private_eligibility_verdicts`, `private_scoring` and
`private_digest`. Those runs used the maintainer's own dossier, so every Family B
golden is **profile-specific by construction**: each record and each MANIFEST
entry says `profile_scope: "maintainer"` (D-13), and the files are the
maintainer-profile acceptance target, never the generic one. Plan 11-04 drafts
them privately, plan 11-05 crosses them, and until then each class is registered
as `awaiting_private_run` with `golden` null. The gate verdicts (`gate_verdicts`)
cross the same way, over the synthetic `gate_drafts.jsonl` and
`gate_fact_sheet.json` that Kestrel authored here.

Kestrel checks Family B by schema, invariants, sha256 and PII only
(`private_golden_problems`) and never recomputes it: there is no HARNESS entry.
**Any replay of a port against Family B runs only inside the private pipeline's
repository, with the private dossier.** v2.1 onboards other people's profiles
against the generic target, never against Family B.

### Replay modes

Each Family B MANIFEST entry carries the class's `replay` mode: what a later port
is held to when replayed against the unscrubbed private copy.

| Mode | Classes | Why |
|------|---------|-----|
| `exact` | `private_dedup_verdicts`, `private_eligibility_verdicts` | rules made every output field from the recorded input and the private config, so a port must reproduce every output field |
| `shape` | `private_scan_arrivals` | a posting is what the source returned at scan time and that response was not recorded, so no port can reproduce a row; the sample fixes the field set, the value shapes and the spread across sources |
| `reference` | `private_scoring`, `private_digest` | a model call made `fit_score`, and `tier`, digest membership and digest order follow from it, so no test and no port phase may assert equality against these two samples; the Score phase sets the comparison rule before it uses them |

### What never crosses, in substance as well as in form

- The dossier, profile and config that produced the runs. Records are
  output-only (`input` holds only the posting fields the output carried) and an
  unknown key is a validator error, so no dossier or profile field can slip in.
- The home region. Every location the private geo config counts as home appears
  only as a `Home-NN` token, and the validator requires that shape on every
  record of a home-family class: any `geo_class` that contains `home` in any
  letter case, so the producer's `home_local` and `home_relocate` as well as a
  plain `home`, read from the eligibility output or the scoring input. On such
  a record `location` and every `offices` element must be a `Home-NN` token. A
  `geo_class` that is not a string is held to the same rule; a record that
  carries no `geo_class` states no verdict and is outside it.
- Employer list membership. A record decided by the private dream-tier, block or
  soft-flag lists stays private; the validator rejects any exported `dream_tier`,
  `blocked`, `soft_flag` or `floored` that is true and any reason code naming
  those decisions.
- Joinability. Identity tokens (`Company-NN`, `Person-NN`, `Email-NN`, `Req-NN`,
  `Home-NN`, the `https://example.invalid/{token}` URLs) are assigned per class,
  so no two files can be joined on a token.

So neither the home region nor any employer's list membership can be read from a
committed Family B file.

### Family B record contract

- **File.** `{class}.jsonl`, between the class minimum (20 rows, `private_digest`
  3) and 200 rows, sorted by `id`, each line the canonical encoding.
- **Envelope (every line).** Exactly `id` (`^[a-z0-9-]{3,40}$`, unique), `month`
  (`YYYY-MM`), `scrubbed` (JSON true), `profile_scope` ("maintainer"), `input`,
  `output`. No two rows carry the same `input` and `output`.
- **Posting object** (the `ScrapedJob` / `Tier0Job` field set). Required `title`,
  `company` (`Company-NN`), `location`, `url` (`https://example.invalid/...`),
  `source`, `remote`; optional `salary`, `posted` (month or empty), `age_days`,
  `offices`, `remote_policy`, `tags`, `search_keyword`, `job_id` (`Req-NN`),
  `recruiter` and `contact` (`Person-NN`), `email` (`Email-NN`), `description`
  (empty only), `dream_tier`, `blocked`, `soft_flag` (false only),
  `api_submittable`, `ats_family`.
- **Per class.** `private_scan_arrivals`: input `source` (and `search_keyword`),
  output one posting. `private_dedup_verdicts`: input `a` and `b` postings, output
  `duplicate` (and `kept`, `fuzzy_ratio`, `reason_code`). `private_eligibility_verdicts`:
  input a posting, output `geo_class` (and `prefilter_skip`, `score_cap`, `blocked`,
  `soft_flag`, `reason_code`). `private_scoring`: input a posting (and `geo_class`),
  output `fit_score` (and `tier`, `review_flag`, `floored`, `estimated_salary`,
  `effort_flag`, `prep_level`, `scorer`, `reason_code`). `private_digest`: one line
  per digest run, input `config` and `counts`, output structured `rows` and a null
  `footer`; never the digest's Markdown.
- **Invariants.** No key outside the class's set; any date field is month-level;
  no day-level date, no `@`, no URL other than the synthetic shape, no PII scan
  hit; every `reason_code` is a generic snake_case code.
- **Coverage.** At least two months in every class; both `duplicate` values in
  `private_dedup_verdicts`; two `geo_class` values in `private_eligibility_verdicts`;
  two `tier` values (null counts) in `private_scoring`.
- **Problems.** The validators run over a file before it has crossed, and what
  they print reaches terminals, transcripts and CI logs. A problem therefore
  names a line number and a rule and never repeats a value read from the file:
  not a cell, not a key and not the row id. An unknown key is counted, not named.

### Provenance of Family B

The producer is "the private pipeline" at the commit of the producing script
(MAP-02's "git hash of the script revision that produced it"). `producer_row`
names the anonymous `P-NN` row of `tests/ports/PORT_LEDGER_PRIVATE.yaml` for that
script. Registration is `python tests/replay/generate_golden.py --register-private
CLASS --file PATH --private-commit SHA --producer-row P-NN`, which validates the
file and records its sha256; an omitted class stays awaiting.
