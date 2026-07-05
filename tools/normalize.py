"""
Shared company/title normalization for dedup and matching.

Job-discovery dedup used to compare raw ``(company, title)`` strings exactly,
so trivial drift ("Hugging Face" vs the Greenhouse slug-derived "Huggingface",
"Acme GmbH" vs "Acme", "Senior PM" vs "Senior PM (m/f/d)") slipped through and
the same roles re-surfaced daily. This module centralizes normalization so the
scraper, dedup, and any future matcher all agree on what "the same job" means.

Deliberately conservative: normalization is deterministic and only collapses
known noise (legal suffixes, punctuation, case, location/gender tags). Parenthetical
SPECIALIZATIONS are preserved -- "PM (Growth)" and "PM (Platform)" are distinct roles
and must not collapse to "pm" -- while noise parentheticals (gender/work-time tags,
recognized locations) are dropped. The optional :func:`fuzzy_ratio` helper uses the
stdlib (no extra dependency) and is intended for high-threshold company matching,
never for silently merging distinct roles.
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

# Bare (non-parenthetical) noise appended to scraped job titles. Parentheticals are
# handled separately by the paren filter below so a specialization inside parens is
# preserved -- do NOT add a blanket ``\(.*?\)`` strip here.
_TITLE_NOISE = re.compile(
    r"\bm/?f/?d\b|\bf/?m/?d\b|\bm/?w/?d\b|\bw/?m/?d\b"  # gender tags without parens
    r"|\bremote\b|\bhybrid\b|\bonsite\b|\bon-site\b"
    r"|\bfull[- ]?time\b|\bpart[- ]?time\b",
    re.IGNORECASE,
)

# Parentheticals are NOT blindly stripped: "PM (Growth)" and "PM (Platform)" are
# DISTINCT roles and must not collapse to "pm". A parenthetical is dropped only when
# its content is pure noise -- gender/work-time tags or a recognized location.
# Anything else (a specialization) is preserved.
_PAREN_RE = re.compile(r"\(([^)]*)\)")
_PAREN_NOISE_WORDS = {
    "m",
    "f",
    "d",
    "w",
    "x",
    "gn",
    "g",
    "n",
    "mfd",
    "fmd",
    "mwd",
    "wmd",
    "dfm",
    "divers",
    "gender",
    "genders",
    "all",
    "any",
    "remote",
    "hybrid",
    "onsite",
    "on",
    "site",
    "fulltime",
    "parttime",
    "full",
    "part",
    "time",
    "permanent",
    "contract",
    "temporary",
    "freelance",
}


def _segment_is_noise(segment: str) -> bool:
    """True if a single comma-segment of a parenthetical is pure noise.

    A segment is noise when every token is a known gender/work-time word, or when the
    whole segment is a recognized location. Location detection reuses the geo gate's
    ``_classify_token`` (renamed verdict token: "home"/"eu_remote"/"foreign") so we do
    not duplicate a city list here.
    """
    from batch_probe import _classify_token

    toks = [t for t in re.split(r"[\s/&.+-]+", segment.lower().strip()) if t]
    if not toks:
        return True
    if all(t in _PAREN_NOISE_WORDS for t in toks):
        return True
    # A whole segment that is a recognized location ("Berlin", "New York", "EU").
    return _classify_token(segment) in ("home", "eu_remote", "foreign")


def _filter_paren(content: str) -> str:
    """Drop noise comma-segments from a parenthetical, KEEP specializations.

    "Remote, Growth" -> "Growth" (so "Eng (Remote, Growth)" stays distinct from
    "Eng (Remote, Platform)"); "m/f/d" -> ""; "Berlin" -> ""; "Growth" -> "Growth".
    Splitting on comma first means multi-word locations ("New York") are classified
    as a whole segment rather than per-token.
    """
    kept = [seg.strip() for seg in content.split(",") if seg.strip() and not _segment_is_noise(seg)]
    return " ".join(kept)


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
    """Normalize a job title for dedup.

    Strips noise parentheticals (gender/work-time tags, locations) and bare noise
    words, but PRESERVES specialization parentheticals so "PM (Growth)" and
    "PM (Platform)" stay distinct. Accents are ASCII-folded via ``_collapse``.
    """
    if not title:
        return ""
    # Drop noise segments inside each parenthetical; keep specialization content.
    cleaned = _PAREN_RE.sub(lambda m: f" {_filter_paren(m.group(1))} ", title)
    cleaned = _TITLE_NOISE.sub(" ", cleaned)
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
