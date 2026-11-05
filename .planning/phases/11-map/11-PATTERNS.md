# Phase 11: Map - Pattern Map

**Mapped:** 2026-11
**Files analyzed:** 14 new, 1 modified (`pyproject.toml`)
**Analogs found:** 13 / 15 (all analog paths verified git-tracked)

Note: RESEARCH.md was read to line 439 of 673 (MAP-04 onward not read); the file list below follows its proposed layout and the orchestrator's list.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `tests/ports/PORT_LEDGER.yaml` | data (ledger) | batch | none exact; shape in RESEARCH Pattern 3 | no-analog |
| `tests/ports/test_script_ledger.py` | test (fs guard) | transform | `tests/test_no_import_masking_skips.py` | exact |
| `tests/ports/golden/**` + `MANIFEST.json` | fixture | file-I/O | `tests/eval/geo/fixtures/` | exact |
| `tests/ports/generate_golden.py` | utility (one-shot) | batch | `tests/eval/geo/fixtures/generate_reference.py` | exact |
| `tests/ports/test_golden_manifest.py` | test | file-I/O | `tests/eval/geo/test_blindset_regression.py` (lines 146-200) | exact |
| `tests/ports/test_golden_<class>.py` | test (replay) | transform | `tests/eval/geo/test_blindset_regression.py` + `replay.py` | role-match |
| `tests/ports/test_ai_providers_golden.py` (MAP-05) | test | CRUD + migration | `tests/test_migrations_packaging.py` + `tests/conftest.py:73-90` | role-match |
| `tests/ports/test_arrival_counts.py`, `test_verdict_list.py` | test (schema + PII gate) | file-I/O | geo `test_fixture_carries_no_pii_or_tracking_urls` | role-match |
| `tests/targets/_support.py`, `tables/*.yaml`, `test_phase_NN_*.py` | test (strict xfail) | request-response | no repo analog (xfail unused today); RESEARCH Pattern 1 | no-analog |
| `tests/targets/test_target_inventory.py` | test (AST guard) | transform | `tests/test_no_import_masking_skips.py` | role-match |
| `pyproject.toml` (marker `v2_pending`) | config | n/a | existing `markers` list, lines 132-138 | exact |
| `arrival-counts.csv`, `verdicts.md` | docs | n/a | none | no-analog |

## Pattern Assignments

### `tests/ports/test_script_ledger.py` and `tests/targets/test_target_inventory.py`
**Analog:** `tests/test_no_import_masking_skips.py`

**Filesystem-derived sweep, never a hand list** (lines 70-92):
```python
_REPO_ROOT = Path(__file__).resolve().parent.parent
SWEEP_ROOTS = (_REPO_ROOT / "tests", _REPO_ROOT / "tools" / "tests")
FIRST_PARTY: frozenset[str] = frozenset(
    {"career_os", "tests"} | {p.stem for p in (_REPO_ROOT / "tools").glob("*.py")}
)

def _sweep_files() -> list[Path]:
    files: list[Path] = []
    for root in SWEEP_ROOTS:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return sorted(files)

SWEPT_FILES = _sweep_files()
```
Adapt: sweep `tools/` with `rglob("*")` and `p.is_file()`, same `__pycache__` exclusion; each file must match exactly one ledger row, each non-private row at least one file.

**Real sweep test with anchor assertion and loud message** (lines 1354-1376): assert a known anchor is in the swept set first (`assert _REPO_ROOT / "tests" / "test_provider_contract.py" in SWEPT_FILES`), then `assert all_violations == [], "...Remedy: ..."`. Copy for `tools/daily_pipeline.py`, `tools/normalize.py`, `tools/check_review_trailers.py` anchors.

**Guard-the-guard** (lines 1380-1440): `_write_fixture(tmp_path, source)` plus table-driven `_FLAG_CASES` / `_IGNORE_CASES`. Copy the idea: run the detector over an in-memory file list with one row removed and one phantom row added; assert both are flagged.

Caution: this file's SWEEP_ROOTS include `tests/`, so every new `tests/ports` and `tests/targets` file is scanned for import-masking skips. Do not use `try/except ImportError` plus `pytest.skip`; the `load_target()`/`NotBuilt` pattern (lazy `importlib` raising `NotBuilt`) is not flagged.

### `tests/ports/golden/**`, `MANIFEST.json`, `generate_golden.py`
**Analog:** `tests/eval/geo/fixtures/` (blind_items.json, judgements.json, reference_assignments.json, GENERATION_LOG.md, README.md, generate_reference.py) and `tests/eval/geo/replay.py`.

**Loader pattern** (replay.py:21-39): a `FIXTURES = Path(__file__).resolve().parent / "fixtures"` constant and one `json.loads((FIXTURES / name).read_text(encoding="utf-8"))` loader per file. Provide the same in a `tests/ports/replay.py` (or `_support.py`); never duplicate the call shape.

**One-shot generator contract** (generate_reference.py:1-45): docstring states "NOT run by CI", takes flags, enforces order scrub, prove neutral, freeze, write; on any PII hit or drift it "writes NOTHING and exits non-zero". Imports:
```python
FIXTURES = Path(__file__).resolve().parent
REPO_ROOT = FIXTURES.parents[3]   # adjust depth for tests/ports/
sys.path.insert(0, str(REPO_ROOT))
from tests.eval.geo.replay import scrub_patterns  # noqa: E402
```
D-05 deviation: the geo `GENERATION_LOG.md` names the source project in clear text; new logs/MANIFEST must say "the private pipeline". Use month-granularity `generated`.

### Shared PII scan for every golden/CSV/verdict test
**Source:** `tests/eval/geo/replay.py:62-107` (`scrub_patterns`, fails loud with `FileNotFoundError` if `.github/pii-patterns.txt` is missing; built-in keys `personal:name-stem`, `personal:surname`, `personal:home-city-country`, `personal:mail-domain`, `generic:email`, `tracking:url-query`).

