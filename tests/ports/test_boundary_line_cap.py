"""A crossing artefact with an over-long line is rejected before it is scanned (G-2039).

Review round 4: the forbidden-content scan reuses a generic email pattern that is quadratic
on a long uninterrupted word, and it ran before any size check. A 40,000-character word in
one cell took about four seconds and the time grew with the square of the length, so a
malformed export could hold the CLI or a CI worker for minutes. No exception is raised, so
the fail-closed guard never saw it.

Real artefacts have short lines (a verdict reason is capped at 300 characters, the ledger
is wrapped by its canonical encoding, a counts row is seven short cells), so a line cap
costs nothing and bounds the scan.
"""

from __future__ import annotations

import time

import pytest

from tests.ports.boundary import (
    COUNTS_HEADER,
    MAX_LINE_CHARS,
    counts_problems,
    private_rows_problems,
    verdict_problems,
)
from tests.ports.test_boundary_gates import _counts_text, _verdict_text

_WORD = "a" * 60_000  # about 8 seconds in the scan before the fix; minutes at ten times that


def _counts(word: str) -> str:
    return ",".join(COUNTS_HEADER) + f"\n{word},2026-06,1,1,1,1,1\n"


def _verdicts(word: str) -> str:
    return _verdict_text(tail=word)


def _ledger(word: str) -> str:
    return f"schema: 1\nrows:\n- id: P-01\n  description: {word}\n"


_CASES = [
    ("counts", counts_problems, _counts),
    ("verdicts", verdict_problems, _verdicts),
    ("private-rows", private_rows_problems, _ledger),
]


@pytest.mark.parametrize(("validate", "build"), [c[1:] for c in _CASES], ids=[c[0] for c in _CASES])
def test_an_over_long_line_is_rejected_quickly_and_by_position(validate, build):
    started = time.monotonic()
    problems = validate(build(_WORD))
    elapsed = time.monotonic() - started

    assert any(f"longer than {MAX_LINE_CHARS} characters" in p for p in problems), problems
    assert elapsed < 2.0, f"scan took {elapsed:.1f}s"
    assert not any(_WORD[:50] in p for p in problems)


def test_a_line_at_the_cap_is_still_scanned():
    """The cap is exclusive: a line of exactly MAX_LINE_CHARS is scanned like any other."""
    header = ",".join(COUNTS_HEADER)
    padding = " " * (MAX_LINE_CHARS - len("person@example.org"))
    at_cap = counts_problems(f"{header}\nperson@example.org{padding}\n")
    over_cap = counts_problems(f"{header}\nperson@example.org{padding} \n")

    assert not any("longer than" in p for p in at_cap), at_cap
    assert any("forbidden content" in p for p in at_cap), at_cap
    assert any("longer than" in p for p in over_cap), over_cap


def test_real_shaped_artefacts_are_far_below_the_cap():
    longest = max(
        len(line) for text in (_counts_text(), _verdict_text()) for line in text.splitlines()
    )

    assert longest < MAX_LINE_CHARS // 4
    assert MAX_LINE_CHARS >= 1000
