"""Guard against import-masking module-level pytest skips (G-1382, TEST-02).

G-1382: ``tests/test_parse_scoring_response.py`` wrapped
``from job_scorer import parse_scoring_response`` in a ``try/except ImportError``
whose handler called ``pytest.skip(..., allow_module_level=True)``. The function
had been removed long ago, so all 19 tests in that file were silently skipped —
never run, never reported as a failure. G-1348 found and fixed the sibling case
in ``tests/test_openai_provider.py``. This is the same anti-pattern; this guard
makes it structural so it cannot recur unnoticed.

What is flagged: a ``pytest.skip(...)`` call carrying the ``allow_module_level``
keyword, sitting inside an ``except`` handler that catches ``ImportError`` (or a
spelling variant of the same idea — see below), OR a first-party
``pytest.importorskip(...)`` at module level (which is the same masking
mechanism spelled differently).

What is NOT flagged: the legitimate module-level file-presence guards in this
repo (``if not path.exists(): pytest.skip(..., allow_module_level=True)``), and
``pytest.importorskip(...)`` of a genuinely optional third-party package (this
is pytest's own sanctioned mechanism for an environment-dependent test suite).

The remedy for a broken import is always the same: import directly, with no
try/except around it, so a broken import fails collection loudly instead of
looking like a deliberate, reasoned skip.

Not detected (outside TEST-02's named construct, recorded rather than silently
ignored — see the Task 2 hardening pass for the full spelling-variant coverage
this module does implement):
- the flag-variable pattern, where an except-ImportError branch sets a boolean
  that ``pytest.mark.skipif`` later reads;
- a module-level ``raise unittest.SkipTest(...)``;
- a per-test ``pytest.skip(...)`` (no ``allow_module_level``) inside an
  ``except ImportError:``;
- ``pytest.importorskip(...)`` of third-party modules (this is the sanctioned
  use of the mechanism, not the anti-pattern).
"""

from __future__ import annotations

import ast
from pathlib import Path

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


def _pytest_names(tree: ast.Module) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """Return (pytest module names, pytest.skip names, pytest.importorskip names).

    Handles a plain ``import pytest`` (optionally aliased), and a from-import of
    ``skip``/``importorskip`` (optionally aliased).
    """
    pytest_modules: set[str] = set()
    skip_names: set[str] = set()
    importorskip_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    pytest_modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
            for alias in node.names:
                if alias.name == "skip":
                    skip_names.add(alias.asname or alias.name)
                elif alias.name == "importorskip":
                    importorskip_names.add(alias.asname or alias.name)
    return frozenset(pytest_modules), frozenset(skip_names), frozenset(importorskip_names)


def _handler_masks_imports(try_node: ast.Try, handler: ast.ExceptHandler) -> bool:
    """True if this handler catches ImportError-like exceptions.

    This is the tracer's committed detector: bare Name, dotted Attribute ending
    in ImportError/ModuleNotFoundError, or either inside a Tuple.
    """

    def _names_import_error(t: ast.expr | None) -> bool:
        if t is None:
            return False
        if isinstance(t, ast.Name):
            return t.id in ("ImportError", "ModuleNotFoundError")
        if isinstance(t, ast.Attribute):
            return t.attr in ("ImportError", "ModuleNotFoundError")
        if isinstance(t, ast.Tuple):
            return any(_names_import_error(elt) for elt in t.elts)
        return False

    return _names_import_error(handler.type)


def _is_module_level_skip(
    node: ast.AST, names: tuple[frozenset[str], frozenset[str], frozenset[str]]
) -> bool:
    pytest_modules, skip_names, _importorskip_names = names
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    is_pytest_skip = (
        isinstance(func, ast.Attribute)
        and func.attr == "skip"
        and isinstance(func.value, ast.Name)
        and func.value.id in pytest_modules
    )
    is_bare_skip = isinstance(func, ast.Name) and func.id in skip_names
    if not (is_pytest_skip or is_bare_skip):
        return False
    for kw in node.keywords:
        if kw.arg == "allow_module_level":
            return not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
    return False


def find_import_masking_skips(path: Path, first_party: frozenset[str] = FIRST_PARTY) -> list[str]:
    """Return sorted "relative/path:lineno" strings for import-masking skips.

    Parses ``path`` with :mod:`ast`. An unparseable file raises ``SyntaxError``
    rather than being silently treated as having no findings — a file this
    guard cannot read must never be reported as clean.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = _pytest_names(tree)
    violations: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _handler_masks_imports(node, handler):
                continue
            for sub in ast.walk(handler):
                if _is_module_level_skip(sub, names):
                    rel = path.relative_to(_REPO_ROOT).as_posix()
                    violations.add(f"{rel}:{sub.lineno}")

    return sorted(violations)


def test_no_import_masking_module_level_skips() -> None:
    """No swept file may mask an ImportError behind a module-level pytest skip.

    Sweeps every ``*.py`` under ``tests/`` and ``tools/tests/`` (recursively)
    and asserts the combined violation list is empty. A broken import must
    fail collection loudly, never look like a deliberate skip.
    """
    assert _REPO_ROOT / "tests" / "test_provider_contract.py" in SWEPT_FILES

    all_violations: list[str] = []
    for path in SWEPT_FILES:
        all_violations.extend(find_import_masking_skips(path))

    assert all_violations == [], (
        "import-masking module-level skip(s) found: "
        + ", ".join(sorted(all_violations))
        + ". Remedy: import directly, with no try/except-ImportError around it, "
        "so a broken import fails collection loudly instead of looking like a "
        "deliberate, reasoned skip."
    )
