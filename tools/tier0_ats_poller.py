#!/usr/bin/env python3
"""Tier-0 ATS poller — direct ATS JSON for dream companies.

Beats aggregator lag (hours to days) by hitting each dream company's public ATS
JSON endpoint directly. Supports Greenhouse, Lever, Ashby. Companies on custom
(non-Greenhouse/Lever/Ashby) career sites are out of scope for this poller.

Endpoint patterns:
  - Greenhouse: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
  - Lever:      https://api.lever.co/v0/postings/{slug}?mode=json
  - Ashby:      https://api.ashbyhq.com/posting-api/job-board/{slug}

Each company's response is normalized to the same dict shape consumed elsewhere
in the pipeline (mirrors ``tools.scrape_resilient.ScrapedJob`` field set):
``title``, ``company``, ``location``, ``url``, ``source``, ``description``,
``posted``, ``remote``, ``salary``, ``tags``, ``search_keyword``, ``scraped_at``.

State tracking (``data/tier0_state.json``, gitignored) persists last-seen job
IDs per company so only NEW postings are surfaced on each run.

CLI:
  python tools/tier0_ats_poller.py --once          # one-shot
  python tools/tier0_ats_poller.py --watch         # 15-min loop
  python tools/tier0_ats_poller.py --once --json   # JSON output for piping
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "tier0_state.json"
COMPANIES_CONFIG = PROJECT_ROOT / "config" / "companies.yaml"
DEFAULT_TIMEOUT = 20.0
DEFAULT_INTER_COMPANY_DELAY = 1.5  # seconds between company fetches
WATCH_INTERVAL_SECONDS = 15 * 60
USER_AGENT = "kestrel-tier0-poller/1.0 (+https://github.com/pleasedodisturb/kestrel)"

logger = logging.getLogger("tier0_ats_poller")


# --- Config: company → (ATS type, slug) --------------------------------------

# The poller hits each dream company's public ATS JSON directly, so it needs a
# ``name -> (ats_type, slug)`` map. The embedded defaults below are
# OBVIOUSLY-FICTIONAL examples; the real shortlist loads from
# ``config/companies.yaml`` (gitignored — copy ``config/companies.example.yaml``)
# under a ``tier0:`` key of ``name: [ats_type, slug]``. This keeps a personal
# dream-company list out of the public repo while the poller mechanism stays
# fully functional. Note Ashby slugs are sometimes case-sensitive.
_FLOOR_TIER_0_COMPANIES: dict[str, tuple[str, str]] = {
    "example-greenhouse-co": ("greenhouse", "example-greenhouse-co"),
    "example-lever-co": ("lever", "example-lever-co"),
    "example-ashby-co": ("ashby", "example-ashby-co"),
}


def _load_tier0_companies() -> dict[str, tuple[str, str]]:
    """Load the Tier-0 map from config/companies.yaml, falling back to the floor."""
    companies = dict(_FLOOR_TIER_0_COMPANIES)
    # Absent config is the normal case (poller runs on the fictional floor) — stay
    # silent. Only a present-but-unreadable/malformed file warrants a warning.
    if not COMPANIES_CONFIG.exists():
        return companies
    try:
        data = yaml.safe_load(COMPANIES_CONFIG.read_text(encoding="utf-8")) or {}
        tier0 = data.get("tier0")
        if isinstance(tier0, dict) and tier0:
            parsed: dict[str, tuple[str, str]] = {}
            for name, spec in tier0.items():
                if isinstance(spec, (list, tuple)) and len(spec) == 2:
                    parsed[str(name)] = (str(spec[0]), str(spec[1]))
            if parsed:
                companies = parsed
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("config/companies.yaml tier0 unreadable (%s); using example floor", exc)
    return companies


TIER_0_COMPANIES: dict[str, tuple[str, str]] = _load_tier0_companies()


# --- Normalized result shape -------------------------------------------------


@dataclass
class Tier0Job:
    """Normalized Tier-0 ATS job record.

    Field set mirrors ``tools.scrape_resilient.ScrapedJob`` so downstream
    pipeline steps (dedup, scoring, digest) consume both interchangeably.
    """

    title: str
    company: str
    location: str
    url: str
    source: str  # "tier0:greenhouse:example-greenhouse-co" etc.
    description: str = ""
    posted: str = ""
    remote: bool = False
    salary: str = ""
    tags: list[str] = field(default_factory=list)
    search_keyword: str = ""
    scraped_at: str = ""
    job_id: str = ""  # ATS-native id, used for dedup

    def dedup_key(self) -> tuple[str, str]:
        return (self.title.lower().strip(), self.company.lower().strip())


# --- Per-ATS fetchers --------------------------------------------------------


def _http_get_json(url: str, *, client: httpx.Client) -> Any:
    """GET + parse JSON, raising on non-2xx."""
    resp = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_greenhouse(slug: str, *, company_key: str, client: httpx.Client) -> list[Tier0Job]:
    """Fetch Greenhouse jobs for ``slug``.

    Endpoint: ``https://boards-api.greenhouse.io/v1/boards/{slug}/jobs``
    Returns ``{"jobs": [...], "meta": {...}}`` with each job having
    ``id``, ``title``, ``absolute_url``, ``location.name``, ``updated_at``.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    payload = _http_get_json(url, client=client)
    now = _utcnow_iso()
    out: list[Tier0Job] = []
    for j in payload.get("jobs", []):
        loc = ""
        if isinstance(j.get("location"), dict):
            loc = j["location"].get("name") or ""
        out.append(
            Tier0Job(
                title=j.get("title", "").strip(),
                company=company_key,
                location=loc,
                url=j.get("absolute_url", ""),
                source=f"tier0:greenhouse:{slug}",
                posted=j.get("updated_at", "") or j.get("first_published", ""),
                remote=_looks_remote(loc),
                scraped_at=now,
                job_id=str(j.get("id", "")),
            )
        )
    return out


