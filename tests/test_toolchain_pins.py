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

import pytest
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


# ---------------------------------------------------------------------------
# Parser self-tests (Task 2, G-1383): prove the parsers themselves are correct
# against constructed fixtures, independent of whatever the real repo files
# currently contain. These are what let test_ruff_pin_matches_precommit_rev be
# trusted as a real drift signal rather than an accident of today's config.
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    """Write `content` to `tmp_path / name`, creating parent dirs, and return the path."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_pin_parsers_detect_drift_between_fixture_files(tmp_path):
    """Mismatched fixtures produce two different, correctly-parsed version strings."""
    pyproject = _write(
        tmp_path,
        "pyproject.toml",
        '[project.optional-dependencies]\ndev = ["ruff==1.0.0"]\n',
    )
    precommit = _write(
        tmp_path,
        ".pre-commit-config.yaml",
        "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v2.0.0\n",
    )
    pin = get_pyproject_ruff_pin(pyproject)
    rev = get_precommit_ruff_rev(precommit)
    assert pin == "1.0.0"
    assert rev == "2.0.0"
    assert pin != rev


def test_pin_parsers_agree_on_matching_fixtures(tmp_path):
    """Matching fixtures produce equal, v-stripped version strings."""
    pyproject = _write(
        tmp_path,
        "pyproject.toml",
        '[project.optional-dependencies]\ndev = ["ruff==1.2.3"]\n',
    )
    precommit = _write(
        tmp_path,
        ".pre-commit-config.yaml",
        "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v1.2.3\n",
    )
    pin = get_pyproject_ruff_pin(pyproject)
    rev = get_precommit_ruff_rev(precommit)
    assert pin == rev == "1.2.3"
    assert not rev.startswith("v")


def test_precommit_rev_comes_from_the_ruff_block_not_the_first_rev(tmp_path):
    """The parser targets the ruff-pre-commit block specifically, not the first rev: line."""
    precommit = _write(
        tmp_path,
        ".pre-commit-config.yaml",
        "repos:\n"
        "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
        "    rev: v5.0.0\n"
        "    hooks:\n"
        "      - id: check-yaml\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v1.2.3\n"
        "    hooks:\n"
        "      - id: ruff\n",
    )
    rev = get_precommit_ruff_rev(precommit)
    assert rev == "1.2.3"
    assert rev != "5.0.0"


@pytest.mark.parametrize(
    "repo_line,rev_line",
    [
        ("  - repo: https://github.com/astral-sh/ruff-pre-commit", '    rev: "v1.2.3"'),
        ("  - repo: https://github.com/astral-sh/ruff-pre-commit", "    rev: 'v1.2.3'"),
        (
            "  - repo: https://github.com/astral-sh/ruff-pre-commit",
            "    rev: v1.2.3  # pinned by G-1383",
        ),
        ('  - repo: "https://github.com/astral-sh/ruff-pre-commit"', "    rev: v1.2.3"),
    ],
    ids=["double-quoted-rev", "single-quoted-rev", "trailing-comment", "quoted-repo-url"],
)
def test_precommit_rev_tolerates_quotes_and_trailing_comment(tmp_path, repo_line, rev_line):
    """Quoting and trailing comments around the repo/rev lines don't affect parsing."""
    precommit = _write(tmp_path, ".pre-commit-config.yaml", f"repos:\n{repo_line}\n{rev_line}\n")
    rev = get_precommit_ruff_rev(precommit)
    assert rev == "1.2.3"
    assert isinstance(rev, str)


def test_precommit_rev_rejects_missing_ruff_block(tmp_path):
    """Absence of the ruff-pre-commit repo block raises ValueError naming it."""
    precommit = _write(
        tmp_path,
        ".pre-commit-config.yaml",
        "repos:\n  - repo: https://github.com/pre-commit/pre-commit-hooks\n    rev: v5.0.0\n",
    )
    with pytest.raises(ValueError) as excinfo:
        get_precommit_ruff_rev(precommit)
    message = str(excinfo.value)
    assert "ruff-pre-commit" in message
    assert "found 0" in message


def test_precommit_rev_rejects_duplicate_ruff_blocks(tmp_path):
    """Two ruff-pre-commit repo blocks raise ValueError rather than picking one silently."""
    precommit = _write(
        tmp_path,
        ".pre-commit-config.yaml",
        "repos:\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v1.0.0\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v2.0.0\n",
    )
    with pytest.raises(ValueError) as excinfo:
        get_precommit_ruff_rev(precommit)
    message = str(excinfo.value)
    assert "ruff-pre-commit" in message
    assert "found 2" in message


def test_precommit_rev_rejects_frozen_sha_rev(tmp_path):
    """A frozen 40-hex SHA rev is rejected loudly instead of silently accepted."""
    sha = "a" * 40
    precommit = _write(
        tmp_path,
        ".pre-commit-config.yaml",
        f"repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: {sha}\n",
    )
    with pytest.raises(ValueError) as excinfo:
        get_precommit_ruff_rev(precommit)
    message = str(excinfo.value)
    assert sha in message
    assert "frozen SHA" in message


@pytest.mark.parametrize(
    "dev_list,expected_substrings",
    [
        ('["ruff>=1.0.0"]', ("==", "ruff must be pinned")),
        ('["ruff==1.*"]', ("==", "ruff must be pinned")),
        ('["black==24.0.0"]', ("ruff", "found 0")),
    ],
    ids=["floor", "wildcard", "no-ruff-entry"],
)
def test_pyproject_pin_rejects_non_exact_specifiers(tmp_path, dev_list, expected_substrings):
    """A floor, a wildcard, or a missing ruff entry all raise ValueError naming the problem."""
    pyproject = _write(
        tmp_path, "pyproject.toml", f"[project.optional-dependencies]\ndev = {dev_list}\n"
    )
    with pytest.raises(ValueError) as excinfo:
        get_pyproject_ruff_pin(pyproject)
    message = str(excinfo.value)
    assert expected_substrings[0] in message
    assert expected_substrings[1] in message


def test_pyproject_pin_matches_ruff_by_canonical_name(tmp_path):
    """canonicalize_name distinguishes ruff from lookalike packages like ruff-lsp."""
    pyproject = _write(
        tmp_path,
        "pyproject.toml",
        '[project.optional-dependencies]\ndev = ["ruff-lsp==0.0.1", "ruff==1.2.3"]\n',
    )
    pin = get_pyproject_ruff_pin(pyproject)
    assert pin == "1.2.3"
    assert pin != "0.0.1"
