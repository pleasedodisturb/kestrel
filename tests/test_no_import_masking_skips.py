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
mechanism spelled differently). Two further variants of the same anti-pattern
are also flagged (WR-01 hardening): a ``raise unittest.SkipTest(...)`` inside
an import-masking handler, and the flag-variable pattern — an import-masking
handler that assigns a name (e.g. ``_HAVE_MODULE = False``) which a
``pytest.mark.skipif(...)``/``skipif(...)`` condition later reads, whether via
a module-level ``pytestmark = ...`` assignment or as a decorator on a test
function or class.

What is NOT flagged: the legitimate module-level file-presence guards in this
repo (``if not path.exists(): pytest.skip(..., allow_module_level=True)``), and
``pytest.importorskip(...)`` of a genuinely optional third-party package (this
is pytest's own sanctioned mechanism for an environment-dependent test suite).

The remedy for a broken import is always the same: import directly, with no
try/except around it, so a broken import fails collection loudly instead of
looking like a deliberate, reasoned skip.

Not detected (recorded rather than silently ignored — see the Task 2/WR-01
hardening passes for the full spelling-variant coverage this module does
implement):
- a per-test ``pytest.skip(...)`` (no ``allow_module_level``) inside an
  ``except ImportError:``;
- ``pytest.importorskip(...)`` of third-party modules (this is the sanctioned
  use of the mechanism, not the anti-pattern).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

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


class _ImportNames(NamedTuple):
    """Aliases this file binds for the pytest/unittest skip machinery we watch."""

    pytest_modules: frozenset[str]
    skip_names: frozenset[str]
    importorskip_names: frozenset[str]
    mark_modules: frozenset[str]
    unittest_modules: frozenset[str]
    skiptest_names: frozenset[str]


def _pytest_names(tree: ast.Module) -> _ImportNames:
    """Return the alias sets used to recognise pytest/unittest skip constructs.

    Handles a plain ``import pytest`` (optionally aliased); a from-import of
    ``skip``/``importorskip``/``mark`` from pytest (optionally aliased, e.g.
    ``from pytest import mark as m``); a plain ``import unittest`` (optionally
    aliased); and a from-import of ``SkipTest`` from unittest (optionally
    aliased).
    """
    pytest_modules: set[str] = set()
    skip_names: set[str] = set()
    importorskip_names: set[str] = set()
    mark_modules: set[str] = set()
    unittest_modules: set[str] = set()
    skiptest_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    pytest_modules.add(alias.asname or alias.name)
                elif alias.name == "unittest":
                    unittest_modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
            for alias in node.names:
                if alias.name == "skip":
                    skip_names.add(alias.asname or alias.name)
                elif alias.name == "importorskip":
                    importorskip_names.add(alias.asname or alias.name)
                elif alias.name == "mark":
                    mark_modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "unittest":
            for alias in node.names:
                if alias.name == "SkipTest":
                    skiptest_names.add(alias.asname or alias.name)
    return _ImportNames(
        pytest_modules=frozenset(pytest_modules),
        skip_names=frozenset(skip_names),
        importorskip_names=frozenset(importorskip_names),
        mark_modules=frozenset(mark_modules),
        unittest_modules=frozenset(unittest_modules),
        skiptest_names=frozenset(skiptest_names),
    )


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


def _handler_masks_imports(try_node: ast.Try | ast.TryStar, handler: ast.ExceptHandler) -> bool:
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


def _is_module_level_skip(node: ast.AST, names: _ImportNames) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    is_pytest_skip = (
        isinstance(func, ast.Attribute)
        and func.attr == "skip"
        and isinstance(func.value, ast.Name)
        and func.value.id in names.pytest_modules
    )
    is_bare_skip = isinstance(func, ast.Name) and func.id in names.skip_names
    if not (is_pytest_skip or is_bare_skip):
        return False
    for kw in node.keywords:
        if kw.arg == "allow_module_level":
            return not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
    return False


def _is_unittest_skiptest_raise(node: ast.AST, names: _ImportNames) -> bool:
    """True for ``raise unittest.SkipTest(...)`` (call or bare) via a recognised alias.

    Treated the same as ``pytest.skip(..., allow_module_level=True)`` when it
    appears inside an import-masking handler (WR-01): both cause the module's
    tests to be silently skipped rather than fail collection loudly.
    """
    if not isinstance(node, ast.Raise) or node.exc is None:
        return False
    ref: ast.expr = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    is_unittest_skiptest = (
        isinstance(ref, ast.Attribute)
        and ref.attr == "SkipTest"
        and isinstance(ref.value, ast.Name)
        and ref.value.id in names.unittest_modules
    )
    is_bare_skiptest = isinstance(ref, ast.Name) and ref.id in names.skiptest_names
    return is_unittest_skiptest or is_bare_skiptest


def _handler_assigned_names(handler: ast.ExceptHandler) -> set[str]:
    """Names assigned anywhere in ``handler``'s body (the flag-variable pattern, WR-01).

    E.g. ``except ImportError: _HAVE_MODULE = False`` — collected so a later
    ``pytest.mark.skipif(not _HAVE_MODULE, ...)`` reading this name can be
    traced back to the import-masking handler that set it.
    """
    assigned: set[str] = set()
    for sub in ast.walk(handler):
        if isinstance(sub, ast.Assign):
            for target in sub.targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
        elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
            assigned.add(sub.target.id)
    return assigned


def _is_skipif_call(node: ast.AST, names: _ImportNames) -> bool:
    """True for ``pytest.mark.skipif(...)`` (or a ``mark``-alias's ``.skipif(...)``)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "skipif"):
        return False
    value = func.value
    is_pytest_mark_skipif = (
        isinstance(value, ast.Attribute)
        and value.attr == "mark"
        and isinstance(value.value, ast.Name)
        and value.value.id in names.pytest_modules
    )
    is_mark_alias_skipif = isinstance(value, ast.Name) and value.id in names.mark_modules
    return is_pytest_mark_skipif or is_mark_alias_skipif


_NEW_SCOPE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _module_scope_nodes(nodes: list[ast.AST]) -> list[ast.AST]:
    """Every node that executes in module scope, descending through compound statements.

    An assignment or call nested in a module-level ``if``/``try``/``with``/loop
    still runs at import time and still binds module globals such as
    ``pytestmark``. Function, class, and lambda bodies open a new scope and are
    not descended into (decorators are handled separately by the caller).
    """
    found: list[ast.AST] = []
    for node in nodes:
        found.append(node)
        if not isinstance(node, _NEW_SCOPE):
            found.extend(_module_scope_nodes(list(ast.iter_child_nodes(node))))
    return found


def _skipif_conditions(call: ast.Call) -> list[ast.expr]:
    """The condition expressions pytest evaluates for a ``skipif(...)`` call.

    Mirrors pytest's ``evaluate_skip_marks``: a ``condition=`` keyword wins;
    otherwise every positional argument is a condition (any true one skips).
    A string condition is evaluated by pytest against the module's globals, so
    it is parsed here into the expression it stands for. An unparseable string
    makes pytest fail collection loudly, so it contributes no names.
    """
    keyword = next((kw.value for kw in call.keywords if kw.arg == "condition"), None)
    raw = [keyword] if keyword is not None else list(call.args)
    conditions: list[ast.expr] = []
    for cond in raw:
        if isinstance(cond, ast.Constant) and isinstance(cond.value, str):
            try:
                conditions.append(ast.parse(cond.value, mode="eval").body)
            except SyntaxError:
                continue
        else:
            conditions.append(cond)
    return conditions


def _condition_references_names(expr: ast.expr, flag_names: frozenset[str]) -> bool:
    """True if any ``Name`` node inside ``expr`` refers to one of ``flag_names``."""
    return any(isinstance(sub, ast.Name) and sub.id in flag_names for sub in ast.walk(expr))


def _find_masking_skipif_uses(
    tree: ast.Module, names: _ImportNames, flag_names: frozenset[str]
) -> list[int]:
    """Line numbers of ``skipif(...)`` calls whose condition reads a masked flag (WR-01).

    Covers both shapes a masked flag is read in: a module-scope
    ``pytestmark = pytest.mark.skipif(...)`` assignment (plain, annotated, or
    augmented, including one nested in a module-level ``if``/``try``/``with``
    — see ``_module_scope_nodes``), and a ``skipif(...)`` used as a decorator
    on any function or class in the file (a decorator is evaluated at
    module-collection time regardless of nesting, so it needs no scope
    restriction).
    """
    if not flag_names:
        return []
    module_scope_ids = {id(node) for node in _module_scope_nodes(list(tree.body))}
    lines: list[int] = []
    for node in ast.walk(tree):
        exprs: list[ast.expr] = []
        in_module_scope = id(node) in module_scope_ids
        if isinstance(node, ast.Assign) and in_module_scope:
            if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
                exprs.append(node.value)
        elif isinstance(node, ast.AnnAssign | ast.AugAssign) and in_module_scope:
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "pytestmark"
                and node.value is not None
            ):
                exprs.append(node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            exprs.extend(node.decorator_list)
        for expr in exprs:
            for sub in ast.walk(expr):
                if _is_skipif_call(sub, names) and any(
                    _condition_references_names(cond, flag_names)
                    for cond in _skipif_conditions(sub)
                ):
                    lines.append(sub.lineno)
    return lines


def _is_first_party_importorskip(
    node: ast.AST,
    names: _ImportNames,
    first_party: frozenset[str],
) -> bool:
    """True for ``pytest.importorskip("first.party.module")`` at any scope.

    Flagged wherever it appears in the file, because it is itself the masking
    construct (DEC-10) — unlike the except-ImportError shapes above, it needs
    no enclosing Try/handler.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    is_pytest_importorskip = (
        isinstance(func, ast.Attribute)
        and func.attr == "importorskip"
        and isinstance(func.value, ast.Name)
        and func.value.id in names.pytest_modules
    )
    is_bare_importorskip = isinstance(func, ast.Name) and func.id in names.importorskip_names
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

    masked_flag_names: set[str] = set()

    for node in ast.walk(tree):
        # ast.TryStar (try/except*) carries the same handler shape as ast.Try.
        if isinstance(node, ast.Try | ast.TryStar):
            for handler in node.handlers:
                if not _handler_masks_imports(node, handler):
                    continue
                for sub in ast.walk(handler):
                    if _is_module_level_skip(sub, names):
                        _report(sub.lineno)
                    if _is_unittest_skiptest_raise(sub, names):
                        _report(sub.lineno)
                masked_flag_names |= _handler_assigned_names(handler)
        if _is_first_party_importorskip(node, names, first_party):
            _report(node.lineno)

    flags = frozenset(masked_flag_names)
    for lineno in _find_masking_skipif_uses(tree, names, flags):
        _report(lineno)

    # A module-scope `if`/`while` gated on a masked flag that skips the module
    # (e.g. `if not HAVE_MODULE: pytest.skip(..., allow_module_level=True)`)
    # is the same masking as a skip inside the handler itself.
    if flags:
        for node in _module_scope_nodes(list(tree.body)):
            if not (
                isinstance(node, ast.If | ast.While)
                and _condition_references_names(node.test, flags)
            ):
                continue
            for sub in _module_scope_nodes(node.body + node.orelse):
                if _is_module_level_skip(sub, names) or _is_unittest_skiptest_raise(sub, names):
                    _report(sub.lineno)

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
    # WR-01: the flag-variable pattern — an except-ImportError handler sets a
    # boolean that a module-level `pytestmark = pytest.mark.skipif(...)` later
    # reads. Exact fixture reproduced from 06-REVIEW.md WR-01.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="module removed")\n'
            "def test_something():\n"
            "    assert not_a_real_module.thing() == 1\n"
        ),
        7,
        id="flag_variable_pytestmark",
    ),
    # WR-01: same flag-variable pattern, but the skipif is a decorator on the
    # test function rather than a module-level `pytestmark = ...` assignment.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "\n"
            '@pytest.mark.skipif(not _HAVE_MODULE, reason="module removed")\n'
            "def test_something():\n"
            "    assert not_a_real_module.thing() == 1\n"
        ),
        8,
        id="flag_variable_skipif_decorator",
    ),
    # Codex review: pytest reads the `condition=` keyword, any positional
    # condition (not just the first), and string conditions evaluated
    # against module globals. Each spelling must still be caught.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            'pytestmark = pytest.mark.skipif(condition=not _HAVE_MODULE, reason="x")\n'
        ),
        7,
        id="flag_variable_condition_keyword",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            'pytestmark = pytest.mark.skipif(False, not _HAVE_MODULE, reason="x")\n'
        ),
        7,
        id="flag_variable_second_positional_condition",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            'pytestmark = pytest.mark.skipif("not _HAVE_MODULE", reason="x")\n'
        ),
        7,
        id="flag_variable_string_condition",
    ),
    # Codex review: module scope is more than tree.body — an assignment or skip
    # nested in a module-level `if` still runs at import time.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "if not _HAVE_MODULE:\n"
            '    pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        8,
        id="flag_variable_conditional_pytestmark",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "if not _HAVE_MODULE:\n"
            '    pytest.skip("x", allow_module_level=True)\n'
        ),
        8,
        id="flag_variable_conditional_module_skip",
    ),
    # WR-01: a module-level `raise unittest.SkipTest(...)` inside an
    # import-masking handler. Exact fixture reproduced from 06-REVIEW.md WR-01.
    pytest.param(
        (
            "import unittest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    raise unittest.SkipTest("module removed")\n'
            "def test_something():\n"
            "    assert not_a_real_module.thing() == 1\n"
        ),
        5,
        id="unittest_skiptest_raise",
    ),
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except* ImportError:\n"
            '    pytest.skip("module removed", allow_module_level=True)\n'
        ),
        5,
        id="except_star_import_error",
    ),
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except* Exception:\n"
            '    pytest.skip("module removed", allow_module_level=True)\n'
        ),
        5,
        id="except_star_broad_handler",
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
    # WR-01 negative: a skipif condition reading a flag that was NOT set by an
    # import-masking handler (no try/except at all here) must not be flagged.
    pytest.param(
        (
            "import pytest\n"
            "SOME_OTHER_FLAG = True\n"
            'pytestmark = pytest.mark.skipif(not SOME_OTHER_FLAG, reason="unrelated")\n'
            "def test_something():\n"
            "    assert True\n"
        ),
        id="skipif_flag_not_from_handler",
    ),
    # WR-01 negative: an import-masking handler assigns a flag, but the
    # skipif elsewhere reads a *different*, unrelated flag — must not be
    # flagged (proves the match is by specific name, not "any skipif exists
    # somewhere in a file that also has a masking handler").
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "UNRELATED_FLAG = True\n"
            'pytestmark = pytest.mark.skipif(not UNRELATED_FLAG, reason="unrelated")\n'
            "def test_something():\n"
            "    assert not_a_real_module.thing() == 1\n"
        ),
        id="skipif_references_unrelated_flag",
    ),
    # Scope negative: a `pytestmark` bound inside a function is a local, not
    # the module's marker, so pytest never applies it.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "def helper():\n"
            '    pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "    return pytestmark\n"
        ),
        id="function_local_pytestmark",
    ),
    # WR-01 negative: the handler masks an import but raises a non-SkipTest
    # exception — this is the desired remedy (fail loudly), not a masking
    # pattern, so it must not be flagged.
    pytest.param(
        (
            "import pytest\n"
            "\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    raise RuntimeError("boom")\n'
        ),
        id="handler_raises_non_skiptest",
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
