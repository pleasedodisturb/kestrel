"""Single-source company blocklist + soft-flag matcher.

Source of truth: ``config/blocklist.yaml`` (copy ``config/blocklist.example.yaml``
to create your own). Imported by the scoring/discovery tooling so the hard-block
and soft-flag lists never drift, and surfaced to discovery agents via
:func:`prompt_snippet`.

Matching is **word-boundary**, case-insensitive -- NOT substring. This fixes both
failure modes of a naive ``if blocked in company_lower`` loop:

* false-negative: a bare token like ``"acme"`` can be blocked without also needing
  it to appear as a substring;
* false-positive: a short token no longer matches *inside* an unrelated company
  name (e.g. blocking ``"orbix"`` must not catch ``"Orbixual Systems"``).

If the YAML is missing or unreadable we fall back to the embedded
:data:`FLOOR_BLOCKED` / :data:`FLOOR_SOFT_FLAG` so the live list can never silently
empty. ``tools/tests/test_blocklist.py`` enforces the non-shrink PATTERN: every
:data:`FLOOR_BLOCKED` entry must stay loaded and blocked. In this repo the personal
``config/blocklist.yaml`` is gitignored, so CI only exercises the floor itself; the
guard bites for real once you track a config (e.g. in a private fork) -- that config
must then stay a superset of the floor or the suite goes red.

The floor entries here are OBVIOUSLY-FICTIONAL examples. Replace them (and the
example YAML) with your own values-based blocklist.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "blocklist.yaml"

# Embedded floor -- fictional example entries. Doubles as (a) the runtime fallback
# if the YAML is unreadable and (b) the floor that tests/test_blocklist.py asserts
# is always loaded + blocked (the non-shrink pattern; see module docstring).
FLOOR_BLOCKED: tuple[str, ...] = (
    # Fictional surveillance / values-mismatch examples -- swap for your own.
    "acme spyware",
    "shadowtrack",
    "panopticorp",
    "villain industries",
    "evilcorp",
    "orbix",
    "lowball labs",
)

FLOOR_SOFT_FLAG: dict[str, str] = {
    "flagco": ("example soft-flag -- recruiter-only intro; route warm, never cold-batch"),
    "cooldownco": "example soft-flag -- recently in pipeline; hold before re-applying",
}


def _load() -> tuple[list[str], dict[str, str]]:
    """Load the blocklist + soft-flag map from YAML, falling back to the floor."""
    try:
        data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        blocked: list[str] = []
        for group in (data.get("blocked") or {}).values():
            blocked.extend(str(c).strip().lower() for c in (group or []) if str(c).strip())
        soft = {str(k).strip().lower(): str(v) for k, v in (data.get("soft_flag") or {}).items()}
        if not blocked:
            raise ValueError("config/blocklist.yaml parsed to an empty blocked list")
        # de-dupe, preserve order
        blocked = list(dict.fromkeys(blocked))
        return blocked, (soft or dict(FLOOR_SOFT_FLAG))
    except (OSError, yaml.YAMLError, ValueError) as exc:  # pragma: no cover - defensive
        print(
            f"[blocklist] WARNING: falling back to embedded floor ({exc})",
            file=sys.stderr,
        )
        return list(FLOOR_BLOCKED), dict(FLOOR_SOFT_FLAG)


BLOCKED_COMPANIES, SOFT_FLAG_COMPANIES = _load()


def _compile(entries) -> re.Pattern:
    """Compile entries into one case-insensitive word-boundary alternation."""
    if not entries:
        # Match nothing.
        return re.compile(r"(?!x)x")
    alt = "|".join(re.escape(e) for e in entries)
    return re.compile(rf"\b(?:{alt})\b", re.IGNORECASE)


_BLOCKED_RE = _compile(BLOCKED_COMPANIES)
_SOFT_FLAG_RE = _compile(list(SOFT_FLAG_COMPANIES))


def is_blocked(company: str | None) -> str | None:
    """Return the blocklist entry that matches ``company`` (word-boundary), else None."""
    if not company:
        return None
    m = _BLOCKED_RE.search(company.lower())
    return m.group(0) if m else None


def soft_flag_reason(company: str | None) -> str | None:
    """Return the soft-flag note for ``company`` (surface-with-warning), else None."""
    if not company:
        return None
    m = _SOFT_FLAG_RE.search(company.lower())
    return SOFT_FLAG_COMPANIES.get(m.group(0)) if m else None


def prompt_snippet() -> str:
    """Render the blocklist for injection into discovery/scoring agent prompts."""
    blocked = ", ".join(BLOCKED_COMPANIES)
    soft = "; ".join(f"{k} ({v})" for k, v in SOFT_FLAG_COMPANIES.items())
    return (
        "NEVER surface, score, or apply to these companies (values-based hard block): "
        f"{blocked}. "
        f"Surface-with-warning-only (do NOT cold-apply): {soft}."
    )
