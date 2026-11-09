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
