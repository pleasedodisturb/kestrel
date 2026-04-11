"""Unit tests for `career_os.services.salary`.

Direct tests for `parse_salary_range` and `salary_midpoint`. The salary
helpers are used heavily in jobs search, scoring and discovery filtering, so
covering edge cases here protects every downstream consumer.
"""

import pytest

from career_os.services.salary import parse_salary_range, salary_midpoint

# ---------------------------------------------------------------------------
# parse_salary_range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("130000-160000 EUR", (130_000.0, 160_000.0)),
        ("130,000 - 160,000", (130_000.0, 160_000.0)),
        ("$120k-$150k", (120_000.0, 150_000.0)),
        ("€80k-€100k", (80_000.0, 100_000.0)),
        ("120k-160k EUR", (120_000.0, 160_000.0)),
        ("120000", (120_000.0, 120_000.0)),
        ("60k", (60_000.0, 60_000.0)),
        ("180000-220000 USD", (180_000.0, 220_000.0)),
    ],
)
def test_parse_salary_range_happy_paths(text, expected):
    assert parse_salary_range(text) == expected


@pytest.mark.parametrize("falsy", [None, "", "   "])
def test_parse_salary_range_empty_returns_none(falsy):
    """Falsy / empty input returns (None, None)."""
    assert parse_salary_range(falsy) == (None, None)


@pytest.mark.parametrize(
    "garbage",
    [
        "negotiable",
        "competitive",
        "DOE",
    ],
)
def test_parse_salary_range_no_numbers(garbage):
    """Strings without any digits return (None, None)."""
    assert parse_salary_range(garbage) == (None, None)


def test_parse_salary_range_filters_implausibly_small_values():
    """Numbers below the 1000 threshold are dropped (likely not salary)."""
    # "10-20 hours" should not be treated as a salary
    low, high = parse_salary_range("10-20 hours per week")
    assert low is None and high is None


def test_parse_salary_range_returns_tuple_of_floats():
    """Even single-value inputs come back as (low, high) floats."""
    low, high = parse_salary_range("100k")
    assert isinstance(low, float)
    assert isinstance(high, float)
    assert low == high == 100_000.0


def test_parse_salary_range_min_max_ordering():
    """Reversed input → min/max ordering preserved."""
    low, high = parse_salary_range("160k-120k")
    assert low == 120_000.0
    assert high == 160_000.0


# ---------------------------------------------------------------------------
# salary_midpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected_mid"),
    [
        ("100k-200k", 150_000.0),
        ("100000", 100_000.0),
        ("$80k-$120k", 100_000.0),
    ],
)
def test_salary_midpoint_happy_paths(text, expected_mid):
    assert salary_midpoint(text) == expected_mid


@pytest.mark.parametrize("falsy", [None, "", "competitive"])
def test_salary_midpoint_unparseable_returns_none(falsy):
    assert salary_midpoint(falsy) is None


def test_salary_midpoint_single_value():
    """A single salary value returns itself as the midpoint."""
    assert salary_midpoint("90k") == 90_000.0
