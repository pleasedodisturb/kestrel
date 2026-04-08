#!/usr/bin/env python3
"""
Scrape job matches from remotely.de and LinkedIn using a persistent browser session.

First run: opens login page — user logs in manually, cookies are saved.
Subsequent runs: reuses saved session, goes straight to scraping.

Usage:
    .venv/bin/python tools/scrape_remotely.py                  # scrape remotely.de matches
    .venv/bin/python tools/scrape_remotely.py --linkedin       # scrape LinkedIn job alerts
    .venv/bin/python tools/scrape_remotely.py --login          # force re-login (clear session)
    .venv/bin/python tools/scrape_remotely.py --all            # scrape both sites
"""

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).parent.parent / ".browser-profile"
REMOTELY_MATCHES_URL = "https://www.remotely.de/user/cv/matches"
REMOTELY_LOGIN_URL = "https://www.remotely.de/login"
LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs/"
LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"


def wait_for_login(page, name: str, success_pattern: str):
    """Wait for user to log in by polling URL changes."""
    print(f"\n>>> Log in to {name} in the browser window...")
    print(f"    Waiting up to 3 minutes for URL to contain '{success_pattern}'")
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            if success_pattern in page.url:
                print(f"    Logged in to {name}!")
                return True
        except Exception:
            pass
        time.sleep(2)
    print(f"    Login timeout for {name}. Continuing anyway...")
    return False