def fetch_lever(slug: str, *, company_key: str, client: httpx.Client) -> list[Tier0Job]:
    """Fetch Lever postings for ``slug``.

    Endpoint: ``https://api.lever.co/v0/postings/{slug}?mode=json``
    Returns a list of postings with ``id``, ``text``, ``hostedUrl``,
    ``categories.location``, ``categories.allLocations``, ``createdAt`` (ms epoch),
    ``workplaceType``, ``descriptionPlain``.
    """
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    payload = _http_get_json(url, client=client)
    now = _utcnow_iso()
    out: list[Tier0Job] = []
    for p in payload or []:
        cats = p.get("categories") or {}
        location = cats.get("location") or ""
        if not location:
            all_locs = cats.get("allLocations") or []
            location = ", ".join(all_locs) if all_locs else ""
        created_ms = p.get("createdAt")
        posted_iso = ""
        if isinstance(created_ms, (int, float)):
            posted_iso = datetime.fromtimestamp(created_ms / 1000, UTC).isoformat()
        workplace = (p.get("workplaceType") or "").lower()
        remote = workplace == "remote" or _looks_remote(location)
        out.append(
            Tier0Job(
                title=p.get("text", "").strip(),
                company=company_key,
                location=location,
                url=p.get("hostedUrl", ""),
                source=f"tier0:lever:{slug}",
                description=(p.get("descriptionPlain") or "")[:1000],
                posted=posted_iso,
                remote=remote,
                tags=[t for t in [cats.get("team"), cats.get("commitment")] if t],
                scraped_at=now,
                job_id=str(p.get("id", "")),
            )
        )
    return out


def fetch_ashby(slug: str, *, company_key: str, client: httpx.Client) -> list[Tier0Job]:
    """Fetch Ashby jobs for ``slug``.

    Endpoint: ``https://api.ashbyhq.com/posting-api/job-board/{slug}``
    Note: Ashby slugs are sometimes case-sensitive (e.g. ``NovaDynamics`` not ``novadynamics``).
    Returns ``{"jobs": [...]}`` with each job having ``id``, ``title``,
    ``location``, ``jobUrl``, ``publishedAt``, ``isRemote``, ``employmentType``,
    ``department``, ``team``, ``descriptionPlain``.
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    payload = _http_get_json(url, client=client)
    now = _utcnow_iso()
    out: list[Tier0Job] = []
    for j in payload.get("jobs", []):
        # Only surface listed jobs when the flag is present.
        if j.get("isListed") is False:
            continue
        out.append(
            Tier0Job(
                title=j.get("title", "").strip(),
                company=company_key,
                location=j.get("location") or "",
                url=j.get("jobUrl") or j.get("applyUrl") or "",
                source=f"tier0:ashby:{slug}",
                description=(j.get("descriptionPlain") or "")[:1000],
                posted=j.get("publishedAt", ""),
                remote=bool(j.get("isRemote")),
                tags=[
                    t for t in [j.get("department"), j.get("team"), j.get("employmentType")] if t
                ],
                scraped_at=now,
                job_id=str(j.get("id", "")),
            )
        )
    return out


_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


# --- State tracking ----------------------------------------------------------


def load_state(state_path: Path) -> dict[str, list[str]]:
    """Load last-seen job IDs per company, or empty dict if missing/corrupt."""
    if not state_path.exists():
        return {}
    try:
        raw = json.loads(state_path.read_text())
        if not isinstance(raw, dict):
            return {}
        # Normalize value to list[str]
        return {k: list(map(str, v)) for k, v in raw.items() if isinstance(v, list)}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load state at %s: %s; treating as empty", state_path, exc)
        return {}


def save_state(state_path: Path, state: dict[str, list[str]]) -> None:
    """Atomic-ish write of state to disk."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(state_path)


# --- Polling orchestration ---------------------------------------------------


@dataclass
class PollResult:
    """Per-company poll result."""

    company: str
    ats: str
    fetched: int
    new: int
    error: str | None = None
    new_jobs: list[Tier0Job] = field(default_factory=list)


