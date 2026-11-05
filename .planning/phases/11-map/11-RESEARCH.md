# Phase 11: Map - Research

**Researched:** 2026-11
**Domain:** Evidence-freezing for a milestone (script ledger, golden fixtures with provenance, strict-xfail mapping tests, aggregate counts, anonymised verdict list). Pure repo, test and docs work. No production code changes, no paid LLM calls, no scan runs.
**Confidence:** HIGH for repo facts and pytest mechanics (opened or ran them this session); MEDIUM for where real recorded outputs can come from (it turns out none exist in this repo); LOW for anything about the private pipeline (Track A did not and must not read it).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Privacy boundary (binding for every plan and agent in this phase)
- **D-01:** The raw retrospective (session transcripts, application rows, company names, person names, dates, stall and recovery narrative, moods, cost lines) is written ONLY inside the private pipeline's repository, as a session doc. Nothing of it is written under Kestrel's `.planning/`, `docs/` or `tests/`.
- **D-02:** What enters Kestrel from Track B is one anonymised verdict list per flow and per feature: kept / trimmed / parked / cut, with counts and reasons. No company names, no person names, no dates finer than a month, no quotes from transcripts. The CI PII scan is the second net, not the first.
- **D-03:** Track A fixtures are synthetic or scrubbed. Scrubbing replaces identity fields (company, URLs, recruiter and person names, emails, requisition IDs) with synthetic values and keeps the fields a verdict depends on (location text, title, remote policy, salary band, posting age) so the golden still exercises the same branch.
- **D-04:** Track A agents never read `private/`, `.env`, or Claude Code transcript directories. Track B agents may read transcripts and private data; they write only inside the private repository. The private paths live in the gitignored `private/retrospective/README.md`, never in a committed file.
- **D-05:** Committed files refer to the private side as "the private pipeline" or "the private pipeline's repository", never by name or path.

