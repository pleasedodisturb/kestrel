"""Performance gate for the geo engine (G-1474): 10k classifications, no compile.

A per-call ``re.compile`` regression is ~2 orders of magnitude slower than the
compile-once design, so the 5s wall-clock budget is generous enough to be
non-flaky on shared CI runners while still catching an O(n * regex-compile)
regression loudly. The second test asserts precompilation directly: every
pattern field of both presets is already a compiled ``re.Pattern``, and zero
``re.compile`` calls happen during a classification batch.

Eval-marked: runs in the dedicated "Geo blind-set gate" CI step.
"""

from __future__ import annotations

import dataclasses
import itertools
import re
import time

import pytest

from career_os.services.geo.presets import FRANKFURT_PROFILE, US_REMOTE_PROFILE
from tests.eval.geo.replay import classify, load_items

pytestmark = pytest.mark.eval

PERF_BUDGET_SECONDS = 5.0
N_CLASSIFICATIONS = 10_000


def test_10k_classifications_within_wall_clock_budget():
    """Cycle the blind-set records through geo_eligibility 10,000 times."""
    items = load_items()
    batch = list(itertools.islice(itertools.cycle(items), N_CLASSIFICATIONS))

    start = time.perf_counter()
    for item in batch:
        classify(item, FRANKFURT_PROFILE)
    elapsed = time.perf_counter() - start

    assert elapsed < PERF_BUDGET_SECONDS, (
        f"{N_CLASSIFICATIONS} classifications took {elapsed:.2f}s "
        f"(budget {PERF_BUDGET_SECONDS}s) — a call-time regex-compile regression?"
    )


def test_preset_patterns_are_precompiled_and_never_recompiled(monkeypatch):
    """Every pattern field is a compiled ``re.Pattern``; zero ``re.compile`` at call time."""
    for profile in (FRANKFURT_PROFILE, US_REMOTE_PROFILE):
        checked = 0
        for field in dataclasses.fields(profile):
            # Selected off the annotation, not a name allow-list: a new pattern
            # field is covered automatically, a new non-pattern flag
            # (home_wins, allow_unspecified_remote) is skipped automatically.
            if "re.Pattern" not in str(field.type):
                continue
            checked += 1
            value = getattr(profile, field.name)
            assert value is None or isinstance(value, re.Pattern), (
                f"{profile.name}.{field.name} is not precompiled: {type(value)!r}"
            )
        assert checked >= 9, f"{profile.name}: only {checked} pattern fields inspected"

    def _forbidden_compile(*args, **kwargs):
        raise AssertionError(
            f"re.compile called during classification (args={args!r}) — "
            "all geo patterns must be compiled once at profile construction"
        )

    items = load_items()
    monkeypatch.setattr(re, "compile", _forbidden_compile)
    for item in itertools.islice(itertools.cycle(items), 500):
        classify(item, FRANKFURT_PROFILE)
        classify(item, US_REMOTE_PROFILE)