def scrape_remotely(page) -> list[dict]:
    """Scrape CV match results from remotely.de."""
    print("\n--- Scraping remotely.de CV matches ---")

    # Go to CV page first (matches load via client-side nav)
    page.goto("https://www.remotely.de/user/cv", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    # Check if redirected to login
    if "/login" in page.url:
        wait_for_login(page, "remotely.de", "/user")
        page.goto("https://www.remotely.de/user/cv", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

    # Click "Job-Matches ansehen" button to navigate to matches
    print("  Clicking 'Job-Matches ansehen'...")
    try:
        page.click("text=Job-Matches ansehen", timeout=10000)
        time.sleep(5)  # wait for matches page to load
    except PlaywrightTimeout:
        # Try direct navigation as fallback
        print("  Button not found, trying direct navigation...")
        page.goto(REMOTELY_MATCHES_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

    print(f"  Current URL: {page.url}")

    # Scroll down to load more matches (infinite scroll / lazy loading)
    for i in range(5):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

    # Extract job matches from the page
    jobs = page.evaluate("""() => {
        const results = [];

        // Method 1: JSON-LD structured data
        const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (const s of ldScripts) {
            try {
                const data = JSON.parse(s.textContent);
                if (data['@type'] === 'JobPosting') {
                    results.push({
                        title: data.title || '',
                        company: data.hiringOrganization?.name || '',
                        location: data.jobLocation?.address?.addressLocality || data.applicantLocationRequirements?.name || 'Remote',
                        url: data.url || window.location.href,
                        datePosted: data.datePosted || '',
                        source: 'remotely.de',
                        employmentType: data.employmentType || '',
                        remotelyId: data.identifier?.value || ''
                    });
                }
            } catch {}
        }
        if (results.length > 0) return results;

        // Method 2: Find all links to /job/ pages with surrounding context
        const allLinks = document.querySelectorAll('a[href*="/job/"]');
        const seen = new Set();
        for (const link of allLinks) {
            const href = link.href;
            if (seen.has(href)) continue;
            seen.add(href);

            // Walk up to find the card container
            let card = link.closest('div[class], li, article') || link.parentElement;
            const text = (card || link).textContent?.trim() || '';

            // Try to extract title and company from the text
            const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 2);

            results.push({
                title: lines[0] || link.textContent?.trim() || '',
                company: lines[1] || '',
                location: lines.find(l => /remote|berlin|frankfurt|münchen|germany|deutschland/i.test(l)) || 'Remote (DE)',
                url: href,
                source: 'remotely.de',
                raw_text: lines.slice(0, 5).join(' | '),
            });
        }
        if (results.length > 0) return results;

        // Method 3: Broad DOM search - any element that looks like a job listing
        const allElements = document.querySelectorAll('h2, h3, h4, [role="listitem"], li');
        for (const el of allElements) {
            const link = el.querySelector('a[href*="/job/"]') || el.closest('a[href*="/job/"]');
            if (!link) continue;
            const href = link.href;
            if (seen.has(href)) continue;
            seen.add(href);
            results.push({
                title: el.textContent?.trim().split('\\n')[0] || '',
                url: href,
                source: 'remotely.de',
            });
        }

        return results;
    }""")

    # If no structured data found, grab the full page HTML for debugging
    if not jobs:
        print("  No structured job data found. Saving page HTML for inspection...")
        html = page.content()
        debug_path = Path(__file__).parent.parent / "remotely_matches_debug.html"
        debug_path.write_text(html)
        print(f"  Saved to {debug_path}")

    print(f"  Found {len(jobs)} job matches on remotely.de")
    return jobs


def scrape_linkedin(page) -> list[dict]:
    """Scrape job recommendations/alerts from LinkedIn."""
    print("\n--- Scraping LinkedIn jobs ---")
    page.goto(LINKEDIN_JOBS_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    # Check if need to login
    if "/login" in page.url or "authwall" in page.url:
        page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded")
        wait_for_login(page, "LinkedIn", "/feed")
        page.goto(LINKEDIN_JOBS_URL, wait_until="domcontentloaded", timeout=60000)

    time.sleep(3)

    # Navigate to recommended/saved jobs
    # Try "My Jobs" → "Recommended for you"
    try:
        page.goto(
            "https://www.linkedin.com/jobs/collections/recommended/",
            wait_until="domcontentloaded",
            timeout=30000,
        )
    except PlaywrightTimeout:
        pass

    time.sleep(3)

    jobs = page.evaluate("""() => {
        const results = [];
        // LinkedIn job cards
        const cards = document.querySelectorAll('.job-card-container, .jobs-search-results__list-item, [data-occludable-job-id]');
        for (const card of cards) {
            const titleEl = card.querySelector('.job-card-list__title, .artdeco-entity-lockup__title, a[class*="job-card"]');
            const companyEl = card.querySelector('.artdeco-entity-lockup__subtitle, .job-card-container__primary-description');
            const locationEl = card.querySelector('.artdeco-entity-lockup__caption, .job-card-container__metadata-item');
            const linkEl = card.querySelector('a[href*="/jobs/view/"]');

            if (titleEl) {
                results.push({
                    title: titleEl.textContent?.trim() || '',
                    company: companyEl?.textContent?.trim() || '',
                    location: locationEl?.textContent?.trim() || '',
                    url: linkEl?.href || '',
                    source: 'linkedin',
                });
            }
        }

        // Fallback: any job view links
        if (results.length === 0) {
            const links = document.querySelectorAll('a[href*="/jobs/view/"]');
            for (const link of links) {
                const text = link.textContent?.trim();
                if (text && text.length > 5 && !text.includes('Sign in')) {
                    results.push({
                        title: text,
                        url: link.href,
                        source: 'linkedin',
                    });
                }
            }
        }

        return results;
    }""")

    if not jobs:
        print("  No structured job data found. Saving page HTML for inspection...")
        html = page.content()
        debug_path = Path(__file__).parent.parent / "linkedin_jobs_debug.html"
        debug_path.write_text(html)
        print(f"  Saved to {debug_path}")

    print(f"  Found {len(jobs)} job recommendations on LinkedIn")
    return jobs


def main():
    parser = argparse.ArgumentParser(description="Scrape job matches from remotely.de and LinkedIn")
    parser.add_argument("--linkedin", action="store_true", help="Scrape LinkedIn recommended jobs")
    parser.add_argument(
        "--remotely", action="store_true", help="Scrape remotely.de CV matches (default)"
    )
    parser.add_argument("--all", action="store_true", help="Scrape both sites")
    parser.add_argument("--login", action="store_true", help="Force re-login (clear session)")
    parser.add_argument("--json", action="store_true", help="Output as JSON (default: table)")
    parser.add_argument(
        "--headless", action="store_true", help="Run headless (only works if already logged in)"
    )
    args = parser.parse_args()

    # Default to remotely if nothing specified
    if not args.linkedin and not args.all:
        args.remotely = True

    if args.login:
        import shutil

        if PROFILE_DIR.exists():
            shutil.rmtree(PROFILE_DIR)
            print("Cleared browser profile. Will prompt for fresh login.")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    all_jobs = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=args.headless,
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            if args.remotely or args.all:
                jobs = scrape_remotely(page)
                all_jobs.extend(jobs)

            if args.linkedin or args.all:
                jobs = scrape_linkedin(page)
                all_jobs.extend(jobs)
        finally:
            context.close()

    # Output
    if args.json:
        print(json.dumps(all_jobs, indent=2, ensure_ascii=False))
    else:
        if not all_jobs:
            print("\nNo jobs found. Try running with --login to re-authenticate.")
            sys.exit(1)

        print(f"\n{'=' * 80}")
        print(f"  Found {len(all_jobs)} total jobs")
        print(f"{'=' * 80}\n")

        for i, job in enumerate(all_jobs, 1):
            print(f"  {i}. [{job.get('source', '?')}] {job.get('title', 'Unknown')}")
            if job.get("company"):
                print(f"     Company:  {job['company']}")
            if job.get("location"):
                print(f"     Location: {job['location']}")
            if job.get("url"):
                print(f"     URL:      {job['url']}")
            print()


if __name__ == "__main__":
    main()
