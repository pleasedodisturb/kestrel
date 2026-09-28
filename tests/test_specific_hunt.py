"""AST-only tests for tools/specific_hunt.py (G-1802).

This file is parsed with `ast`, never imported — specific_hunt.py imports
jobspy at module scope, and importing it would pull in the real dependency.
"""

import ast
from pathlib import Path

SPECIFIC_HUNT_PATH = Path(__file__).resolve().parent.parent / "tools" / "specific_hunt.py"


def _parse_specific_hunt() -> ast.Module:
    """Parse tools/specific_hunt.py into an AST module."""
    source = SPECIFIC_HUNT_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(SPECIFIC_HUNT_PATH))


def _scrape_jobs_calls(tree: ast.Module) -> list[ast.Call]:
    """Find every Call node whose func is the Name `scrape_jobs`."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "scrape_jobs"
    ]


class TestSpecificHuntDocstring:
    """The module docstring documents blank LinkedIn descriptions (AC6)."""

    def test_docstring_mentions_linkedin_fetch_description_and_blank_and_374(self):
        """Docstring names the opt-in flag, the "blank" symptom, and issue #374."""
        tree = _parse_specific_hunt()
        docstring = ast.get_docstring(tree)

        assert docstring is not None
        assert "linkedin_fetch_description" in docstring
        assert "blank" in docstring
        assert "#374" in docstring


class TestSpecificHuntCallShape:
    """The doc must match the actual call: no opt-in, LinkedIn is in scope."""

    def test_exactly_one_scrape_jobs_call(self):
        """specific_hunt.py makes exactly one scrape_jobs call site."""
        tree = _parse_specific_hunt()
        calls = _scrape_jobs_calls(tree)

        assert len(calls) == 1
        assert isinstance(calls[0].func, ast.Name)

    def test_call_includes_linkedin_and_no_fetch_description_kwarg(self):
        """The call's site_name includes linkedin and passes no linkedin_fetch_description."""
        tree = _parse_specific_hunt()
        call = _scrape_jobs_calls(tree)[0]

        site_name_kw = next(kw for kw in call.keywords if kw.arg == "site_name")
        site_names = [elt.value for elt in site_name_kw.value.elts]
        kwarg_names = [kw.arg for kw in call.keywords]

        assert "linkedin" in site_names
        assert "linkedin_fetch_description" not in kwarg_names
