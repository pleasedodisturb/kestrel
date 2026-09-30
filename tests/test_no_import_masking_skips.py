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

import pytest

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


def _handler_is_broad(handler: ast.ExceptHandler) -> bool:
    """True for a bare ``except:`` or one that catches Exception/BaseException."""
    if handler.type is None:
        return True
    return isinstance(handler.type, ast.Name) and handler.type.id in ("Exception", "BaseException")


def _body_contains_import(body: list[ast.stmt]) -> bool:
    """True if any statement in ``body`` performs an import.

    Covers ``import``/``from ... import``, ``importlib.import_module(...)``,
    and the builtin ``__import__(...)``.
    """
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return True
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "import_module":
                    return True
                if isinstance(func, ast.Name) and func.id == "__import__":
                    return True
    return False


def _handler_masks_imports(try_node: ast.Try, handler: ast.ExceptHandler) -> bool:
    """True if this handler masks an import failure.

    Two cases (DEC-10): the handler type names ImportError/ModuleNotFoundError
    (bare Name, dotted Attribute, or either inside a Tuple), or the handler is
    broad (bare/Exception/BaseException) and the try body itself imports.
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

    if _names_import_error(handler.type):
        return True
    return _handler_is_broad(handler) and _body_contains_import(try_node.body)


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


def _is_first_party_importorskip(
    node: ast.AST,
    names: tuple[frozenset[str], frozenset[str], frozenset[str]],
    first_party: frozenset[str],
) -> bool:
    """True for ``pytest.importorskip("first.party.module")`` at any scope.

    Flagged wherever it appears in the file, because it is itself the masking
    construct (DEC-10) — unlike the except-ImportError shapes above, it needs
    no enclosing Try/handler.
    """
    pytest_modules, _skip_names, importorskip_names = names
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    is_pytest_importorskip = (
        isinstance(func, ast.Attribute)
        and func.attr == "importorskip"
        and isinstance(func.value, ast.Name)
        and func.value.id in pytest_modules
    )
    is_bare_importorskip = isinstance(func, ast.Name) and func.id in importorskip_names
    if not (is_pytest_importorskip or is_bare_importorskip):
        return False
    if not node.args:
        return False
    first_arg = node.args[0]
    if not (isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str)):
        return False
    return first_arg.value.split(".")[0] in first_party


def find_import_masking_skips(path: Path, first_party: frozenset[str] = FIRST_PARTY) -> list[str]:
    """Return sorted "relative/path:lineno" strings for import-masking skips.

    Parses ``path`` with :mod:`ast`. An unparseable file raises ``SyntaxError``
    rather than being silently treated as having no findings — a file this
    guard cannot read must never be reported as clean. The relative-path
    formatting falls back to the absolute path for a fixture file that lives
    outside ``_REPO_ROOT`` (e.g. a self-test's ``tmp_path`` fixture).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = _pytest_names(tree)
    violations: set[str] = set()

    def _report(lineno: int) -> None:
        try:
            rel = path.relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            rel = path.as_posix()
        violations.add(f"{rel}:{lineno}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if not _handler_masks_imports(node, handler):
                    continue
                for sub in ast.walk(handler):
                    if _is_module_level_skip(sub, names):
                        _report(sub.lineno)
        if _is_first_party_importorskip(node, names, first_party):
            _report(node.lineno)

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


# ---------------------------------------------------------------------------
# Guard-the-guard: fixture-based self-tests (G-1382, TEST-02 hardening)
# ---------------------------------------------------------------------------


def _write_fixture(tmp_path: Path, source: str) -> Path:
    """Write ``source`` to a throwaway .py file under tmp_path and return its path."""
    path = tmp_path / "fixture.py"
    path.write_text(source, encoding="utf-8")
    return path


_FLAG_CASES = [
    pytest.param(
        (
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "import pytest\n"
            "\n"
            'sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))\n'
            "\n"
            "try:\n"
            "    from job_scorer import parse_scoring_response\n"
            "except ImportError:\n"
            "    pytest.skip(\n"
            '        "parse_scoring_response removed from tools/job_scorer.py",\n'
            "        allow_module_level=True,\n"
            "    )\n"
        ),
        11,
        id="removed_block",
    ),
    pytest.param(
        (
            "import pytest\n"
            "\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ModuleNotFoundError:\n"
            '    pytest.skip("x", allow_module_level=True)\n'
        ),
        6,
        id="module_not_found",
    ),
    pytest.param(
        (
            "import pytest\n"
            "\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except (ImportError, AttributeError):\n"
            '    pytest.skip("x", allow_module_level=True)\n'
        ),
        6,
        id="tuple_handler",
    ),
    pytest.param(
        (
            "import pytest as pt\n"
            "\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    pt.skip("x", allow_module_level=True)\n'
        ),
        6,
        id="pytest_alias",
    ),
    pytest.param(
        (
            "from pytest import skip as pyskip\n"
            "\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    pyskip("x", allow_module_level=True)\n'
        ),
        6,
        id="from_import_skip",
    ),
    pytest.param(
        (
            "import pytest\n"
            "\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    if True:\n"
            '        pytest.skip("x", allow_module_level=True)\n'
        ),
        7,
        id="nested_if_in_handler",
    ),
    pytest.param(
        (
            "import pytest\n"
            "\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except Exception:\n"
            '    pytest.skip("x", allow_module_level=True)\n'
        ),
        6,
        id="broad_except_around_import",
    ),
    pytest.param(
        (
            "import pytest\n"
            "\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except:\n"
            '    pytest.skip("x", allow_module_level=True)\n'
        ),
        6,
        id="bare_except_around_import",
    ),
    pytest.param(
        (
            "import importlib\n"
            "import pytest\n"
            "\n"
            "try:\n"
            '    importlib.import_module("not_a_real_module")\n'
            "except Exception:\n"
            '    pytest.skip("x", allow_module_level=True)\n'
        ),
        7,
        id="broad_except_around_importlib",
    ),
    pytest.param(
        ('import pytest\n\npytest.importorskip("career_os.services.geo")\n'),
        3,
        id="first_party_importorskip_package",
    ),
    pytest.param(
        ('import pytest\n\npytest.importorskip("job_scorer")\n'),
        3,
        id="first_party_importorskip_tools_module",
    ),
]


@pytest.mark.parametrize("source, expected_line", _FLAG_CASES)
def test_detector_flags_masking_variants(tmp_path: Path, source: str, expected_line: int) -> None:
    """Every spelling variant of the import-masking skip yields exactly one hit."""
    fixture = _write_fixture(tmp_path, source)
    violations = find_import_masking_skips(fixture)
    assert len(violations) == 1
    assert violations[0].endswith(f":{expected_line}")


_IGNORE_CASES = [
    pytest.param(
        (
            "from pathlib import Path\n"
            "\n"
            "import pytest\n"
            "\n"
            'path = Path("/nonexistent")\n'
            "if not path.exists():\n"
            '    pytest.skip("not found", allow_module_level=True)\n'
        ),
        id="file_presence_guard",
    ),
    pytest.param(
        ('import pytest\n\npytest.importorskip("hypothesis", reason="optional")\n'),
        id="third_party_importorskip",
    ),
    pytest.param(
        (
            "import pytest\n"
            "\n"
            "try:\n"
            "    x = 1 / 0\n"
            "except Exception:\n"
            "    pass\n"
            "\n"
            'pytest.skip("unrelated", allow_module_level=True)\n'
        ),
        id="broad_except_without_import",
    ),
]


@pytest.mark.parametrize("source", _IGNORE_CASES)
def test_detector_ignores_legitimate_skips(tmp_path: Path, source: str) -> None:
    """Legitimate skip shapes must never be flagged as import-masking."""
    fixture = _write_fixture(tmp_path, source)
    violations = find_import_masking_skips(fixture)
    assert violations == []
    assert fixture.exists()


def test_detector_raises_on_unparseable_file(tmp_path: Path) -> None:
    """An unparseable file must raise, never silently report no findings."""
    bad = _write_fixture(tmp_path, "def broken(:\n    pass\n")
    with pytest.raises(SyntaxError) as exc_info:
        find_import_masking_skips(bad)
    assert exc_info.type is SyntaxError
    assert exc_info.value.filename == str(bad)


def test_real_file_presence_guards_are_not_flagged() -> None:
    """The three legitimate real file-presence guards must never be flagged."""
    guarded = [
        _REPO_ROOT / "tests" / "test_batch_apply_browser.py",
        _REPO_ROOT / "tests" / "test_batch_apply_overlay.py",
        _REPO_ROOT / "tools" / "tests" / "test_config_loaders.py",
    ]
    for path in guarded:
        assert path in SWEPT_FILES
        assert find_import_masking_skips(path) == []


def test_sweep_covers_both_roots_and_subpackages() -> None:
    """Guard the guard: the sweep must not silently shrink across roots/subpackages."""
    expected = [
        _REPO_ROOT / "tests" / "test_provider_contract.py",
        _REPO_ROOT / "tools" / "tests" / "test_config_loaders.py",
        _REPO_ROOT / "tests" / "property" / "test_state_machine.py",
        _REPO_ROOT / "tests" / "fuzz" / "test_api_fuzz.py",
        _REPO_ROOT / "tests" / "conftest.py",
        _REPO_ROOT / "tests" / "test_no_import_masking_skips.py",
    ]
    missing = [p for p in expected if p not in SWEPT_FILES]
    assert not missing, f"sweep missing expected files: {missing}"
    assert not any("__pycache__" in p.parts for p in SWEPT_FILES)


def test_first_party_names_are_derived_from_the_repo() -> None:
    """FIRST_PARTY must be derived from the repo layout, not a hand-written list."""
    assert {"career_os", "tests", "job_scorer"} <= FIRST_PARTY
    assert not ({"hypothesis", "mcp"} & FIRST_PARTY)
