"""Generic 7-way geo-eligibility classifier (the single geo authority).

Pure and total: no file I/O, no network, no logging, no module-level state
beyond the class-name constants. All geographic vocabulary lives in the
:class:`~career_os.services.geo.profile.GeoProfile` passed by the caller —
this module contains NO home-region knowledge.

Public classes returned by :func:`geo_eligibility`:

- ``home_local``              -> home commute belt; no move needed. ELIGIBLE.
- ``home_relocate``           -> elsewhere in the home country; a move, but no
                                 visa. ELIGIBLE (ranking only — never filter).
- ``eligible_remote``         -> remote within an eligible region, pan-region,
                                 or unspecified remote.
- ``visa_free_relocate``      -> onsite in a visa-free region: real move. MAYBE.
- ``visa_required_relocate``  -> onsite where a work visa is needed. MAYBE,
                                 kept distinct so the burden stays visible.
- ``foreign``                 -> explicit ineligible place (onsite OR
                                 country-locked remote) => cap / review queue.
- ``unknown``                 -> no geo signal => do NOT bury; let the AI score.

Two contract rules (measured on a 277-item human-judged blind set) survive
verbatim from the source engine:

1. Region tokens in the TITLE bind first — "(AMER)" or ", Korea" name the
   served market regardless of office; an eligible token alongside rescues.
2. A bare "Remote" location consults the DESCRIPTION before defaulting
   eligible — skipping this consult admitted 10 junk roles (precision
   74.6% -> 65.2%) before the blind-set regression caught it.
"""

from __future__ import annotations

import re

from career_os.services.geo.profile import GeoProfile

# Classes an application can actually pursue. `unknown` is deliberately
# eligible: absence of geo data must never bury a gem (geo-gate rule).
ELIGIBLE_CLASSES = frozenset({"home_local", "home_relocate", "eligible_remote", "unknown"})
# Kept but flagged: these carry a real move and possibly a work visa.
MAYBE_CLASSES = frozenset({"visa_free_relocate", "visa_required_relocate"})
# Every class geo_eligibility can return.
ALL_CLASSES = ELIGIBLE_CLASSES | MAYBE_CLASSES | frozenset({"foreign"})

# Aggregation priority: the best candidate wins. A role with a home-city and
# a foreign office is a home role; a role with a foreign office plus a
# home-remote office is a home role (the multi-office rescue).
_GEO_PRIORITY = [
    "home_local",
    "home_relocate",
    "eligible_remote",
    "visa_free_relocate",
    "visa_required_relocate",
]


def _search(pattern: re.Pattern[str] | None, text: str) -> re.Match[str] | None:
    """Search with a possibly-absent pattern: a ``None`` field never matches."""
    return pattern.search(text) if pattern is not None else None


def classify_candidate(candidate: str | None, remote: bool, profile: GeoProfile) -> str:
    """Rich geo class for a single location string.

    May return the INTERNAL classes ``bare_remote`` and ``country_locked`` in
    addition to the public ones; :func:`geo_eligibility` collapses both before
    returning. Total by construction: any input maps to exactly one class.
    """
    s = str(candidate).lower().strip() if candidate is not None else ""
    if not s:
        return "unknown"

    home_hit = _search(profile.home_country, s)
    foreign_hit = _search(profile.foreign, s)
    eligible_hit = _search(profile.eligible_region, s)

    if home_hit and not foreign_hit:
        # Both classes are ELIGIBLE — relocation within the home country is
        # acceptable. The split is for ranking only: local needs no move.
        return "home_local" if _search(profile.home_local, s) else "home_relocate"

    # An eligible region beats a foreign token when both are named (EMEA/AMER).
    if foreign_hit and not eligible_hit:
        return "foreign"

    if _search(profile.visa_free_remote_phrase, s) or _search(profile.visa_free_wide, s):
        return "eligible_remote"

    if _search(profile.visa_required, s):
        # A visa-required place with "remote" means sitting THERE — unusable.
        return "country_locked" if (remote or "remote" in s) else "visa_required_relocate"

    if _search(profile.visa_free_region, s):
        return "country_locked" if (remote or "remote" in s) else "visa_free_relocate"

    # Bare/unqualified "remote" with no recognizable place. NOT eligible yet:
    # the aggregator must consult the description first. "Remote" on a company
    # whose text names foreign cities is a foreign-remote role — treating bare
    # remote as eligible was a porting bug that admitted junk roles the
    # benchmark filter rejected.
    if "remote" in s:
        return "bare_remote"

    return "unknown"


def geo_eligibility(
    location: str | None,
    offices: list[str] | None = None,
    remote: bool = False,
    title: str = "",
    description: str = "",
    *,
    profile: GeoProfile,
) -> str:
    """Authoritative geo verdict for a posting under the given profile.

    Authoritative ``offices`` (ATS offices[], primary + secondary locations)
    OVERRIDE the unreliable list-level ``location`` string. ``remote`` is
    informational only — it can never make an explicit foreign place eligible.

    Returns exactly one of the 7 public classes (see module docstring);
    the internal ``country_locked`` and ``bare_remote`` classes collapse
    before returning (``country_locked`` -> ``foreign``).
    """
    # Region tokens in the title bind first — "(US East)" with a home-city
    # office still serves a foreign market (ignoring these let junk through).
    title_l = str(title).lower() if title is not None else ""
    if title_l:
        title_foreign = _search(profile.title_region_foreign, title_l) or _search(
            profile.foreign, title_l
        )
        title_eligible = _search(profile.eligible_region, title_l)
        if title_foreign and not title_eligible:
            return "foreign"
        visa_required_title = _search(profile.visa_required, title_l)
        if visa_required_title and not title_eligible:
            # A visa-required market token on a Remote posting means being
            # locked to that market, which collapses to "foreign" (the
            # pipeline's hard-block class) so every existing != "foreign"
            # consumer stays correct.
            return "foreign" if remote else "visa_required_relocate"

    candidates = [o for o in (offices or []) if o and str(o).strip()]
    if not candidates and location is not None and str(location).strip():
        candidates = [str(location)]

    classes = {classify_candidate(str(c), remote, profile) for c in candidates}

    # A positive class from any candidate wins (multi-office rescue: a foreign
    # office plus a home-remote office = a home role).
    for cls in _GEO_PRIORITY:
        if cls in classes:
            return cls
    if "foreign" in classes or "country_locked" in classes:
        return "foreign"

    # A title naming an eligible region ALONGSIDE a foreign one is a
    # multi-region posting open to home — "(EMEA/AMER)" with a bare "Remote"
    # location. Positive classification, not just a veto; checked only after
    # candidates fail so a concrete office verdict always wins over the title.
    if (
        title_l
        and _search(profile.eligible_region, title_l)
        and (_search(profile.title_region_foreign, title_l) or _search(profile.foreign, title_l))
    ):
        return "eligible_remote"

    # No candidate gave a verdict (empty, unknown, or bare "Remote"). Consult
    # the description BEFORE defaulting to eligible — this ordering is the
    # benchmark behaviour: "Remote" on a posting whose text names foreign
    # cities is a foreign-remote role, not an eligible one.
    desc = str(description)[:2500].lower() if description is not None else ""
    if desc:
        if _search(profile.foreign, desc) and not _search(profile.home_country, desc):
            return "foreign"
        if _search(profile.home_country, desc):
            return "home_local" if _search(profile.home_local, desc) else "home_relocate"

    # Truly no signal anywhere. A remote posting is unspecified-remote =>
    # eligible; otherwise unknown (never buried — geo-gate rule).
    if remote or "bare_remote" in classes:
        return "eligible_remote"
    return "unknown"
