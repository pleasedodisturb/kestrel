"""
Job scraper for TPM/Product/AI roles using python-jobspy.
Searches LinkedIn and Indeed by default.

google is rejected (see UNSUPPORTED_SITES): python-jobspy 1.1.x returns 0
rows for Google Jobs because the page is a JavaScript bootstrap shell
(upstream issue #302). Glassdoor is off by default because jobspy 1.1.82
answers it with HTTP 400 (upstream PRs #384, #347) — it can still be
requested explicitly via --sites.

Usage:
    python tools/scraper.py
    python tools/scraper.py --keywords "AI Product Manager"
    python tools/scraper.py --location "Berlin, Germany" --hours 24
"""

import argparse
from datetime import datetime
from pathlib import Path

from jobspy import scrape_jobs

DEFAULT_KEYWORDS = [
    "Senior Technical Program Manager AI",
    "Technical Program Manager ML",
    "Technical Product Manager AI",
    "AI Program Lead",
    "Senior Product Manager AI developer tools",
    "Innovation Lead AI transformation",
    "Technical Program Manager remote",
]

# Glassdoor dropped from the default list (not just google): python-jobspy
# 1.1.82 answers it with HTTP 400 and 0 rows (upstream PRs #384, #347), the
# same verified silent zero as Google Jobs. Still accepted when requested
# explicitly via --sites; only google is rejected outright (see below).
DEFAULT_SITES = ["linkedin", "indeed"]
DEFAULT_LOCATION = "Berlin, Germany"
DEFAULT_HOURS_OLD = 72
DEFAULT_RESULTS_PER_KEYWORD = 30

# Sites that cannot return real results via python-jobspy 1.1.x, and why
# (G-1802). Checked case-insensitively by validate_sites.
UNSUPPORTED_SITES: dict[str, str] = {
    "google": (
        "python-jobspy 1.1.x returns 0 rows for Google Jobs — the page is a "
        "JavaScript bootstrap shell, not server-rendered listings (upstream "
        "issue #302)"
    ),
}


def validate_sites(sites: list[str]) -> None:
    """Reject any site in `sites` that UNSUPPORTED_SITES names as dead.

    Case-insensitive. Raises ValueError naming each rejected site with its
    reason and the supported defaults, so a caller cannot reach scrape_jobs
    with a site that is known to return nothing.
    """
    rejected = [s for s in sites if s.strip().lower() in UNSUPPORTED_SITES]
    if not rejected:
        return
    reasons = "; ".join(f"{s!r}: {UNSUPPORTED_SITES[s.strip().lower()]}" for s in rejected)
    raise ValueError(
        f"Unsupported site(s) rejected: {reasons}. Supported defaults: {DEFAULT_SITES}."
    )


def scrape_all(
    keywords: list[str] | None = None,
    location: str = DEFAULT_LOCATION,
    hours_old: int = DEFAULT_HOURS_OLD,
    results_per_keyword: int = DEFAULT_RESULTS_PER_KEYWORD,
    sites: list[str] | None = None,
) -> "pd.DataFrame":
    import pandas as pd

    keywords = keywords or DEFAULT_KEYWORDS
    sites = sites or DEFAULT_SITES
    validate_sites(sites)
    all_jobs = []

    for kw in keywords:
        print(f"Scraping: '{kw}' in {location}...")
        try:
            jobs = scrape_jobs(
                site_name=sites,
                search_term=kw,
                location=location,
                results_wanted=results_per_keyword,
                hours_old=hours_old,
                country_indeed="Germany",
            )
            jobs["search_keyword"] = kw
            all_jobs.append(jobs)
            print(f"  Found {len(jobs)} results")
        except Exception as e:
            print(f"  Error scraping '{kw}': {e}")

    if not all_jobs:
        print("No jobs found.")
        return pd.DataFrame()

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["title", "company", "location"], keep="first")
    print(f"\nTotal unique jobs: {len(combined)}")
    return combined


def main():
    parser = argparse.ArgumentParser(description="Scrape job listings")
    parser.add_argument("--keywords", nargs="+", help="Search keywords (default: predefined list)")
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Location to search")
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS_OLD, help="Max age in hours")
    parser.add_argument(
        "--results", type=int, default=DEFAULT_RESULTS_PER_KEYWORD, help="Results per keyword"
    )
    parser.add_argument("--sites", nargs="+", default=DEFAULT_SITES, help="Sites to scrape")
    args = parser.parse_args()

    try:
        validate_sites(args.sites)
    except ValueError as exc:
        parser.error(str(exc))

    jobs = scrape_all(
        keywords=args.keywords,
        location=args.location,
        hours_old=args.hours,
        results_per_keyword=args.results,
        sites=args.sites,
    )

    if jobs.empty:
        return

    output_dir = Path(__file__).parent.parent / "tracking"
    output_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = output_dir / f"scraped_jobs_{date_str}.csv"
    jobs.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
