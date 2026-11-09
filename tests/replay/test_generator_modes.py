"""The golden generator's operations never combine (review round 2, G-2039).

``--check`` promises to write nothing. Before the fix ``main`` dispatched on the first
operation flag it met, so ``--check --register-awaiting`` ran the registration and rewrote
MANIFEST.json, ``--check --register-private`` could freeze a class, and a regeneration
request (``--all`` or ``--class``) given together with a registration was silently dropped.

Every case runs against a copy of the golden directory in which one awaiting entry has been
removed, so a registration that runs is visible as a changed MANIFEST.
"""

from __future__ import annotations

import pytest

from tests.replay import _support as S
from tests.replay import generate_golden
from tests.replay.test_golden import _copy_golden, _snapshot

_SHA = "0123456789abcdef0123456789abcdef01234567"
_REGISTER_PRIVATE = [
    "--register-private",
    "private_scoring",
    "--file",
    "unused.jsonl",
    "--private-commit",
    _SHA,
]

_CONFLICTS = [
    ("check-with-register-awaiting", ["--check", "--register-awaiting"]),
    ("register-awaiting-with-check", ["--register-awaiting", "--check"]),
    ("check-with-register-private", ["--check", *_REGISTER_PRIVATE]),
    ("check-with-dry-run-registration", ["--check", *_REGISTER_PRIVATE, "--dry-run"]),
    ("both-registrations", ["--register-awaiting", *_REGISTER_PRIVATE]),
    ("regenerate-all-with-register-awaiting", ["--all", "--register-awaiting"]),
    (
        "regenerate-class-with-register-awaiting",
        ["--class", "dedup_verdicts", "--register-awaiting"],
    ),
    ("regenerate-all-with-register-private", ["--all", *_REGISTER_PRIVATE]),
]


def _copy_missing_one_awaiting_entry(tmp_path):
    """A golden copy whose MANIFEST lacks one awaiting class: a registration would add it."""
    copy_dir = _copy_golden(tmp_path)
    manifest_path = copy_dir / "MANIFEST.json"
    manifest = S.load_manifest(manifest_path)
    del manifest["classes"]["private_scoring"]
    manifest_path.write_text(S.dump_manifest(manifest), encoding="utf-8", newline="")
    return copy_dir


@pytest.mark.parametrize("flags", [c[1] for c in _CONFLICTS], ids=[c[0] for c in _CONFLICTS])
def test_conflicting_operations_are_refused_before_anything_is_written(tmp_path, capsys, flags):
    copy_dir = _copy_missing_one_awaiting_entry(tmp_path)
    before = _snapshot(copy_dir)

    with pytest.raises(SystemExit) as refused:
        generate_golden.main([*flags, "--golden-dir", str(copy_dir)])

    assert refused.value.code == 2
    assert "separate operations" in capsys.readouterr().err
    assert _snapshot(copy_dir) == before


def test_the_copy_really_shows_a_registration_that_runs(tmp_path):
    """Guard for the cases above: on this copy a registration does change the MANIFEST."""
    copy_dir = _copy_missing_one_awaiting_entry(tmp_path)
    before = _snapshot(copy_dir)

    code = generate_golden.main(["--register-awaiting", "--golden-dir", str(copy_dir)])

    assert code == 0
    assert _snapshot(copy_dir) != before
    assert "private_scoring" in S.load_manifest(copy_dir / "MANIFEST.json")["classes"]


_PRIVATE_ONLY = [
    ("dry-run", ["--dry-run"]),
    ("file", ["--file", "unused.jsonl"]),
    ("private-commit", ["--private-commit", _SHA]),
    ("gates", ["--gates", "fact"]),
    ("producer-row", ["--producer-row", "P-01"]),
    ("ledger", ["--ledger", "unused.yaml"]),
]
_OTHER_OPERATIONS = [
    ("register-awaiting", ["--register-awaiting"]),
    ("check", ["--check"]),
    ("regenerate", ["--all"]),
]


@pytest.mark.parametrize(
    "operation", [o[1] for o in _OTHER_OPERATIONS], ids=[o[0] for o in _OTHER_OPERATIONS]
)
@pytest.mark.parametrize("option", [o[1] for o in _PRIVATE_ONLY], ids=[o[0] for o in _PRIVATE_ONLY])
def test_an_option_of_private_registration_is_refused_on_every_other_operation(
    tmp_path, capsys, operation, option
):
    """Review round 3: ``--register-awaiting --dry-run`` wrote the MANIFEST.

    The options that belong to ``--register-private`` were only checked after the other
    registration had already run, so a requested dry run mutated the file.
    """
    copy_dir = _copy_missing_one_awaiting_entry(tmp_path)
    before = _snapshot(copy_dir)

    with pytest.raises(SystemExit) as refused:
        generate_golden.main([*operation, *option, "--golden-dir", str(copy_dir)])

    assert refused.value.code == 2
    assert "belong to --register-private" in capsys.readouterr().err
    assert _snapshot(copy_dir) == before


def test_check_still_accepts_the_class_selectors(tmp_path):
    """``--check --all`` is the documented spelling; it stays one operation and writes nothing."""
    copy_dir = _copy_golden(tmp_path)
    before = _snapshot(copy_dir)

    code = generate_golden.main(["--check", "--all", "--golden-dir", str(copy_dir)])

    assert code == 0
    assert _snapshot(copy_dir) == before