def poll_once(
    *,
    companies: dict[str, tuple[str, str]] | None = None,
    state_path: Path = DEFAULT_STATE_PATH,
    inter_company_delay: float = DEFAULT_INTER_COMPANY_DELAY,
    client: httpx.Client | None = None,
    persist: bool = True,
) -> list[PollResult]:
    """Poll all configured companies once. Returns per-company results.

    Failure isolation: a single company 5xx never blocks others. Errors are
    captured on the per-company ``PollResult`` and logged.

    When ``persist`` is True, ``state_path`` is updated with current job IDs.
    """
    companies = companies or TIER_0_COMPANIES
    state = load_state(state_path)
    owns_client = client is None
    if owns_client:
        client = httpx.Client(follow_redirects=True)
    results: list[PollResult] = []
    try:
        for idx, (company_key, (ats_type, slug)) in enumerate(companies.items()):
            if idx > 0 and inter_company_delay > 0:
                time.sleep(inter_company_delay)
            fetcher = _FETCHERS.get(ats_type)
            if fetcher is None:
                logger.warning("No fetcher for ATS type %s (company=%s)", ats_type, company_key)
                results.append(
                    PollResult(
                        company=company_key,
                        ats=ats_type,
                        fetched=0,
                        new=0,
                        error=f"unsupported ATS type: {ats_type}",
                    )
                )
                continue
            try:
                jobs = fetcher(slug, company_key=company_key, client=client)
            except Exception as exc:  # noqa: BLE001 — per-company isolation
                logger.warning("Fetch failed for %s (%s/%s): %s", company_key, ats_type, slug, exc)
                results.append(
                    PollResult(
                        company=company_key,
                        ats=ats_type,
                        fetched=0,
                        new=0,
                        error=str(exc),
                    )
                )
                continue
            seen_ids = set(state.get(company_key, []))
            new_jobs = [j for j in jobs if j.job_id and j.job_id not in seen_ids]
            # Update state to current snapshot (we trust the ATS as source of truth).
            state[company_key] = sorted({j.job_id for j in jobs if j.job_id})
            results.append(
                PollResult(
                    company=company_key,
                    ats=ats_type,
                    fetched=len(jobs),
                    new=len(new_jobs),
                    new_jobs=new_jobs,
                )
            )
            logger.info(
                "[%s] %s — fetched=%d new=%d", ats_type, company_key, len(jobs), len(new_jobs)
            )
    finally:
        if owns_client:
            client.close()
    if persist:
        save_state(state_path, state)
    return results


# --- Helpers -----------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _looks_remote(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return "remote" in t or "anywhere" in t


def _summary_line(r: PollResult) -> str:
    if r.error:
        return f"  {r.company:>14} [{r.ats:<10}] ERROR: {r.error}"
    return f"  {r.company:>14} [{r.ats:<10}] fetched={r.fetched:<4} new={r.new}"


# --- CLI ---------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Tier-0 ATS poller (Greenhouse/Lever/Ashby)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="Run one poll cycle and exit (default)")
    g.add_argument("--watch", action="store_true", help="Loop every 15 min until killed")
    p.add_argument(
        "--company",
        help="Only poll this single company key from TIER_0_COMPANIES",
    )
    p.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help=f"State file path (default: {DEFAULT_STATE_PATH})",
    )
    p.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not write state to disk (dry-run for dedup)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_INTER_COMPANY_DELAY,
        help=f"Seconds between company fetches (default: {DEFAULT_INTER_COMPANY_DELAY})",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit new jobs as JSON to stdout (one array)",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging (DEBUG)",
    )
    return p


def _run_once(args: argparse.Namespace) -> list[PollResult]:
    if args.company:
        if args.company not in TIER_0_COMPANIES:
            logger.error(
                "Unknown company %r; known: %s",
                args.company,
                ", ".join(sorted(TIER_0_COMPANIES)),
            )
            return []
        companies = {args.company: TIER_0_COMPANIES[args.company]}
    else:
        companies = TIER_0_COMPANIES
    return poll_once(
        companies=companies,
        state_path=args.state,
        inter_company_delay=args.delay,
        persist=not args.no_persist,
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    def _emit(results: list[PollResult]) -> None:
        total_new = sum(r.new for r in results)
        total_fetched = sum(r.fetched for r in results)
        errors = sum(1 for r in results if r.error)
        logger.info(
            "Poll summary: companies=%d fetched=%d new=%d errors=%d",
            len(results),
            total_fetched,
            total_new,
            errors,
        )
        for r in results:
            logger.info(_summary_line(r))
        if args.json:
            new_jobs: list[dict] = []
            for r in results:
                for j in r.new_jobs:
                    new_jobs.append(asdict(j))
            sys.stdout.write(json.dumps(new_jobs, indent=2))
            sys.stdout.write("\n")

    if args.watch:
        logger.info("Entering watch loop (interval=%ds)", WATCH_INTERVAL_SECONDS)
        while True:
            try:
                _emit(_run_once(args))
            except KeyboardInterrupt:
                logger.info("Interrupted, exiting watch loop")
                return 0
            except Exception as exc:  # noqa: BLE001 — keep the loop alive
                logger.exception("Unexpected error in watch loop: %s", exc)
            time.sleep(WATCH_INTERVAL_SECONDS)
    else:
        _emit(_run_once(args))
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
