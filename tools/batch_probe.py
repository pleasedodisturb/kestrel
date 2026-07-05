"""
batch_probe.py -- authoritative geo-eligibility gate + ATS office introspection.

WHY THIS EXISTS (two failure modes of a naive geo filter):

  Failure #1 ("remote rescue"): a posting's ``isRemote`` boolean is used as a
  *fallback* that overrides an explicit foreign-location rejection, so a role
  onsite in a country you cannot work in sneaks through because it is "remote".

  Failure #2 ("list-string lie"): the geo gate trusts the ATS *list endpoint*
  location string instead of the authoritative per-job office. The list string
  is free-text marketing and lies -- e.g. it names a home-country city while the
  REAL office is in another country, or it advertises a broad region while the
  role is actually country-locked remote somewhere you are not eligible.

ROOT CAUSE (both): the *list* location string is unreliable. Authoritative
location lives in the per-job payload:
  - Greenhouse: ``offices[].name`` (fetch the single-job endpoint).
  - Ashby: ``address`` + ``location`` + ``secondaryLocations[]``.

ELIGIBILITY RULE (the only rule that matters here):
  Eligible ONLY if:
    (a) onsite/hybrid in the HOME region (any home city -- intra-home relocation
        assumed OK), OR
    (b) remote genuinely open to a home-based person: remote-home,
        remote-EU-wide, remote-EMEA, remote-Europe, or global/unspecified remote.
  DROP if:
    - onsite/hybrid in a foreign location (even if a home city is *also* listed
      in the unreliable list string, when the REAL office is foreign), OR
    - country-locked remote to a foreign country.

KEY INVARIANT: ``is_remote`` NEVER makes a role eligible on its own. It only
distinguishes "remote posting" from "onsite". WHERE the role is open is decided
exclusively by the location text + authoritative offices. This is what kills
failure #1.

HOME REGION IS PARAMETERIZED: the set of "home" place tokens is loaded from
``config/geo.yaml`` (copy ``config/geo.example.yaml``) -- there is NO hardcoded
country assumption in this module. A home token always wins classification, so
any country/region can be configured as home.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlparse

import httpx
import yaml

GeoClass = Literal["home", "eligible_remote"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# Location token sets. Word-boundary matching is used for short/ambiguous
# tokens (e.g. "us" must not match inside "austria"). Substring matching is
# fine for the long unambiguous ones.
#
# Pan-region and foreign token sets are PUBLIC GEOGRAPHY (not location-specific
# to any one user) and live in code. The HOME token set is user-specific and is
# loaded from config (see GeoConfig below) so nothing about the home country is
# hardcoded here.
# ---------------------------------------------------------------------------

# Pan-EU / continent-wide / global remote signals => eligible remote for a
# home-based person. DACH-style multi-country regions count here.
_PAN_REGION_TOKENS: tuple[str, ...] = (
    "emea",
    "europe",
    "european",
    "dach",
    "benelux",
    "nordics",
)
# Word-boundary tokens for short pan/global signals.
_PAN_REGION_REGEX: tuple[re.Pattern, ...] = (
    re.compile(r"\beu[\s\-]?wide\b", re.I),
    re.compile(r"\beu\b", re.I),
    re.compile(r"\bglobal\b", re.I),
    re.compile(r"\bworldwide\b", re.I),
    re.compile(r"\banywhere\b", re.I),
)

# Non-home country / region / major-city tokens. ANY of these (and no home
# token) => the candidate is FOREIGN, whether onsite or country-locked remote.
# A configured home token ALWAYS wins over this list (see _classify_token), so
# if a place here is actually your home you simply add it to config home_tokens.
# Long unambiguous substrings:
_FOREIGN_TOKENS: tuple[str, ...] = (
    "united states",
    "usa",
    "u.s.",
    "north america",
    "latam",
    "apac",
    "san francisco",
    "new york",
    "los angeles",
    "chicago",
    "seattle",
    "austin",
    "boston",
    "denver",
    "atlanta",
    "miami",
    "dallas",
    "houston",
    "phoenix",
    "san jose",
    "san diego",
    "washington",
    "france",
    "paris",
    "marseille",
    "lyon",
    "spain",
    "madrid",
    "barcelona",
    "valencia",
    "portugal",
    "lisbon",
    "porto",
    "netherlands",
    "amsterdam",
    "rotterdam",
    "utrecht",
    "ireland",
    "dublin",
    "italy",
    "milan",
    "rome",
    "turin",
    "poland",
    "warsaw",
    "krakow",
    "kraków",
    "wroclaw",
    "sweden",
    "stockholm",
    "gothenburg",
    "denmark",
    "copenhagen",
    "finland",
    "helsinki",
    "norway",
    "oslo",
    "belgium",
    "brussels",
    "antwerp",
    "switzerland",
    "zurich",
    "zürich",
    "geneva",
    "lausanne",
    "austria",
    "vienna",
    "czech",
    "prague",
    "czechia",
    "romania",
    "bucharest",
    "bulgaria",
    "sofia",
    "greece",
    "athens",
    "hungary",
    "budapest",
    "estonia",
    "tallinn",
    "latvia",
    "riga",
    "lithuania",
    "vilnius",
    "ukraine",
    "kyiv",
    "kiev",
    "lviv",
    "united kingdom",
    "london",
    "manchester",
    "edinburgh",
    "india",
    "bangalore",
    "bengaluru",
    "mumbai",
    "delhi",
    "canada",
    "toronto",
    "vancouver",
    "montreal",
    "brazil",
    "são paulo",
    "sao paulo",
    "australia",
    "sydney",
    "melbourne",
    "singapore",
    "tokyo",
    "japan",
    "israel",
    "tel aviv",
)
# Word-boundary tokens for short/ambiguous foreign signals.
_FOREIGN_REGEX: tuple[re.Pattern, ...] = (
    re.compile(r"\bus\b", re.I),
    re.compile(r"\bna\b", re.I),  # North America
    re.compile(r"\buk\b", re.I),
)

# Vendor career-host -> Greenhouse board slug. Many companies front their
# Greenhouse board with a custom domain but still expose gh_jid; the board API
# (boards-api.greenhouse.io) resolves by slug. Ships EMPTY / fictional-only --
# add your own vendor hosts as needed.
_GH_VENDOR_SLUGS: dict[str, str] = {
    # Example only -- replace with real vendor career hosts you track:
    "example-vendor.com": "examplevendor",
}


# ---------------------------------------------------------------------------
# Home-region configuration (parameterized -- no hardcoded country here).
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_GEO_CONFIG_PATH = _CONFIG_DIR / "geo.yaml"
_GEO_EXAMPLE_PATH = _CONFIG_DIR / "geo.example.yaml"


@dataclass(frozen=True)
class GeoConfig:
    """Home-region token set + policy flags.

    ``home_tokens`` are place names (cities + country/region names) that count as
    the applicant's home location. A role anchored in any of them classifies as
    "home" (always eligible). There is deliberately no built-in country default:
    the tokens come from ``config/geo.yaml`` / ``config/geo.example.yaml``.
    """

    home_tokens: tuple[str, ...] = ()
    allow_pan_region_remote: bool = True
    extra_foreign_tokens: tuple[str, ...] = field(default_factory=tuple)


def _load_geo_config() -> GeoConfig:
    """Load the home-region config from geo.yaml, then geo.example.yaml.

    Falls back to an empty home set (everything non-pan/foreign is "unknown")
    when neither file is present -- the home region is intentionally not baked
    into the code.
    """
    for path in (_GEO_CONFIG_PATH, _GEO_EXAMPLE_PATH):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        tokens = tuple(
            str(t).strip().lower() for t in (data.get("home_tokens") or []) if str(t).strip()
        )
        if tokens:
            return GeoConfig(
                home_tokens=tokens,
                allow_pan_region_remote=bool(data.get("allow_pan_region_remote", True)),
                extra_foreign_tokens=tuple(
                    str(t).strip().lower()
                    for t in (data.get("extra_foreign_tokens") or [])
                    if str(t).strip()
                ),
            )
    return GeoConfig()


_CONFIG: GeoConfig = _load_geo_config()


def _has_substr(text: str, tokens: Iterable[str]) -> bool:
    return any(t in text for t in tokens)


def _has_regex(text: str, patterns: Iterable[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def _classify_token(candidate: str) -> Literal["home", "eu_remote", "foreign", "unknown"]:
    """Classify a single location string.

    Priority: a HOME signal wins outright (intra-home relocation OK). Then
    pan-region/global remote. Then any explicit foreign signal => foreign. A bare
    "remote" with no recognizable place => unspecified remote => eu_remote.
    Anything else => unknown (treated conservatively by the caller).
    """
    s = (candidate or "").lower().strip()
    if not s:
        return "unknown"

    if _has_substr(s, _CONFIG.home_tokens):
        return "home"

    if _CONFIG.allow_pan_region_remote and (
        _has_substr(s, _PAN_REGION_TOKENS) or _has_regex(s, _PAN_REGION_REGEX)
    ):
        return "eu_remote"

    # Explicit foreign place => foreign, whether onsite OR country-locked remote.
    if (
        _has_substr(s, _FOREIGN_TOKENS)
        or _has_substr(s, _CONFIG.extra_foreign_tokens)
        or _has_regex(s, _FOREIGN_REGEX)
    ):
        return "foreign"

    # No recognizable place. Bare/unqualified "remote" => unspecified => eligible,
    # unless strict mode requires an explicit home-region anchor.
    if "remote" in s and _CONFIG.allow_pan_region_remote:
        return "eu_remote"

    return "unknown"


def geo_classify(
    location_text: str,
    offices: list[str] | None = None,
    is_remote: bool = False,
) -> GeoClass | None:
    """Authoritative geo gate.

    Args:
        location_text: the (unreliable) list-level location string.
        offices: authoritative per-job location candidates. For Greenhouse pass
            ``offices[].name``; for Ashby pass the primary location plus every
            ``secondaryLocations[].location``. When provided, these OVERRIDE
            ``location_text`` (the list string is only a fallback).
        is_remote: posting's remote flag. Informational only -- it can never make
            a role eligible by itself (this is what fixed failure #1).

    Returns:
        "home"            -> onsite/hybrid/remote anchored in the home region.
        "eligible_remote" -> remote open to a home-based person (home / EU-wide /
                             EMEA / Europe / global / unspecified remote).
        None              -> DROP (foreign onsite, or country-locked foreign remote).
    """
    # Authoritative override: when per-job offices are present they REPLACE the
    # unreliable list string (that is the whole point -- failure #2). The list
    # string is used only as a fallback when no offices were resolved.
    office_candidates = [o for o in (offices or []) if o and o.strip()]
    if office_candidates:
        candidates = office_candidates
    elif location_text and location_text.strip():
        candidates = [location_text]
    else:
        candidates = []

    if not candidates:
        # No location info at all. A self-declared remote with zero geo signal
        # is treated as unspecified-remote (eligible); otherwise unknown -> drop.
        return "eligible_remote" if is_remote else None

    classes = [_classify_token(c) for c in candidates]

    # Aggregation priority: any home anchor wins; else any eligible remote;
    # else everything is foreign/unknown -> drop.
    if "home" in classes:
        return "home"
    if "eu_remote" in classes:
        return "eligible_remote"
    # Only foreign / unknown remain.
    if all(c == "unknown" for c in classes):
        # No place recognized anywhere. Fall back to the remote flag.
        return "eligible_remote" if is_remote else None
    return None


def geo_ok(
    location_text: str,
    offices: list[str] | None = None,
    is_remote: bool = False,
) -> bool:
    """Boolean convenience wrapper around :func:`geo_classify`."""
    return geo_classify(location_text, offices, is_remote) is not None


# ---------------------------------------------------------------------------
# Authoritative per-job fetchers
# ---------------------------------------------------------------------------

_GH_URL_RE = re.compile(
    r"greenhouse\.io/(?:embed/job_app\?for=)?(?P<slug>[^/?]+)/jobs/(?P<jid>\d+)",
    re.I,
)


def parse_greenhouse_url(url: str) -> tuple[str, str] | None:
    """Extract (board_slug, job_id) from a Greenhouse or vendor-hosted URL.

    Handles:
      - job-boards.greenhouse.io/{slug}/jobs/{id}
      - job-boards.eu.greenhouse.io/{slug}/jobs/{id}
      - boards.greenhouse.io/{slug}/jobs/{id}
      - vendor hosts (configured in _GH_VENDOR_SLUGS) with ?gh_jid=
    """
    m = _GH_URL_RE.search(url)
    if m:
        return m.group("slug"), m.group("jid")

    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    qs = parse_qs(parsed.query)
    jid = (qs.get("gh_jid") or qs.get("gh_src") or [None])[0]
    if jid and jid.isdigit():
        slug = _GH_VENDOR_SLUGS.get(host) or _GH_VENDOR_SLUGS.get(parsed.netloc.lower())
        if slug:
            return slug, jid
    return None


def fetch_greenhouse_offices(
    slug: str, job_id: str, client: httpx.Client | None = None
) -> tuple[list[str], str, bool]:
    """Fetch the authoritative office list for a single Greenhouse job.

    Returns (office_names, list_location_name, is_remote_guess). The
    ``office_names`` are authoritative; ``list_location_name`` is the unreliable
    string kept only for logging/fallback.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"
    own = client is None
    client = client or httpx.Client(timeout=20, headers=_HEADERS, follow_redirects=True)
    try:
        r = client.get(url)
        r.raise_for_status()
        d = r.json()
    finally:
        if own:
            client.close()

    offices = [
        (o.get("name") or o.get("location") or "")
        for o in d.get("offices", [])
        if isinstance(o, dict)
    ]
    offices = [o for o in offices if o.strip()]
    loc_obj = d.get("location") or {}
    list_loc = loc_obj.get("name", "") if isinstance(loc_obj, dict) else str(loc_obj)
    blob = (list_loc + " " + " ".join(offices)).lower()
    is_remote = "remote" in blob
    return offices, list_loc, is_remote


def _ashby_candidates_from_posting(p: dict) -> tuple[list[str], str, bool]:
    """Build authoritative candidate strings from an Ashby posting dict.

    Uses primary ``location``/``locationName``/``address`` plus every
    ``secondaryLocations[].location`` (and their address countries). Returns
    (candidates, primary_location_text, is_remote).
    """
    primary = p.get("location") or p.get("locationName") or ""
    if isinstance(primary, dict):
        primary = primary.get("name", "")

    candidates: list[str] = []
    if primary:
        candidates.append(str(primary))

    addr = p.get("address") or {}
    if isinstance(addr, dict):
        pa = addr.get("postalAddress", {}) or {}
        country = pa.get("addressCountry")
        locality = pa.get("addressLocality")
        # Only add the address-derived candidate when the primary text is an
        # *explicit place* (not a bare/unqualified "remote"). A bare "Remote"
        # posting whose HQ address happens to be foreign must stay eligible.
        if str(primary).strip().lower() not in {"remote", "remote (global)", "global", ""}:
            for part in (locality, country):
                if part:
                    candidates.append(str(part))

    for sec in p.get("secondaryLocations", []) or []:
        if not isinstance(sec, dict):
            continue
        sloc = sec.get("location")
        if sloc:
            candidates.append(str(sloc))
        sa = (sec.get("address") or {}).get("postalAddress", {}) or {}
        for part in (sa.get("addressLocality"), sa.get("addressCountry")):
            if part:
                candidates.append(str(part))

    is_remote = bool(p.get("isRemote")) or "remote" in str(primary).lower()
    return candidates, str(primary), is_remote


def fetch_ashby_location(
    slug: str, posting_id: str, client: httpx.Client | None = None
) -> tuple[list[str], str, bool] | None:
    """Fetch authoritative location candidates for a single Ashby posting."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    own = client is None
    client = client or httpx.Client(timeout=20, headers=_HEADERS, follow_redirects=True)
    try:
        r = client.get(url, params={"includeCompensation": "true"})
        r.raise_for_status()
        d = r.json()
    finally:
        if own:
            client.close()

    posts = d.get("jobs", d.get("jobPostings", []))
    for p in posts:
        if p.get("id") == posting_id:
            return _ashby_candidates_from_posting(p)
    return None


def parse_ashby_url(url: str) -> tuple[str, str] | None:
    """Extract (slug, posting_id) from jobs.ashbyhq.com/{slug}/{uuid}[/application]."""
    m = re.search(r"ashbyhq\.com/(?P<slug>[^/]+)/(?P<pid>[0-9a-f-]{36})", url, re.I)
    if m:
        return m.group("slug"), m.group("pid")
    return None


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------


def probe_role(url: str, list_loc: str, client: httpx.Client) -> tuple[GeoClass | None, str]:
    """Resolve authoritative location for a manifest URL and classify it.

    Returns (geo_class, detail). Falls back to the list location string for ATS
    hosts we cannot query authoritatively (Lever/custom boards).
    """
    gh = parse_greenhouse_url(url)
    if gh:
        try:
            offices, ll, is_remote = fetch_greenhouse_offices(*gh, client=client)
            cls = geo_classify(ll or list_loc, offices=offices, is_remote=is_remote)
            return cls, f"greenhouse offices={offices!r} list={ll!r}"
        except Exception as e:  # noqa: BLE001
            cls = geo_classify(list_loc)
            return cls, f"greenhouse FETCH-FAIL ({e!r}); fell back to list={list_loc!r}"

    ash = parse_ashby_url(url)
    if ash:
        try:
            res = fetch_ashby_location(*ash, client=client)
            if res is None:
                cls = geo_classify(list_loc)
                return cls, f"ashby posting not found; fell back to list={list_loc!r}"
            candidates, primary, is_remote = res
            cls = geo_classify(primary, offices=candidates, is_remote=is_remote)
            return cls, f"ashby candidates={candidates!r}"
        except Exception as e:  # noqa: BLE001
            cls = geo_classify(list_loc)
            return cls, f"ashby FETCH-FAIL ({e!r}); fell back to list={list_loc!r}"

    # Non-GH/Ashby host: classify from the (only available) list string.
    cls = geo_classify(list_loc)
    return cls, f"non-ATS host; list-only={list_loc!r}"


def validate_manifest(path: str) -> int:
    """Run the gate over a manifest of roles, printing keep/drop decisions."""
    roles = json.loads(Path(path).read_text())
    dropped: list[int] = []
    with httpx.Client(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
        for r in roles:
            cls, detail = probe_role(r["url"], r.get("loc", ""), client)
            verdict = "KEEP " if cls else "DROP "
            if cls is None:
                dropped.append(r["n"])
            print(f"#{r['n']:>2} {verdict} [{cls or 'None':<15}] {r['co']:<14} | {detail}")
    print(f"\nDROPPED {len(dropped)} / {len(roles)}: {dropped}")
    return len(dropped)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        validate_manifest(sys.argv[1])
    else:
        print("usage: python batch_probe.py <manifest.json>", file=sys.stderr)
        sys.exit(2)
