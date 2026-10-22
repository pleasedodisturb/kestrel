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

The general contract (G-1382 review rounds): a skip that only happens because
of a *tainted* value is masking. A name is tainted when an import-masking
handler assigns it, when an import-time assignment derives it from a tainted
name, or when it is assigned inside an import-time branch gated on one. Flagged
are: a ``pytestmark`` (module or class scope, at any nesting) whose value reads
a tainted name; a skip action (module-level skip, ``SkipTest`` raise, skip
mark, or a call to a helper that skips the module) inside a masking handler or
a tainted branch. The ``_FLAG_CASES``/``_IGNORE_CASES`` fixtures are the
input-to-output mapping for this contract, each row confirmed against real
pytest with the import broken.

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
  use of the mechanism, not the anti-pattern);
- known false negatives tracked in G-1974: first-party
  ``importlib.util.find_spec(...)`` checks that use no ``try``, mutation
  through method calls (``FLAGS.update(have=False)``), and skip helpers
  reached through an alias or attribute;
- dynamic namespace access, out of scope: ``exec``/``eval``, and reads or
  writes through ``globals()``/``locals()``/``vars()`` (e.g. ``return
  "mod" in locals()`` after a masked import, or ``globals()["HAVE"] =
  False``). The guard reasons about static bindings only.

Deliberately conservative (may flag code that pytest runs): a rebinding
inside a loop or ``try`` body never clears taint, because it is not
provably executed.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
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


_DEFERRED_SCOPE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _module_scope_nodes(nodes: list[ast.AST]) -> list[ast.AST]:
    """Every node that executes at import time, descending through compound statements.

    An assignment or call nested in a module-level ``if``/``try``/``with``/loop
    still runs at import time and still binds globals such as ``pytestmark``.
    Class bodies also run at import time, and pytest applies a class-level
    ``pytestmark`` to every test method, so they are descended into too.
    Function and lambda bodies only run when called and are skipped, but a
    function's decorators and default values are evaluated at definition time,
    so they are included.
    """
    found: list[ast.AST] = []
    for node in nodes:
        found.append(node)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            eager: list[ast.AST] = [*node.decorator_list, *node.args.defaults]
            eager.extend(d for d in node.args.kw_defaults if d is not None)
            found.extend(_module_scope_nodes(eager))
        elif not isinstance(node, _DEFERRED_SCOPE):
            found.extend(_module_scope_nodes(list(ast.iter_child_nodes(node))))
    return found


# The import-time namespace a node is evaluated in: ``None`` for the module,
# else the ``id()`` of the innermost enclosing ClassDef whose body holds it.
_Scope = int | None


def _import_time_scopes(tree: ast.Module) -> dict[int, _Scope]:
    """Map each node in ``_module_scope_nodes`` to the namespace it is evaluated in.

    A class body is its own namespace; its decorators and bases, like a
    function's decorators and defaults, are evaluated in the enclosing one.
    """
    scopes: dict[int, _Scope] = {}

    def visit(nodes: list[ast.AST], scope: _Scope) -> None:
        for node in nodes:
            scopes[id(node)] = scope
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                eager: list[ast.AST] = [*node.decorator_list, *node.args.defaults]
                eager.extend(d for d in node.args.kw_defaults if d is not None)
                visit(eager, scope)
            elif isinstance(node, ast.ClassDef):
                visit([*node.decorator_list, *node.bases, *node.keywords], scope)
                visit(list(node.body), id(node))
            elif not isinstance(node, _DEFERRED_SCOPE):
                visit(list(ast.iter_child_nodes(node)), scope)

    visit(list(tree.body), None)
    return scopes


class _Namespaces(NamedTuple):
    """Where import-time code is evaluated, and where its assignments bind.

    ``of(node)`` is the namespace an expression is evaluated in. ``binding``
    is where an assignment of ``name`` made in ``scope`` lands: normally the
    same namespace, but a class body that declares ``global name`` binds the
    module global instead.
    """

    scopes: dict[int, _Scope]
    class_globals: dict[int, frozenset[str]]

    def of(self, node: ast.AST) -> _Scope:
        return self.scopes.get(id(node))

    def binding(self, scope: _Scope, name: str) -> _Scope:
        if scope is not None and name in self.class_globals.get(scope, frozenset()):
            return None
        return scope


def _namespaces(tree: ast.Module) -> _Namespaces:
    scopes = _import_time_scopes(tree)
    class_globals: dict[int, set[str]] = {}
    for node in _module_scope_nodes(list(tree.body)):
        where = scopes.get(id(node))
        if isinstance(node, ast.Global) and where is not None:
            class_globals.setdefault(where, set()).update(node.names)
    return _Namespaces(scopes, {k: frozenset(v) for k, v in class_globals.items()})


def _is_skip_mark_ref(node: ast.AST, names: _ImportNames) -> bool:
    """True for ``pytest.mark.skip``/``pytest.mark.skipif`` (or a ``mark`` alias's), called or not."""
    if not (isinstance(node, ast.Attribute) and node.attr in ("skip", "skipif")):
        return False
    value = node.value
    via_pytest = (
        isinstance(value, ast.Attribute)
        and value.attr == "mark"
        and isinstance(value.value, ast.Name)
        and value.value.id in names.pytest_modules
    )
    via_alias = isinstance(value, ast.Name) and value.id in names.mark_modules
    return via_pytest or via_alias