#### Track A: what to freeze
- **D-06:** The script ledger covers every script in Kestrel `tools/` and every private-pipeline script that v2.0 ports, one row each: status (scheduled / by hand / dead), inputs, outputs, disposition (port / keep until Retire / delete). It is the seed of Retire's `PORT_LEDGER`; Retire's test that keeps the ledger honest is designed here.
- **D-07:** Goldens come from recorded outputs already on disk (scan outputs, digests, verdict logs), never from re-running the pipeline. Each golden records the git hash of the script revision that produced it.
- **D-08:** Mapping tables for later phases (Find, Filter, Scan, Score, Track, Write, Connect, Apply) are encoded as tests marked `xfail(strict=True, reason="v2.0 Phase <N>")`, collected by CI today. A phase turns them green by removing the marker; a strict xfail that passes early fails CI, so the ledger of pending behaviour stays honest.
- **D-09:** Per-source arrival counts are aggregates by month: arrived, survived prefilter, scored, shortlisted, applied. They are committed so Find decides source ports and cuts on evidence (the maintainer's rule: all sources are ported and judged on evidence, none cut up front).
- **D-10:** The protective golden for MAP-05 seeds an `ai_providers` row in `integration_configs`, runs `alembic upgrade head`, and reads the key back through the factory path (`career_os.ai.factory._read_credential_from_db`). It exists because Cut A deletes rows from that table by name and the factory's read is a silent `except Exception: return ""` today.

#### Track B: the flow retrospective
- **D-11:** The unit of analysis is the FLOW, not the artefact: what it produces, how often it ran, where it stalled, where the maintainer pushed through, his energy on it (up or down), what it cost. Window: June to October 2026. Evidence from this machine only: the private repository's git history and session handoffs, its application tracker and outcome records, its logs and data folders, Claude Code session transcripts for that repository, Linear tickets, screenpipe activity where useful.
- **D-12:** Verdict per flow and per feature: KEEP (efficient, productive) / SCOPE-AND-PLAN (under-realised but wanted) / PARK (with a product-map entry) / REMOVE (exists for the sake of existing). Under-use alone is never a reason to remove.
- **D-13:** Every verdict carries two tags: profile-specific vs generic (the maintainer's own TPM/product profile vs any job seeker), and a "works for a non-technical profile" column, because v2.0 carries a per-profile constraint and v2.1 onboards other people's profiles.
- **D-14:** The verdict list is the input the maintainer reviews before Cut A is planned. Cuts are his decision; Map only supplies the evidence.

### Claude's Discretion
- File layout for ledger, goldens, counts and xfail tests under `tests/` and `docs/` (follow `tests/eval/geo/` as the golden precedent).
- How transcripts are parsed and summarised for Track B, as long as D-01..D-05 hold.
- Whether Track A and Track B run as parallel plans (they share no files, so they should).

### Deferred Ideas (OUT OF SCOPE)
- The `notify()` seam and any Pushover work: Retire, after everything else is verified
- Moving AI credentials out of `integration_configs`: Connect
- Source cuts (WARN, board scrapers): Find, on Map's counts
- Calendar sinks (Apple Calendar/Reminders default on a Mac, agent MCP recipes): Track
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MAP-01 | Script ledger for every `tools/` script and every ported private-pipeline script | Full `tools/` inventory below (68 tracked files, 48 outside `tools/tests/`), run-status evidence, honesty-test design |
| MAP-02 | Goldens for scan arrivals, dedup, eligibility, scoring, digest, fact and voice gate verdicts, each with producing git hash, PII scan green | Golden class table, producer hazards, manifest design, finding that no recorded live outputs exist in this repo |
| MAP-03 | Mapping tables as strict-xfail tests CI collects | Verified xfail mechanics, layout `tests/targets/`, inventory meta-test, per-phase table sources |
| MAP-04 | Per-source arrival counts as aggregates | Schema gap analysis (what the DB does and does not persist), aggregate CSV contract |
| MAP-05 | Protective `ai_providers` golden | Prototype run end to end this session, fixture-override gotcha, regression assertion |
| MAP-06 | Retrospective session doc in the private pipeline's repository only | Track B, boundary rules, a Kestrel-side "nothing leaked" test |
| MAP-07 | Verdict (keep / scope-and-plan / park / remove) plus two tags per flow and feature | Verdict-list schema and stable IDs; vocabulary inconsistency flagged |
| MAP-08 | Anonymised verdict list only in `.planning/`, PII scan passes | PII gate mechanics, what a committed file must avoid |
| MAP-09 | Cut A and Retire cut lists cite a verdict for every item | Citation-checker design; the cut lists do not exist until Phases 13 and 22 (open question) |
</phase_requirements>

## Summary

Map is a test-and-docs phase whose value is that later phases cannot quietly lose behaviour. Everything Track A needs already has a precedent in the repo: `tests/eval/geo/` (frozen reference + replay helper + one-shot generator + provenance log + live PII scan over the fixture), `tests/test_no_import_masking_skips.py` (filesystem-derived AST guard with guard-the-guard self-tests), and `tests/test_migrations_packaging.py` (programmatic `alembic upgrade head` on a temp SQLite file). No new package is needed. The recommended layout is two new test packages, `tests/ports/` (ledger, goldens, MAP-05, counts schema, verdict-list schema) and `tests/targets/` (strict-xfail mapping tables), both under `tests/` so the CI backend step `pytest tests/ -v --tb=short -m "not eval"` collects them today.

Four findings change the plan versus what CONTEXT.md assumes. (1) **There are no recorded live outputs in this repo to scrub.** The only tracked `tracking/scraped_scored_*.json` is a one-row placeholder, the gitignored local ones are one-row test leftovers, and `daily-scan.yml` has never produced a successful run (154 listed runs: 89 scheduled skipped, 62 scheduled failures, 3 dispatch failures, 0 successes). D-07 therefore cannot be satisfied from Kestrel-side recorded outputs; the realistic goldens are (a) deterministic in-repo functions replayed over synthetic or already-scrubbed inputs at a pinned script hash, (b) the existing scrubbed sets (geo 277, scoring golden sets), and (c) verdicts of private-only gates (fact, voice) produced privately over inputs authored in Kestrel. This needs a maintainer confirmation (Open Question 1). (2) **The Kestrel database cannot produce MAP-04's funnel by itself**: prefilter drops jobs before they are persisted, per-source arrival counts are not stored, and `discovery_runs` keeps only per-run totals. The aggregate has to come from the private pipeline's per-day raw and scored files, as a Track B task that writes only aggregates. (3) **ARCHITECTURE.md section 10's proposed dispositions conflict with later maintainer decisions** (sources are all ported; writing and prefill tools are core; APPLY-02 keeps auto-submit scripts), so the ledger must follow REQUIREMENTS.md, not that table. (4) **The `Review trailers` CI job would fail a PR that carries the milestone branch's history**: 14 of the 19 commits on `G-2013/v2-lean-milestone` carry no `Reviewed-by` trailer, so `G-2039/map` must be cut from `main`, and the milestone's `.planning/` docs need their own route to main.

**Primary recommendation:** Build Track A as `tests/ports/` plus `tests/targets/` using the geo precedent verbatim (JSON fixtures + manifest with sha256 and `git hash-object` blob + live `scrub_patterns()` scan), register one marker (`v2_pending`) in `pyproject.toml`, mark every mapping test `xfail(strict=True, raises=NotBuilt, reason="v2.0 Phase N")`, and guard both the ledger and the xfail inventory with filesystem-derived tests that carry their own guard-the-guard cases. Route MAP-04 and the private-script ledger rows to Track B, which writes only anonymised aggregates.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Script ledger and its honesty test | Test suite (`tests/ports/`) | Repo docs | Must survive deletion of `tools/` in Retire, so it cannot live under `tools/`; a test keeps it honest in CI |
| Golden fixtures and provenance manifest | Test suite (`tests/ports/golden/`) | Git (blob hash is the provenance) | Frozen data plus replay tests; `git hash-object` works in shallow CI clones, `git log` does not |
| Replay of old script against golden | Test suite | `tools/` modules (oracle) | The oracle is the old script until Retire converts the test to golden-only |
| Strict-xfail mapping tables | Test suite (`tests/targets/`) | pyproject marker registry | CI collects `tests/` today; tables are data (YAML) so the maintainer can review input-to-output rows |
| MAP-05 protective golden | Test suite | Alembic + SQLite temp file | Exercises migration chain plus the factory's raw-sqlite credential read, no API server |
| Per-source arrival aggregates | Private pipeline (Track B) | Kestrel `docs/` (committed CSV only) | Raw per-day files and logs live privately; Kestrel DB lacks pre-prefilter counts |
| Flow retrospective | Private pipeline's repository | none | Raw evidence never enters Kestrel (D-01) |
| Anonymised verdict list | Kestrel `.planning/phases/11-map/` | CI PII scan (second net) | The only Track B artefact allowed in; stable IDs let Cut A and Retire cite it |
| PII and secret scanning | CI (`PII leak check` step, gitleaks) | Local pre-commit gitleaks | File placement first, scan second (COE 2026-07-09) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | local 9.0.3; CI installs `pytest>=8.3.0` | Test runner, strict xfail, junit/collect-only inventory | Already the suite's runner. [VERIFIED: `.venv/bin/python -m pytest --version` printed `pytest 9.0.3`; pyproject `"pytest>=8.3.0"`] |
| alembic | `>=1.15.0` (pyproject) | Programmatic `command.upgrade(cfg, "head")` for MAP-05 | Precedent in `tests/test_migrations_packaging.py` |
| PyYAML | 6.0.3 local, transitive | Ledger and mapping-table data files, `yaml.safe_load` | `uvicorn[standard]` requires it. [VERIFIED: `importlib.metadata.requires('uvicorn')` printed `pyyaml>=5.1; extra == 'standard'`]; it is NOT declared directly in pyproject (STACK.md already flags this) |
| hypothesis | 6.165.1 local, `hypothesis>=6.100` in `dev` | Optional property inputs for pure-function goldens | Already a dev dependency; geo tests use it |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx.MockTransport` | httpx `>=0.28.0` | Feed recorded ATS payloads to `tier0_ats_poller.fetch_*` (they take `client=`) | Scan-arrivals golden |
| `tests/eval/geo/replay.py::scrub_patterns` | in repo | The PII/tracking pattern set; reuse over every new fixture | Every golden integrity test |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| YAML ledger | JSON or markdown table | JSON has no comments (the ledger needs reasons); markdown needs a hand parser. YAML is fine because the CI tools tests already import `yaml` |
| `xfail_strict = true` in ini | explicit `strict=True` per marker | Explicit is what D-08 asks for and is checkable by AST; the ini key is a cheap extra net (no existing xfail in `tests/` or `tools/tests/` [VERIFIED: grep for `xfail` over both returned nothing]) |

**Installation:** none. No new package is recommended.

**Version verification:** no package is added or bumped, so there is no registry lookup to record.

## Package Legitimacy Audit

No external packages are recommended for installation in this phase. Audit table not applicable.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                      TRACK A (Kestrel, public)                         TRACK B (private pipeline's repo)
                      ------------------------                         --------------------------------
 tools/*  ---------> ledger rows --------------> tests/ports/PORT_LEDGER.yaml
 (48 files + 20 tests)        ^                         |
                              |                         v
 daily-scan.yml, automation/  +--- scheduler glue   test_script_ledger.py  (fs-derived, guard-the-guard)

 synthetic / already-scrubbed inputs
        |                                  private gate scripts (fact, voice)   raw per-day scan files, logs, tracker
        v                                         ^ run over Kestrel-authored            |
 old script @ pinned blob hash  --replay-->  tests/ports/golden/<class>/*.jsonl           |  aggregate only
        |                                         |   + MANIFEST.json (sha256, blob, commit, env)
        |                                         v                                       v
        +-----------------------------> test_golden_*.py (oracle == golden)      arrival-counts.csv (counts, no rows)
                                                  |                                       |
 research/SUMMARY.md, FEATURES.md                 v                                       v
 (target behaviours) --> tests/targets/tables/*.yaml -> test_phase_NN_*.py          verdict list (anonymised, stable IDs)
                         strict xfail, raises=NotBuilt, reason "v2.0 Phase N"       --> .planning/phases/11-map/
                                  |                                                         |
 alembic chain (37 revisions) --> test_ai_providers_golden.py (MAP-05)                     v
                                                                                   Cut A / Retire cut lists cite IDs
                                  CI: pytest tests/ -m "not eval"  +  PII leak check (git grep)  +  gitleaks
```

### Recommended Project Structure
```
tests/ports/
├── __init__.py
├── PORT_LEDGER.yaml              # MAP-01: one row per tools/ file/dir + scheduler glue + anonymised private rows
├── test_script_ledger.py         # MAP-01 honesty test (AST/fs-derived style) + guard-the-guard cases
├── golden/
│   ├── README.md                 # contract: D-03 scrub, D-07 sources, regeneration rule, hash recipe
│   ├── MANIFEST.json             # per golden file: sha256, producer path, git blob, commit, python, hashseed
│   ├── scan_arrivals/*.json(l)
│   ├── dedup_verdicts/*.jsonl
│   ├── eligibility_verdicts/*.jsonl   # geo 277 stays at tests/eval/geo; add prefilter/blocklist/tier cases here
│   ├── scoring/*.jsonl                # deterministic parts only (floors, tiers, keyword scorer, caps)
│   ├── digest/*.md + inputs.json
│   └── gate_verdicts/*.jsonl          # fact and voice, produced privately over Kestrel-authored drafts
├── generate_golden.py            # one-shot, NOT run by CI (geo `generate_reference.py` pattern)
├── test_golden_manifest.py       # sha256 integrity, provenance format, live scrub_patterns() scan
├── test_golden_<class>.py        # replay: old script at current blob == golden
├── test_ai_providers_golden.py   # MAP-05
├── test_arrival_counts.py        # MAP-04 schema gate (no job-level rows)
└── test_verdict_list.py          # MAP-07/08/09 schema, vocabulary, forbidden-pattern gate
tests/targets/
├── __init__.py
├── _support.py                   # NotBuilt, load_target(), load_table()
├── tables/phase_14_find.yaml ... phase_21_apply.yaml
├── test_phase_14_find.py ... test_phase_21_apply.py
└── test_target_inventory.py      # AST: every mapping test is strict-xfail with raises + reason regex; counts per phase
docs/research/ or .planning/phases/11-map/
├── arrival-counts.csv            # MAP-04 aggregate
└── verdicts.md                   # MAP-07/08 anonymised list
```
Placement rule: no `eval` marker, no files outside `tests/`, `docs/`, `.planning/phases/11-map/` (CONTEXT "Integration Points"). The `eval` marker is excluded by `-m "not eval"` in the fast run, which is why the geo gate needed its own CI step; new goldens must not copy that marker. [VERIFIED: `.github/workflows/ci.yml:65-77`: `pytest tests/ -v --tb=short -m "not eval" --cov=...` and the separate `pytest tests/eval/geo` step]

### Pattern 1: Strict xfail mapping table (MAP-03)
**What:** Each target behaviour is a YAML table of input to expected-output rows. One parametrized test per table, one test item per row, whole test marked strict xfail pinned to a custom "not built" exception.
**When to use:** every behaviour in Find, Filter, Scan, Score, Track, Write, Connect, Apply.
**Verified mechanics** (ran a five-test file in the scratchpad with pytest 9.0.3):
- red as intended: `XFAIL (v2.0 Phase 14)` in `-v` output; junit `<skipped type="pytest.xfail" message="v2.0 Phase 14" />`
- passes early with `strict=True`: reported `FAILED ... [XPASS(strict)] v2.0 Phase 15`, run exits non-zero
- raises a different exception than `raises=`: reported `FAILED` with the real traceback (so a typo in a table cannot hide as "pending")
- without `raises=`, an `ImportError` inside the test body counts as an expected failure, so a typo'd import masquerades as pending; hence `raises=` is mandatory
- a module-level import of a not-yet-existing module is a collection ERROR, not an xfail; import targets lazily inside the test via `load_target()`
```python
# tests/targets/_support.py  (illustrative; verified shape, not committed yet)
import importlib
from pathlib import Path
import yaml

class NotBuilt(Exception):
    """The target module or attribute does not exist yet."""

def load_target(module: str, attr: str):
    try:
        return getattr(importlib.import_module(module), attr)
    except (ImportError, AttributeError) as exc:
        raise NotBuilt(f"{module}.{attr} not built yet") from exc

def load_table(name: str) -> list[dict]:
    path = Path(__file__).parent / "tables" / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["rows"]
```
```python
# tests/targets/test_phase_15_filter.py
import pytest
from tests.targets._support import NotBuilt, load_table, load_target

ROWS = load_table("phase_15_filter")          # data loads at import: a bad table is a collection ERROR, on purpose

@pytest.mark.v2_pending
@pytest.mark.xfail(strict=True, raises=NotBuilt, reason="v2.0 Phase 15")
@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
def test_assess_decision_table(row):
    """assess() returns the documented decision and ordered reason codes for each input."""
    assess = load_target("career_os.services.assess", "assess")
    result = assess(row["input"])
    assert result.decision == row["expect"]["decision"]
    assert list(result.reason_codes) == row["expect"]["reason_codes"]
```
Keep two or more `assert` statements per test function: the Claude Stop hook `.claude/hooks/check-test-assertions.py` rejects a staged `tests/` file whose `test_` function has fewer than 2 `Assert` nodes, and `docs/reference/TESTING.md` RULE-01 says the same. [VERIFIED: hook source lines 1-12 and 38-52, TESTING.md RULE-01]

Counting without special tooling: register `v2_pending` in `[tool.pytest.ini_options] markers` (edit `pyproject.toml:132-138`; it is outside `src/` and `frontend/src/`, so the read-only gate `git diff main --stat -- src/ frontend/src/` stays empty). Then `pytest tests/targets --collect-only -q -m v2_pending | tail -1` prints the count, and `-v` output greps as `XFAIL`. `--collect-only -q` alone lists node ids only; it does not show marks. [VERIFIED by running it]

### Pattern 2: Provenance manifest for goldens (MAP-02)
**What:** one `MANIFEST.json` with an entry per golden file, checked by a test on every CI run.
```json
{
  "schema": 1,
  "files": {
    "dedup_verdicts/job_key_cases.jsonl": {
      "sha256": "<of the committed bytes>",
      "producer": "tools/normalize.py",
      "producer_blob": "<git hash-object tools/normalize.py at generation>",
      "producer_commit": "<git rev-parse HEAD at generation>",
      "inputs": "synthetic",
      "generated": "2026-11",
      "python": "3.14.10",
      "pythonhashseed": "0"
    }
  }
}
```
Hash recipe, checked this session: `git hash-object tools/normalize.py` returned `b92a08e9c3ca6175b41981aa22c9d8ef80d1f381`, identical to `git rev-parse HEAD:tools/normalize.py`; `git log -1 --format=%H -- tools/normalize.py` returned `38049007a7e48c358ab6d5c30600c55149b21b59`. Record both. Test only the **blob** in CI: `actions/checkout` is shallow by default in the backend job (`ci.yml:20` has no `fetch-depth`), so `git log` and `git cat-file -e <old commit>` are unreliable there, while `git hash-object` needs no history. [VERIFIED: ci.yml lines 17-24 show a bare `actions/checkout` step]
Tests: (a) sha256 of each file equals the manifest (append-only rule, REPLAY-1 item 6); (b) `producer_blob` and `producer_commit` are well-formed 40-hex; (c) replay: current script over the golden inputs equals golden outputs; (d) decision for planner: also assert `git hash-object <producer>` equals `producer_blob` and fail with a "regenerate with review" message when a script is edited. That makes a legitimate edit of an old script a deliberate act, which matches "old scripts stay until Retire" but will fire on harmless fixes; recommend (d) as a warning-level assertion only if the maintainer wants that friction (Open Question 6).
Use month granularity for `generated` (the verdict-list rule is "no dates finer than a month"; the geo log's full timestamp is the precedent but is not required).

### Pattern 3: Ledger honesty test (MAP-01, D-06)
Style of `tests/test_no_import_masking_skips.py`: derive the swept set from the filesystem, never from a hand-written list, and prove the detector with fixture cases.
- `TOOLS_FILES = sorted(p for p in (REPO/"tools").rglob("*") if p.is_file() and "__pycache__" not in p.parts)` (that test uses `rglob` and excludes `__pycache__` the same way; `tools/__pycache__` exists locally and is untracked).
- Ledger rows are either exact file paths, a directory (`tools/kestrel-mcp/`), or a glob (`tools/tests/*.py`); every file must match exactly one row; every non-private row must match at least one file.
- Enumerations validated: `run_status in {scheduled, by_hand, dead}` (D-06 vocabulary; mark CI-run scripts `scheduled` with `trigger: ci`), `disposition in {port, keep_until_retire, delete}`, `dead` rows carry a `reason`, `port` rows carry `target` (may be `TBD:<phase>`).
- Guard-the-guard: assert the ledger is non-empty, assert known anchors are present (`tools/daily_pipeline.py`, `tools/normalize.py`, `tools/check_review_trailers.py`), and run the detector over an in-memory file list with one row removed and with one phantom row added, asserting both are flagged. Copy the `_FLAG_CASES` / `test_sweep_covers_both_roots_and_subpackages` idea.
- Keep a separate Retire-owned field set (`port_status: pending`, `proof`, `golden`, `verified_at`) out of Map: Map seeds `run_status` and `disposition` only; Retire adds the lifecycle. ARCHITECTURE.md section 10 sketches `tools/PORT_LEDGER.yaml`; place it at `tests/ports/PORT_LEDGER.yaml` instead because Retire deletes `tools/`. [CITED: .planning/research/ARCHITECTURE.md:472-486]
- FOUND-01 (Phase 12) moves `check_review_trailers.py` out of `tools/`; that PR must update the ledger row and the honesty test. Record `relocate: Phase 12` on that row.

### Pattern 4: MAP-05 protective golden
Prototype run end to end in the scratchpad (not committed): `command.upgrade(cfg, "f7a8b9c0d1e2")`, raw `INSERT` of an `ai_providers` row, `command.upgrade(cfg, "head")`, point `settings.database_url` at the temp file, then read the key back. Output observed: direct read returned the seeded value; `factory.get_ai_provider("openrouter")` built a provider whose `_api_key` equalled the seeded value; with a missing database file and with an empty database (no table) `_read_credential_from_db` returned `''` and the factory then raised `ValueError: OPENROUTER_API_KEY is required for OpenRouterProvider`, i.e. the silent swallow surfaces only as a misleading "key required" error.
```python
# tests/ports/test_ai_providers_golden.py  (shape verified by the prototype)
import json, sqlite3
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
import career_os
from career_os.ai import factory
from career_os.config import settings

REAL_READ = factory._read_credential_from_db      # captured at import, before the autouse fixture patches it
PKG = Path(career_os.__file__).resolve().parent
FAKE = "unit-test-not-a-real-key-0001"            # no provider key prefix, so gitleaks has nothing to match

def _cfg(url):
    cfg = Config()                                 # NOT the ini file: fileConfig() disables loggers (see test_migrations_packaging.py)
    cfg.set_main_option("script_location", str(PKG / "_alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg

def test_ai_providers_key_survives_upgrade_head(tmp_path, monkeypatch):
    """A seeded ai_providers row is readable through the factory after upgrade to head."""
    db = tmp_path / "map05.db"
    url = f"sqlite:///{db}"
    command.upgrade(_cfg(url), "f7a8b9c0d1e2")     # integration_configs exists from this revision
    with sqlite3.connect(db) as con:
        con.execute(
            "INSERT INTO integration_configs (name, display_name, enabled, credentials, status,"
            " created_at, updated_at) VALUES (?,?,?,?,?,datetime('now'),datetime('now'))",
            ("ai_providers", "AI Providers", 1, json.dumps({"openrouter_api_key": FAKE}), "connected"),
        )
    command.upgrade(_cfg(url), "head")
    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(factory, "_read_credential_from_db", REAL_READ)   # undo tests/conftest.py hermetic_db_credentials
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)               # env wins over DB in _resolve_api_key
    assert factory._read_credential_from_db("openrouter_api_key") == FAKE
    assert factory.get_ai_provider("openrouter")._api_key == FAKE         # value, not "no exception"
```
Facts this rests on, each opened this session:
- `factory._read_credential_from_db` (`src/career_os/ai/factory.py:32-61`) uses `settings.database_url`, returns `""` unless it starts with `sqlite`, runs `"SELECT credentials FROM integration_configs WHERE name = ?"` with `("ai_providers",)`, and wraps the connect/query in `except Exception:` `return ""`; the JSON blob is read with `creds.get(credential_key, "")`.
- `IntegrationConfig` (`src/career_os/models/integrations.py:29-45`): `__tablename__ = "integration_configs"`; NOT NULL columns `name`, `display_name`, `enabled`, `status`, `created_at`, `updated_at`; `credentials` nullable JSON text; `name` unique.
- Revision `f7a8b9c0d1e2` creates the table; `d2e5a7f1b9c3` is the precedent: its `upgrade()` ends with `op.execute("DELETE FROM integration_configs WHERE name = 'timingsapp'")` and its `downgrade()` recreates `time_sessions`. Alembic reports a single head `w5x6y7z8a9b0` and 37 revisions [VERIFIED: ran `ScriptDirectory.get_heads()`/`walk_revisions()`]. Seeding at an intermediate revision then upgrading is what exercises the forward migrations, which is the real Cut A risk.
- `tests/conftest.py:73-90` has an autouse fixture `hermetic_db_credentials` that replaces `career_os.ai.factory._read_credential_from_db` with a lambda returning `""`; the MAP-05 test must restore the real function (captured at module import) or it proves nothing. The conftest also sets `OPENROUTER_API_KEY=""` via `setdefault`, which is falsy, so the DB path is reached; delete the variable anyway.
- Seed with raw SQL or the ORM, not `services.integrations.update_integration`: that function auto-runs a connection test when credentials are set and the row is enabled (`services/integrations.py:178-181`).
Strengthen it (recommended): also seed `ticktick`, `calendar`, `pushover`, `voice` rows, assert all five survive `upgrade head` today, and record the expected survivor set in one constant that Cut A changes deliberately; assert the failure mode too (a row with `credentials = 'not json'` returns `""`) only if Foundation's FOUND-09 warning is expected to change it, otherwise leave that to Foundation. Regression assertion that catches a cut migration emptying credentials: `_read_credential_from_db("openrouter_api_key") == FAKE` after `upgrade head` (a deleted row or dropped table yields `""` and fails). Also assert the `integration_configs` row count for `ai_providers` is 1 so a vacuous pass on a missing seed cannot occur.

### Anti-Patterns to Avoid
- **Golden produced from the maintainer's machine config.** `tools/batch_probe.py` loads `_CONFIG` at import from `config/geo.yaml`, falling back to `config/geo.example.yaml`; `tools/blocklist.py` does the same for `config/blocklist.yaml`. A golden recorded on a machine with a real config differs from CI, which uses the example files. Pin by monkeypatching `batch_probe._CONFIG` (precedent: `tools/tests/test_geo_gate.py:49-51`) and rebuilding the blocklist regexes, and record that pin in the manifest. [VERIFIED: tools/batch_probe.py:257-288, tools/blocklist.py:58-100]
- **Digest golden that touches the real database or the real tracking dir.** `step_dedup_against_tracking` opens `SessionLocal()` (the local `data/career_os.db`) before falling back to a CSV; `step_generate_digest` writes `config.digest_path` and appends to `$GITHUB_STEP_SUMMARY` if set. Use a `PipelineConfig` with `tracking_dir`, `date`, `timestamp` overridden and the env var unset. [VERIFIED: tools/daily_pipeline.py:69-88, 469-540, 640-668]
- **Clock leakage.** `scrape_*` functions stamp `scraped_at` with `datetime.now()`; strip or freeze that field in scan-arrival goldens. [VERIFIED: grep of tools/scrape_resilient.py lines 124-786]
- **Treating an old script as the proof of itself after Retire.** The Map replay tests import `tools/` modules (conftest puts `tools/` on `sys.path`); that is correct for Map and is exactly the "shared code makes the test vacuous" trap for later ports (REPLAY-1 item 3). Keep golden DATA separate from the oracle test so Retire can drop the oracle and keep the data. [CITED: .planning/research/PITFALLS.md REPLAY-1]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PII/tracking pattern set for fixtures | a new regex list | `from tests.eval.geo.replay import scrub_patterns` | Merges `.github/pii-patterns.txt`, fragment-assembled personal identifiers, generic email, URL-with-query; raises if the gate file is missing; a second copy drifts |
| Migration run in a test | subprocess `alembic` or the repo ini | `Config()` + `set_main_option("script_location"/"sqlalchemy.url")` + `command.upgrade` | The ini path calls `fileConfig()`, which disables loggers and broke caplog tests (documented in `test_migrations_packaging.py`) |
| Filesystem-derived "no file without a row" guard | a hand-listed set of scripts | `rglob` minus `__pycache__` as in `test_no_import_masking_skips.py` | A hand list is the thing that goes stale |
| Pending-behaviour tracker | `pytest.skip`, comments, a TODO doc | `xfail(strict=True, raises=NotBuilt)` | Skips can hide; a strict xfail that starts passing fails CI |
| Script revision identity | commit timestamps or filenames | `git hash-object <file>` (blob) plus `git rev-parse HEAD` | Blob needs no history; works in shallow CI clones |
| Digest/PDF/markdown golden compare | fuzzy diff | exact byte compare of a stored file | The point of a golden is that any change is a decision |

**Key insight:** every mechanism this phase needs exists in the repo already; the risk is not building them but weakening them (vacuous gates, regenerated goldens, hand-listed sets).

## Runtime State Inventory

Not a rename or refactor phase. Omitted per template.

## Script Inventory (seed for MAP-01)

Counts: `git ls-files tools` returns 68 files [VERIFIED]: 38 top-level `*.py`, `tools/README.md`, two `spike_*_results.md`, 3 files in `tools/kestrel-mcp/`, 4 in `tools/sonarcloud-mcp/`, and 20 test files in `tools/tests/`. ARCHITECTURE.md's "45 entries" counts scripts and the two directories; the honesty test must account for all 68 (use one directory/glob row for `tools/tests/` and for each MCP directory).

**What runs on a schedule (evidence).** `.github/workflows/daily-scan.yml` is the only workflow that invokes `tools/` besides CI itself; it runs `tools/daily_pipeline.py`, `tools/update_sheet.py`, `tools/validate_sheet.py` (lines 135, 247, 249, 258). Its job is gated by `if: github.event_name == 'workflow_dispatch' || vars.DAILY_SCAN_ENABLED == 'true'`. Observed with `gh`: `gh variable list` returned no repository variables, and `gh run list --workflow daily-scan.yml --limit 200` returned 154 runs: 89 scheduled `skipped`, 62 scheduled `failure`, 3 `workflow_dispatch` `failure`, zero successes; the non-skipped runs fall in 2026-04 to 2026-07 only. So the schedule is declared but the Kestrel-side job has not produced an output in the visible history. Other scheduler glue lives outside `tools/`: `automation/cron_runner.sh`, `automation/com.kestrel.daily-scan.plist`, `automation/n8n_workflow.json` (all templates that call `tools/daily_pipeline.py`). On this machine `~/Library/LaunchAgents` holds one agent that belongs to the private pipeline; whether it calls any Kestrel `tools/` script is UNVERIFIED (not opened; Track B can answer). CI runs `pytest tools/tests/` and `python tools/check_review_trailers.py` (ci.yml lines 79-85 and 357).

Transitive import graph from the scheduled entry points (computed by AST over `tools/*.py`): `daily_pipeline` imports `job_scorer`, `normalize`, `scrape_resilient`; `scrape_resilient` imports `germany_jobs`, `scrape_new_sources`, `scraper`, `source_registry`; `job_scorer` and `normalize` import `batch_probe`. `tier0_ats_poller` has no importer among the tools.

Dispositions below are PROPOSED. They follow REQUIREMENTS.md decisions where those exist; ARCHITECTURE.md section 10's table predates them and conflicts in three places (flagged). The maintainer confirms; MAP-09's cut lists cite verdicts, not this column.

| File | Does | Run status (evidence) | Tests today (heuristic grep, verify by import) | Proposed disposition |
|------|------|----------------------|-------|-------------|
| `_filter_jobs.py` | Throwaway wrapper that shells out to `germany_jobs.py` with a hard-coded city | dead: no importer, no test, no doc [VERIFIED: read] | none | delete |
| `annotate.py` | Blind two-axis labelling of a label set | by hand | `tools/tests/test_annotate.py`, `test_label_pipeline_integration.py`, `test_calibrate.py` | port (audit) |
| `auto_apply.py` | API + Playwright auto-submit | by hand | `tests/test_auto_apply.py` | keep until Retire (REQUIREMENTS Future APPLY-02 says auto-submit scripts are kept, never deleted, never default) |
| `batch_apply_browser.py` | Playwright batch form filling | by hand | `tests/test_batch_apply_browser.py`, `test_batch_apply_overlay.py`, `test_batch_apply_browser_js_textarea.py` | keep until Retire (APPLY-02) |
| `batch_probe.py` | Legacy geo token classifier plus ATS office probing | scheduled (transitive, daily-scan) | `tools/tests/test_geo_gate.py`, `test_job_scorer_geo.py` | port |
| `blocklist.py` | Word-boundary company blocklist from `config/blocklist.yaml` | by hand (library) | `tools/tests/test_blocklist.py`, `test_t3_lane.py` | port |
| `build_label_set.py` | Stratified blind label-set builder | by hand | `tools/tests/test_build_label_set.py` | port |
| `calibrate.py` | Precision/recall report vs own labels | by hand | `tools/tests/test_calibrate.py` | port |
| `captcha_solver.py` | Paid anti-captcha hCaptcha solver | by hand | none | keep until Retire (APPLY-02) |
| `check_review_trailers.py` | CI patch-id trailer gate | scheduled with `trigger: ci` (ci.yml:357) | `tests/test_check_review_trailers.py` | keep; relocate in Phase 12 (FOUND-01) |
| `daily_pipeline.py` | scrape, score, dedup, filter, digest orchestrator | scheduled (daily-scan.yml; see evidence above), templates in `automation/` | `tests/test_daily_pipeline.py`, `tools/tests/test_daily_pipeline_port.py` | port, then retire |
| `generate_batch_covers.py` | Cover-letter markdown from templates and hooks | by hand | none | keep until Retire (writing tools are core per REQUIREMENTS Out of Scope) |
| `generate_batch_submit_yaml.py` | Batch submit YAML from hooks and DB URLs | by hand | none | keep until Retire (prefill core) |
| `germany_jobs.py` | Arbeitsagentur and Arbeitnow search | scheduled (transitive) | `tests/test_germany_jobs.py`, `test_new_sources.py`, `test_arbeitsagentur_live.py` | port (sources all ported, judged on MAP-04) |
| `job_scorer.py` | LLM scorer plus deterministic floors, tiers, ATS-host helpers | scheduled (transitive) | `tests/test_job_scorer.py`, `tools/tests/test_job_scorer_tiers.py`, `test_job_scorer_geo.py` | port the deterministic parts; LLM part superseded by `services/scoring.py` |
| `kit_builder.py` | T2 application-kit folders | by hand | `tools/tests/test_kit_builder.py` | keep until Retire |
| `local_scorer.py` | Deterministic keyword scorer | by hand | none found | delete candidate (superseded); confirm no hidden user |
| `md_to_pdf_cover_letter.py` | Markdown to PDF | by hand | `tests/test_md_to_pdf.py` | keep until Retire (writing core) |
| `normalize.py` | Company/title normalisation, `job_key`, fuzzy ratio | scheduled (transitive) | `tools/tests/test_normalize.py` | port |
| `open_question_probe.py` | Detects free-text questions on apply forms | by hand | `tools/tests/test_open_question_probe.py` | keep until Retire |
| `render_cover_letter_html.py` | Cover letter to PDF via Playwright | by hand | none | keep until Retire |
| `render_tailored_cvs.py` | Tailored CV PDFs via RenderCV | by hand | `tests/test_render_tailored_cvs.py` | keep until Retire |
| `research_jobs.py`, `research_remotely.py` | Platform research helpers, no docstring | by hand | `tests/test_html_stripping.py` (research_jobs only) | delete candidate; confirm |
| `scrape_form_questions.py` | Scrape ATS form fields | by hand | none | keep until Retire |
| `scrape_new_sources.py` | Himalayas, Greenhouse, Lever, Ashby, Workable, startup.jobs scrapers | scheduled (transitive) | `tests/test_new_sources.py`, `tools/tests/test_ats_scrapers.py`, `test_scrape_workable.py`, `test_dead_sources.py` | port |
| `scrape_remotely.py` | Persistent-browser scrape of remotely.de **and LinkedIn** | by hand | none | delete candidate. Note: lines 3, 10, 27-28, 161-179 drive a logged-in LinkedIn session, which contradicts `tools/README.md`'s statement that no tool here reads LinkedIn from an authenticated session. Ledger it with that reason |
| `scrape_resilient.py` | Rate-limited multi-source scraper | scheduled (transitive) | `tests/test_scrape_resilient.py`, `tools/tests/test_source_registry.py` | port |
| `scraper.py` | python-jobspy search | scheduled (transitive) | `tests/test_scraper.py` | port |
| `snapshot_db.py` | Atomic rotating SQLite snapshots | by hand (README "Ops"); whether the private pipeline's scheduler calls it is UNVERIFIED | `tests/test_snapshot_db.py` | keep until Retire |
| `source_registry.py` | Per-run source health, floors | scheduled (transitive) | `tests/test_source_registry.py`, `tools/tests/test_source_registry.py` | port |
| `specific_hunt.py` | Targeted jobspy searches | by hand | `tests/test_specific_hunt.py` | delete candidate; confirm |
| `spike_batch_quality.py`, `spike_prefilter.py` (+ two `*_results.md`) | Spikes; results are the record | dead (spikes) | `tests/test_batch_quality_spike.py`, `tools/tests/test_spike_prefilter.py` | delete after results move to `docs/research/` |
| `t3_lane.py` | Auto-fill, never submit | by hand | `tools/tests/test_t3_lane.py` | keep until Retire |
| `tier0_ats_poller.py` | Direct Greenhouse/Lever/Ashby polling | by hand (no importer, not in any workflow) | `tests/test_tier0_ats_poller.py`, `tools/tests/test_config_loaders.py` | port |
| `update_sheet.py`, `validate_sheet.py` | Google Sheet logging and validation | scheduled (daily-scan steps 247-258; need Google secrets) | none | delete candidate |
| `kestrel-mcp/` | MCP server wrapping the REST API | by hand | `tools/tests/test_kestrel_mcp.py` | port (Connect) |
| `sonarcloud-mcp/` | SonarCloud MCP for dev sessions | by hand | none found | keep until Retire, or delete; maintainer call |
| `README.md`, `spike_*_results.md`, `tools/tests/*` | docs and tests | n/a | n/a | one directory/glob row each |

Adjacent rows to add (they die with `tools/` in Retire): `.github/workflows/daily-scan.yml`, `automation/cron_runner.sh`, `automation/com.kestrel.daily-scan.plist`, `automation/n8n_workflow.json`. `scripts/` is outside D-06's scope.

**Private-pipeline rows.** Track A may not read the private repository (D-04) and committed files may not name it or its paths (D-05). Recommend the ledger carry those rows under anonymous IDs (`P-01`, `P-02`, ...) with a generic description, run status, anonymised inputs/outputs and disposition only, authored by a Track B agent. Do not put script names or paths in the ledger.

Conflicts to resolve in the ledger, with the winning source named in the row's `reason`:
| Topic | ARCHITECTURE.md section 10 says | Later decision says | Use |
|-------|----|----|----|
| Board scrapers (`scrape_*`, `germany_jobs`, `scraper`) | DROP unless on the productive list | REQUIREMENTS "Decisions carried": sources all ported, judged on MAP-04 counts | port |
| Writing and prefill tools (`render_*`, `md_to_pdf_*`, `generate_batch_*`, `kit_builder`) | FOLD or DROP | REQUIREMENTS Out of Scope: cutting them was a maintainer correction, "core, not sprawl" | keep until Retire, port later |
| `auto_apply`, `batch_apply_browser`, `captcha_solver` | FOLD or DROP | REQUIREMENTS Future APPLY-02: scripts kept, never deleted, never default | keep until Retire |

## Golden classes (MAP-02, D-07)

D-07 says goldens come from recorded outputs already on disk and never from re-running the pipeline. What exists on disk inside Kestrel:

| Where | What | Usable as a live-output golden? |
|-------|------|--------------------------------|
| `tests/eval/geo/fixtures/` | 277 scrubbed postings, judge verdicts, frozen reference classes, `GENERATION_LOG.md` (`SCRUB-PROOF: PASS`, per-pattern counts, environment fingerprint) | Yes for eligibility. Already a golden; reference it, do not copy. Note its provenance log names the source project in clear text; new logs must say "the private pipeline" (D-05) |
| `tests/fixtures/scoring_golden_set*.json` (6 families, 20+ jobs each) + `tests/eval/baseline_metrics.json` | Synthetic-shaped jobs with expected bands; mock-provider baseline | Scoring plumbing only. README states mock κ is near 0 and does not measure quality |
| `tests/fixtures/arbeitsagentur_v6_jobs.json` | One recorded source payload | Yes for one source's scan-arrival normalisation, after a scrub check |
| `tracking/scraped_scored_*.json` | Tracked file is a one-row placeholder (`"title": "Test", "company": "Co"`); local gitignored ones are the same shape | No |
| `tracking/daily-scan-*.md`, `scraped_raw_*.json` | Never committed [VERIFIED: `git log --all` over those paths shows only the placeholder JSON and `tracking/README.md`/`sample/`] | No |
| `data/career_os.db` (gitignored) | Local database | Not opened by this research (personal data). Whether it covers the window is UNVERIFIED |
| Actions artifacts | 30-day retention, and zero successful runs exist | No |

Conclusion: real recorded outputs exist only in the private pipeline. The STATE.md and ROADMAP.md wording ("synthetic or scrubbed, never copied from the private pipeline's data") and D-07 ("recorded outputs") pull in different directions. Recommended resolution, to be confirmed (Open Question 1): inputs are authored or scrubbed in Kestrel, the oracle is the current deterministic script at a pinned blob (a pure function replay is not a "pipeline run" and costs nothing), and only verdicts of private-only gates cross the boundary.

| Class | Producer(s) at a pinned blob | Inputs | Determinism hazards | Notes |
|-------|-----------------------------|--------|---------------------|-------|
| Scan arrivals | `tier0_ats_poller.fetch_greenhouse/fetch_lever/fetch_ashby(slug, *, company_key, client)` (take an `httpx.Client`), `scrape_new_sources` adapters, `germany_jobs` | Recorded or hand-built payloads fed through `httpx.MockTransport`; fictional companies | `scraped_at` uses `datetime.now()`; `_utcnow_iso()` in the poller | Output = normalised job dicts. Freeze the clock or drop the field |
| Dedup verdicts | `normalize.normalize_company/normalize_title/job_key/fuzzy_ratio`, `scrape_resilient.deduplicate`, `daily_pipeline.step_dedup_against_tracking` | Synthetic company/title pairs covering suffixes, `(m/f/d)`, casing, slug drift (the docstring's own examples) | `step_dedup_against_tracking` reads the real DB first | Cover collisions and non-collisions; `job_key` returns `(company, title)` tuples |
| Eligibility verdicts | `tests/eval/geo` (277) plus `batch_probe.geo_classify`, `job_scorer.geo_eligibility`, `blocklist.is_blocked/soft_flag_reason`, `job_scorer.pre_filter_job` | Synthetic locations and titles; pinned `GeoConfig` | Module-level `_CONFIG` and compiled blocklist regexes load from gitignored config | The duplicate token classifier in `batch_probe` is the known divergence point |
| Scoring | Deterministic only: `daily_pipeline._fallback_score`, `effective_scoring_cap`, `_source_priority`, `job_scorer.apply_floors/classify_tier/is_dream_tier/is_api_submittable`, `local_scorer.score_job_local` | Synthetic scored-job dicts | None for the deterministic set | LLM output cannot be frozen without a paid call; the existing mock-provider baseline stays the scoring-engine proof |
| Digest | `daily_pipeline.step_generate_digest(config, all_scraped, scored, filtered)` | Synthetic jobs; `PipelineConfig` with fixed `date`/`timestamp` and tmp `tracking_dir` | Writes to disk; reads `GITHUB_STEP_SUMMARY`; footer embeds `config.timestamp` | Store the exact markdown bytes; pre-commit `end-of-file-fixer` and `trailing-whitespace` would rewrite it, see pitfall 3 |
| Fact and voice gate verdicts | No code in Kestrel: grep for fact/voice gate found only docs (`docs/guides/anti-slop-writing.md`, `voice-corpus-architecture.md`, `cover-letter-writing.md`) | Kestrel-authored synthetic drafts and a synthetic fact sheet, committed first | The gates live in the private pipeline | A Track B-permitted agent or the maintainer runs the private gates over those drafts and returns verdict plus reason code per draft and the producing hash recorded as "the private pipeline @ <sha>"; no rule lexicon, fact sheet or real draft crosses |

Hypothesis (already a dev dependency) can widen pure-function inputs (normalisation, `job_key`, geo tokens), but a Hypothesis run that is not frozen into the golden is not a golden; freeze its examples.

## Mapping tables (MAP-03): sources per phase

Later-phase reviews have not closed, so no requirements exist for Find through Apply. Their target behaviours are the "Delivers" lists in `.planning/research/SUMMARY.md` (lines 90-139) and the tables in `FEATURES.md`/`ARCHITECTURE.md`. Treat every table as PROVISIONAL and say so in the YAML header; each phase's review may rewrite its rows, and that is a one-file change. Phase numbers follow ROADMAP.md line 42 order after Cut A (13): Find 14, Filter 15, Scan 16, Score 17, Track 18, Write 19, Connect 20, Apply 21, Retire 22, Install 23. These numbers are provisional until each `/gsd-phase add`; STATE.md also uses the older build-order numbering ("Phase 11 Retire"), which collides with GSD's Phase 11 Map, so the xfail reason strings must use GSD numbers.

| Phase | File | Target behaviour tables worth encoding (source) |
|-------|------|-------------------------------------------------|
| 14 Find | `phase_14_find.yaml` | URL normalisation L0 rows (`utm_*`, `gh_src`, fragment, trailing slash); L1 identity: same `(ats, slug, id)` is one posting, partial identity yields no key; L2 seen-set including same-run duplicates; liveness tri-state (404/410 expired, 429/5xx/timeout unknown, `unknown` never removes); canary verdicts `ok/small/empty/error/no-provider`, 50% drift; Ashby `isListed=false` is not an arrival (FEATURES 1a-1e) |
| 15 Filter | `phase_15_filter.yaml` | `assess()` decision, ordered `reason_codes`, `geo_class`, `rule_version`; gate order seen, blocklist, title, geo, skill/industry; no geo config means class `unknown`, no gate; multi-office any-office-eligible with `multi_office_partial` (FEATURES 2a-2b, SUMMARY Phase 4) |
| 16 Scan | `phase_16_scan.yaml` | Exit codes 0 ok, 1 fatal or partial, 2 spend halt, 3 preflight failed, 75 lease held (SUMMARY Phase 5 lists 0/1/2/3/75; ARCHITECTURE.md:180 lists 0/2/3/4/1, they disagree: flag, do not guess; encode rows only after the maintainer picks); refuses `mock`; `--dry-run --json` writes nothing |
| 17 Score | `phase_17_score.yaml` | Digest funnel and canary banner; audit sample stratified by reason code with seed and inclusion probability recorded; overturn exports a profile-free fixture; rater sees job facts before filter fields (SUMMARY Phase 6, ARCHITECTURE:285) |
| 18 Track | `phase_18_track.yaml` | `submission_state` axis `none/prepared/submit_attempted/submission_confirmed` separate from `ApplicationStatus` (quoted enum: `discovered, interested, applied, interviewing, offer, accepted, rejected, ghosted`); `VALID_TRANSITIONS` unchanged; append-only outcomes ledger; "did it go through" prompt after N hours (FEATURES 3b) |
| 19 Write | `phase_19_write.yaml` | `fact_gate` fails closed on empty dossier; numbers, employers, titles, tenure recompute; one `gate_draft()` choke point enumerating every draft producer; `voice_gate` lexical layer |
| 20 Connect | `phase_20_connect.yaml` | MCP tool manifest golden; read-only default; no submit/send/delete/raw-SQL tool; JD text marked untrusted and length-capped; every tool has a CLI twin with `--json` |
| 21 Apply | `phase_21_apply.yaml` | Prefill only from verified dossier facts; never submits; skipped fields listed; free-text answers pass `gate_draft()`; sets `prepared` |

Optional, recommend only if cheap: Foundation and Cut A rows that are already pure input-to-output and already have settled requirements (COST-01 classification fixtures per provider, COST-05 Free chain contains no paid model, FOUND-10 serialised prompt contains no profile fields, CUT-02 `.ics` writer golden). Those phases write their own tests; adding them here duplicates effort, so default to the eight phases named in D-08 and let Phases 12-13 plan their own (Open Question 5).

**Inventory meta-test** (`tests/targets/test_target_inventory.py`, passes today): parse every `tests/targets/test_phase_*.py` with `ast`; for each `test_` function assert an `xfail` mark with `strict=True`, a `raises=` keyword and a `reason` matching `^v2\.0 Phase (1[4-9]|2[0-3])$`; assert the reason's phase number matches the filename; assert a committed expected count per phase (so deleting a table is a visible decision); assert every table file loads and every row has `id`, `input`, `expect`; assert there are at least 2 `assert` statements per test. A phase turns its tests green by removing the marker and updating the expected count in the same PR. CI already makes the other two properties hard: a passing strict xfail is FAILED, a collection error is ERROR.

## MAP-04 arrival counts (D-09)

What Kestrel persists today (opened `src/career_os/models/discovery.py`, `models/scoring.py`, `models/models.py`, `services/discovery.py`):
- `discovered_jobs`: one row per deduplicated job per profile (`uq_discovered_job_dedup`); `sources` is a JSON array of source names (`"[]"` default); `source_urls`; `fit_score` nullable float; `application_id` nullable FK; `created_at`. Pre-dedup arrivals per source are not stored.
- `discovery_runs`: per-run `total_found`, `new_jobs`, `duplicates`, `errors`, `warnings` (JSON); not per source. The prefilter result is recorded only as a text warning (`"Pre-filter (strategy): P/T passed, F filtered (R%)"`) and the filtered jobs are dropped before the upsert (`services/discovery.py:509-535`), so "survived prefilter" per source is not recoverable from the schema.
- `scored_jobs`: per-job score rows (`fit_score`, `discovered_job_id`, `application_id`).
- `applications`: `source` (String 100), `status` (default `discovered`), `date_applied`, `created_at`. "Applied" = rows with `date_applied` set or status in `applied, interviewing, offer, accepted, rejected, ghosted` after having been applied; the definition is a maintainer decision.
The daily pipeline instead writes per-day files (`tracking/scraped_raw_<date>.json`, `scraped_scored_<date>.json`, digest) that carry a per-job `source` field; those files are where "arrived" and "scored" per source live, and the repo does not hold them. So the aggregate must be produced by Track B (it may read the private data) and only the counts crossed over. Recommended contract for the committed CSV (`arrival-counts.csv`):
`source,month,arrived,survived_prefilter,scored,shortlisted,applied` with `month` as `YYYY-MM`, integers only, no job-level columns, no company or ATS-slug names. Per-company ATS sources must be rolled up to the family (`greenhouse`, `lever`, `ashby`, `workable`, `smartrecruiters`, `personio`), because the source name there is derived from a company. Allowed source values: `FLOOR_SOURCES` in `tools/source_registry.py:93-110` (`aijobs, arbeitnow, ashby, germantechjobs, greenhouse, himalayas, jobicy, lever, personio, remoteok, remotely.de, remotive, smartrecruiters, startupjobs, weworkremotely, workable`) plus `JOBSPY_BOARDS` (`indeed, linkedin, glassdoor, google, zip_recruiter`) plus `arbeitsagentur` (emitted at `tools/germany_jobs.py:268` but absent from `FLOOR_SOURCES`) plus `manual` and `other`. A funnel need not be monotone because applications also arrive by hand and by extension, so do not assert `applied <= shortlisted`. Kestrel-side gate `test_arrival_counts.py`: exact header, month regex, non-negative ints, source in the allowed set, no extra columns, row count above zero, and small-cell suppression is a maintainer option (Open Question 7). A one-shot aggregator script, if any, follows the `generate_reference.py` pattern (not run by CI) and writes only this CSV.

## PII scan and the verdict list (MAP-02, MAP-08)

- Job: `PII leak check` step in the `backend` job of `.github/workflows/ci.yml` (lines 138-186). It runs `git grep -lE -- "$pattern"` over EVERY tracked file (so `.planning/` and `docs/` are covered), with patterns from `.github/pii-patterns.txt` (committed; today all comments, so zero active patterns) and the private `PII_PATTERNS` repository secret. With zero patterns it warns "INACTIVE" and exits 0; on a fork PR the secret is absent. It prints file names, never the match.
- What the secret holds is unknown to Track A and must stay that way; do not try to guess or reconstruct it. The practical rule is the COE's: place files correctly first, scan second. [CITED: docs/coe/2026-07-09_initial-commit-pii-exposure.md "How a future agent avoids this": verify by marker search over the whole tree, never by file list; the strip list is itself PII]
- No local invocation of the CI step exists. The nearest local equivalent is `tests/eval/geo/replay.py::scrub_patterns()`, which merges the committed gate file, fragment-assembled identifiers, a generic email shape `[\w.+-]+@[\w-]+\.[a-z]{2,}` and `https?://[^\s"]{1,150}\?` (any URL followed by a query string). Run it over every committed golden, count file, ledger and verdict list.
- Other nets: `secret-scan.yml` (gitleaks, `.gitleaks.toml`; its allowlist covers `tests/fixtures/.*` and `docs/.*`, not `tests/ports/` or `.planning/`) and the `gitleaks` pre-commit hook. A fake key shaped like a real provider key can trip gitleaks; use the non-prefixed constant in the MAP-05 sketch.
- What a committed golden or verdict list must avoid: emails; URLs with query strings or tracking parameters; real company, person or recruiter names; requisition IDs; API-key shaped strings; any date finer than a month in the verdict list (add a gate regex for `\b\d{4}-\d{2}-\d{2}\b` there); transcript quotes; private paths or repository names; counts small enough to re-identify a single posting if the source is a single company (roll up per-company sources).
- Verdict-list vocabulary conflict: D-02 says "kept / trimmed / parked / cut", D-12 and MAP-07 say KEEP / SCOPE-AND-PLAN / PARK / REMOVE. Use D-12/MAP-07 (the later, requirement-level statement) and say so in the list header. Give every row a stable ID (`F-01` flows, `X-01` features) so the Phase 13 and Retire cut lists can cite it; `test_verdict_list.py` checks columns `id, kind, verdict, profile_scope (specific|generic), non_technical (yes|no|partial), count, reason`, unique IDs, allowed values, and the forbidden-pattern gate.

## Common Pitfalls

### Pitfall 1: Green gate that checked nothing
**What goes wrong:** the ledger test passes because the file set is hand-listed, a golden replay passes because both sides call the same code, an xfail "passes" because an `ImportError` was absorbed.
**Why it happens:** each guard is only as strong as its negative case.
**How to avoid:** every guard ships guard-the-guard cases (missing row, phantom row, mutated golden byte, early-passing xfail); record one mutation probe per gate in the plan verification and assert the mutation actually applied (memory rule: a non-matching anchor silently reruns unmutated code).
**Warning signs:** a test that cannot be made to fail in under a minute.

### Pitfall 2: Golden depends on the maintainer's machine
**What goes wrong:** `_CONFIG` in `batch_probe`, the compiled blocklist in `blocklist`, `datetime.now()`, `PYTHONHASHSEED`, local `data/career_os.db`, `GITHUB_STEP_SUMMARY`, Python 3.14 locally versus 3.11 in CI (`ci.yml` backend job uses `python-version: "3.11"`).
**How to avoid:** pin every config explicitly in the replay harness; inject the clock; run replay with two hash seeds; generate on the same minor Python that CI uses or record the version and assert order-independence; never open the real DB.
**Warning signs:** green locally, red on the PR, or the reverse.

### Pitfall 3: Formatters rewrite the fixture
**What goes wrong:** `.pre-commit-config.yaml` runs `end-of-file-fixer`, `trailing-whitespace`, `mixed-line-ending` (all without a `tests/` exclude) and `ruff-format` on `^(src|tests)/`; a markdown digest golden or a `.py` data module is rewritten, its sha256 stops matching the manifest, and the commit loops (memory: pre-commit auto-fix deadlock).
**How to avoid:** store goldens as JSON/JSONL; for the digest golden make the stored bytes already satisfy those hooks (single trailing newline, no trailing spaces, LF) or add `exclude: ^tests/ports/golden/` to those hooks. `check-added-large-files` has a 1024 KB limit (the geo fixture `blind_items.json` is about 448 KB). [VERIFIED: .pre-commit-config.yaml lines 14-30]
**Warning signs:** `git diff` after `pre-commit run` touching a fixture.

### Pitfall 4: Branch history fails `Review trailers`
**What goes wrong:** `G-2013/v2-lean-milestone` is 19 commits ahead of `main`; `git log main..G-2013/v2-lean-milestone --format=%(trailers:key=Reviewed-by)` shows trailers on 5 and none on 14 (`ci.yml` job `review-trailers` runs `check_review_trailers.py --base --head` over the whole PR range, refuses merge commits and amended content). Branching `G-2039/map` from the milestone branch would fail CI.
**How to avoid:** cut `G-2039/map` from `main` as ROADMAP says; decide separately how `.planning/` milestone docs reach `main` (a signed docs PR; Open Question 3). Rebase, never merge main in; never amend after `review-push sign`. Commit types `docs` (visible in the changelog) and `test` (hidden) do not bump the version (`release-please-config.json`); there is no `.release-hold` yet (FOUND-11 adds it later), and a release PR is open, so merging to main will not by itself cut a release.
**Warning signs:** `Review trailers` red with "no trailer" on commits you did not write.

### Pitfall 5: Track boundary leaks through side channels
**What goes wrong:** a ledger row, golden log or verdict list names the private repository or a private script, a manifest records a private path, a geo-style `GENERATION_LOG.md` names the source project in clear text (the geo log does today), or a fixture is "scrubbed" from private data without the D-03 contract.
**How to avoid:** the only allowed spellings are "the private pipeline" and "the private pipeline's repository"; ledger rows for private scripts use anonymous IDs; add a Kestrel-side test that greps the new files for `private/`, `retrospective`, the word "transcript" outside an allowlisted sentence, and ISO dates in `.planning/phases/11-map/verdicts.md`. Track A agents do not open `private/`, `.env*` or `~/.claude/projects/`; this research did not.
**Warning signs:** a plan task whose input path begins with `private/`.

### Pitfall 6: xfail tests that import their targets
**What goes wrong:** `from career_os.services.assess import assess` at module top makes a collection ERROR; a body-level import without `raises=` makes a typo look like pending work.
**How to avoid:** `load_target()` inside the test body and `raises=NotBuilt` (Pattern 1).

### Pitfall 7: Mapping tables rot silently
**What goes wrong:** Find through Apply reviews have not closed, so rows encode research docs, not decisions.
**How to avoid:** header comment "PROVISIONAL until Phase N review closes", the inventory meta-test pins counts so a rewrite is a deliberate diff, and each later phase's plan starts by reconciling its table with its closed review.

## Code Examples

### Ledger row shape
```yaml
# tests/ports/PORT_LEDGER.yaml (illustrative rows)
- path: tools/normalize.py
  run_status: scheduled
  trigger: "daily-scan.yml via daily_pipeline (job gated off, no successful run in listed history)"
  inputs: "company and title strings"
  outputs: "normalised keys, job_key tuple, fuzzy ratio"
  disposition: port
  target: "TBD:Phase 14"
  tests: [tools/tests/test_normalize.py]
  reason: "dedup authority; golden at tests/ports/golden/dedup_verdicts"
- path: tools/tests/
  glob: "tools/tests/*.py"
  run_status: scheduled
  trigger: ci
  disposition: keep_until_retire
  reason: "CI step 'Run tool-script tests'"
- id: P-01
  private: true
  description: "scheduled nightly scorer in the private pipeline"
  run_status: scheduled
  disposition: port
```

### Strict-xfail run, verified output shape
```
test_xf.py::test_red_not_implemented XFAIL (v2.0 Phase 14)
test_xf.py::test_early_pass FAILED            # [XPASS(strict)] v2.0 Phase 15
test_xf.py::test_errors_differently FAILED    # KeyError: 'x' (raises=NotImplementedError did not match)
```
Source: ran in `/private/tmp/claude-501/-Users-pleasedodisturb-Projects-apps-kestrel/223d635d-41b0-4c7f-8374-9c68a61c9dc4/scratchpad/xf/` with pytest 9.0.3. [CITED: https://docs.pytest.org/en/stable/reference/reference.html#pytest-mark-xfail, the link pytest prints for the marker]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Differential test against a script, regenerate golden when it drifts | Frozen golden + sha256 manifest + producing blob hash, regeneration needs a review note | Geo port 2026-08 (`tests/eval/geo`) | Map extends this to every output class |
| Tests written after a port | Red tests first, phase flips them green | Maintainer rule "tests and output mapping first" | Map is its milestone-level instance |
| Ledger inside `tools/` (ARCHITECTURE.md draft) | Ledger under `tests/ports/` | This research | Survives Retire's deletion of `tools/` |

**Deprecated/outdated:** ARCHITECTURE.md section 10's disposition table where it conflicts with REQUIREMENTS.md (see conflicts table); the comment at the top of `tools/tests/test_daily_pipeline_port.py` saying `tools/tests/` is not in CI testpaths (CI runs it as its own step, `ci.yml:79-85`).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A pure in-process replay of deterministic Kestrel functions over synthetic inputs satisfies D-07 ("never from re-running the pipeline") because it makes no scan, network or LLM call | Golden classes | If the maintainer reads D-07 as "only pre-existing recorded outputs", MAP-02 has no sources and needs Track B scrubs instead |
| A2 | Fact and voice gate verdicts can cross the boundary as verdict-plus-reason-code over Kestrel-authored drafts without breaching D-01..D-05 | Golden classes | Boundary breach or an empty MAP-02 row for gates |
| A3 | The `PII_PATTERNS` secret is available to CI runs of same-repo PR branches | PII scan | If absent, the PII gate is INACTIVE and passes vacuously; the plan must not rely on it |
| A4 | Phase numbers 14 to 23 for Find through Install follow ROADMAP.md's stated add order | Mapping tables | Reason strings need a search-and-replace; the inventory regex must be updated |
| A5 | "Applied" for MAP-04 means `date_applied` set or a post-applied status | MAP-04 | Counts mean something else; maintainer defines |
| A6 | Candidate `delete` rows (`local_scorer`, `research_*`, `specific_hunt`, `update_sheet`, `validate_sheet`, `sonarcloud-mcp`) have no hidden users on the maintainer's machine or in the private pipeline | Script inventory | A script deleted later that something still calls |
| A7 | Heuristic test-to-script mapping in the inventory is approximate (grep, not import resolution) | Script inventory | A listed "none" is wrong; the plan should resolve by import |
| A8 | `uvicorn[standard]` stays a dependency so PyYAML stays available to ledger tests until Foundation declares it | Standard stack | Ledger tests fail on import if the transitive dependency disappears |

## Open Questions

1. **How may goldens be sourced given no recorded outputs exist in Kestrel?**
   - Known: no successful `daily-scan` run, placeholder-only tracking files, real outputs only in the private pipeline; STATE.md and ROADMAP.md say "never copied from the private pipeline's data", D-03 allows "scrubbed".
   - Unclear: does D-07's "recorded outputs" forbid deterministic replay over synthetic inputs?
   - Recommendation: approve A1 and A2 (synthetic inputs, pinned blob, private gate verdicts only), and say so in the plan's first task so no executor tries to scrub from private data.
2. **Who writes the private-pipeline ledger rows and MAP-04 aggregate, and in what order?** Recommendation: a Track B task, run before the PR is opened, emitting anonymous-ID ledger rows and `arrival-counts.csv` only; Track A defines the schemas first so Track B output is validated by the same tests.
3. **How do the milestone's `.planning/` docs reach `main`?** `G-2039/map` must branch from main (Pitfall 4), but CONTEXT, REQUIREMENTS and research live only on `G-2013/v2-lean-milestone`. Recommendation: land them through a separate signed docs PR before or alongside Map; do not PR the milestone branch as is.
4. **Scan exit-code table conflict** (SUMMARY Phase 5 vs ARCHITECTURE:180). Encode Scan rows only after the maintainer chooses.
5. **Include Phases 12 and 13 in the mapping tables?** Default no (D-08 names eight phases).
6. **Fail on producer-blob change?** Pattern 2 option (d): friction versus strictness.
7. **Small-cell suppression in the aggregate** (for example suppress counts below 3 for single-source rows).
8. **Verdict vocabulary**: confirm D-12/MAP-07 over D-02's "kept/trimmed/parked/cut".
9. **MAP-09 timing**: the Cut A and Retire cut lists do not exist until Phases 13 and 22. Map can deliver stable verdict IDs and a citation-checker test; "every item cites a verdict" can only be checked when those lists exist. Recommendation: Map delivers the checker; Phase 13 and Retire turn it on for their lists.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (project venv) | all tests | yes | 3.14.10 local (CI uses 3.11) | none needed; record version in manifest |
| pytest | all | yes | 9.0.3 | none |
| alembic | MAP-05 | yes (in venv) | pyproject `>=1.15.0` | none |
| PyYAML | ledger, tables | yes (transitive) | 6.0.3 | JSON data files |
| hypothesis | optional property inputs | yes | 6.165.1 | skip |
| git | hash recipe | yes | present | none |
| `gh` CLI (authenticated) | run-history evidence | yes | used this session | none |
| `.venv/bin/python` baseline | suite | yes | collect-only: 4767 of 4794 selected in 5.2 s; geo + masking guard: 239 passed in 3.4 s | none |
| GitHub secrets (`PII_PATTERNS`) | PII gate | UNVERIFIED | n/a | rely on file placement |

**Missing dependencies with no fallback:** none for Track A. Track B needs the private repository and its data, outside this research.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 local (`pytest>=8.3.0` floor), `asyncio_mode = "auto"`, `timeout = 30`, `testpaths = ["tests"]` [VERIFIED: pyproject.toml:128-138] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`; add marker `v2_pending` |
| Quick run command | `.venv/bin/python -m pytest tests/ports tests/targets -q -p no:cacheprovider` |
| Full suite command | `.venv/bin/python -m pytest tests/ -v --tb=short -m "not eval"` (exact CI line, plus `--cov`), then `pytest tests/eval/geo` and `pytest tools/tests/` as CI does |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MAP-01 | Every `tools/` file has exactly one ledger row, no phantom rows, enums valid | unit (fs-derived) + guard-the-guard | `pytest tests/ports/test_script_ledger.py -q` | Wave 0 |
| MAP-02 | Each golden replays equal at pinned blob; manifest sha256 and format valid; `scrub_patterns()` finds nothing | unit | `pytest tests/ports -q -k "golden or manifest"` | Wave 0 |
| MAP-02 (CI net) | `PII leak check` step | CI job | runs in `backend` job on the PR | exists |
| MAP-03 | Every mapping test strict-xfail with `raises` and reason; full run shows only XFAIL for them, none XPASS, none ERROR | unit (AST inventory) + CI behaviour | `pytest tests/targets -q -rxX`; `pytest tests/targets --collect-only -q -m v2_pending | tail -1` | Wave 0 |
| MAP-04 | CSV schema, allowed sources, ints only, no job-level or company columns | unit | `pytest tests/ports/test_arrival_counts.py -q` | Wave 0 |
| MAP-05 | Seeded `ai_providers` key readable through the factory after `upgrade head`; row count 1 | integration (temp SQLite) | `pytest tests/ports/test_ai_providers_golden.py -q` | Wave 0 |
| MAP-06 | Retrospective exists in the private repo only | manual-only (cannot be checked from Kestrel); Kestrel side: no new path begins `private/`, none contains retrospective narrative | maintainer attests in the PR; `pytest tests/ports/test_verdict_list.py -k boundary` | Wave 0 |
| MAP-07 | Each verdict row has allowed verdict, two tags, count, reason, unique ID | unit | `pytest tests/ports/test_verdict_list.py -q` | Wave 0 |
| MAP-08 | Verdict list matches no forbidden pattern (emails, query URLs, ISO dates, scrub patterns); CI PII scan green | unit + CI | same file; CI `PII leak check` | Wave 0 |
| MAP-09 | Citation checker exists and accepts only known verdict IDs; applied to the Phase 13 and Retire lists when they exist | unit now, enforcement later | `pytest tests/ports/test_verdict_list.py -k citation` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ports tests/targets -q` (target under 30 s; the suite's existing geo plus guard run took 3.4 s)
- **Per wave merge:** full CI-equivalent command above
- **Phase gate:** full suite green, `git diff main --stat -- src/ frontend/src/` empty, `pytest tests/ -m "not eval" --collect-only -q | tail -1` shows the new counts, a recorded mutation probe per gate (delete a ledger row, flip a golden byte, remove a strict-xfail marker's `strict`, replace the seeded key in MAP-05), then `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/ports/__init__.py`, `tests/targets/__init__.py` (the suite imports as the `tests` package)
- [ ] `tests/ports/test_script_ledger.py` plus `PORT_LEDGER.yaml`
- [ ] `tests/ports/test_golden_manifest.py`, `golden/MANIFEST.json`, per-class replay tests, `generate_golden.py`
- [ ] `tests/ports/test_ai_providers_golden.py`
- [ ] `tests/ports/test_arrival_counts.py`, `tests/ports/test_verdict_list.py`
- [ ] `tests/targets/_support.py`, `test_target_inventory.py`, eight table files and test modules
- [ ] `pyproject.toml` marker registration for `v2_pending`
- [ ] Framework install: none

## Security Domain

`security_enforcement` is not set to false in `.planning/config.json`, so this section applies.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a (no auth surface touched) |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | yes | `yaml.safe_load` only; strict schema checks on ledger, tables, CSV and verdict list; path matching against the repo root only |
| V6 Cryptography | no | sha256 from `hashlib` for integrity only, no secrets |
| V8 Data Protection | yes | file-placement-first privacy boundary; `scrub_patterns()` over every committed fixture; CI `PII leak check` and gitleaks as second nets |
| V14 Configuration | yes | pin config in replays; never read `.env` or the live database |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Personal or private-repo data committed to the public repo | Information Disclosure | D-01..D-05 placement rules; anonymous IDs; forbidden-pattern tests on the verdict list; no ISO dates; no private names or paths |
| Real or realistic credential in a fixture | Information Disclosure | non-prefixed fake constant; gitleaks pre-commit and CI |
| Golden silently re-baselined | Tampering | sha256 manifest, append-only regeneration note, producer blob recorded |
| Vacuous gate gives false confidence | Repudiation / Tampering | guard-the-guard cases and recorded mutation probes |
| Malicious YAML | Tampering | `safe_load` only |
| A cut migration empties AI credentials | Denial of Service (data loss) | MAP-05 golden asserts the key value after `upgrade head` |

## Sources

### Primary (HIGH confidence, files opened this session)
- `.planning/phases/11-map/11-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/research/SUMMARY.md`, `.planning/research/PITFALLS.md` (CUT-1, CUT-2, CUT-5, REPLAY-1, MIG-1), `.planning/research/ARCHITECTURE.md` (section 10), `.planning/research/FEATURES.md` (Find, Filter sections)
- `.github/workflows/ci.yml` (backend, PII leak check, review-trailers, ci-complete), `daily-scan.yml`, `secret-scan.yml`, `commitlint.yml`, `nightly.yml`; `.github/pii-patterns.txt`, `.gitleaks.toml`, `.pre-commit-config.yaml`, `commitlint.config.js`, `release-please-config.json`, `pyproject.toml`
- `tests/eval/geo/` (fixtures README, `GENERATION_LOG.md`, `replay.py`, `test_blindset_regression.py`, `generate_reference.py`), `tests/test_no_import_masking_skips.py`, `tests/test_migrations_packaging.py`, `tests/conftest.py`, `.claude/hooks/check-test-assertions.py`, `docs/reference/TESTING.md`, `docs/coe/2026-07-09_initial-commit-pii-exposure.md`
- `src/career_os/ai/factory.py`, `models/integrations.py`, `models/discovery.py`, `models/scoring.py`, `models/models.py`, `schemas/applications.py`, `services/discovery.py`, `_alembic/versions/d2e5a7f1b9c3_*.py`, `f7a8b9c0d1e2_*.py`, `_alembic/env.py`
- `tools/*.py` headers, `tools/README.md`, `tools/daily_pipeline.py`, `tools/source_registry.py`, `tools/batch_probe.py`, `tools/blocklist.py`, `tools/_filter_jobs.py`, `tools/scrape_remotely.py`, `automation/`
- Commands run: pytest xfail experiment (scratchpad), MAP-05 prototype (scratchpad), `ScriptDirectory` revision walk, `importlib.metadata.requires`, `git hash-object`/`rev-parse`/`log`, `gh run list`, `gh workflow list`, `gh variable list`, `pytest --collect-only`

### Secondary (MEDIUM confidence)
- pytest marker reference (https://docs.pytest.org/en/stable/reference/reference.html#pytest-mark-xfail), the URL printed by `pytest --markers`; behaviour re-verified empirically

### Tertiary (LOW confidence)
- Private pipeline contents: not read by design; all statements about it are UNVERIFIED

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, nothing new is added and every piece was exercised
- Architecture: HIGH for layout and mechanics, MEDIUM for the golden-sourcing resolution (needs maintainer confirmation)
- Pitfalls: HIGH, each traced to a file or a run this session

**Research date:** 2026-11
**Valid until:** 2026-12 (repo-state facts such as the 154-run history, the 19-commit branch and the Dependabot queue move daily; pytest mechanics are stable)