**Integrity test to copy** (test_blindset_regression.py:146-180):
```python
patterns = scrub_patterns()
required = {"personal:name-stem", "personal:surname", "personal:home-city-country",
            "personal:mail-domain", "generic:email", "tracking:url-query"}
assert required <= set(patterns), (
    f"scrub gate degraded — built-in patterns missing: {sorted(required - set(patterns))}")
hits = {label: p.findall(blob) for label, p in patterns.items() if p.search(blob)}
assert not hits, f"scrub gate: committed fixture matches PII/tracking patterns: {sorted(hits)}"
```
Feed it every file under `tests/ports/golden/`, `arrival-counts.csv`, `verdicts.md`. Also copy the provenance-intact test (lines 182-200: assert `SCRUB-PROOF: PASS` in the log) for MANIFEST/log.

Gotcha: `replay.py` imports `career_os.services.geo...` at module top; importing only `scrub_patterns` still pulls that. Acceptable (same package), but a `tests/ports` test must not be marked `eval`; `-m "not eval"` is the CI fast run and the geo gate has a separate step (ci.yml 65-77).

### `tests/ports/test_ai_providers_golden.py` (MAP-05)
**Analogs:** `tests/test_migrations_packaging.py` (imports lines 15-25) and `tests/conftest.py:73-90`.

**Imports/paths** (test_migrations_packaging.py:15-30):
```python
from alembic.config import Config
from alembic.script import ScriptDirectory
import career_os
REPO_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = Path(career_os.__file__).resolve().parent
```
Build `Config()` programmatically (set `script_location` to `PKG_DIR / "_alembic"` and `sqlalchemy.url`), not from the ini: the ini path calls `fileConfig()` which disables loggers (documented in that file). Single-head assertion precedent: `test_single_alembic_head`.

**Autouse fixture that MUST be undone** (conftest.py:73-88):
```python
@pytest.fixture(autouse=True)
def hermetic_db_credentials(monkeypatch):
    monkeypatch.setattr("career_os.ai.factory._read_credential_from_db", lambda credential_key: "")
```
Its docstring: "A test that needs a stored credential can re-patch this in its body." Capture `REAL_READ = factory._read_credential_from_db` at module import (before fixtures run) and `monkeypatch.setattr(factory, "_read_credential_from_db", REAL_READ)`, point `settings.database_url` at the temp SQLite URL, `delenv("OPENROUTER_API_KEY")`. Full verified shape is RESEARCH.md Pattern 4 lines 281-297; seed at revision `f7a8b9c0d1e2`, raw SQL insert, upgrade to `head`, assert value equality (`== FAKE`) plus row count 1 so a missing seed cannot pass vacuously. Seed via raw SQL, not `update_integration` (auto-runs a connection test).

### `tests/targets/*` (strict xfail)
**Analog:** none in repo (no existing `xfail`). Use RESEARCH.md Pattern 1 verbatim: `NotBuilt`, lazy `load_target()`, `@pytest.mark.v2_pending`, `@pytest.mark.xfail(strict=True, raises=NotBuilt, reason="v2.0 Phase N")`, YAML loaded at import via `yaml.safe_load`. Two or more `assert` statements per test (hook `.claude/hooks/check-test-assertions.py`, TESTING.md RULE-01). Reason numbers use GSD phase numbers 14-21. `tests/targets/__init__.py` needed since imports are `from tests.targets._support import ...` (tests/ is a package; `tests.profile_data` import in conftest line 91 confirms).

### `pyproject.toml` (modify)
**Analog:** lines 132-138; append one line in the same style:
```toml
markers = [
    "eval: scoring golden-set agreement eval (G-1336) — runs nightly, excluded from the fast unit run",
    "regression: golden-set fit-score band regression tests",
    ...
    "live: hits a real external API over the network (G-1717); skipped unless KESTREL_LIVE_TESTS=1, never runs in CI",
    "v2_pending: mapping-table test for a v2.0 phase not built yet (strict xfail, Map phase 11)",
]
```

### Replay tests for tools/ oracles
`tests/conftest.py:19` does `sys.path.insert(0, str(PROJECT_ROOT / "tools"))`, so `import normalize`, `import batch_probe` work. Pin config by monkeypatching `batch_probe._CONFIG` (precedent `tools/tests/test_geo_gate.py:49-51`, per RESEARCH).

## Shared Patterns
- **Fail loud, never degrade:** `scrub_patterns()` raises on a missing gate file; sweep tests assert anchors first. Apply to every ledger/golden/counts/verdict test.
- **Derive sets from the filesystem:** `rglob` minus `__pycache__`; no hand-written lists.
- **Guard-the-guard fixtures** with `tmp_path` for each new guard.
- **Provenance:** `git hash-object` blob (works in shallow CI clones) in MANIFEST; do not test `git log` in CI.
- **Module docstring on every Python file; type hints; ruff line length 100** (CLAUDE.md).

## No Analog Found
| File | Reason |
|---|---|
| `tests/ports/PORT_LEDGER.yaml` | No ledger exists; use RESEARCH.md Pattern 3 enums (`run_status`: scheduled/by_hand/dead; `disposition`: port/keep_until_retire/delete) |
| `tests/targets/**` | No xfail precedent; RESEARCH.md Pattern 1 is the spec |
| `arrival-counts.csv`, `verdicts.md` | New artefacts; schema gates written fresh, PII scan reused |

## Metadata
**Analog search scope:** `tests/`, `tests/eval/geo/`, `pyproject.toml`. `tests/ports` and `tests/targets` do not exist yet.
**Pattern extraction date:** 2026-11