def _skip_helpers(tree: ast.Module, names: _ImportNames) -> frozenset[str]:
    """Names of import-time functions whose body skips the whole module.

    A helper such as ``def _bail(): pytest.skip(..., allow_module_level=True)``
    is harmless until called; a call from a masking handler or a tainted
    branch is the same masking as an inline skip there.
    """
    helpers: set[str] = set()
    for node in _module_scope_nodes(list(tree.body)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and any(
            _is_module_level_skip(sub, names) or _is_unittest_skiptest_raise(sub, names)
            for sub in ast.walk(node)
        ):
            helpers.add(node.name)
    return frozenset(helpers)


def _is_skip_helper_call(node: ast.AST, helpers: frozenset[str]) -> bool:
    return (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in helpers
    )


def _assignment_parts(node: ast.AST) -> tuple[set[str], ast.expr | None]:
    """(names bound, value expression) for an assignment-like node, else (empty, None)."""
    targets: list[ast.expr] = []
    value: ast.expr | None = None
    if isinstance(node, ast.Assign):
        targets, value = list(node.targets), node.value
    elif isinstance(node, ast.AnnAssign | ast.AugAssign | ast.NamedExpr):
        targets, value = [node.target], node.value
    bound = {sub.id for t in targets for sub in ast.walk(t) if isinstance(sub, ast.Name)}
    return bound, value


def _gated_region_ids(scope: list[ast.AST], taint: _Taint, ns: _Namespaces) -> set[int]:
    """ids of import-time nodes that only run because of a tainted ``if``/``while`` test."""
    gated: set[int] = set()
    for node in scope:
        if isinstance(node, ast.If | ast.While) and _condition_references_names(
            node.test, taint.at(node.lineno, ns.of(node))
        ):
            gated |= {id(sub) for sub in _module_scope_nodes(node.body + node.orelse)}
    return gated


def _import_time_taint_seeds(
    tree: ast.Module, ns: _Namespaces
) -> dict[tuple[_Scope, str], set[int]]:
    """Module globals an import-masking handler really assigns at import time, by line.

    A handler in import-time scope (module or class body, see
    ``_module_scope_nodes``) seeds every name it assigns, at the assignment's
    line. A handler inside a function seeds only the names that function
    declares ``global``, and only when the function is called at import time
    (seeded at the call's line): otherwise the assignment is a local, or never
    runs before the skip condition is evaluated. Each seed is keyed by the
    namespace it binds in: a handler in a class body binds a class attribute,
    not the module global.
    """
    scope = _module_scope_nodes(list(tree.body))
    seeds: dict[tuple[_Scope, str], set[int]] = {}

    def collect(nodes: list[ast.AST], keep: set[str] | None, line: int | None) -> None:
        for node in nodes:
            if not isinstance(node, ast.Try | ast.TryStar):
                continue
            for handler in node.handlers:
                if not _handler_masks_imports(node, handler):
                    continue
                # Only what the handler itself runs: a function defined in the
                # handler binds its own locals, and only if it is ever called.
                for sub in _module_scope_nodes(list(handler.body)):
                    bound = _assignment_parts(sub)[0] | _import_bound_names(sub)
                    # A `global` helper binds module globals; otherwise the
                    # handler binds in the namespace it runs in.
                    where = None if keep is not None else ns.of(sub)
                    for name in bound if keep is None else bound & keep:
                        key = (ns.binding(where, name), name)
                        seeds.setdefault(key, set()).add(line or sub.lineno)

    collect(scope, None, None)
    calls: dict[str, set[int]] = {}
    for node in scope:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.setdefault(node.func.id, set()).add(node.lineno)
    for node in scope:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in calls:
            declared = {
                name for sub in ast.walk(node) if isinstance(sub, ast.Global) for name in sub.names
            }
            for call_line in calls[node.name]:
                collect(list(ast.walk(node)), declared, call_line)
    return seeds


def _always_returns(stmts: list[ast.stmt]) -> bool:
    """True if executing ``stmts`` is guaranteed to end in a ``return``/``raise``.

    A direct ``return``/``raise`` does, and so does an ``if`` whose two
    branches both always return, or a ``try`` whose body (or ``else``) always
    returns and whose every handler always exits, or whose ``finally``
    always returns. Anything less certain (a one-armed ``if``, a loop) is
    deliberately treated as possibly falling through.
    """
    for stmt in stmts:
        if isinstance(stmt, ast.Return | ast.Raise):
            return True
        if isinstance(stmt, ast.If) and _always_returns(stmt.body) and _always_returns(stmt.orelse):
            return True
        if isinstance(stmt, ast.Try | ast.TryStar) and (
            _always_returns(stmt.finalbody)
            or (
                (_always_returns(stmt.body) or _always_returns(stmt.orelse))
                and all(_always_returns(h.body) for h in stmt.handlers)
            )
        ):
            return True
    return False


def _import_bound_names(node: ast.AST) -> set[str]:
    """Names an ``import``/``from ... import`` statement binds (``import a.b`` binds ``a``)."""
    if isinstance(node, ast.Import):
        return {alias.asname or alias.name.split(".")[0] for alias in node.names}
    if isinstance(node, ast.ImportFrom):
        return {alias.asname or alias.name for alias in node.names if alias.name != "*"}
    return set()


def _local_flow_returns_dependent(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, initial: frozenset[str] = frozenset()
) -> bool:
    """True if ``fn`` returns a value that depends on a masked import (local flow).

    Walks the direct statements of ``fn.body`` in source order, tracking
    import-dependent locals: those assigned (or bound by an import statement)
    on either path of a ``try`` with a masking handler (the handler, or the
    try body / ``else``), and any local
    later bound from one (``result = available``). A direct, unconditional
    rebinding to a value that reads none of them clears the names it rebinds
    (``available = True``); rebindings nested in ``if``/loops/``try`` only add,
    because they are not provably executed. A branch gated on a dependent
    local makes what it assigns dependent. (Control-flow shapes where
    different ``return`` statements decide the result, including returns in
    a handler or a gated branch, are covered by
    ``_probes_and_can_return_differently``.)
    """
    # ``initial``: names already known to carry the dependency into this
    # function, e.g. other masking-result functions it may call.
    dependent: set[str] = set(initial)
    for stmt in fn.body:
        nodes = _module_scope_nodes([stmt])
        for node in nodes:
            if not isinstance(node, ast.Try | ast.TryStar):
                continue
            masking = [h for h in node.handlers if _handler_masks_imports(node, h)]
            if not masking:
                continue
            for sub in _module_scope_nodes([*node.body, *node.orelse]):
                dependent |= _assignment_parts(sub)[0] | _import_bound_names(sub)
            for handler in masking:
                for sub in _module_scope_nodes(list(handler.body)):
                    dependent |= _assignment_parts(sub)[0] | _import_bound_names(sub)
        if isinstance(stmt, ast.Assign | ast.AnnAssign) and stmt.value is not None:
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            if _condition_references_names(stmt.value, frozenset(dependent)):
                dependent |= _assignment_parts(stmt)[0]
            else:
                dependent -= {n for t in targets for n in _rebound_names(t)}
            continue
        # Control dependency: what a branch gated on a dependent local assigns
        # or returns depends on the import too.
        # Iterate to a fixed point: a local made dependent here can gate a
        # later branch in the same compound statement.
        gated: set[int] = set()
        changed = True
        while changed:
            before = (len(dependent), len(gated))
            for node in nodes:
                if isinstance(node, ast.If | ast.While) and _condition_references_names(
                    node.test, frozenset(dependent)
                ):
                    gated |= {id(sub) for sub in _module_scope_nodes(node.body + node.orelse)}
            for node in nodes:
                bound, value = _assignment_parts(node)
                if value is not None and (
                    id(node) in gated or _condition_references_names(value, frozenset(dependent))
                ):
                    dependent |= bound
            changed = (len(dependent), len(gated)) != before
        if any(
            isinstance(node, ast.Return)
            and node.value is not None
            and _condition_references_names(node.value, frozenset(dependent))
            for node in nodes
        ):
            return True
    return False


def _probes_and_can_return_differently(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, known: frozenset[str] = frozenset()
) -> bool:
    """True if ``fn`` contains an import probe and can return more than one value.

    A probe is a ``try`` with a masking handler anywhere in the function's
    own body (nested in ``if``/loops included), or a reference to a ``known``
    masking-result function (``if probe(): return True``). Possible return values are
    the return expressions, compared structurally, plus an implicit ``None``
    when the body does not always return (see ``_always_returns``). With a
    probe present, more than one possible value means the result can depend
    on the import. Deliberately conservative: unrelated branching returns in
    a probing function also count, which only matters if that function's
    result reaches a skip condition.
    """
    own = _module_scope_nodes(list(fn.body))
    probes = any(
        (
            isinstance(node, ast.Try | ast.TryStar)
            and any(_handler_masks_imports(node, h) for h in node.handlers)
        )
        or (isinstance(node, ast.Name) and node.id in known)
        for node in own
    )
    if not probes:
        return False
    values = {
        ast.dump(node.value if node.value is not None else ast.Constant(None))
        for node in own
        if isinstance(node, ast.Return)
    }
    if not _always_returns(fn.body):
        values.add(ast.dump(ast.Constant(None)))
    return len(values) > 1


def _masking_result_seeds(tree: ast.Module, ns: _Namespaces) -> dict[tuple[_Scope, str], set[int]]:
    """Import-time functions whose failure path returns a value, seeded at the ``def``.

    ``def check(): try: import x; return True / except ImportError: return
    False`` makes ``check`` tainted, so ``HAVE = check()`` and ``skipif(not
    check())`` read taint through it. Counted: a ``return`` inside a masking
    handler; a ``return`` reading a local assigned on either path of a masking
    ``try`` (the handler, or the try body / ``else``); or
    a probing function that can return more than one value, including an
    implicit ``None`` (see ``_probes_and_can_return_differently``); or a
    wrapper whose return reads another masking-result function (fixpoint).
    A handler that re-raises or leaves the result alone does not count.
    """
    seeds: dict[tuple[_Scope, str], set[int]] = {}
    for fn in _module_scope_nodes(list(tree.body)):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        returns_on_failure = _local_flow_returns_dependent(fn)
        if not returns_on_failure:
            returns_on_failure = _probes_and_can_return_differently(fn)
        if returns_on_failure:
            key = (ns.binding(ns.of(fn), fn.name), fn.name)
            seeds.setdefault(key, set()).add(fn.lineno)
    # Wrappers: a function whose return reads a masking-result function
    # (`def available(): return probe()`) is one too, through any chain.
    functions = [
        fn
        for fn in _module_scope_nodes(list(tree.body))
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    grew = bool(seeds)
    while grew:
        grew = False
        # A function body resolves bare names against module globals only (a
        # class namespace is never visible from inside a function), so only
        # module-scope masking functions can reach a wrapper by name.
        known = frozenset(name for scope, name in seeds if scope is None)
        for fn in functions:
            key = (ns.binding(ns.of(fn), fn.name), fn.name)
            if key in seeds or not (
                _local_flow_returns_dependent(fn, known)
                or _probes_and_can_return_differently(fn, known)
            ):
                continue
            seeds[key] = {fn.lineno}
            grew = True
    return seeds


def _masking_handler_region_ids(scope: list[ast.AST]) -> set[int]:
    """ids of import-time nodes inside an import-masking handler body.

    A masking handler only runs when the import fails, so anything it does at
    import time is import-driven, exactly like a branch gated on a tainted
    name.
    """
    region: set[int] = set()
    for node in scope:
        if isinstance(node, ast.Try | ast.TryStar):
            for handler in node.handlers:
                if _handler_masks_imports(node, handler):
                    region |= {id(sub) for sub in _module_scope_nodes(list(handler.body))}
    return region


_END_OF_MODULE = 10**9


class _TaintView(NamedTuple):
    """Tainted names as seen by an expression evaluated at one point of the import.

    ``now`` applies to code evaluated where it appears; ``final`` to a string
    skipif condition, which pytest evaluates against the module's globals only
    after the whole module has been imported.
    """

    now: frozenset[str]
    final: frozenset[str]


class _Taint(NamedTuple):
    """Flow- and scope-sensitive taint, keyed by (namespace, name).

    A binding counts as tainted at ``line`` unless an unconditional direct
    rebinding in its namespace sits strictly between its last taint and
    ``line``. Taint itself is not ordered (a taint after the use still
    counts), which keeps loops and later calls conservative.

    Lookup follows Python: module code sees module bindings; a class body sees
    its own bindings, then module bindings it has not directly rebound before
    ``line``. A class body never sees an enclosing class's namespace.
    """

    taint_lines: dict[tuple[_Scope, str], set[int]]
    clear_lines: dict[tuple[_Scope, str], set[int]]

    def _live(self, key: tuple[_Scope, str], line: int) -> bool:
        lines = self.taint_lines.get(key)
        return bool(lines) and not any(max(lines) < c < line for c in self.clear_lines.get(key, ()))

    def at(self, line: int, scope: _Scope = None) -> frozenset[str]:
        live = {n for (s, n) in self.taint_lines if s == scope and self._live((s, n), line)}
        if scope is not None:
            live |= {
                n
                for (s, n) in self.taint_lines
                if s is None
                and self._live((None, n), line)
                and not any(c < line for c in self.clear_lines.get((scope, n), ()))
            }
        return frozenset(live)

    def view(self, line: int, scope: _Scope = None) -> _TaintView:
        # pytest evaluates a string condition against the module's globals,
        # never a class namespace, so `final` is always module scope.
        return _TaintView(now=self.at(line, scope), final=self.at(_END_OF_MODULE))

    @property
    def ever(self) -> bool:
        return bool(self.taint_lines)


def _rebound_names(target: ast.expr) -> set[str]:
    """Names an assignment target actually rebinds.

    ``x = ...`` and tuple/list/starred unpacking rebind names; ``obj.attr =
    ...`` and ``obj[key] = ...`` only mutate ``obj``, so they rebind nothing.
    (``_assignment_parts`` deliberately reports mutated bases too, because a
    mutation inside a masking handler does taint the object.)
    """
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Tuple | ast.List):
        return {name for elt in target.elts for name in _rebound_names(elt)}
    if isinstance(target, ast.Starred):
        return _rebound_names(target.value)
    return set()


def _top_level_clears(tree: ast.Module, ns: _Namespaces) -> dict[tuple[_Scope, str], set[int]]:
    """Lines where a direct assignment unconditionally rebinds a name in its namespace.

    Only statements directly in the module body (namespace ``None``) or
    directly in an import-time class body (that class) count: a rebinding inside an
    ``if``/``try``/loop is not provably executed. Augmented assignment reads
    its own target, so it never clears; an attribute or subscript write only
    mutates its base (see ``_rebound_names``). A rebinding whose value reads taint is
    also a taint event on the same line, and ``_Taint.at`` only honours a
    clear strictly after the last taint, so it needs no special case here.
    """
    # A class body runs only if its class statement does. Unconditionally
    # reached classes sit directly in the module body or directly in another
    # such class's body; only their rebindings may clear a module binding
    # (via `global`). A conditional class's class-local rebindings still
    # count: they only affect uses inside that class body, which run only if
    # the class does.
    unconditional: set[int] = set()
    pending = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    while pending:
        cls = pending.pop()
        unconditional.add(id(cls))
        pending.extend(n for n in cls.body if isinstance(n, ast.ClassDef))
    bodies: list[tuple[_Scope, list[ast.stmt]]] = [(None, list(tree.body))]
    bodies.extend(
        (id(node), list(node.body))
        for node in _module_scope_nodes(list(tree.body))
        if isinstance(node, ast.ClassDef)
    )
    clears: dict[tuple[_Scope, str], set[int]] = {}
    for where, body in bodies:
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                targets = stmt.targets
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                targets = [stmt.target]
            else:
                continue
            for name in {n for t in targets for n in _rebound_names(t)}:
                lands = ns.binding(where, name)
                if lands is None and where is not None and where not in unconditional:
                    continue
                clears.setdefault((lands, name), set()).add(stmt.lineno)
    return clears


def _flow_taint(
    tree: ast.Module,
    names: _ImportNames,
    seeds: dict[tuple[_Scope, str], set[int]],
    ns: _Namespaces,
) -> _Taint:
    """Close ``seeds`` over import-time assignments, tracking clears (fixpoint).

    A name becomes tainted at an import-time assignment that binds it from a
    value reading a name tainted at that line (``MISSING = not HAVE_MODULE``),
    or that sits in a branch gated on one. (An augmented assignment to a
    tainted name needs no rule: it never clears, see ``_top_level_clears``.)
    Taint lines only grow across iterations, so the loop terminates.
    """
    scope = _module_scope_nodes(list(tree.body))
    clears = _top_level_clears(tree, ns)
    taint_lines = {key: set(lines) for key, lines in seeds.items()}
    changed = bool(taint_lines)
    while changed:
        changed = False
        taint = _Taint(taint_lines, clears)
        gated = _gated_region_ids(scope, taint, ns)
        for node in scope:
            bound, value = _assignment_parts(node)
            if not bound:
                continue
            where = ns.of(node)
            view = taint.view(node.lineno, where)
            reads = value is not None and _reads_tainted(value, names, view)
            if reads or id(node) in gated:
                for name in bound:
                    key = (ns.binding(where, name), name)
                    if node.lineno not in taint_lines.setdefault(key, set()):
                        taint_lines[key].add(node.lineno)
                        changed = True
    return _Taint(taint_lines, clears)


def _skipif_conditions(call: ast.Call) -> list[tuple[ast.expr, bool]]:
    """The condition expressions pytest evaluates for a ``skipif(...)`` call.

    Mirrors pytest's ``evaluate_skip_marks``: a ``condition=`` keyword wins;
    otherwise every positional argument is a condition (any true one skips).
    Each comes with whether it was a string. A string condition is evaluated
    by pytest against the module's globals after import, so it is parsed here
    into the expression it stands for. An unparseable string makes pytest fail
    collection loudly, so it contributes no names.
    """
    keyword = next((kw.value for kw in call.keywords if kw.arg == "condition"), None)
    raw = [keyword] if keyword is not None else list(call.args)
    conditions: list[tuple[ast.expr, bool]] = []
    for cond in raw:
        if isinstance(cond, ast.Constant) and isinstance(cond.value, str):
            try:
                conditions.append((ast.parse(cond.value, mode="eval").body, True))
            except SyntaxError:
                continue
        else:
            conditions.append((cond, False))
    return conditions


def _condition_references_names(expr: ast.expr, flag_names: frozenset[str]) -> bool:
    """True if any ``Name`` node inside ``expr`` refers to one of ``flag_names``."""
    return any(isinstance(sub, ast.Name) and sub.id in flag_names for sub in ast.walk(expr))


def _skipif_reads(call: ast.Call, view: _TaintView) -> bool:
    """True if any condition pytest evaluates for this skipif reads a tainted name."""
    return any(
        _condition_references_names(cond, view.final if is_string else view.now)
        for cond, is_string in _skipif_conditions(call)
    )


def _reads_tainted(expr: ast.expr, names: _ImportNames, view: _TaintView) -> bool:
    """True if ``expr`` reads a tainted name, counting string skipif conditions as code."""
    return _condition_references_names(expr, view.now) or any(
        _is_skipif_call(sub, names) and _skipif_reads(sub, view) for sub in ast.walk(expr)
    )


def _flow_bound_names(
    tree: ast.Module,
    ns: _Namespaces,
    binds_mark: Callable[[ast.expr, int, _Scope, _Taint], bool],
) -> _Taint:
    """Flow-sensitive set of names bound to a mark value of some kind (fixpoint).

    ``binds_mark(value, line, scope, current)`` decides whether an import-time
    assignment at ``line`` in namespace ``scope`` puts such a mark in its
    targets, given the set so far. The result follows the same rule as taint (``_Taint.at``): an
    unconditional top-level rebinding clears a name for what comes after it,
    so ``MARK = <mark>; MARK = <other>; pytestmark = MARK`` sees the other.
    """
    scope = _module_scope_nodes(list(tree.body))
    clears = _top_level_clears(tree, ns)
    lines: dict[tuple[_Scope, str], set[int]] = {}
    changed = True
    while changed:
        changed = False
        current = _Taint(lines, clears)
        for node in scope:
            bound, value = _assignment_parts(node)
            where = ns.of(node)
            if not bound or value is None or not binds_mark(value, node.lineno, where, current):
                continue
            for name in bound:
                key = (ns.binding(where, name), name)
                if node.lineno not in lines.setdefault(key, set()):
                    lines[key].add(node.lineno)
                    changed = True
    return _Taint(lines, clears)


def _skip_carrying_names(tree: ast.Module, names: _ImportNames, ns: _Namespaces) -> _Taint:
    """Names bound at import time to a value that holds a skip mark (flow-sensitive).

    E.g. ``MARKS = [pytest.mark.skip(...)] if not HAVE_MODULE else []`` makes
    ``MARKS`` skip-carrying, and so does any name later bound from ``MARKS``.
    """
    return _flow_bound_names(
        tree,
        ns,
        lambda value, line, where, current: _can_supply_skip(value, names, current.at(line, where)),
    )


def _can_supply_skip(expr: ast.expr, names: _ImportNames, carrying: frozenset[str]) -> bool:
    """True if ``expr`` holds a skip mark directly or via a skip-carrying name."""
    return any(_is_skip_mark_ref(sub, names) for sub in ast.walk(expr)) or (
        _condition_references_names(expr, carrying)
    )


def _taint_decides_skip(
    expr: ast.expr,
    names: _ImportNames,
    tainted: _TaintView,
    carrying: frozenset[str],
    masking: frozenset[str],
) -> bool:
    """True if a tainted name decides whether ``expr`` (a mark value) applies a skip.

    Reading a tainted name is not enough: ``parametrize("a", [HAVE])`` cannot
    skip, and ``mark.skip(reason=f"{HAVE}")`` skips whatever the flag says.
    Containers are judged element by element; a conditional expression masks
    when its test is tainted and a branch can supply a skip; a skipif masks
    when a condition it evaluates is tainted; a bare name masks when it is a
    masking mark name (see ``_masking_mark_names``).
    """

    def again(e: ast.expr) -> bool:
        return _taint_decides_skip(e, names, tainted, carrying, masking)

    if isinstance(expr, ast.List | ast.Tuple | ast.Set):
        return any(again(e) for e in expr.elts)
    if isinstance(expr, ast.Starred):
        return again(expr.value)
    if isinstance(expr, ast.IfExp):
        branch_skips = _can_supply_skip(expr.body, names, carrying) or _can_supply_skip(
            expr.orelse, names, carrying
        )
        return (
            (_reads_tainted(expr.test, names, tainted) and branch_skips)
            or again(expr.body)
            or again(expr.orelse)
        )
    if isinstance(expr, ast.BinOp):
        return again(expr.left) or again(expr.right)
    if isinstance(expr, ast.Name):
        return expr.id in masking
    if _is_skipif_call(expr, names):
        return _skipif_reads(expr, tainted)
    if isinstance(expr, ast.Call) and _is_skip_mark_ref(expr.func, names):
        return False
    return _can_supply_skip(expr, names, carrying) and _reads_tainted(expr, names, tainted)


def _masking_mark_names(
    tree: ast.Module,
    names: _ImportNames,
    taint: _Taint,
    carrying: _Taint,
    ns: _Namespaces,
) -> _Taint:
    """Names bound at import time to a mark value whose skip taint decides (flow-sensitive).

    ``MARK = pytest.mark.skipif(not HAVE_MODULE)`` makes ``MARK`` masking, so a
    later ``pytestmark = MARK`` or ``@MARK`` is too, until ``MARK`` is
    unconditionally rebound. ``MARK = pytest.mark.skip(reason=f"{HAVE_MODULE}")``
    is not masking: it skips regardless.
    """
    return _flow_bound_names(
        tree,
        ns,
        lambda value, line, where, current: _taint_decides_skip(
            value,
            names,
            taint.view(line, where),
            carrying.at(line, where),
            current.at(line, where),
        ),
    )


def _find_masking_skipif_uses(
    tree: ast.Module, names: _ImportNames, taint: _Taint, ns: _Namespaces
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
    if not taint.ever:
        return []
    module_scope_ids = {id(node) for node in _module_scope_nodes(list(tree.body))}
    carrying = _skip_carrying_names(tree, names, ns)
    masking = _masking_mark_names(tree, names, taint, carrying, ns)
    lines: list[int] = []
    for node in ast.walk(tree):
        # (expression, line to report if taint decides its skip outside an
        # inline skipif): a module/class-scope pytestmark value, reported at
        # the assignment, and every decorator, reported at the decorator.
        marks: list[tuple[ast.expr, int]] = []
        # A pytestmark value and a def's decorators are both evaluated in the
        # namespace that holds the statement.
        where = ns.of(node)
        if id(node) in module_scope_ids:
            bound, value = _assignment_parts(node)
            if "pytestmark" in bound and value is not None:
                marks.append((value, node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            marks.extend((dec, dec.lineno) for dec in node.decorator_list)
        for expr, line in marks:
            view = taint.view(line, where)
            hits = [
                sub.lineno
                for sub in ast.walk(expr)
                if _is_skipif_call(sub, names) and _skipif_reads(sub, view)
            ]
            # Taint can also decide the skip outside an inline skipif: e.g.
            # `[mark.skip] if not HAVE_MODULE else []`, or an alias such as
            # `pytestmark = MARK` / `@MARK` for a masking MARK.
            if not hits and _taint_decides_skip(
                expr, names, view, carrying.at(line, where), masking.at(line, where)
            ):
                hits.append(line)
            lines.extend(hits)
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

    helpers = _skip_helpers(tree, names)

    for node in ast.walk(tree):
        # ast.TryStar (try/except*) carries the same handler shape as ast.Try.
        if isinstance(node, ast.Try | ast.TryStar):
            for handler in node.handlers:
                if not _handler_masks_imports(node, handler):
                    continue
                # A skip inside a function defined (not called) in the handler
                # never runs; a call to such a helper is caught below.
                for sub in _module_scope_nodes(list(handler.body)):
                    if (
                        _is_module_level_skip(sub, names)
                        or _is_unittest_skiptest_raise(sub, names)
                        or _is_skip_helper_call(sub, helpers)
                    ):
                        _report(sub.lineno)
        if _is_first_party_importorskip(node, names, first_party):
            _report(node.lineno)

    ns = _namespaces(tree)
    seeds = _import_time_taint_seeds(tree, ns)
    for key, lines in _masking_result_seeds(tree, ns).items():
        seeds.setdefault(key, set()).update(lines)
    taint = _flow_taint(tree, names, seeds, ns)
    for lineno in _find_masking_skipif_uses(tree, names, taint, ns):
        _report(lineno)

    # Any skip action in an import-time region that only runs because the
    # import failed is masking: a branch gated on a tainted name (e.g. `if not
    # HAVE_MODULE: pytest.skip(..., allow_module_level=True)`) or a masking
    # handler body itself (e.g. `except ImportError: pytestmark =
    # pytest.mark.skip(...)`). Skip actions: module-level skip, SkipTest
    # raise, a skip mark, or a call to a skip helper.
    scope = _module_scope_nodes(list(tree.body))
    import_driven = _masking_handler_region_ids(scope)
    if taint.ever:
        import_driven |= _gated_region_ids(scope, taint, ns)
    if import_driven:
        for sub in scope:
            if id(sub) in import_driven and (
                _is_module_level_skip(sub, names)
                or _is_unittest_skiptest_raise(sub, names)
                or _is_skip_mark_ref(sub, names)
                or _is_skip_helper_call(sub, helpers)
            ):
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


# Shared preamble for the taint-tracking fixtures below: lines 1-6 mask a
# failed import and leave the flag `_HAVE_MODULE` tainted, so every case's own
# body starts on line 7.
_MASKED_FLAG_PREAMBLE = (
    "import pytest\n"
    "_HAVE_MODULE = True\n"
    "try:\n"
    "    import not_a_real_module\n"
    "except ImportError:\n"
    "    _HAVE_MODULE = False\n"
)

# Scope fixtures (Codex review run 5798565a34b0): an import-masking handler
# inside a helper function only taints a module global when the helper binds
# it (`global`) and actually runs at import time.
_PROBE_LOCAL = (
    "def _probe():\n"
    "    try:\n"
    "        import not_a_real_module\n"
    "    except ImportError:\n"
    "        _HAVE_MODULE = False\n"
)
_PROBE_GLOBAL = (
    "def _probe():\n"
    "    global _HAVE_MODULE\n"
    "    try:\n"
    "        import not_a_real_module\n"
    "    except ImportError:\n"
    "        _HAVE_MODULE = False\n"
)
_SKIPIF_ON_FLAG_TEST = (
    '@pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
    "def test_something():\n"
    "    assert not_a_real_module.thing() == 1\n"
)

# Flow-ordering fixtures (Codex review run 6df3ce9ff855): lines 1-7 mask a
# failed import and taint `_HAVE_MODULE`; each case's body starts on line 8.
# `os` is imported for the conditional-clear row.
_FLOW_PREAMBLE = (
    "import os\n"
    "import pytest\n"
    "_HAVE_MODULE = True\n"
    "try:\n"
    "    import not_a_real_module\n"
    "except ImportError:\n"
    "    _HAVE_MODULE = False\n"
)
_FLOW_TEST = "def test_something():\n    assert not_a_real_module.thing() == 1\n"
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
    # Codex review: a class body runs at import time and pytest applies a
    # class-level `pytestmark` to every method in it.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "class TestFeature:\n"
            '    pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "    def test_something(self):\n"
            "        assert not_a_real_module.thing() == 1\n"
        ),
        8,
        id="flag_variable_class_pytestmark",
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
    # Taint mapping (Codex rounds 5+): a skip that only happens because of a
    # tainted value is masking. Tainted = set in a masking handler, derived
    # from a tainted name, or assigned inside a branch gated on one. Every
    # row below was confirmed as a silent pytest skip when the import breaks.
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + "if not _HAVE_MODULE:\n"
        + '    pytestmark = pytest.mark.skipif(True, reason="x")\n',
        8,
        id="taint_gated_pytestmark_constant_condition",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + "if not _HAVE_MODULE:\n"
        + '    pytestmark = pytest.mark.skip(reason="x")\n',
        8,
        id="taint_gated_pytestmark_unconditional_skip",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + "if not _HAVE_MODULE:\n"
        + '    @pytest.mark.skip(reason="x")\n'
        + "    def test_something():\n"
        + "        assert not_a_real_module.thing() == 1\n",
        8,
        id="taint_gated_skip_decorator",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + "MISSING = not _HAVE_MODULE\n"
        + 'pytestmark = pytest.mark.skipif(MISSING, reason="x")\n',
        8,
        id="taint_alias_of_flag",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'pytestmark = [pytest.mark.skip(reason="x")] if not _HAVE_MODULE else []\n',
        7,
        id="taint_conditional_expression_marks",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def _bail():\n"
            '    pytest.skip("x", allow_module_level=True)\n'
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _bail()\n"
        ),
        7,
        id="skip_helper_called_in_handler",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + "def _bail():\n"
        + '    pytest.skip("x", allow_module_level=True)\n'
        + "if not _HAVE_MODULE:\n"
        + "    _bail()\n",
        10,
        id="skip_helper_called_in_gated_branch",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + "if not _HAVE_MODULE:\n"
        + "    MISSING = True\n"
        + "else:\n"
        + "    MISSING = False\n"
        + 'pytestmark = pytest.mark.skipif(MISSING, reason="x")\n',
        11,
        id="taint_assigned_inside_gated_branch",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'MARKS = [pytest.mark.skip(reason="x")] if not _HAVE_MODULE else []\n'
        + "pytestmark = MARKS\n",
        8,
        id="taint_mark_list_bound_to_a_name",
    ),
    # Codex review (run 3c758387f1b1): a skip mark bound to an alias first,
    # then applied via pytestmark or as a decorator. Each row skips silently
    # under pytest when the import breaks.
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'MARK = pytest.mark.skipif("not _HAVE_MODULE", reason="x")\n'
        + "pytestmark = MARK\n",
        8,
        id="alias_string_condition_pytestmark",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'MARK = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + "pytestmark = MARK\n",
        8,
        id="alias_expression_condition_pytestmark",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'MARK = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + "@MARK\n"
        + "def test_something():\n"
        + "    assert not_a_real_module.thing() == 1\n",
        8,
        id="alias_expression_condition_decorator",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'MARK = pytest.mark.skipif("not _HAVE_MODULE", reason="x")\n'
        + "@MARK\n"
        + "def test_something():\n"
        + "    assert not_a_real_module.thing() == 1\n",
        8,
        id="alias_string_condition_decorator",
    ),
    pytest.param(
        "import pytest\n_HAVE_MODULE = True\n"
        + _PROBE_GLOBAL
        + "_probe()\n"
        + _SKIPIF_ON_FLAG_TEST,
        10,
        id="global_flag_set_by_helper_called_at_import",
    ),
    # Codex review (run 336bf867d1f7): every binding form a handler can use
    # for the flag seeds taint, not just a plain `NAME = ...`. Each row skips
    # silently under pytest when the import breaks.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    module, _HAVE_MODULE = None, False\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        7,
        id="handler_binds_flag_by_tuple_unpack",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    [module, _HAVE_MODULE] = [None, False]\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        7,
        id="handler_binds_flag_by_list_unpack",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    *rest, _HAVE_MODULE = [None, False]\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        7,
        id="handler_binds_flag_by_starred_unpack",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    (_HAVE_MODULE := False)\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        7,
        id="handler_binds_flag_by_walrus",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE &= False\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        7,
        id="handler_binds_flag_by_augmented_assignment",
    ),
    # Codex review (run 8a8ca3138644): a masking handler body only runs when
    # the import fails, so a skip mark created there is import-driven exactly
    # like one in an `if not HAVE_MODULE:` branch. Reported where the skip is
    # created. Each row skips silently under pytest when the import breaks.
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    pytestmark = pytest.mark.skip(reason="module unavailable")\n'
            "def test_feature():\n"
            "    assert not_a_real_module.thing() == 1\n"
        ),
        5,
        id="handler_assigns_skip_pytestmark",
    ),
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    pytestmark = pytest.mark.skipif(True, reason="x")\n'
        ),
        5,
        id="handler_assigns_constant_skipif_pytestmark",
    ),
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "    MARK = []\n"
            "except ImportError:\n"
            '    MARK = pytest.mark.skip(reason="x")\n'
            "pytestmark = MARK\n"
        ),
        6,
        id="handler_binds_skip_mark_alias",
    ),
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    @pytest.mark.skip(reason="x")\n'
            "    def test_feature():\n"
            "        assert False\n"
        ),
        5,
        id="handler_defines_skip_decorated_test",
    ),
    # Flow ordering: taint is cleared only by an unconditional top-level
    # rebinding that does not read taint, and only for uses evaluated after
    # it. Each row skips silently under pytest, except the loop row (see its
    # comment).
    pytest.param(
        _FLOW_PREAMBLE
        + 'if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
        + "    _HAVE_MODULE = True\n"
        + 'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + _FLOW_TEST,
        10,
        id="flow_conditional_rebinding_does_not_clear",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + "_HAVE_MODULE = _HAVE_MODULE and True\n"
        + 'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + _FLOW_TEST,
        9,
        id="flow_rebinding_that_reads_taint_does_not_clear",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + 'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + "_HAVE_MODULE = True\n"
        + _FLOW_TEST,
        8,
        id="flow_expression_condition_evaluated_before_clear",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + '@pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + _FLOW_TEST
        + "_HAVE_MODULE = True\n",
        8,
        id="flow_decorator_evaluated_before_clear",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + "MISSING = not _HAVE_MODULE\n"
        + "_HAVE_MODULE = True\n"
        + 'pytestmark = pytest.mark.skipif(MISSING, reason="x")\n'
        + _FLOW_TEST,
        10,
        id="flow_derived_before_clear_stays_tainted",
    ),
    # Deliberately conservative: pytest runs this test (range(1) iterates),
    # but a loop body is not provably executed (`for _ in []:` never clears),
    # so a rebinding inside a loop does not clear taint. A false positive here
    # fails CI loudly; the alternative could hide a broken import silently.
    pytest.param(
        _FLOW_PREAMBLE
        + "for _ in range(1):\n"
        + "    _HAVE_MODULE = True\n"
        + 'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + _FLOW_TEST,
        10,
        id="flow_rebinding_inside_loop_is_conservatively_not_a_clear",
    ),
    # Codex review (run 8778b042e5dd): writing an attribute or subscript
    # mutates its base object but does not rebind it, so it must not clear
    # taint; a mutation inside the masking handler still taints the base.
    # Each row skips silently under pytest when the import breaks.
    pytest.param(
        (
            "from types import SimpleNamespace\n"
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "    state = SimpleNamespace(available=True)\n"
            "except ImportError:\n"
            "    state = SimpleNamespace(available=False)\n"
            'state.note = "x"\n'
            'pytestmark = pytest.mark.skipif(not state.available, reason="x")\n'
        ),
        9,
        id="flow_attribute_write_does_not_clear",
    ),
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            '    FLAGS = {"have": True}\n'
            "except ImportError:\n"
            '    FLAGS = {"have": False}\n'
            'FLAGS["note"] = "x"\n'
            'pytestmark = pytest.mark.skipif(not FLAGS["have"], reason="x")\n'
        ),
        8,
        id="flow_subscript_write_does_not_clear",
    ),
    pytest.param(
        (
            "from types import SimpleNamespace\n"
            "import pytest\n"
            "state = SimpleNamespace(available=True)\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    state.available = False\n"
            'pytestmark = pytest.mark.skipif(not state.available, reason="x")\n'
        ),
        8,
        id="handler_attribute_mutation_taints_base",
    ),
    pytest.param(
        (
            "import pytest\n"
            'FLAGS = {"have": True}\n'
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    FLAGS["have"] = False\n'
            'pytestmark = pytest.mark.skipif(not FLAGS["have"], reason="x")\n'
        ),
        7,
        id="handler_subscript_mutation_taints_base",
    ),
    # Codex review (run 6a4bdb5ca439): mark aliases follow the same flow rule
    # as taint. These stay flagged (each skips silently under pytest): a use
    # before the rebinding, a conditional rebinding, and a carrying alias that
    # is never rebound.
    pytest.param(
        _FLOW_PREAMBLE
        + 'MARK = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + "pytestmark = MARK\n"
        + 'MARK = pytest.mark.filterwarnings("ignore")\n'
        + _FLOW_TEST,
        9,
        id="flow_masking_alias_used_before_rebind",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + 'MARK = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + 'if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
        + '    MARK = pytest.mark.filterwarnings("ignore")\n'
        + "pytestmark = MARK\n"
        + _FLOW_TEST,
        11,
        id="flow_masking_alias_conditional_rebind",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + 'M = pytest.mark.skip(reason="x")\n'
        + "pytestmark = M if not _HAVE_MODULE else []\n"
        + _FLOW_TEST,
        9,
        id="flow_carrying_alias_still_carrying",
    ),
    # Codex review (run 356257de6d0d): a class body reads its own names first,
    # then module globals; module code reads only globals. These stay flagged
    # (each skips silently under pytest).
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "class TestProbe:\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        _HAVE_MODULE = False\n"
            '    pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "    def test_something(self):\n"
            "        assert False\n"
        ),
        8,
        id="scope_class_handler_class_pytestmark",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "class TestProbe:\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        _HAVE_MODULE = False\n"
            '    @pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "    def test_something(self):\n"
            "        assert False\n"
        ),
        8,
        id="scope_class_handler_method_decorator",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "class Other:\n"
            "    _HAVE_MODULE = True\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        9,
        id="scope_class_rebinding_does_not_clear_global",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "class TestProbe:\n"
            '    pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "    def test_something(self):\n"
            "        assert False\n"
        ),
        8,
        id="scope_class_use_reads_tainted_global",
    ),
    # Codex review (run a643ad9b096d): `global NAME` in a class body makes
    # its assignments bind the module global. These stay flagged (each skips
    # silently under pytest).
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "class Probe:\n"
            "    global _HAVE_MODULE\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        _HAVE_MODULE = False\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        9,
        id="scope_class_global_handler_taints_module",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "class TestProbe:\n"
            "    global _HAVE_MODULE\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        _HAVE_MODULE = False\n"
            '    pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "    def test_something(self):\n"
            "        assert False\n"
        ),
        9,
        id="scope_class_global_handler_class_use",
    ),
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "class Fixer:\n"
            "    global _HAVE_MODULE\n"
            '    if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
            "        _HAVE_MODULE = True\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        12,
        id="scope_class_global_conditional_rebinding_does_not_clear",
    ),
    # Codex review (run 44f93fe5b69b): a class body only runs if the class
    # definition does, so its `global` rebinding clears the module only when
    # the class is reached unconditionally. Each row skips silently.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "if False:\n"
            "    class Fixer:\n"
            "        global _HAVE_MODULE\n"
            "        _HAVE_MODULE = True\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        11,
        id="scope_conditional_class_global_does_not_clear",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "if False:\n"
            "    class Outer:\n"
            "        class Fixer:\n"
            "            global _HAVE_MODULE\n"
            "            _HAVE_MODULE = True\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        ),
        12,
        id="scope_nested_class_under_conditional_does_not_clear",
    ),
    # Masking-result functions (gap 3): a function whose failure path returns
    # a value (a `return` in a masking handler, or a returned local the
    # handler assigned) taints its name, so `HAVE = check()` and
    # `skipif(not check())` are masking. Plus a handler that defines and
    # calls a skip helper is reported once, at the call (Codex review run
    # ea5b9891a5f7 family). Each row skips silently under pytest.
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        return False\n"
            "_HAVE_MODULE = check()\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        9,
        id="result_return_in_handler_via_flag",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        return False\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        8,
        id="result_return_in_handler_direct_call",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        return False\n"
            "    return True\n"
            "_HAVE_MODULE = check()\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        9,
        id="result_return_after_try",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        ok = True\n"
            "    except ImportError:\n"
            "        ok = False\n"
            "    return ok\n"
            "_HAVE_MODULE = check()\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        10,
        id="result_return_local_flag",
    ),
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    def helper():\n"
            '        pytest.skip("x", allow_module_level=True)\n'
            "    helper()\n"
            "def test_something():\n"
            "    assert False\n"
        ),
        7,
        id="handler_defines_and_calls_skip_helper",
    ),
    # Codex review (run 750036dd78b0): a failure path that falls through to
    # the end of the function returns an implicit None while the success path
    # returned early. Each row skips silently under pytest.
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        pass\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        8,
        id="result_implicit_none_after_pass",
    ),
    pytest.param(
        (
            "import logging\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            '        logging.debug("missing")\n'
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        9,
        id="result_implicit_none_after_handler_work",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        pass\n"
            "    else:\n"
            "        return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        9,
        id="result_success_return_in_else",
    ),
    # Codex review (run 24d960ccfce1): only code that always returns stops the
    # fall-through; a later return inside a one-armed `if` does not.
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    if False:\n"
            "        return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        11,
        id="result_conditional_later_return_does_not_guarantee",
    ),
    # Deliberately conservative: pytest runs this test (`if True` returns), but
    # a one-armed `if` does not guarantee a return statically, so the failure
    # path still counts as falling through. Fails CI loudly, never silently.
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    if True:\n"
            "        return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        11,
        id="result_one_armed_if_return_is_conservatively_not_guaranteed",
    ),
    # Codex review (run 3ddc64abc80b): a guaranteed later return only rules
    # out an implicit None; if any value the failure path can return differs
    # from a success-path return, the result still depends on the import.
    # Each row skips silently under pytest when the import breaks.
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return False\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        10,
        id="result_later_return_value_differs",
    ),
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        pass\n"
            '    if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
            "        return True\n"
            "    else:\n"
            "        return False\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        13,
        id="result_later_branch_return_value_differs",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        pass\n"
            "    else:\n"
            "        return 1\n"
            "    return 0\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        10,
        id="result_else_success_later_return_differs",
    ),
    # Codex review (run 406402445f64): only a handler that always exits
    # (return/raise on every path) stops the fall-through. Skips silently.
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            '        if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
            "            raise\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        10,
        id="result_handler_conditional_raise_falls_through",
    ),
    # Codex review (run 56da02729f64): a returned local assigned on the
    # success path (try body or else) depends on the import as much as one
    # the handler assigns. Each row skips silently under pytest.
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return available\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        10,
        id="result_default_then_success_path_assign",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    ok = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        pass\n"
            "    else:\n"
            "        ok = True\n"
            "    return ok\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        11,
        id="result_success_path_assign_in_else",
    ),
    # Codex review (run 65bdca14d742): a local bound from an import-dependent
    # local is import-dependent too, through any chain. Skips silently.
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    result = available\n"
            "    return result\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        11,
        id="result_returned_alias_of_path_local",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    first = available\n"
            "    second = bool(first)\n"
            "    return second\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        12,
        id="result_returned_alias_chain_of_path_local",
    ),
    # Function-local flow (Codex review run aeb3c2e4730a): these keep the
    # dependency, each skips silently under pytest.
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            '    if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
            "        available = True\n"
            "    return available\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        13,
        id="result_conditional_local_rebind_does_not_clear",
    ),
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    available = available or False\n"
            "    return available\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        12,
        id="result_local_rebind_reading_taint_does_not_clear",
    ),
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    result = available\n"
            "    available = True\n"
            "    return result\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        13,
        id="result_alias_taken_before_local_rebind",
    ),
    # Codex review (run b3c9e812a6c8): a branch gated on a dependent local
    # carries the dependency into what it assigns or returns. Skips silently.
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    if available:\n"
            "        result = True\n"
            "    else:\n"
            "        result = False\n"
            "    return result\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        14,
        id="result_assign_in_branch_gated_on_local",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    if available:\n"
            "        return True\n"
            "    return False\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        12,
        id="result_return_in_branch_gated_on_local",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    if available:\n"
            "        return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        11,
        id="result_gated_return_without_fallback",
    ),
    # Codex review (run a7bab6f7671d): a local that becomes dependent inside
    # a compound statement gates later branches in that same statement.
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    if True:\n"
            "        if available:\n"
            "            result = True\n"
            "        else:\n"
            "            result = False\n"
            "        if result:\n"
            "            return True\n"
            "    return False\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        17,
        id="result_dependency_gates_later_branch_in_same_statement",
    ),
    # Codex review (run d1f694323860): an import probe nested in an `if` or a
    # loop is still a probe; a function containing one that can return more
    # than one value depends on the import. Each row skips silently.
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    if True:\n"
            "        try:\n"
            "            import not_a_real_module\n"
            "            return True\n"
            "        except ImportError:\n"
            "            pass\n"
            "    return False\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        10,
        id="result_probe_nested_in_if",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            '    for name in ["not_a_real_module"]:\n'
            "        try:\n"
            "            __import__(name)\n"
            "            return True\n"
            "        except ImportError:\n"
            "            pass\n"
            "    return False\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        10,
        id="result_probe_nested_in_loop",
    ),
    # Codex review (run 33308ffaa945): a function that returns a masking
    # result (through any chain of wrappers) is a masking result too.
    # Each row skips silently under pytest.
    pytest.param(
        (
            "import pytest\n"
            "def probe():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        return False\n"
            "def available():\n"
            "    return probe()\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        10,
        id="result_wrapper_returns_masking_result",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def probe():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        return False\n"
            "def inner():\n"
            "    return probe()\n"
            "def outer():\n"
            "    return bool(inner())\n"
            'pytestmark = pytest.mark.skipif(not outer(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        12,
        id="result_wrapper_chain_returns_masking_result",
    ),
    # Codex review (run de174506ffac): a wrapper that branches on a masking
    # result and returns constants decides its result from the import too.
    pytest.param(
        (
            "import pytest\n"
            "def probe():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        return False\n"
            "def available():\n"
            "    if probe():\n"
            "        return True\n"
            "    return False\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        12,
        id="result_wrapper_branches_on_masking_result",
    ),
    # Namespaces (Codex review run 5083bc2701b1): a class body sees its own
    # masking function; pinned so the wrapper fix cannot drop it.
    pytest.param(
        (
            "import pytest\n"
            "class TestProbe:\n"
            "    def probe():\n"
            "        try:\n"
            "            import not_a_real_module\n"
            "            return True\n"
            "        except ImportError:\n"
            "            return False\n"
            '    pytestmark = pytest.mark.skipif(not probe(), reason="x")\n'
            "    def test_something(self):\n"
            "        assert False\n"
        ),
        9,
        id="result_class_body_uses_class_masking_function",
    ),
    # Codex review (run 402db9202f23): an import statement binds a name on
    # the success path just like an assignment. Each row skips silently.
    pytest.param(
        (
            "import pytest\n"
            "def available():\n"
            "    mod = None\n"
            "    try:\n"
            "        import not_a_real_module as mod\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return mod is not None\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        9,
        id="result_import_alias_binding_returned",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def available():\n"
            "    thing = None\n"
            "    try:\n"
            "        from not_a_real_module import thing\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return thing is not None\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        9,
        id="result_from_import_binding_returned",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def available():\n"
            "    not_a_real_module = None\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return not_a_real_module is not None\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        9,
        id="result_bare_import_binding_returned",
    ),
    # Codex review (run 309c5bd5034e): an import inside a masking handler
    # binds a name on the failure path, in a function or at module level.
    # Each row skips silently under pytest.
    pytest.param(
        (
            "import pytest\n"
            "def available():\n"
            "    mod = None\n"
            "    try:\n"
            "        import not_a_real_module as other\n"
            "    except ImportError:\n"
            "        import types as mod\n"
            "    return mod is None\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        9,
        id="result_handler_import_binding_returned",
    ),
    pytest.param(
        (
            "import types\n"
            "import pytest\n"
            "mod = None\n"
            "try:\n"
            "    import not_a_real_module as other\n"
            "except ImportError:\n"
            "    import types as mod\n"
            'pytestmark = pytest.mark.skipif(mod is types, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        8,
        id="handler_import_binding_taints_module_name",
    ),
    # Codex review (run e029fa328621): at module level, what the success path
    # of a masking try binds (assignment or import) is import-dependent too.
    # Each row skips silently under pytest.
    pytest.param(
        (
            "import pytest\n"
            "mod = None\n"
            "try:\n"
            "    import not_a_real_module as mod\n"
            "except ImportError:\n"
            "    pass\n"
            'pytestmark = pytest.mark.skipif(mod is None, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        7,
        id="module_success_path_import_binding_taints",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = False\n"
            "try:\n"
            "    import not_a_real_module\n"
            "    _HAVE_MODULE = True\n"
            "except ImportError:\n"
            "    pass\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        8,
        id="module_success_path_assignment_taints",
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
    # Taint mapping negatives: none of these hides a broken import (each
    # either fails loudly or skips for a reason unrelated to the import).
    pytest.param(
        _MASKED_FLAG_PREAMBLE + 'pytestmark = pytest.mark.skip(reason="not ready")\n',
        id="deliberate_unconditional_module_skip",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE + "if not _HAVE_MODULE:\n    thing = None\n",
        id="gated_branch_without_skip",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + '@pytest.mark.parametrize("v", [1] if _HAVE_MODULE else [2])\n'
        + "def test_something(v):\n"
        + "    assert v\n",
        id="non_skip_mark_reads_flag",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + "def _bail():\n"
        + '    pytest.skip("x", allow_module_level=True)\n',
        id="skip_helper_never_called",
    ),
    # Codex review (run 47400ec72c8e): a pytestmark that reads a tainted name
    # but cannot apply a skip because of it is not masking. Both rows were
    # checked against pytest: the first runs its test, the second skips even
    # when the import succeeds (so the skip is not import-driven).
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'pytestmark = pytest.mark.parametrize("available", [_HAVE_MODULE])\n'
        + "def test_something(available):\n"
        + "    assert True\n",
        id="module_parametrize_reads_flag",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + "pytestmark = [\n"
        + '    pytest.mark.parametrize("a", [_HAVE_MODULE]),\n'
        + '    pytest.mark.skip(reason="not ready"),\n'
        + "]\n",
        id="unconditional_skip_beside_flag_read",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE + 'pytestmark = pytest.mark.skip(reason=f"have={_HAVE_MODULE}")\n',
        id="unconditional_skip_mentions_flag_in_reason",
    ),
    # Alias negatives: the aliased mark either cannot skip, or skips whatever
    # the flag says (verified skipped with a working import).
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'MARK = pytest.mark.parametrize("a", [_HAVE_MODULE])\n'
        + "@MARK\n"
        + "def test_something(a):\n"
        + "    assert a is not None\n",
        id="alias_parametrize_decorator_reads_flag",
    ),
    pytest.param(
        _MASKED_FLAG_PREAMBLE
        + 'MARK = pytest.mark.skip(reason=f"have={_HAVE_MODULE}")\n'
        + "@MARK\n"
        + "def test_something():\n"
        + "    assert True\n",
        id="alias_unconditional_skip_decorator",
    ),
    # Scope negatives: each test runs (fails loudly) under pytest, because the
    # helper's assignment never reaches the module global at import time.
    pytest.param(
        "import pytest\n_HAVE_MODULE = True\n" + _PROBE_LOCAL + _SKIPIF_ON_FLAG_TEST,
        id="local_flag_in_uncalled_helper",
    ),
    pytest.param(
        "import pytest\n_HAVE_MODULE = True\n" + _PROBE_LOCAL + "_probe()\n" + _SKIPIF_ON_FLAG_TEST,
        id="local_flag_in_called_helper",
    ),
    pytest.param(
        "import pytest\n_HAVE_MODULE = True\n" + _PROBE_GLOBAL + _SKIPIF_ON_FLAG_TEST,
        id="global_flag_in_uncalled_helper",
    ),
    # A non-skip mark set in a masking handler cannot hide the broken import:
    # the test runs (fails loudly) under pytest.
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            '    pytestmark = pytest.mark.filterwarnings("ignore")\n'
            "def test_feature():\n"
            "    assert not_a_real_module.thing() == 1\n"
        ),
        id="handler_assigns_non_skip_mark",
    ),
    # Flow negatives: an unconditional top-level rebinding clears taint for
    # what is evaluated after it. Each test runs (fails loudly) under pytest.
    pytest.param(
        _FLOW_PREAMBLE
        + "_HAVE_MODULE = True\n"
        + 'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + _FLOW_TEST,
        id="flow_unconditional_clear_before_use",
    ),
    # pytest evaluates a string condition against the module's globals after
    # the module has finished importing, so a later clear still applies.
    pytest.param(
        _FLOW_PREAMBLE
        + 'pytestmark = pytest.mark.skipif("not _HAVE_MODULE", reason="x")\n'
        + "_HAVE_MODULE = True\n"
        + _FLOW_TEST,
        id="flow_string_condition_sees_final_value",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + "_HAVE_MODULE = True\n"
        + "MISSING = not _HAVE_MODULE\n"
        + 'pytestmark = pytest.mark.skipif(MISSING, reason="x")\n'
        + _FLOW_TEST,
        id="flow_derived_after_clear_is_clean",
    ),
    # A real name rebinding still clears (the test runs under pytest).
    pytest.param(
        (
            "from types import SimpleNamespace\n"
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "    state = SimpleNamespace(available=True)\n"
            "except ImportError:\n"
            "    state = SimpleNamespace(available=False)\n"
            "state = SimpleNamespace(available=True)\n"
            'pytestmark = pytest.mark.skipif(not state.available, reason="x")\n'
        ),
        id="flow_real_rebinding_of_object_clears",
    ),
    # Mark-alias negatives: the alias is unconditionally rebound to a non-skip
    # mark before use, so pytest runs each test.
    pytest.param(
        _FLOW_PREAMBLE
        + 'MARK = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + 'MARK = pytest.mark.filterwarnings("ignore")\n'
        + "pytestmark = MARK\n"
        + _FLOW_TEST,
        id="flow_masking_alias_rebound_before_pytestmark",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + 'MARK = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
        + 'MARK = pytest.mark.filterwarnings("ignore")\n'
        + "@MARK\n"
        + _FLOW_TEST,
        id="flow_masking_alias_rebound_before_decorator",
    ),
    pytest.param(
        _FLOW_PREAMBLE
        + 'M = pytest.mark.skip(reason="x")\n'
        + 'M = pytest.mark.filterwarnings("ignore")\n'
        + "pytestmark = M if not _HAVE_MODULE else []\n"
        + _FLOW_TEST,
        id="flow_carrying_alias_rebound_before_use",
    ),
    # Scope negatives (each test runs under pytest): a class-local handler
    # cannot taint the module global; a class-local rebinding shadows a
    # tainted global for that class; a string condition is evaluated against
    # module globals, never the class namespace.
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "class TestProbe:\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        _HAVE_MODULE = False\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="scope_class_handler_does_not_taint_module_global",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "class TestProbe:\n"
            "    _HAVE_MODULE = True\n"
            '    pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "    def test_something(self):\n"
            "        assert False\n"
        ),
        id="scope_class_rebinding_shadows_tainted_global",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "class TestProbe:\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        _HAVE_MODULE = False\n"
            '    pytestmark = pytest.mark.skipif("not _HAVE_MODULE", reason="x")\n'
            "    def test_something(self):\n"
            "        assert False\n"
        ),
        id="scope_string_condition_reads_module_globals",
    ),
    # A direct class-body rebinding under `global` rebinds the module global,
    # so it clears for module and class uses alike (each test runs).
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "class Fixer:\n"
            "    global _HAVE_MODULE\n"
            "    _HAVE_MODULE = True\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="scope_class_global_rebinding_clears_module",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "class TestProbe:\n"
            "    global _HAVE_MODULE\n"
            "    _HAVE_MODULE = True\n"
            '    pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "    def test_something(self):\n"
            "        assert False\n"
        ),
        id="scope_class_global_rebinding_then_class_use",
    ),
    # A class nested directly in an unconditional class runs too, so its
    # `global` rebinding clears the module (the test runs).
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    _HAVE_MODULE = False\n"
            "class Outer:\n"
            "    class Fixer:\n"
            "        global _HAVE_MODULE\n"
            "        _HAVE_MODULE = True\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="scope_nested_unconditional_class_global_clears",
    ),
    # Gap 1-3 negatives: a re-raising handler fails loudly; a handler with no
    # effect on the return value; a masking result used by a non-skip mark;
    # and function bodies defined (not called) inside a handler, which never
    # run at import (Codex review run ea5b9891a5f7). Each test runs or errors.
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        raise\n"
            "    return True\n"
            "_HAVE_MODULE = check()\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_handler_reraises",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return True\n"
            "_HAVE_MODULE = check()\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_handler_without_return_effect",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        return False\n"
            '@pytest.mark.parametrize("v", [check()])\n'
            "def test_something(v):\n"
            "    assert v is not None\n"
        ),
        id="result_used_in_non_skip_mark",
    ),
    pytest.param(
        (
            "import pytest\n"
            "_HAVE_MODULE = True\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    def helper():\n"
            "        _HAVE_MODULE = False\n"
            'pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="handler_defines_uncalled_local_assigner",
    ),
    pytest.param(
        (
            "import pytest\n"
            "try:\n"
            "    import not_a_real_module\n"
            "except ImportError:\n"
            "    def helper():\n"
            '        pytest.skip("x", allow_module_level=True)\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="handler_defines_uncalled_skip_helper",
    ),
    # Implicit-return negatives: the fall-through reaches a later return (same
    # value on both paths), or the function never returns at all, so pytest
    # skips even with a working import (not import-driven).
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_fallthrough_reaches_later_return",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        pass\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_function_never_returns",
    ),
    # Guaranteed later returns (both branches of an if/else, recursively)
    # stop the fall-through, so these tests run under pytest.
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        pass\n"
            '    if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
            "        return True\n"
            "    else:\n"
            "        return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_both_branches_return",
    ),
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        pass\n"
            '    if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
            "        return True\n"
            "    else:\n"
            "        if True:\n"
            "            return True\n"
            "        else:\n"
            "            return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_nested_both_branches_return",
    ),
    # A handler that raises on every path fails collection loudly.
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        raise\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_handler_unconditional_raise",
    ),
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            '        if os.environ.get("NOT_A_REAL_ENV_VAR"):\n'
            "            raise\n"
            "        else:\n"
            '            raise RuntimeError("missing")\n'
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_handler_raises_on_every_branch",
    ),
    # Success-path locals that never reach a return, or a returned local set
    # only before the try, do not depend on the import (tests run).
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        mod = not_a_real_module\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_success_path_assign_not_returned",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    ok = True\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return ok\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_returned_local_set_only_before_try",
    ),
    # An alias of a local unrelated to the import stays clean (test runs).
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    flag = True\n"
            "    result = flag\n"
            "    return result\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_returned_alias_of_unrelated_local",
    ),
    # A direct, unconditional rebinding to an independent value clears the
    # local (both paths return True, the test runs).
    pytest.param(
        (
            "import os\n"
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    available = True\n"
            "    return available\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_unconditional_local_rebind_clears",
    ),
    # A gated branch whose returns all match the fallback, or that does not
    # affect the return at all, is not import-dependent (tests run).
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    if available:\n"
            "        return True\n"
            "    return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_gated_return_same_value_everywhere",
    ),
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    available = False\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        available = True\n"
            "    except ImportError:\n"
            "        pass\n"
            "    if available:\n"
            '        print("ok")\n'
            "    return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_gated_branch_without_return_effect",
    ),
    # A nested probe with a single possible return value (test runs).
    pytest.param(
        (
            "import pytest\n"
            "def check():\n"
            "    if True:\n"
            "        try:\n"
            "            import not_a_real_module\n"
            "        except ImportError:\n"
            "            pass\n"
            "    return True\n"
            'pytestmark = pytest.mark.skipif(not check(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_nested_probe_single_return_value",
    ),
    # A wrapper around a function unrelated to the import stays clean.
    pytest.param(
        (
            "import pytest\n"
            "def probe():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        return False\n"
            "def helper():\n"
            "    return True\n"
            "def available():\n"
            "    return helper()\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_wrapper_of_unrelated_function",
    ),
    # A wrapper that calls a masking result but has one possible return value.
    pytest.param(
        (
            "import pytest\n"
            "def probe():\n"
            "    try:\n"
            "        import not_a_real_module\n"
            "        return True\n"
            "    except ImportError:\n"
            "        return False\n"
            "def available():\n"
            "    probe()\n"
            "    return True\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_wrapper_calls_masking_result_single_return",
    ),
    # A function body resolves bare names against module globals only, so a
    # masking method on a class cannot taint callers of a module-level
    # function with the same name (the test runs).
    pytest.param(
        (
            "import pytest\n"
            "class Unused:\n"
            "    def probe(self):\n"
            "        try:\n"
            "            import not_a_real_module\n"
            "            return True\n"
            "        except ImportError:\n"
            "            return False\n"
            "def probe():\n"
            "    return True\n"
            "def available():\n"
            "    return probe()\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_class_method_does_not_taint_module_wrapper",
    ),
    # The import binds a different name than the one returned, so the result
    # is None either way (pytest skips even with a working import).
    pytest.param(
        (
            "import pytest\n"
            "def available():\n"
            "    mod = None\n"
            "    try:\n"
            "        import not_a_real_module as other\n"
            "    except ImportError:\n"
            "        pass\n"
            "    return mod is not None\n"
            'pytestmark = pytest.mark.skipif(not available(), reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="result_import_binds_unrelated_name",
    ),
    # The skip reads a name the probe never touches (always False, so pytest
    # skips even with a working import: not import-driven).
    pytest.param(
        (
            "import pytest\n"
            "OTHER = False\n"
            "try:\n"
            "    import not_a_real_module\n"
            "    _HAVE_MODULE = True\n"
            "except ImportError:\n"
            "    pass\n"
            'pytestmark = pytest.mark.skipif(not OTHER, reason="x")\n'
            "def test_something():\n"
            "    assert False\n"
        ),
        id="module_skip_reads_name_unrelated_to_probe",
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
