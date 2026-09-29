# Phase 6: Test honesty - Research

**Researched:** 2026-09-29
**Domain:** Python test-suite hygiene (pytest collection/skip semantics) + toolchain version governance (ruff, pre-commit, CI)
**Confidence:** HIGH

## Summary

This phase has no new library to learn — both problems are entirely inside this repo's own configuration and test files, and every claim below was checked directly against the live repo and the live CI run from today (2026-09-29, run `36580634314`, commit `2a065a2`, conclusion `success`), not against training-data assumptions.

**Finding 1 (TEST-01/02):** There are exactly three `pytest.skip(..., allow_module_level=True)` call sites under `tests/` and one more under `tools/tests/`. Only **one** — `tests/test_parse_scoring_response.py:15-18` — masks an `ImportError` (the anti-pattern the ticket targets). The other three (`tests/test_batch_apply_browser.py`, `tests/test_batch_apply_overlay.py`, `tools/tests/test_config_loaders.py`) are file-presence guards (`if not path.exists(): skip`), structurally different and explicitly called out as fine in the ticket's own notes — confirmed by reading all four files in full. `pytest --collect-only -q tests/test_parse_scoring_response.py -rs` reproduces the exact reported symptom today: `SKIPPED [1] tests/test_parse_scoring_response.py:15: parse_scoring_response removed from tools/job_scorer.py` / `no tests collected` — 19 dead tests, exactly as the ticket states `[VERIFIED: pytest --collect-only output, this session]`.

**Finding 2 (TEST-01, parser relocation):** `parse_scoring_response` was added in G-291 and has zero references anywhere in the codebase today outside the dead test file itself `[VERIFIED: grep -rn "parse_scoring_response" ., this session — only tests/test_parse_scoring_response.py matches]`. Its functional role — turning raw, possibly fenced/trailing-comma/surrounding-text LLM output into structured scoring data — is now owned by `_try_parse_structured()` in `src/career_os/ai/openrouter_provider.py:353-420`, imported and called by **every** real provider (anthropic, openai, groq, gemini, huggingface, mistral, ollama, together, xai). It is already covered by `tests/test_json_parse_retry.py`, `tests/test_ai_provider.py`, `tests/test_dimensional_scaling.py`, `tests/test_role_intelligence.py`. It reproduces the code-fence-strip and trailing-comma-strip and brace-depth-extraction logic the dead test exercises, but the contract is **not** identical: it takes `(content: str, feature: AIFeature)` and returns a Pydantic model (`ScoreResult`, which now carries the `role_match`/`disqualifiers` gate fields from the G-1335 scoring-engine-v2 milestone), not `(raw: str) -> dict` with the old flat `score/reasoning/estimated_salary/effort_flag/prep_level/prep_notes` shape. It also has no single-quote-JSON fallback, unlike the dead test's `TestSingleQuotes` case. **Recommendation: delete**, not relocate — the parsing behavior already lives on and is already tested elsewhere under a newer, actively-maintained contract; resurrecting the old flat-dict contract would create a second, divergent JSON-parsing code path with no live caller.

