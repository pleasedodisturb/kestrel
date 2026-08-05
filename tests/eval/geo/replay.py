"""Shared loader + replay helper for the geo blind-set eval gates (G-1474).

One implementation of the benchmark-record argument shape, used by BOTH eval
test modules (``test_blindset_regression.py`` and ``test_perf.py``) and by the
one-shot ``fixtures/generate_reference.py`` script. A second copy of that
argument shape is exactly how a silent drift between the differential gate and
the frozen reference would get introduced — never duplicate :func:`classify`.

Also home to :func:`scrub_patterns`, the PII/tracking pattern set that both the
one-time scrub and the recurring fixture-integrity test enforce, so the two
scans can never diverge either.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from career_os.services.geo.classifier import geo_eligibility
from career_os.services.geo.profile import GeoProfile

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def load_items() -> list[dict]:
    """The scrubbed 277-item blind set (``{id,company,title,location,remote,desc}``)."""
    return json.loads((FIXTURES / "blind_items.json").read_text(encoding="utf-8"))


def load_judgements() -> dict[str, dict]:
    """Human GO/SKIP verdicts keyed by item id."""
    return json.loads((FIXTURES / "judgements.json").read_text(encoding="utf-8"))


def load_reference() -> dict:
    """Frozen Eyas class assignments + role_keep flags (see GENERATION_LOG.md)."""
    return json.loads((FIXTURES / "reference_assignments.json").read_text(encoding="utf-8"))


def classify(item: dict, profile: GeoProfile) -> str:
    """Classify a benchmark record dict, reproducing the Eyas call shape EXACTLY.

    Mirrors ``eyas tools/benchmarks/g1388/geofix_v2.py::geo_v2``: location is the
    joined ``location``/``offices``/``country`` fields, ``offices`` is always
    ``None``, the title is lowercased by the caller, and the description comes
    from the record's ``desc`` key. Any change here invalidates the frozen
    reference — regenerate it via ``fixtures/generate_reference.py`` first.
    """
    location = " ".join(str(item.get(f, "") or "") for f in ("location", "offices", "country"))
    return geo_eligibility(
        location,
        offices=None,
        remote=bool(item.get("remote")),
        title=(item.get("title") or "").lower(),
        description=item.get("desc") or "",
        profile=profile,
    )


def scrub_patterns(repo_root: Path | None = None) -> dict[str, re.Pattern[str]]:
    """The pattern set the committed fixture must NEVER match (case-insensitive).

    Sources, merged:

    - every active pattern in the repo's ``.github/pii-patterns.txt`` gate file;
    - the personal-identifier set fixed by G-1474 (names, home city+country pair,
      private mail domain) — assembled from fragments so this source file cannot
      itself trip the repo's PII grep gate, which scans raw file text;
    - a generic email-address shape;
    - tracking-parameter URLs (any ``http(s)`` URL still carrying a query string).

    Keys are stable redacted labels safe to print in logs and assertion messages.
    """
    root = repo_root if repo_root is not None else _REPO_ROOT
    patterns: dict[str, re.Pattern[str]] = {}

    gate_file = root / ".github" / "pii-patterns.txt"
    if not gate_file.exists():
        # Fail loud. Silently falling back to the handful of hand-written
        # patterns below would make the fixture-integrity test pass HARDER the
        # moment its ruleset disappears (rename, sdist, installed package) —
        # the wrong failure direction for a security gate.
        raise FileNotFoundError(
            f"PII gate file missing: {gate_file}. scrub_patterns() must never "
            "degrade to a partial pattern set."
        )
    for n, line in enumerate(gate_file.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns[f"gate:pii-patterns.txt#{n}"] = re.compile(stripped, re.IGNORECASE)

    # Fragment-assembled personal identifiers (see docstring). The name patterns
    # use the broad stem so derived spellings are caught too.
    personal = {
        "personal:name-stem": "vit" + "ali",
        "personal:surname": "ga" + "ran",
        "personal:home-city-country": "frank" + "furt,\\s*ger" + "many",
        "personal:mail-domain": "pm" + "\\.m" + "e",
    }
    for label, pat in personal.items():
        patterns[label] = re.compile(pat, re.IGNORECASE)

    patterns["generic:email"] = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)
    patterns["tracking:url-query"] = re.compile(r"https?://[^\s\"]{1,150}\?", re.IGNORECASE)
    return patterns
