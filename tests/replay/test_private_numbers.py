"""Non-finite numbers never enter a frozen private golden (review round 5, G-2039).

Python's ``json.loads`` accepts ``NaN``, ``Infinity`` and ``-Infinity``, which are not JSON,
and ``dump_jsonl`` writes them back unchanged, so a sample carrying one passed validation
and could be frozen with ``--register-private``. A strict reader cannot load such a file.

Every numeric position of every Family B sample is driven with all three constants.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.replay import _support as S
from tests.replay.test_golden import _clean_private_rows
from tests.replay.test_private_guards import _problems


def _numeric_paths(value: Any, prefix: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield prefix
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _numeric_paths(child, (*prefix, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _numeric_paths(child, (*prefix, index))


def _set(root: Any, path: tuple[Any, ...], new: Any) -> None:
    for key in path[:-1]:
        root = root[key]
    root[path[-1]] = new


_CASES = [
    (cls, path)
    for cls in S.FAMILY_B_CLASSES
    for path in _numeric_paths(_clean_private_rows(cls)[0])
]


def test_the_samples_carry_numbers_to_replace():
    """Guard for the matrix below: it is not empty and it reaches the scoring sample."""
    assert len(_CASES) >= 3
    assert "private_scoring" in {cls for cls, _ in _CASES}


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "-inf"]
)
@pytest.mark.parametrize(
    ("cls", "path"), _CASES, ids=[f"{c}:{'.'.join(map(str, p))}" for c, p in _CASES]
)
def test_a_non_finite_number_is_rejected(tmp_path, cls, path, bad):
    rows = _clean_private_rows(cls)
    _set(rows[0], path, bad)

    problems = _problems(tmp_path, cls, rows)

    assert problems != []
    assert any("not valid JSON" in p for p in problems), problems


def test_the_number_check_itself_refuses_non_finite_values():
    """An overflowing literal such as 1e999 parses to infinity without any constant token."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        assert not S._is_number(bad), bad
    assert S._is_number(10**400)
    assert S._is_number(0.5)
    assert not S._is_number(True)