**Finding 3 (TEST-02, guard mechanism):** Ruff has no rule for this anti-pattern. A GitHub issue requesting exactly this check against `flake8-pytest-style`/ruff's `PT` rule family is open and unimplemented `[CITED: github.com/m-burst/flake8-pytest-style/issues/188]`. The repo already has an established convention for this class of guard — `tests/test_provider_contract.py`'s "sweep + guard-the-guard" pattern (`test_provider_modules_discovered` walks all `*_provider` modules and asserts the sweep count itself hasn't silently shrunk) `[VERIFIED: tests/test_provider_contract.py:35-46, read this session]`. The same shape — an `ast`-based scan of `tests/*.py` for a `pytest.skip(..., allow_module_level=True)` call nested inside an `except ImportError:` handler, plus a positive self-test proving the detector fires on a constructed bad-pattern fixture — is directly reusable and is the only approach of the three considered that is "provable on demand" without touching CI infrastructure.

**Finding 4 (TEST-03/04, ruff drift — this is real and currently live):** `.pre-commit-config.yaml:25` pins `rev: v0.11.0`. `pyproject.toml:51` floats `"ruff>=0.11.0"`. The actual CI run from **today** resolved that floor to `ruff-0.16.9` `[VERIFIED: gh run view 36580634314 --log, this session — "Collecting ruff>=0.11.0 ... Using cached ruff-0.16.9..."]`, five minor versions ahead of the pre-commit pin. The local dev `.venv` in this checkout has yet a **third** value, `ruff 0.15.15` `[VERIFIED: .venv/bin/ruff --version, this session]` — proving the floor genuinely drifts release-to-release and that no two of the three places this repo runs ruff (pre-commit, CI, a given contributor's stale venv) are guaranteed to agree. Good news: as of the same CI run, `ruff check src/ tests/` and `ruff format --check src/ tests/` both pass clean against 0.16.9 (`All checks passed!` / `387 files already formatted`) `[VERIFIED: same CI log]` — so pinning to today's resolved version requires **no reformatting or lint-error fixups**, only the pin itself. **The version number to actually pin must be re-verified at implementation time** (`gh run list --workflow=ci.yml` + read the Lint step of the latest green run, or `pip index versions ruff`), not hardcoded from this research — ruff ships roughly weekly and even the numbers in this document may already be one or two releases stale by the time the phase executes.

**Finding 5 (TEST-03, an undiscovered live gap in the `_alembic` exclude):** The `_alembic` exclude is **not currently symmetric** between CI and pre-commit, independent of the version pin. `[tool.ruff] extend-exclude = ["src/career_os/_alembic"]` in `pyproject.toml` only takes effect for **directory-discovered** files. Empirically: `ruff check src/ tests/` (CI's exact invocation) finds zero `_alembic` files — the exclude works `[VERIFIED: ruff check src/ tests/ 2>&1 | grep -c "_alembic"` → `0`, this session]. But `ruff check` against an **explicitly-named** `_alembic` file or directory — which is exactly what pre-commit's `ruff`/`ruff-format` hooks do, since their only filter is `files: ^(src|tests)/` (a regex that matches `src/career_os/_alembic/...`) and pre-commit passes matched paths as literal CLI arguments — bypasses the exclude entirely: `ruff check src/career_os/_alembic/versions/<file>.py` reported 4 real errors, `ruff check src/career_os/_alembic/` reported 164 `[VERIFIED: direct commands, this session]`. `force-exclude` is not set anywhere `[VERIFIED: grep -n "force-exclude" pyproject.toml .pre-commit-config.yaml` → no output]`. Per ruff's own semantics, `force-exclude = true` is exactly the setting that makes `exclude`/`extend-exclude` apply even to explicitly-passed paths — the missing piece. This means today, if a contributor touches a file under `src/career_os/_alembic/` and runs `pre-commit run` (or it runs pre-push), the ruff hooks would try to lint/reformat migration scaffolding the header comment in `.pre-commit-config.yaml:1-6` explicitly says must not be touched. TEST-03's "the `_alembic` exclude is preserved" criterion is not automatically satisfied by fixing the version drift alone — it needs `force-exclude = true` added under `[tool.ruff]` (single fix, both invocation shapes covered) or an explicit `exclude: ^src/career_os/_alembic/` added to both ruff hooks in `.pre-commit-config.yaml` (matches the existing per-hook pattern already used for the other four hooks in that file).

**Primary recommendation:** For TEST-01/02: delete `tests/test_parse_scoring_response.py` (dead subject, already-superseded contract, already-tested replacement) and add an `ast`-based sweep test (new file, e.g. `tests/test_no_import_masking_skips.py`) modeled on `tests/test_provider_contract.py`'s guard-the-guard pattern. For TEST-03/04: pin `ruff==<CI's currently-resolved version>` in `pyproject.toml` dev extras (replacing the `>=0.11.0` floor) and `rev: v<same version>` in `.pre-commit-config.yaml`, add `force-exclude = true` under `[tool.ruff]`, and add a `tests/test_toolchain_pins.py` that parses both files (`tomllib` — stdlib since target is Python 3.11+, no new dependency — and a regex or `yaml` read against `.pre-commit-config.yaml`) and asserts the two pins are equal.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| TEST-01 | No test file under `tests/` masks an ImportError with a module-level `pytest.skip(allow_module_level=True)`; `tests/test_parse_scoring_response.py` either runs against a relocated parser or is deleted with its dead subject | Finding 1 confirms the exact live symptom (`pytest --collect-only -rs` output). Finding 2 traces `parse_scoring_response`'s successor (`_try_parse_structured`) and its existing test coverage, and recommends **delete** over relocate with the contract-divergence evidence to back it |
| TEST-02 | A guard test or CI step fails when an import-masking module-level skip is reintroduced | Finding 3 rules out a ruff builtin rule (verified via web search — none exists) and a regex/grep approach (false-positives against the repo's own legitimate file-presence guards), and recommends the AST-based sweep + guard-the-guard pattern already established in `tests/test_provider_contract.py`. Full design in Architecture Patterns > Pattern 2, with both a permanent self-test and a manual scratch-check proof in Validation Architecture |
| TEST-03 | One ruff version governs pre-commit and CI; a file formatted locally cannot fail `ruff format --check` in CI; the `_alembic` exclude stays | Finding 4 pins down the exact current drift (three different ruff versions observed in one session) with the CI-verified target version and proof it requires no reformatting. Finding 5 (Pitfall 3) surfaces a second, previously-undocumented gap — `force-exclude` is not set, so the `_alembic` exclude does not actually hold under pre-commit's file-list invocation shape today, independent of the version-pin fix |
| TEST-04 | A test or CI step fails when the pre-commit ruff rev and the pyproject ruff pin drift apart | Finding 4 plus the Alternatives Considered comparison of "pin both + drift guard" vs. "pre-commit-in-CI" recommends the former (smaller CI blast radius — verified `gitleaks`/`prettier` are not currently in the backend CI job and Option 2 would newly introduce them). Design + self-test + scratch-check proof in Validation Architecture |
</phase_requirements>

## Architectural Responsibility Map

This phase touches dev-tooling/CI configuration and the test suite itself, not a runtime request path — the standard Browser/SSR/API/CDN/DB tiers don't map cleanly. Using the closest-fit tier per the standard table:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Test-suite collection honesty (no masked ImportError skips) | API / Backend (dev tooling — pytest collection, not a runtime endpoint) | — | The guard runs inside `pytest tests/`, the same process/tier as the backend test suite; it has no browser, SSR, or DB surface |
| Dead parser removal / relocation | API / Backend (`src/career_os/ai/`) | — | `_try_parse_structured` is backend AI-provider-layer code; the decision is whether backend test coverage for it is adequate |
| Ruff version governance (pre-commit vs. CI vs. pyproject) | API / Backend (CI/build tooling, not shipped code) | — | Affects `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml` — none of which are runtime-served; closest fit is backend build tooling |
| Drift guard for the two ruff pins | API / Backend (test-suite-as-CI-gate) | — | Implemented as a pytest test, runs in the same `backend` CI job as everything else |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ruff` | `0.16.9` as resolved by the latest green CI run today (**re-verify at implementation time — do not hardcode this number without re-checking**, `[VERIFIED: gh run view 36580634314 --log, 2026-09-29]`) | Linting + formatting, already the project's sole linter/formatter | Already the project standard (`pyproject.toml`, `.pre-commit-config.yaml`); this phase pins it, doesn't introduce it |
| `tomllib` | stdlib (Python 3.11+) | Parse `pyproject.toml`'s `ruff>=...`/`ruff==...` pin for the drift-guard test | Zero new dependency — `requires-python = ">=3.11"` already guarantees it; no need for the `tomli` backport |
| `ast` | stdlib | Parse `tests/*.py` to detect `pytest.skip(allow_module_level=True)` nested inside `except ImportError:` | Zero new dependency; matches the level of rigor the existing `tests/test_provider_contract.py` sweep already uses (module/AST introspection, not regex) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pyyaml` | `6.0.3` — **already installed, but not a declared project dependency** `[VERIFIED: .venv/bin/pip show pyyaml; also observed in CI's "Install dependencies" log as a transitive install, 2026-09-29]` | Parse `.pre-commit-config.yaml`'s `rev:` field for the drift-guard test | Only if the plan chooses a real YAML parse over a regex on the `rev:` line. `tools/tests/test_config_loaders.py:30` already does `import yaml` unconditionally with no explicit dependency declaration, so there is direct precedent for relying on it — but it is currently only present because *something else* (most likely `python-jobspy`, `markdownify`, or `beautifulsoup4`'s toolchain) pulls it in transitively, not because the project asked for it. **Recommendation:** add `pyyaml` explicitly to the `dev` extra in `pyproject.toml` if the guard test imports it — cheap, removes an undeclared-dependency risk, and formalizes what `tools/tests/test_config_loaders.py` already silently assumes. If avoiding a new declared dependency is preferred, a regex on the `rev:` line under the `astral-sh/ruff-pre-commit` block in `.pre-commit-config.yaml` is a viable zero-dependency alternative — the file's structure (one `repo:`/`rev:` pair per block) is simple and stable enough that a targeted regex is low-risk here. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ast`-based import-masking sweep test | A ruff builtin `PT`-series rule | Does not exist — verified via web search; the closest issue (flake8-pytest-style#188) is open, unimplemented, and even if implemented would flag *any* `allow_module_level=True`, not specifically ones inside an `except ImportError:` handler, so it would also flag the two legitimate file-presence guards as false positives |
| `ast`-based import-masking sweep test | A CI grep/heuristic step (regex-based proximity match of `except ImportError` near `allow_module_level=True`) | Cheaper to write, but brittle against reformatting (e.g., a blank line or comment between the `except` and the `pytest.skip(` call breaks a naive regex), harder to unit-test in isolation, and less "provable on demand" as a committed artifact — the AST walk is exact regardless of formatting |
| Pin ruff exact version in both files (Option 1) | Run `pre-commit run --all-files` (or scoped `pre-commit run ruff ... && pre-commit run ruff-format ...`) inside CI's `Lint` step instead of bare `ruff check`/`ruff format --check` (Option 2) | Option 2 eliminates the pyproject floating-floor's relevance for lint entirely (CI would always match pre-commit exactly, by construction), but (a) `pre-commit` is not currently a declared project dependency at all — it is a personal global tool at `~/.local/bin/pre-commit` per this machine's `~/.claude/CLAUDE.md`, so CI would need to newly install it; (b) `pre-commit run --all-files` (unscoped) would newly pull `prettier` and `gitleaks` into the backend Lint step, both already redundant with existing CI coverage — `gitleaks` already runs standalone in `.github/workflows/secret-scan.yml` `[VERIFIED: .github/workflows/secret-scan.yml:15-26, read this session]`, and `prettier` currently runs nowhere in CI, so introducing it here would be new, unreviewed scope creep unrelated to this phase; a scoped invocation (`pre-commit run ruff --all-files`, `pre-commit run ruff-format --all-files`) avoids that but is a larger CI-surface change than Option 1 for the same outcome |

**Installation:** No new packages to install for the primary recommendation (Option 1: pin-both). If `pyyaml` is added explicitly:
```bash
# pyproject.toml [project.optional-dependencies] dev — add "pyyaml>=6.0.3"
pip install -e ".[dev]"
```

**Version verification:** `ruff==<X.Y.Z>` must be re-verified at implementation time, not taken from this document. Run, immediately before writing the pin:
```bash
gh run list --workflow=ci.yml --branch=main --limit=1 --json databaseId,conclusion
gh run view <databaseId> --log | grep "Using cached ruff-"
```
This is the ground truth for "the version CI actually installs" — more reliable than `pip index versions ruff` (which shows the PyPI-latest, possibly ahead of what CI's cache last resolved) or the local `.venv` (which, in this checkout, is already one minor version stale relative to CI: `0.15.15` locally vs. `0.16.9` in the last CI run, both observed the same day).

## Package Legitimacy Audit

No new external packages are being installed by this phase's primary recommendation. `ruff` is already a first-party project dependency (only its pin changes, not its identity); `tomllib`/`ast` are stdlib. `pyyaml`, if declared explicitly rather than left as an undeclared transitive dependency, is not new to the *environment* — it is already installed and already imported directly and unconditionally by `tools/tests/test_config_loaders.py:30` — only newly *declared*. No legitimacy check is required for a package already present, imported, and exercised in the existing test suite; the gate exists to catch hallucinated/slopsquatted new packages, which this is not.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Contributor edits code
        |
        v
  git commit  --->  pre-commit hooks run locally
        |                 |
        |                 +--> ruff (lint, --fix)         [pinned rev in .pre-commit-config.yaml]
        |                 +--> ruff-format                [same pin]
        |                 +--> gitleaks / prettier / etc.
        |
        v
  git push  --->  GitHub Actions CI (.github/workflows/ci.yml)
                        |
                        +--> backend job
                        |      +--> pip install -e ".[dev]"   [ruff version resolved from pyproject.toml pin/floor]
                        |      +--> ruff check src/ tests/          <-- must agree with the pre-commit pin
                        |      +--> ruff format --check src/ tests/ <-- must agree with the pre-commit pin
                        |      +--> pytest tests/ -m "not eval"     <-- collects tests/test_*.py
                        |      |         |
                        |      |         +--> tests/test_no_import_masking_skips.py (NEW)
                        |      |               scans tests/*.py via ast, fails if any
                        |      |               pytest.skip(allow_module_level=True) sits
                        |      |               inside an `except ImportError:` handler
                        |      |
                        |      |         +--> tests/test_toolchain_pins.py (NEW)
                        |      |               parses pyproject.toml (tomllib) + .pre-commit-config.yaml
                        |      |               (yaml or regex), fails if the two ruff versions differ
                        |      |
                        |      +--> pytest tools/tests/ (separate step, own pytest invocation)
                        |
                        +--> review-trailers job (tools/check_review_trailers.py — unrelated to ruff, unaffected)
                        +--> ci-complete gate (requires backend + frontend + extension + actionlint + review-trailers)
```

### Recommended Project Structure
```
tests/
├── test_provider_contract.py       # existing "sweep + guard-the-guard" pattern this phase reuses
├── test_no_import_masking_skips.py # NEW (G-1382/TEST-02) — ast sweep + self-test
├── test_toolchain_pins.py          # NEW (G-1383/TEST-04) — pyproject vs .pre-commit-config.yaml drift guard
└── test_parse_scoring_response.py  # DELETE (G-1382/TEST-01) — dead subject, superseded contract
```

### Pattern 1: Sweep + guard-the-guard (established convention, reuse it)
**What:** A pytest module that (a) programmatically discovers a set of targets (files, modules), (b) asserts an invariant across all of them, and (c) has a *separate* test asserting the discovery step itself found the expected targets — so silently shrinking the sweep (e.g., deleting or renaming a file) can't silently make the guard vacuously pass.
**When to use:** Any "this property must hold for every X" guard, exactly this phase's TEST-02 and TEST-04 shape.
**Example (existing precedent in this repo):**
```python
# Source: tests/test_provider_contract.py:31-46 (read this session)
PROVIDER_MODULES = sorted(
    m.name for m in pkgutil.iter_modules(ai_pkg.__path__) if m.name.endswith("_provider")
)


def test_provider_modules_discovered():
    """Guard the guard: the sweep must cover every real provider, not a magic number."""
    assert "openai_provider" in PROVIDER_MODULES
    expected_modules = {module for module, _cls, _kwargs in REAL_PROVIDERS.values()}
    missing = expected_modules - set(PROVIDER_MODULES)
    assert not missing, f"provider modules not found by the sweep: {sorted(missing)}"


@pytest.mark.parametrize("module_name", PROVIDER_MODULES)
def test_provider_module_imports(module_name: str):
    importlib.import_module(f"career_os.ai.{module_name}")
```

### Pattern 2: AST-based anti-pattern detection (recommended new pattern for TEST-02)
**What:** Walk each `tests/*.py` file's AST; for every `Try` node, check whether any `ExceptHandler` whose type references `ImportError` contains, anywhere in its body, a `Call` to `pytest.skip` with an `allow_module_level` keyword. This distinguishes the one real anti-pattern (`try: import X / except ImportError: pytest.skip(..., allow_module_level=True)`) from the two legitimate file-presence guards (`if not path.exists(): pytest.skip(..., allow_module_level=True)`), which have no `except ImportError:` ancestor.
**When to use:** TEST-02's guard. AST, not regex/string search — the file-presence guards use the exact same `pytest.skip(..., allow_module_level=True)` call shape, so any check keyed on that call alone (not its enclosing `except ImportError:` context) produces false positives on files the ticket explicitly says are fine.
**Sketch (not verified against a real ruff/pytest run — design pattern only, `[ASSUMED]` as literal code, ground truth is the AST shapes of the two files already read this session):**
```python
import ast
from pathlib import Path

def find_import_masking_skips(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _handles_import_error(handler):
                continue
            for sub in ast.walk(handler):
                if _is_module_level_skip(sub):
                    violations.append(f"{path}:{sub.lineno}")
    return violations

def _handles_import_error(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if isinstance(t, ast.Name):
        return t.id == "ImportError"
    if isinstance(t, ast.Tuple):
        return any(isinstance(e, ast.Name) and e.id == "ImportError" for e in t.elts)
    return False

def _is_module_level_skip(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    if not (node.func.attr == "skip" and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest"):
        return False
    return any(kw.arg == "allow_module_level" for kw in node.keywords)
```

### Anti-Patterns to Avoid
- **`try: from X import Y / except ImportError: pytest.skip(..., allow_module_level=True)`:** Masks a genuine code defect (removed/renamed function, broken import chain) as an intentional, environment-dependent skip. `pytest -rs` and `--collect-only` both make it *look* like a deliberate, reasoned skip rather than a silent failure — exactly what happened to this file and, per the ticket, to `test_openai_provider.py` before G-1348 fixed that instance.
- **Regex-only detection of `pytest.skip(allow_module_level=True)` without checking the enclosing exception handler:** Produces false positives against the two legitimate file-presence guards in this exact repo — proven, not hypothetical.
- **Floating dependency floors (`ruff>=0.11.0`) for a tool whose *output* (formatting/lint results) must be byte-identical between two independently-updated invocation sites:** A floor is fine for a library whose API is what matters; it is wrong for a tool whose *deterministic output* is compared across two separately-triggered installs (pre-commit's isolated hook env vs. CI's `pip install`), because "any version >= X" from two different install times/caches is not guaranteed to be the same version.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting "does this file use pytest.skip at module level" | A brand-new bespoke pytest plugin or conftest hook | A plain pytest test function using `ast` (Pattern 2 above) | No plugin infrastructure needed; a plain test is easier to read, run standalone (`pytest tests/test_no_import_masking_skips.py -v`), and matches the existing `test_provider_contract.py` convention exactly |
| Parsing TOML for the ruff pin | A regex against `pyproject.toml` | `tomllib` (stdlib, Python 3.11+) | Zero risk of a regex mis-parsing a valid TOML edge case (e.g., a comment containing the string `ruff`); already free, no new dependency |

**Key insight:** Both guards this phase needs are small, self-contained, already-precedented pytest tests — there is no case for reaching outside the standard library plus what's already a project dependency.

## Common Pitfalls

### Pitfall 1: Guard detects the anti-pattern but also flags the legitimate file-presence guards
**What goes wrong:** A naive "any module-level `pytest.skip(..., allow_module_level=True)`" check flags `tests/test_batch_apply_browser.py` and `tests/test_batch_apply_overlay.py` (and `tools/tests/test_config_loaders.py`, if in scope), which the ticket explicitly says are fine.
**Why it happens:** The call shape (`pytest.skip(..., allow_module_level=True)`) is identical between the "masking an ImportError" case and the "file presence guard" case; only the *enclosing context* (`except ImportError:` vs. `if not path.exists():`) differs.
**How to avoid:** Key the detector on the `except ImportError:` (or a tuple containing `ImportError`) ancestor specifically, per Pattern 2 above — verified by direct reading of all three/four files this session to confirm this is the actual, sufficient discriminator in this codebase today.
**Warning signs:** CI goes red on `tests/test_batch_apply_browser.py` or `tests/test_batch_apply_overlay.py` immediately after adding the guard, with no code change to those files.

### Pitfall 2: Hardcoding the ruff version this research observed
**What goes wrong:** The plan pins `ruff==0.15.15` (this session's local `.venv` value) or `ruff==0.16.9` (this session's CI-observed value) without re-checking at execution time, and by the time the phase is executed, PyPI has shipped a newer release, so either (a) the pin is already behind what a fresh `pip install -e ".[dev]"` would grab in an unrelated future CI run reading a stale lockless floor elsewhere, or (b) — more likely, since this phase moves from a floor to an exact pin — nothing breaks automatically, but the number in the eventual commit is stale/wrong relative to "today" as understood at plan-write time vs. execute time.
**Why it happens:** `ruff` releases roughly weekly; this research already observed three different values in one session (0.11.0 pinned, 0.15.15 local venv, 0.16.9 latest CI run) — the ground is moving under any hardcoded number.
**How to avoid:** Re-run the "Version verification" commands (above) immediately before writing the exact pin into `pyproject.toml`/`.pre-commit-config.yaml`, not from memory of this document.
**Warning signs:** None visible until the pin is written — this is a plan/execute-time discipline issue, not something a test can catch (the drift-guard test only proves internal consistency between the two files, not that either value is "current").

### Pitfall 3: Fixing the version pin without also fixing the `_alembic` force-exclude gap
**What goes wrong:** TEST-03's "the `_alembic` exclude is preserved" criterion reads as "don't regress it," implying it currently works everywhere — it does not. It works for CI's directory-based invocation (`ruff check src/ tests/`) but not for pre-commit's file-list-based invocation, independent of the version-pin fix (verified with the CI-matching version, 0.15.15, present in this checkout, and confirmed the failure mode is about *invocation shape*, not ruff version).
**Why it happens:** `extend-exclude` in `pyproject.toml` only applies during ruff's own directory discovery; when a path is passed to ruff as an explicit CLI argument (which is what pre-commit does for every hook, always), ruff by default still lints/formats it unless `force-exclude = true` is set.
**How to avoid:** Add `force-exclude = true` under `[tool.ruff]` in `pyproject.toml` as part of this phase's `.pre-commit-config.yaml`/`pyproject.toml` edits (or, equivalently, add `exclude: ^src/career_os/_alembic/` to both the `ruff` and `ruff-format` hooks in `.pre-commit-config.yaml`, matching the pattern the other four hooks in that file already use).
**Warning signs:** A future commit touching `src/career_os/_alembic/versions/*.py` gets reformatted or flagged by a local `pre-commit run`/pre-push hook, contradicting the file's own header comment (`.pre-commit-config.yaml:1-6`) that says this must never happen.

## Code Examples

### Reproducing today's dead-test symptom (verified this session)
```bash
# Source: direct command output, this session
.venv/bin/python -m pytest --collect-only -q tests/test_parse_scoring_response.py -rs
# =========================== short test summary info ============================
# SKIPPED [1] tests/test_parse_scoring_response.py:15: parse_scoring_response removed from tools/job_scorer.py
# no tests collected in 0.58s
```

### Confirming which _alembic invocation shape is safe (verified this session)
```bash
# Source: direct command output, this session
.venv/bin/ruff check src/ tests/ 2>&1 | grep -c "_alembic"
# 0   <- CI's exact invocation, directory-discovered, exclude honored

.venv/bin/ruff check src/career_os/_alembic/versions/e6f7a8b9c0d1_add_company_research_reports_table.py
# Found 4 errors.   <- explicit file path, exclude NOT honored (no force-exclude set)
```

### Confirming today's CI-resolved ruff version (verified this session)
```bash
# Source: gh run view 36580634314 --log (latest green main run, 2026-09-29T14:10Z), this session
# "Collecting ruff>=0.11.0 (from kestrel-app==0.28.2)"
# "Using cached ruff-0.16.9-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
# ... Lint step: "All checks passed!" / "387 files already formatted"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `parse_scoring_response` — standalone flat-dict JSON parser in `tools/job_scorer.py`, ported from CareerOS (G-291) | `_try_parse_structured` — Pydantic-schema-validating parser in `src/career_os/ai/openrouter_provider.py`, shared by all 9 real providers, part of the G-1335/G-1337/G-1338 "Scoring Engine v2" architecture (role-fit gate, 0-5 dimensional scoring) | Scoring Engine v2 milestone, shipped 2026-07-17 per `.planning` project memory | The old flat `score/reasoning/estimated_salary/...` dict contract is fully superseded; anything written against the old shape (including the dead test file) is testing a contract nothing in production emits anymore |

**Deprecated/outdated:**
- `parse_scoring_response` (`tools/job_scorer.py`): removed from the module at some point after G-291; zero references remain anywhere except the dead test. `git log -S` on the exact string only surfaces the original G-291 port and unrelated later merge commits — no isolated "remove parse_scoring_response" commit was found in history, i.e. it most likely fell out incidentally during a later `tools/job_scorer.py` rewrite rather than being deliberately deleted with its own commit `[ASSUMED — history search was inconclusive on the exact removal commit; does not change the delete-vs-relocate recommendation, which rests on "zero live callers today," independently verified]`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact ruff version to pin (`0.16.9` observed today) will still be correct by the time this phase executes | Standard Stack, Pitfall 2 | Low — the plan explicitly instructs re-verification at implementation time; if skipped, the pin is merely stale-but-internally-consistent (the drift guard still holds pre-commit and pyproject equal to each other), not broken |
| A2 | The Pattern 2 AST-detection code sketch is correct Python/works against pytest/ast as written | Architecture Patterns > Pattern 2 | Medium — it was designed against the real shapes of the four files read this session but was not executed; the planner/executor should run it against a constructed bad-pattern fixture (the Nyquist "scratch check" below) before trusting it in CI |
| A3 | No isolated commit deliberately removed `parse_scoring_response` from `tools/job_scorer.py` — it fell out incidentally | State of the Art | Very low — doesn't affect the delete recommendation, which is based on "zero live callers today," a fact independently verified by grep, not by git history |

## Open Questions (RESOLVED)

1. **Should the TEST-02 guard also cover `tools/tests/*.py`, not just `tests/*.py`?**
   - What we know: G-1382's own AC text says "No test file in **tests/**..." (scoped), but `tools/tests/test_config_loaders.py` has an identical file-presence-guard pattern (fine, not a violation) and the *class* of anti-pattern (masking ImportError) is architecturally identical whether it happens under `tests/` or `tools/tests/`. `tools/tests/` is a separate `pytest` invocation in CI (`Run tool-script tests` step) but the phase's stated goal — "the test suite tells the truth" — isn't directory-scoped.
   - What's unclear: Whether scoping strictly to `tests/` (satisfying the literal AC) vs. also sweeping `tools/tests/` (serving the broader phase goal, at near-zero marginal cost since no violation currently exists there) is the intended scope.
   - Recommendation: Sweep both. The cost of including `tools/tests/**/*.py` in the glob is one extra directory in an `ast.walk`, and today it finds zero violations there (confirmed: the only `tools/tests/` `allow_module_level` instance is the file-presence-guard pattern), so it costs nothing today and closes the same class of gap for free.
   - **RESOLVED (2026-09-29, plan 06-02 DEC-09):** sweep both `tests/` and `tools/tests/`, recursing into subpackages.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `ruff` | TEST-03/04 (the thing being pinned) | Yes | `0.15.15` in local `.venv` / `0.16.9` in today's CI run / `0.11.0` in the current pre-commit pin — three different values observed in one session | N/A — this divergence is the problem the phase fixes |
| `pre-commit` | Local dev-loop enforcement of the ruff pin | Yes, but as a **personal global tool** (`~/.local/bin/pre-commit`), not a declared project dependency | Not checked (out of scope — not part of this phase's pin) | If a contributor's machine lacks `pre-commit` globally, the pre-commit half of the drift-guard's *purpose* (not the drift-guard test itself, which runs in CI regardless) doesn't apply to them locally — CI is still the enforcement backstop |
| `pyyaml` | Optional, only if the TEST-04 guard parses `.pre-commit-config.yaml` as YAML rather than via regex | Yes, already installed (transitively) in both the local venv and CI | `6.0.3` in both | Regex on the `rev:` line under the `astral-sh/ruff-pre-commit` block (zero-dependency alternative) |
| `tomllib` | TEST-04 guard, parsing `pyproject.toml` | Yes | stdlib, Python 3.11+ (`requires-python = ">=3.11"`) | None needed |
| `gh` CLI | Verifying "what ruff version does CI actually install today" at implementation time | Yes (used this session) | Not checked | `pip index versions ruff` (less authoritative — shows PyPI-latest, not necessarily what CI's last resolved cache used) |

**Missing dependencies with no fallback:** none.

**Missing dependencies with fallback:** `pyyaml` explicit declaration (fallback: regex-based `rev:` extraction).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (CI-installed; local venv reports differently but CI is ground truth) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths = `["tests"]`, `asyncio_mode = "auto"`, `timeout = 30`) |
| Quick run command | `.venv/bin/python -m pytest tests/test_no_import_masking_skips.py tests/test_toolchain_pins.py -v` |
| Full suite command | `pytest tests/ -v --tb=short -m "not eval" --cov=src/career_os --cov-report=xml` (exact CI invocation, `ci.yml:71`) plus `pytest tools/tests/ -v --tb=short` (separate CI step, `ci.yml:87`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-01 | `pytest -rs tests/` reports zero import-masking module-level skips | collection | `.venv/bin/python -m pytest --collect-only -q tests/ -rs \| grep -c "SKIPPED.*allow_module_level"` combined with manual review that any remaining SKIPPEDs are file-presence guards, not ImportError masks | ❌ Wave 0 — no automated distinguishing check exists yet beyond the new AST guard itself |
| TEST-01 | `tests/test_parse_scoring_response.py` deleted, no collection error/skip for that path | collection | `.venv/bin/python -m pytest --collect-only -q tests/ 2>&1 \| tail -5` (baseline today: `4536 tests collected`, 0 errors — verified this session; re-run after deletion and confirm count drops by exactly 19 with 0 errors) | N/A — deletion, not a new file |
| TEST-02 | Guard fails when an import-masking module-level skip is reintroduced | unit (self-test) + manual scratch check | `.venv/bin/python -m pytest tests/test_no_import_masking_skips.py -v` (must include a permanent self-test asserting the detector flags a constructed bad-pattern fixture — see "guard the guard" scratch-check proof below) | ❌ Wave 0 — new file |
| TEST-03 | `ruff format --check src/ tests/` (CI) and pre-commit's `ruff-format` hook agree on every file | manual/CI parity | `.venv/bin/ruff format --check src/ tests/` (CI-equivalent, once pinned) vs. `pre-commit run ruff-format --all-files` (do **not** run today without stashing first — it reformats in place; only run after the version pin lands, on a clean tree, to confirm zero diff) | N/A — parity property, proven by construction (both invocations now resolve the same pinned version) once TEST-04's guard passes |
| TEST-03 | `_alembic` exclude preserved | regression | `.venv/bin/ruff check src/career_os/_alembic/versions/<any-file>.py` after adding `force-exclude = true` — should report **0 errors** (today, without the fix, it reports 4+ on the sampled file — verified this session) | ❌ Wave 0 — `force-exclude = true` not yet added |
| TEST-04 | Guard fails when the pre-commit rev and pyproject pin drift apart | unit (self-test) + manual scratch check | `.venv/bin/python -m pytest tests/test_toolchain_pins.py -v` (must include a permanent self-test asserting the parser/comparator fails against constructed mismatched fixtures — see scratch-check proof below) | ❌ Wave 0 — new file |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_no_import_masking_skips.py tests/test_toolchain_pins.py -v` (fast, targeted)
- **Per wave merge:** `pytest tests/ -v --tb=short -m "not eval" --cov=src/career_os --cov-report=xml` (full backend suite, matches CI) + `.venv/bin/ruff check src/ tests/` + `.venv/bin/ruff format --check src/ tests/`
- **Phase gate:** Full CI green (`backend`, `frontend`, `extension`, `actionlint`, `review-trailers` all pass — this phase touches none of `frontend`/`extension`/`actionlint`/`review-trailers`, so only `backend` is expected to change status)

### Wave 0 Gaps
- [ ] `tests/test_no_import_masking_skips.py` — new file, covers TEST-02 (and, structurally, re-proves TEST-01 stays fixed if the deleted file were ever reintroduced)
- [ ] `tests/test_toolchain_pins.py` — new file, covers TEST-04
- [ ] `force-exclude = true` under `[tool.ruff]` in `pyproject.toml` — not a test file, but a required config change for TEST-03's "_alembic exclude preserved" criterion to actually hold under pre-commit's invocation shape (see Pitfall 3)

### The two "scratch check" proofs (success criteria 3 and 5 require these explicitly)

**TEST-02 scratch check (import-masking skip reintroduction):**
1. Implement the detector as a pure function (`find_import_masking_skips(path: Path) -> list[str]`, per Pattern 2) so it can be called against an arbitrary path, not just a fixed `tests/` glob.
2. Permanent self-test (runs every CI execution, "guards the guard"): use pytest's `tmp_path` fixture to write a file containing exactly the anti-pattern (`try: import not_a_real_module \n except ImportError: \n import pytest; pytest.skip("x", allow_module_level=True)`), call the detector against it, assert the return value is non-empty.
3. Live manual proof during phase execution (satisfies the literal "deliberate reintroduction in a scratch check" wording): temporarily re-add the exact `try/except ImportError: pytest.skip(...)` block removed from `tests/test_parse_scoring_response.py` into a throwaway file under `tests/` (e.g. `tests/_scratch_reintro_check.py`), run `pytest tests/test_no_import_masking_skips.py -v` and observe it FAIL, then delete the throwaway file and re-run to observe it PASS. Do not commit the throwaway file.

**TEST-04 scratch check (pin drift reintroduction):**
1. Implement the comparator as a pure function (`get_pyproject_ruff_pin() -> str`, `get_precommit_ruff_rev() -> str`, plus an equality assertion) so both halves can be independently constructed for a self-test.
2. Permanent self-test: use `tmp_path` to write a fake `pyproject.toml` with `ruff==1.0.0` and a fake `.pre-commit-config.yaml` with `rev: v2.0.0` under the ruff-pre-commit block, call the parse+compare functions against the tmp files, assert they raise/report a mismatch.
3. Live manual proof during phase execution: `git status` clean, edit `.pre-commit-config.yaml`'s `rev:` for `astral-sh/ruff-pre-commit` to a different value than `pyproject.toml`'s pin, run `pytest tests/test_toolchain_pins.py -v` and observe it FAIL, then `git checkout -- .pre-commit-config.yaml` (or restore via editor) and re-run to observe it PASS. Confirm `git status` is clean again before continuing.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Phase touches test infra and CI/dev tooling only — no auth surface |
| V3 Session Management | No | Same |
| V4 Access Control | No | Same |
| V5 Input Validation | No | Same — the AST/TOML/YAML parsing this phase adds runs only against trusted, repo-owned files (`tests/*.py`, `pyproject.toml`, `.pre-commit-config.yaml`), never untrusted user input |
| V6 Cryptography | No | Same |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Supply-chain drift (a build tool resolving a different, potentially-compromised version between two invocation paths) | Tampering (in the general sense — not this phase's `ruff` case specifically, since ruff is fetched from PyPI/GitHub mirrors over the existing trusted pipeline) | This phase's own fix (pin + drift guard) is itself the mitigation for its narrow case; broader supply-chain integrity (`npm audit signatures`, `pip-audit`) is already covered elsewhere in CI and is unaffected by this phase |

Not otherwise applicable — this phase adds no new request-handling, no new user input parsing, and no new external network calls.

## Sources

### Primary (HIGH confidence)
- Direct repo reads this session: `tests/test_parse_scoring_response.py`, `tests/test_batch_apply_browser.py`, `tests/test_batch_apply_overlay.py`, `tools/tests/test_config_loaders.py`, `tests/test_provider_contract.py`, `src/career_os/ai/openrouter_provider.py`, `src/career_os/schemas/ai.py`, `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.github/workflows/secret-scan.yml`
- Direct command execution this session: `pytest --collect-only`, `ruff check`/`ruff format --check` (multiple invocation shapes), `ruff --version`, `pip index versions ruff`, `pip show pyyaml`, `python --version`, `gh run list`/`gh run view --log`

### Secondary (MEDIUM confidence)
- [GitHub Changelog: Dependabot now supports pre-commit hooks](https://github.blog/changelog/2026-03-10-dependabot-now-supports-pre-commit-hooks/) — confirms `package-ecosystem: pre-commit` is real and supported (announced 2026-03-10), validating the ticket's own claim that Dependabot can auto-bump `.pre-commit-config.yaml` revs
- [flake8-pytest-style issue #188](https://github.com/m-burst/flake8-pytest-style/issues/188) — confirms no builtin rule exists for this anti-pattern, and that even a hypothetical future rule would need the same `except ImportError` context-awareness this research recommends

### Tertiary (LOW confidence)
- None — every claim in this document is either a direct repo/command observation this session or a cited official source; no WebSearch-only, unverified claims were used

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; the only "stack" decision (ruff exact version) is explicitly flagged as needing re-verification at execution time, not a stale guess
- Architecture: HIGH — reuses an existing, read, in-repo pattern (`tests/test_provider_contract.py`) rather than inventing a new one
- Pitfalls: HIGH — all three pitfalls (false-positive guard, stale version pin, `_alembic` force-exclude gap) were reproduced with direct commands this session, not inferred

**Research date:** 2026-09-29
**Valid until:** 7 days for the exact ruff version number (fast-moving, weekly releases — re-verify before use); 30 days for everything else (architecture/pattern recommendations, dead-code findings, CI structure)
