"""
Shared company/title normalization for dedup and matching.

Job-discovery dedup used to compare raw ``(company, title)`` strings exactly,
so trivial drift ("Hugging Face" vs the Greenhouse slug-derived "Huggingface",
"Acme GmbH" vs "Acme", "Senior PM" vs "Senior PM (m/f/d)") slipped through and
the same roles re-surfaced daily. This module centralizes normalization so the
daily-pipeline tracking dedup (and any future matcher) can agree on what "the
same job" means. (Intra-scrape dedup in scrape_resilient still keys on the raw
title/company pair — migrating it is a follow-up.)

Deliberately conservative: normalization is deterministic and only collapses
known noise (legal suffixes, punctuation, case, location/gender tags). The
optional :func:`fuzzy_ratio` helper uses the stdlib (no extra dependency) and
is intended for high-threshold company matching, never for silently merging
distinct roles.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Legal-entity / vanity suffixes that carry no identity signal.
_COMPANY_SUFFIXES = {
    "gmbh",
    "ag",
    "se",
    "kg",
    "ohg",
    "ug",
    "eg",
    "ev",
    "inc",
    "llc",
    "ltd",
    "limited",
    "corp",
    "co",
    "plc",
    "bv",
    "nv",
    "oy",
    "ab",
    "sa",
    "sas",
    "srl",
    "spa",
    "as",
    "aps",
    "labs",
    "lab",
    "technologies",
    "technology",
    "software",
    "group",
    "holding",
    "holdings",
    "the",
}

# Noise commonly appended to scraped job titles.
_TITLE_NOISE = re.compile(
    r"\(.*?\)"  # parenthetical: (m/f/d), (Remote), (Berlin)
    r"|\bm/?f/?d\b|\bf/?m/?d\b"  # gender tags without parens
    r"|\bremote\b|\bhybrid\b|\bonsite\b|\bon-site\b"
    r"|\bfull[- ]?time\b|\bpart[- ]?time\b",
    re.IGNORECASE,
)


def _collapse(s: str) -> str:
    """Lowercase, transliterate accents to ASCII, drop punctuation, collapse space.

    The NFKD pass folds accented variants onto their base letters so common EU
    scraper drift dedups: "Café" -> "cafe" (not the mangled "caf" you get from
    stripping the accent byte), "Müller" == "Muller", "Søren" == "Soren".
    """
    # Decompose accents then drop the combining marks (ASCII-fold).
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_company(name: str | None) -> str:
    """Normalize a company name for comparison.

    Lowercases, strips punctuation and legal/vanity suffixes, collapses space.
    Empty / falsy input yields ``""``.
    """
    if not name:
        return ""
    tokens = [t for t in _collapse(name).split(" ") if t and t not in _COMPANY_SUFFIXES]
    if not tokens:  # the whole name was suffix-like (e.g. "The Co") — keep collapsed form
        tokens = _collapse(name).split(" ")
    # Join WITHOUT spaces so spacing variants collapse together
    # ("Hugging Face" == "Huggingface", "Data Dog" == "Datadog").
    return "".join(tokens)


def normalize_title(title: str | None) -> str:
    """Normalize a job title: strip location/gender/remote noise, punctuation, case."""
    if not title:
        return ""
    cleaned = _TITLE_NOISE.sub(" ", title)
    return _collapse(cleaned)


def job_key(company: str | None, title: str | None) -> tuple[str, str]:
    """Canonical dedup key for a job: (normalized company, normalized title)."""
    return (normalize_company(company), normalize_title(title))


def fuzzy_ratio(a: str | None, b: str | None) -> float:
    """Similarity ratio in [0, 100] between two strings (stdlib SequenceMatcher).

    Use a HIGH threshold (>=90) and only for company-level matching — this is a
    safety net for residual drift, not a license to merge distinct roles.
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio() * 100.0
