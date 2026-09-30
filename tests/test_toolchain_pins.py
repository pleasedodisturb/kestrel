"""Guard against ruff version drift between pyproject.toml and .pre-commit-config.yaml.

G-1383 saw three different ruff versions in one day: `.pre-commit-config.yaml`
pinned `v0.11.0`, a contributor's local `.venv` reported `0.15.15`, and the same
day's green CI run resolved `ruff-0.16.9` from `pyproject.toml`'s `ruff>=0.11.0`
floor. A floating floor is fine for a library whose *API* matters, but ruff's
*output* (lint findings, reformatted bytes) is compared across two
independently-installed copies of the tool — pre-commit's isolated hook
environment and CI's `pip install -e .[dev]` — and "any version >= X" gives no
guarantee those two installs resolve to the same release.

This file guards two things: that `pyproject.toml`'s `dev` extra pins ruff with
an exact `==` specifier and that value equals the `rev:` pinned for
astral-sh/ruff-pre-commit in `.pre-commit-config.yaml`, and that
`[tool.ruff] force-exclude = true` keeps the `_alembic` exclude intact.

A one-sided Dependabot PR that bumps only the pyproject pin (or only the
pre-commit rev) is EXPECTED to fail `test_ruff_pin_matches_precommit_rev` until
the other file follows in the same PR — that failure is this file's entire
purpose, not a bug in it.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_REPO_ROOT = Path(__file__).resolve().parent.parent
RUFF_PRECOMMIT_URL = "https://github.com/astral-sh/ruff-pre-commit"

_REPO_LINE_RE = re.compile(r"^\s*-\s*repo:\s*(.+)$")
_REV_LINE_RE = re.compile(r"^\s*rev:\s*(.+)$")
_VERSION_REV_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


def _strip_quotes_and_comment(value: str) -> str:
    """Strip surrounding quotes (single or double) and a trailing # comment."""
    value = value.strip()
    if value and value[0] in "\"'":
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            return value[1:end]
        return value[1:]
    idx = value.find("#")
    if idx != -1:
        value = value[:idx]
    return value.strip()


def get_pyproject_ruff_pin(path: Path) -> str:
    """Return the exact ruff version pinned in pyproject.toml's dev extra.

    Raises ValueError if there is not exactly one ruff entry, or if that entry
    is not pinned with a single exact `==` specifier (no wildcard).
    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    dev_entries = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    ruff_reqs = [
        req
        for entry in dev_entries
        if canonicalize_name((req := Requirement(entry)).name) == "ruff"
    ]
    if len(ruff_reqs) != 1:
        raise ValueError(
            f"{path}: expected exactly one ruff entry in "
            f"project.optional-dependencies.dev, found {len(ruff_reqs)}"
        )
    req = ruff_reqs[0]
    specifiers = list(req.specifier)
    if len(specifiers) != 1 or specifiers[0].operator != "==" or "*" in specifiers[0].version:
        raise ValueError(
            "ruff must be pinned with == so pre-commit and CI install the same "
            f'version, found specifier: "{req.specifier}"'
        )
    return specifiers[0].version


def get_precommit_ruff_rev(path: Path) -> str:
    """Return the ruff-pre-commit rev (without the leading v) from .pre-commit-config.yaml.

    Raises ValueError if there is not exactly one astral-sh/ruff-pre-commit repo
    block, if that block does not have exactly one `rev:` line, or if the rev
    is not a `vX.Y.Z` version (e.g. a frozen SHA rev).
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    repo_indices = [i for i, line in enumerate(lines) if _REPO_LINE_RE.match(line)]
    ruff_repo_indices = []
    for idx in repo_indices:
        match = _REPO_LINE_RE.match(lines[idx])
        assert match is not None
        url = _strip_quotes_and_comment(match.group(1))
        if url.endswith(".git"):
            url = url[: -len(".git")]
        if url == RUFF_PRECOMMIT_URL:
            ruff_repo_indices.append(idx)
    if len(ruff_repo_indices) != 1:
        raise ValueError(
            f"{path}: expected exactly one repo entry for {RUFF_PRECOMMIT_URL}, "
            f"found {len(ruff_repo_indices)}"
        )
    start = ruff_repo_indices[0]
    later_repo_indices = [i for i in repo_indices if i > start]
    end = min(later_repo_indices) if later_repo_indices else len(lines)
    rev_line_indices = [i for i in range(start, end) if _REV_LINE_RE.match(lines[i])]
    if len(rev_line_indices) != 1:
        raise ValueError(
            f"{path}: expected exactly one rev: line for {RUFF_PRECOMMIT_URL}, "
            f"found {len(rev_line_indices)}"
        )
    rev_match = _REV_LINE_RE.match(lines[rev_line_indices[0]])
    assert rev_match is not None
    rev = _strip_quotes_and_comment(rev_match.group(1))
    version_match = _VERSION_REV_RE.match(rev)
    if not version_match:
        raise ValueError(
            f"{path}: ruff-pre-commit rev must be a version like v1.2.3, found "
            f"{rev!r} (a frozen SHA rev is rejected)"
        )
    return version_match.group(1)


def test_ruff_pin_matches_precommit_rev():
    """pyproject's exact ruff pin must equal the astral-sh/ruff-pre-commit rev."""
    pin = get_pyproject_ruff_pin(_REPO_ROOT / "pyproject.toml")
    rev = get_precommit_ruff_rev(_REPO_ROOT / ".pre-commit-config.yaml")
    assert re.fullmatch(r"\d+\.\d+\.\d+", pin), pin
    assert pin == rev, (
        f"ruff drift: pyproject.toml dev extra pins ruff=={pin} but "
        f".pre-commit-config.yaml astral-sh/ruff-pre-commit rev is v{rev}; "
        "bump both together (G-1383)"
    )


def test_ruff_exclude_keeps_alembic_out():
    """force-exclude plus extend-exclude keep _alembic out of every invocation shape."""
    with (_REPO_ROOT / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    ruff_config = data["tool"]["ruff"]
    assert ruff_config["force-exclude"] is True
    assert "src/career_os/_alembic" in ruff_config["extend-exclude"]
