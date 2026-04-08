# NOTE: Run this script with the project's venv:
#   .venv/bin/python tools/germany_jobs.py --keywords "TPM" --location "Frankfurt"
#   .venv/bin/python tools/germany_jobs.py --preset tpm --score
#   .venv/bin/python tools/germany_jobs.py --preset all --remote --output json
"""
Germany job search via Arbeitsagentur and Arbeitnow APIs.

Free APIs for Germany-focused roles. Run via Goose Developer:
  .venv/bin/python tools/germany_jobs.py --keywords "TPM" --location "Frankfurt"
  .venv/bin/python tools/germany_jobs.py --keywords "Product Manager" --limit 20 --output json
  .venv/bin/python tools/germany_jobs.py --preset tpm --score
  .venv/bin/python tools/germany_jobs.py --preset all --remote --score

Multi-keyword: use comma-separated keywords or a --preset flag.

Presets:
  tpm     → Technical Program Manager, Projektleiter, Programmmanager, Technischer Projektleiter
  pm      → Produktmanager, Product Manager, IT-Projektmanager, Digitalisierungsmanager
  ai      → KI-Produktmanager, AI Product Manager, Innovationsmanager, KI-Programm, Produktentwickler
  builder → Product Engineer, AI Engineer, Lösungsarchitekt, Softwareentwickler KI
  all     → all of the above, deduplicated by (title, company)

APIs:
  - Arbeitsagentur: https://rest.arbeitsagentur.de/jobboerse/jobsuche-service (X-API-Key: jobboerse-jobsuche)
  - Arbeitnow: https://www.arbeitnow.com/api/job-board-api (no key)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from urllib.parse import quote_plus, urlencode

try:
    import httpx
except ImportError:
    raise ImportError("httpx is required: pip install httpx")

ARBEITSAGENTUR_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
ARBEITSAGENTUR_API_KEY = "jobboerse-jobsuche"
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"

# Keyword presets
PRESETS: dict[str, list[str]] = {
    "tpm": [
        "Technical Program Manager",
        "Projektleiter",
        "Programmmanager",
        "Technischer Projektleiter",
        "Technical Product Manager",
        "Technischer Produktmanager",
    ],
    "pm": [
        "Produktmanager",
        "Product Manager",
        "IT-Projektmanager",
        "Digitalisierungsmanager",
    ],
    "ai": [
        "KI-Produktmanager",
        "AI Product Manager",
        "Innovationsmanager",
        "KI-Programm",
        "Produktentwickler",
        "AI Operations",
        "MLOps",
        "KI-Betrieb",
    ],
    "builder": [
        "Product Engineer",
        "AI Engineer",
        "Lösungsarchitekt",
        "Softwareentwickler KI",
        "Founding Engineer",
        "Staff Engineer",
        "Principal Engineer",
    ],
    "devrel": [
        "Developer Relations",
        "Developer Advocate",
        "Developer Experience",
        "DevRel",
        "Entwickler-Community",
    ],
    "leadership": [
        "Head of Engineering",
        "VP Engineering",
        "Engineering Manager",
        "Leiter Softwareentwicklung",
        "Head of Product",
        "AI Program Lead",
    ],
}

# Scoring signals
SCORE_SIGNALS = [
    "ai",
    "ki",
    "product",
    "program",
    "technical",
    "innovation",
    "platform",
    "builder",
    "digital",
]


# Signals suggesting German-only work environment
GERMAN_ONLY_SIGNALS = [
    "muttersprache",
    "deutsch c1",
    "deutsch c2",
    "deutschkenntnisse",
    "deutschsprachig",
    "sehr gute deutschkenntnisse",
    "fließend deutsch",
    "nur deutsch",
    "sprachkenntnisse deutsch",
    "verhandlungssicheres deutsch",
]
GERMAN_ONLY_TITLE_PATTERNS = [
    "sachbearbeiter",
    "kaufmann",
    "kauffrau",
    "verwaltung",
    "vertriebsmitarbeiter",
    "kundenberater",
    "arbeitsvermittler",
]


def is_likely_german_only(job: dict) -> bool:
    """Heuristic: does this job likely require German as primary working language?"""
    title_lower = job.get("title", "").lower()
    desc_lower = job.get("description", "").lower()
    tags_lower = " ".join(job.get("tags", [])).lower()
    all_text = f"{title_lower} {desc_lower} {tags_lower}"
    if any(sig in all_text for sig in GERMAN_ONLY_SIGNALS):
        return True
    if any(pat in title_lower for pat in GERMAN_ONLY_TITLE_PATTERNS):
        return True
    return False


def score_job(job: dict) -> int:
    """Score job 1-5 based on keyword signals in title, company, tags."""
    text = " ".join(
        [
            job.get("title", ""),
            job.get("company", ""),
            " ".join(job.get("tags", [])),
        ]
    ).lower()
    hits = sum(1 for sig in SCORE_SIGNALS if sig in text)
    # Map hits to 1-5 stars
    if hits == 0:
        return 1
    elif hits == 1:
        return 2
    elif hits == 2:
        return 3
    elif hits <= 4:
        return 4
    else:
        return 5


def stars(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def fetch_arbeitsagentur(
    keywords: str = "",
    location: str = "",
    limit: int = 25,
    days_old: int = 30,
    remote: bool = False,
) -> list[dict]:
    """Fetch jobs from Arbeitsagentur (Germany's Federal Employment Agency)."""
    params: dict[str, str | int | bool] = {
        "size": min(limit, 100),
        "page": 1,
        "veroeffentlichtseit": days_old,
        "angebotsart": 1,  # ARBEIT
    }
    if keywords:
        params["was"] = keywords
    if location:
        params["wo"] = location
    if remote:
        params["arbeitszeit"] = "ho"  # HEIM_TELEARBEIT

    url = f"{ARBEITSAGENTUR_BASE}/pc/v4/jobs?{urlencode(params)}"
    headers = {"X-API-Key": ARBEITSAGENTUR_API_KEY}

    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        print(f"Arbeitsagentur API error: {e}", file=sys.stderr)
        return []

    jobs = data.get("stellenangebote", [])
    result = []
    for j in jobs:
        arbeitgeber = j.get("arbeitgeber", "")
        beruf = j.get("beruf", "")
        refnr = j.get("refnr", "")
        ar = j.get("arbeitsort", {}) or {}
        ort = ar.get("ort", "") or ar.get("region", "") or ""
        land = ar.get("land", "Deutschland")
        hash_id = j.get("hashId", "")

        # Fix URL generation: prefer hashId detail URL, fall back to search by refnr
        if hash_id:
            job_url = f"https://www.arbeitsagentur.de/jobboerse/jobsuche/detail/{hash_id}"
        elif refnr:
            job_url = f"https://www.arbeitsagentur.de/jobsuche/suche?was={quote_plus(refnr)}"
        else:
            job_url = ""

        result.append(
            {
                "source": "arbeitsagentur",
                "title": beruf or f"Stelle {refnr}",
                "company": arbeitgeber,
                "location": f"{ort}, {land}".strip(", ") if ort or land else "Deutschland",
                "url": job_url,
                "refnr": refnr,
                "posted": j.get("aktuelleVeroeffentlichungsdatum", ""),
                "tags": [],
            }
        )
    return result


def fetch_arbeitnow(
    keywords: str = "",
    location: str = "",
    limit: int = 25,
    remote_only: bool = False,
) -> list[dict]:
    """Fetch jobs from Arbeitnow (Berlin-based, EU tech focus)."""
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(ARBEITNOW_API)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        print(f"Arbeitnow API error: {e}", file=sys.stderr)
        return []

    jobs = data.get("data", [])
    result = []
    kw_lower = keywords.lower().split() if keywords else []
    loc_lower = location.lower() if location else ""

    for j in jobs:
        if remote_only and not j.get("remote", False):
            continue
        title = j.get("title", "")
        company = j.get("company_name", "")
        loc = j.get("location", "")
        if loc_lower and loc_lower not in loc.lower():
            continue
        if kw_lower and not any(k in (title + " " + company).lower() for k in kw_lower):
            continue
        result.append(
            {
                "source": "arbeitnow",
                "title": title,
                "company": company,
                "location": loc,
                "url": j.get("url", ""),
                "remote": j.get("remote", False),
                "tags": j.get("tags", []),
                "posted": datetime.fromtimestamp(j.get("created_at", 0)).strftime("%Y-%m-%d")
                if j.get("created_at")
                else "",
            }
        )
        if len(result) >= limit:
            break

    return result


def fetch_all_for_keywords(
    keyword_list: list[str],
    location: str,
    limit: int,
    remote: bool,
    sources: list[str],
) -> list[dict]:
    """Fetch jobs for multiple keywords; deduplicate by (title, company)."""
    seen: set[tuple[str, str]] = set()
    all_jobs: list[dict] = []
    aa_count = 0
    an_count = 0

    for kw in keyword_list:
        if "arbeitsagentur" in sources:
            jobs = fetch_arbeitsagentur(
                keywords=kw,
                location=location,
                limit=limit,
                remote=remote,
            )
            for j in jobs:
                key = (j["title"].lower(), j["company"].lower())
                if key not in seen:
                    seen.add(key)
                    all_jobs.append(j)
                    aa_count += 1

        if "arbeitnow" in sources:
            jobs = fetch_arbeitnow(
                keywords=kw,
                location=location,
                limit=limit,
                remote_only=remote,
            )
            for j in jobs:
                key = (j["title"].lower(), j["company"].lower())
                if key not in seen:
                    seen.add(key)
                    all_jobs.append(j)
                    an_count += 1

    return all_jobs, aa_count, an_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Germany job APIs (Arbeitsagentur, Arbeitnow)"
    )
    parser.add_argument(
        "--keywords",
        default="",
        help="Search keywords, comma-separated for multi-search (e.g. 'TPM,Product Manager')",
    )
    parser.add_argument(
        "--preset",
        choices=["tpm", "pm", "ai", "builder", "devrel", "leadership", "all"],
        help="Keyword preset: tpm, pm, ai, builder, devrel, leadership, or all",
    )
    parser.add_argument("--location", default="Frankfurt", help="Location (default: Frankfurt)")
    parser.add_argument(
        "--limit", type=int, default=25, help="Max results per keyword per source (default: 25)"
    )
    parser.add_argument("--remote", action="store_true", help="Filter remote/telework only")
    parser.add_argument("--output", choices=["csv", "json"], default="csv", help="Output format")
    parser.add_argument(
        "--english-only", action="store_true", help="Filter out likely German-language-only jobs"
    )
    parser.add_argument(
        "--sources", nargs="+", default=["arbeitsagentur", "arbeitnow"], help="Source APIs to query"
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Print a rough fit score (1-5 stars) based on keyword signals",
    )
    args = parser.parse_args()

    # Determine keyword list
    keyword_list: list[str] = []
    if args.preset:
        if args.preset == "all":
            for kws in PRESETS.values():
                keyword_list.extend(kws)
        else:
            keyword_list = PRESETS[args.preset]
        print(f"Using preset '{args.preset}': {keyword_list}", file=sys.stderr)
    elif args.keywords:
        # Support comma-separated multi-keyword
        keyword_list = [k.strip() for k in args.keywords.split(",") if k.strip()]
    else:
        keyword_list = [""]  # empty search = broad fetch

    # Fetch jobs
    all_jobs, aa_total, an_total = fetch_all_for_keywords(
        keyword_list=keyword_list,
        location=args.location,
        limit=args.limit,
        remote=args.remote,
        sources=args.sources,
    )

    if not all_jobs:
        print("No jobs found.", file=sys.stderr)
        print("Found 0 jobs total (0 from Arbeitsagentur, 0 from Arbeitnow)", file=sys.stderr)
        return

    # Score all jobs
    for j in all_jobs:
        j["score"] = score_job(j)

    if args.output == "json":
        print(json.dumps(all_jobs, indent=2, ensure_ascii=False))
    else:
        # CSV output
        headers = ["source", "title", "company", "location", "url", "posted"]
        if args.score:
            headers.append("score")
        print(",".join(headers))
        for j in all_jobs:
            row = [str(j.get(h, "")).replace(",", ";") for h in headers if h != "score"]
            if args.score:
                row.append(str(j.get("score", 1)))
            print(",".join(row))

    # Summary line (always printed to stdout so it's visible)
    total = len(all_jobs)
    summary = (
        f"Found {total} jobs total ({aa_total} from Arbeitsagentur, {an_total} from Arbeitnow)"
    )
    if args.score:
        # Also print score breakdown
        score_dist = {}
        for j in all_jobs:
            s = j.get("score", 1)
            score_dist[s] = score_dist.get(s, 0) + 1
        score_str = " | ".join(
            f"{stars(s)}:{count}" for s, count in sorted(score_dist.items(), reverse=True)
        )
        summary += f"  [{score_str}]"
    print(summary, file=sys.stderr)


if __name__ == "__main__":
    main()
