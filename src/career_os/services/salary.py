"""Shared salary parsing utilities.

Provides salary string → numeric value conversion used across multiple services
(discovery filtering, job search, market intelligence, sorting).
"""

from __future__ import annotations

import re

# Matches numbers optionally followed by 'k'/'K' suffix.
# Group 1: the numeric part (may contain commas, dots, spaces).
# Group 2: the optional 'k'/'K' suffix.
_SALARY_RE = re.compile(r"(\d[\d,. ]*\d|\d)([kK])?")


def parse_salary_range(salary_str: str | None) -> tuple[float | None, float | None]:
    """Extract (low, high) salary values from a salary range string.

    Handles formats like:
    - "130000-160000 EUR"
    - "130,000 - 160,000"
    - "180000-220000 USD"
    - "$120k-$150k"
    - "€80k-€100k"
    - "120k-160k EUR"
    - "60k"
    - "120000"

    Returns (None, None) if parsing fails.
    """
    if not salary_str:
        return None, None

    matches = _SALARY_RE.findall(salary_str)
    if not matches:
        return None, None

    values: list[float] = []
    for num_str, k_suffix in matches:
        cleaned = num_str.replace(",", "").replace(" ", "").replace(".", "")
        try:
            val = float(cleaned)
            # Apply k-notation multiplier (e.g., 120k → 120000)
            if k_suffix:
                val *= 1000
            # Ignore implausibly small numbers (likely not salary)
            if val >= 1000:
                values.append(val)
        except ValueError:
            continue

    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    return min(values), max(values)


def salary_midpoint(salary_str: str | None) -> float | None:
    """Parse a salary string and return the midpoint value.

    Useful for numeric sorting and comparison.
    Returns None if the salary cannot be parsed.
    """
    low, high = parse_salary_range(salary_str)
    if low is None or high is None:
        return None
    return (low + high) / 2.0
