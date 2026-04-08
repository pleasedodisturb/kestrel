#!/usr/bin/env python3
"""
Auto-submit job applications via direct API (Lever, Greenhouse) or
Playwright browser automation (Ashby, company sites, unknown platforms).

Reads a YAML config with personal details and application list.
API submissions happen instantly. Browser submissions open a real browser,
fill the form, upload files, and pause for user confirmation before submit.

Usage:
    .venv/bin/python tools/auto_apply.py applications-to-submit.yaml
    .venv/bin/python tools/auto_apply.py applications-to-submit.yaml --dry-run
    .venv/bin/python tools/auto_apply.py applications-to-submit.yaml --only shopware
    .venv/bin/python tools/auto_apply.py applications-to-submit.yaml --browser-only
"""

import argparse
import csv
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
PROFILE_DIR = PROJECT_ROOT / ".browser-profile"
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def detect_platform(url: str) -> str:
    """Detect job board platform from URL."""
    if "jobs.ashbyhq.com" in url:
        return "ashby"
    if "jobs.lever.co" in url or "jobs.eu.lever.co" in url:
        return "lever"
    if "greenhouse.io" in url:
        return "greenhouse"
    if "remotely.de" in url:
        return "remotely"
    if "attio.com" in url:
        return "company"
    if "linkedin.com" in url:
        return "linkedin"
    return "unknown"


def parse_lever_url(url: str) -> tuple[str, str, str]:
    """Extract (base_url, site, posting_id) from a Lever job URL.

    Examples:
        https://jobs.lever.co/mistral/67858cb5-... → (https://api.lever.co, mistral, 67858cb5-...)
        https://jobs.eu.lever.co/tradelink/42af... → (https://api.eu.lever.co, tradelink, 42af...)
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot parse Lever URL: {url}")
    site = parts[0]
    posting_id = parts[1]
    if "eu.lever.co" in parsed.hostname:
        base = "https://api.eu.lever.co"
    else:
        base = "https://api.lever.co"
    return base, site, posting_id


def parse_greenhouse_url(url: str) -> tuple[str, str]:
    """Extract (board_token, job_id) from a Greenhouse job URL.

    Examples:
        https://job-boards.greenhouse.io/grafanalabs/jobs/5796211004 → (grafanalabs, 5796211004)
        https://job-boards.eu.greenhouse.io/jetbrains/jobs/4782168101 → (jetbrains, 4782168101)
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    # Pattern: /{board_token}/jobs/{job_id}
    if len(parts) >= 3 and parts[1] == "jobs":
        return parts[0], parts[2]
    raise ValueError(f"Cannot parse Greenhouse URL: {url}")


# ---------------------------------------------------------------------------
# Greenhouse API key extraction
# ---------------------------------------------------------------------------


def extract_greenhouse_api_key(board_token: str) -> str | None:
    """Try to find the Greenhouse Job Board API key from the embed script.

    Greenhouse embeds the API key in their job board pages as a query param
    or in the page source. We try the public boards-api endpoint which often
    works without auth for basic GET, then check if POST works unauthenticated.
    """
    # Many Greenhouse boards allow unauthenticated POST for applications
    # The board_token itself acts as identification
    # Try a test GET first to verify the board exists
    try:
        resp = httpx.get(
            f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs",
            timeout=10,
        )
        if resp.status_code == 200:
            return "__no_key_needed__"
    except Exception:
        pass

    # Try EU endpoint
    try:
        resp = httpx.get(
            f"https://boards-api.eu.greenhouse.io/v1/boards/{board_token}/jobs",
            timeout=10,
        )
        if resp.status_code == 200:
            return "__no_key_needed_eu__"
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Direct API submissions
# ---------------------------------------------------------------------------


def submit_lever_api(personal: dict, app: dict, dry_run: bool) -> dict:
    """Submit application via Lever Postings API (no browser needed).

    Returns: {"ok": True/False, "method": "lever_api", "detail": "..."}
    """
    base_url, site, posting_id = parse_lever_url(app["url"])
    endpoint = f"{base_url}/v0/postings/{site}/{posting_id}"

    cv_path = PROJECT_ROOT / app["cv"]
    cl_md_path = PROJECT_ROOT / app["cover_letter"].replace(".pdf", ".md")

    # Read cover letter text for the comments field
    comments = ""
    if cl_md_path.exists():
        text = cl_md_path.read_text(encoding="utf-8")
        lines = text.split("\n")
        body_start = 0
        for i, line in enumerate(lines):
            if line.strip() == "---" and i > 2:
                body_start = i + 1
                break
        comments = "\n".join(lines[body_start:]).strip()
        comments = re.sub(r"\*\*(.+?)\*\*", r"\1", comments)  # strip bold

    full_name = f"{personal['first_name']} {personal['last_name']}"

    if dry_run:
        print(f"    [DRY RUN] Would POST to {endpoint}")
        print(f"    Name: {full_name}, Email: {personal['email']}")
        print(f"    Resume: {cv_path.name}")
        print(f"    Comments: {len(comments)} chars")
        return {"ok": True, "method": "lever_api", "detail": "dry run"}

    # Lever accepts multipart/form-data for resume uploads
    with open(cv_path, "rb") as resume_file:
        files = {"resume": (cv_path.name, resume_file, "application/pdf")}
        data = {
            "name": full_name,
            "email": personal["email"],
            "phone": personal["phone"],
            "urls[LinkedIn]": personal.get("linkedin", ""),
            "urls[GitHub]": personal.get("github", ""),
            "comments": comments,
            "silent": "true",  # don't send auto-email to candidate
        }

        try:
            resp = httpx.post(endpoint, data=data, files=files, timeout=30)
            result = resp.json()

            if resp.status_code == 200 and result.get("ok"):
                app_id = result.get("applicationId", "unknown")
                print(f"    SUCCESS via Lever API! Application ID: {app_id}")
                return {"ok": True, "method": "lever_api", "detail": f"applicationId={app_id}"}
            else:
                error = result.get("error", resp.text[:200])
                print(f"    Lever API error ({resp.status_code}): {error}")
                return {"ok": False, "method": "lever_api", "detail": error}

        except Exception as e:
            print(f"    Lever API exception: {e}")
            return {"ok": False, "method": "lever_api", "detail": str(e)}


def submit_greenhouse_api(personal: dict, app: dict, dry_run: bool) -> dict:
    """Submit application via Greenhouse Job Board API (no browser needed).

    Returns: {"ok": True/False, "method": "greenhouse_api", "detail": "..."}
    """
    board_token, job_id = parse_greenhouse_url(app["url"])

    # Determine if EU or global
    if "eu.greenhouse.io" in app["url"]:
        endpoint = f"https://boards-api.eu.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
    else:
        endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"

    cv_path = PROJECT_ROOT / app["cv"]
    cl_path = PROJECT_ROOT / app["cover_letter"]

    if dry_run:
        print(f"    [DRY RUN] Would POST to {endpoint}")
        print(f"    Name: {personal['first_name']} {personal['last_name']}")
        print(f"    Resume: {cv_path.name}, Cover: {cl_path.name}")
        return {"ok": True, "method": "greenhouse_api", "detail": "dry run"}

    files = {}
    if cv_path.exists():
        files["resume"] = (cv_path.name, open(cv_path, "rb"), "application/pdf")
    if cl_path.exists():
        files["cover_letter"] = (cl_path.name, open(cl_path, "rb"), "application/pdf")

    data = {
        "first_name": personal["first_name"],
        "last_name": personal["last_name"],
        "email": personal["email"],
        "phone": personal["phone"],
        "location": personal.get("location", ""),
    }

    try:
        resp = httpx.post(endpoint, data=data, files=files, timeout=30)

        # Close file handles
        for f in files.values():
            f[1].close()

        if resp.status_code in (200, 201):
            print(f"    SUCCESS via Greenhouse API! Status: {resp.status_code}")
            return {"ok": True, "method": "greenhouse_api", "detail": f"status={resp.status_code}"}
        else:
            detail = resp.text[:300]
            print(f"    Greenhouse API error ({resp.status_code}): {detail}")
            return {"ok": False, "method": "greenhouse_api", "detail": detail}

    except Exception as e:
        # Close file handles on error
        for f in files.values():
            f[1].close()
        print(f"    Greenhouse API exception: {e}")
        return {"ok": False, "method": "greenhouse_api", "detail": str(e)}


# ---------------------------------------------------------------------------
# Browser-based submissions (Playwright)
# ---------------------------------------------------------------------------


def screenshot(page, name: str) -> Path:
    """Take a screenshot and save it."""
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    path = SCREENSHOTS_DIR / f"{name}_{int(time.time())}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"    Screenshot: {path}")
    return path


def _fill_input(context, selector: str, value: str):
    """Safely fill an input field if it exists."""
    if not value:
        return False
    loc = context.locator(selector)
    if loc.count() > 0:
        try:
            loc.first.click()
            loc.first.fill(value)
            return True
        except Exception as e:
            print(f"    Warning: could not fill '{selector}': {e}")
    return False


def _try_fill(context, selectors: list[str], value: str) -> bool:
    """Try multiple selectors, return True if any worked."""
    if not value:
        return False
    for sel in selectors:
        if _fill_input(context, sel, value):
            return True
    return False


def _upload_file(context, index: int, file_path: str, label: str) -> bool:
    """Upload a file to the nth file input on the page."""
    file_inputs = context.locator('input[type="file"]')
    if file_inputs.count() > index:
        try:
            file_inputs.nth(index).set_input_files(file_path)
            print(f"    Uploaded {label}: {Path(file_path).name}")
            time.sleep(1)
            return True
        except Exception as e:
            print(f"    Warning: file upload failed for {label}: {e}")
    return False


def fill_ashby_browser(page, personal: dict, app: dict):
    """Fill an Ashby application form in the browser."""
    url = app["url"]
    # Navigate to application form
    page.goto(url, wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Ashby job pages have an "Apply" button
    if "/application" not in page.url:
        apply_btn = page.locator("a[href*='/application'], button:has-text('Apply')")
        if apply_btn.count() > 0:
            apply_btn.first.click()
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)
        else:
            page.goto(url.rstrip("/") + "/application", wait_until="networkidle", timeout=30000)
            time.sleep(2)

    print("    Filling Ashby form...")
    full_name = f"{personal['first_name']} {personal['last_name']}"

    # Ashby uses _systemfield_ prefixed names or plain names
    _try_fill(
        page,
        [
            'input[name="_systemfield_name"]',
            'input[name="name"]',
            'input[aria-label*="name" i]',
            'input[placeholder*="name" i]',
        ],
        full_name,
    )

    _try_fill(
        page,
        [
            'input[name="_systemfield_email"]',
            'input[name="email"]',
            'input[type="email"]',
            'input[aria-label*="email" i]',
        ],
        personal["email"],
    )

    _try_fill(
        page,
        [
            'input[name="_systemfield_phone"]',
            'input[name="phone"]',
            'input[type="tel"]',
            'input[aria-label*="phone" i]',
        ],
        personal["phone"],
    )

    _try_fill(
        page,
        [
            'input[name*="linkedin" i]',
            'input[placeholder*="linkedin" i]',
            'input[aria-label*="linkedin" i]',
        ],
        personal.get("linkedin", ""),
    )

    # File uploads
    cv_path = str(PROJECT_ROOT / app["cv"])
    cl_path = str(PROJECT_ROOT / app["cover_letter"])
    _upload_file(page, 0, cv_path, "CV")
    time.sleep(1)
    _upload_file(page, 1, cl_path, "cover letter")

    return True


def fill_lever_browser(page, personal: dict, app: dict):
    """Fill a Lever application form in the browser (fallback if API fails)."""
    url = app["url"]
    if "/apply" not in url:
        url = url.rstrip("/") + "/apply"

    page.goto(url, wait_until="networkidle", timeout=30000)
    time.sleep(2)

    print("    Filling Lever form...")
    full_name = f"{personal['first_name']} {personal['last_name']}"

    _try_fill(page, ['input[name="name"]', 'input[placeholder*="name" i]'], full_name)
    _try_fill(page, ['input[name="email"]', 'input[type="email"]'], personal["email"])
    _try_fill(page, ['input[name="phone"]', 'input[type="tel"]'], personal["phone"])
    _try_fill(page, ['input[name="org"]'], personal.get("current_company", ""))
    _try_fill(
        page,
        ['input[name="urls[LinkedIn]"]', 'input[placeholder*="linkedin" i]'],
        personal.get("linkedin", ""),
    )
    _try_fill(
        page,
        ['input[name="urls[GitHub]"]', 'input[placeholder*="github" i]'],
        personal.get("github", ""),
    )

    # Resume upload
    resume_input = page.locator('input[name="resume"], input[type="file"]')
    if resume_input.count() > 0:
        cv_path = str(PROJECT_ROOT / app["cv"])
        resume_input.first.set_input_files(cv_path)
        print(f"    Uploaded CV: {Path(cv_path).name}")
        time.sleep(1)

    # Cover letter in comments textarea
    cl_textarea = page.locator('textarea[name="comments"]')
    if cl_textarea.count() > 0:
        cl_md = PROJECT_ROOT / app["cover_letter"].replace(".pdf", ".md")
        if cl_md.exists():
            text = cl_md.read_text(encoding="utf-8")
            lines = text.split("\n")
            body_start = 0
            for i, line in enumerate(lines):
                if line.strip() == "---" and i > 2:
                    body_start = i + 1
                    break
            body = "\n".join(lines[body_start:]).strip()
            body = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
            cl_textarea.fill(body)
            print(f"    Pasted cover letter into comments ({len(body)} chars)")

    return True


def fill_greenhouse_browser(page, personal: dict, app: dict):
    """Fill a Greenhouse application form in the browser (fallback if API fails)."""
    page.goto(app["url"], wait_until="networkidle", timeout=30000)
    time.sleep(3)

    print("    Filling Greenhouse form...")

    # Greenhouse forms are often in an iframe
    has_iframe = page.locator("#grnhse_iframe").count() > 0
    ctx = page.frame_locator("#grnhse_iframe") if has_iframe else page

    _try_fill(
        ctx,
        [
            'input[name="job_application[first_name]"]',
            "input#first_name",
            'input[autocomplete="given-name"]',
        ],
        personal["first_name"],
    )

    _try_fill(
        ctx,
        [
            'input[name="job_application[last_name]"]',
            "input#last_name",
            'input[autocomplete="family-name"]',
        ],
        personal["last_name"],
    )

    _try_fill(
        ctx,
        [
            'input[name="job_application[email]"]',
            "input#email",
            'input[type="email"]',
        ],
        personal["email"],
    )

    _try_fill(
        ctx,
        [
            'input[name="job_application[phone]"]',
            "input#phone",
            'input[type="tel"]',
        ],
        personal["phone"],
    )

    _try_fill(
        ctx,
        [
            'input[name="job_application[location]"]',
            "input#location",
        ],
        personal.get("location", ""),
    )

    _try_fill(
        ctx,
        [
            'input[name*="linkedin" i]',
            'input[id*="linkedin" i]',
        ],
        personal.get("linkedin", ""),
    )

    # File uploads
    cv_path = str(PROJECT_ROOT / app["cv"])
    cl_path = str(PROJECT_ROOT / app["cover_letter"])
    _upload_file(ctx, 0, cv_path, "CV")
    _upload_file(ctx, 1, cl_path, "cover letter")

    return True


def fill_generic_browser(page, personal: dict, app: dict):
    """Best-effort form fill for unknown platforms (company sites, remotely.de, etc)."""
    page.goto(app["url"], wait_until="networkidle", timeout=30000)
    time.sleep(3)

    print("    Filling generic form (best-effort)...")
    full_name = f"{personal['first_name']} {personal['last_name']}"

    # Try common field patterns
    _try_fill(
        page,
        [
            'input[name*="name" i]:not([name*="last"]):not([name*="company"])',
            'input[autocomplete="name"]',
            'input[placeholder*="full name" i]',
            'input[placeholder*="name" i]:not([placeholder*="last"]):not([placeholder*="company"])',
        ],
        full_name,
    )

    _try_fill(
        page,
        [
            'input[name*="first" i]',
            'input[autocomplete="given-name"]',
        ],
        personal["first_name"],
    )

    _try_fill(
        page,
        [
            'input[name*="last" i]',
            'input[autocomplete="family-name"]',
        ],
        personal["last_name"],
    )

    _try_fill(
        page,
        [
            'input[type="email"]',
            'input[name*="email" i]',
            'input[autocomplete="email"]',
        ],
        personal["email"],
    )

    _try_fill(
        page,
        [
            'input[type="tel"]',
            'input[name*="phone" i]',
            'input[autocomplete="tel"]',
        ],
        personal["phone"],
    )

    _try_fill(
        page,
        [
            'input[name*="linkedin" i]',
            'input[placeholder*="linkedin" i]',
        ],
        personal.get("linkedin", ""),
    )

    # File uploads
    cv_path = str(PROJECT_ROOT / app["cv"])
    cl_path = str(PROJECT_ROOT / app["cover_letter"])
    _upload_file(page, 0, cv_path, "CV")
    _upload_file(page, 1, cl_path, "cover letter")

    return True


BROWSER_HANDLERS = {
    "ashby": fill_ashby_browser,
    "lever": fill_lever_browser,
    "greenhouse": fill_greenhouse_browser,
    "company": fill_generic_browser,
    "remotely": fill_generic_browser,
    "unknown": fill_generic_browser,
}


# ---------------------------------------------------------------------------
# CSV update
# ---------------------------------------------------------------------------


def update_csv_status(company: str, role: str, new_status: str = "applied"):
    """Update application status in tracking CSV."""
    csv_path = PROJECT_ROOT / "tracking" / "applications.csv"
    if not csv_path.exists():
        return

    rows = []
    updated = False
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row["company"].strip() == company.strip() and role.lower() in row["role"].lower():
                row["status"] = new_status
                row["date_applied"] = str(date.today())
                updated = True
                print(f"    CSV updated: {company} — {role} → {new_status}")
            rows.append(row)

    if updated and fieldnames:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def confirm_and_submit_browser(page, company: str, role: str, dry_run: bool) -> bool:
    """Screenshot, ask for confirmation, click submit."""
    slug = company.lower().replace(" ", "-").replace(".", "")
    screenshot(page, f"pre_submit_{slug}")

    if dry_run:
        print("\n    [DRY RUN] Form filled — NOT submitting.")
        return True

    print(f"\n    >>> Form filled for {company} — {role}")
    print("    >>> Review the browser window, then:")
    response = input("    >>> ENTER=submit, s=skip, q=quit: ").strip().lower()

    if response == "q":
        print("    Quitting.")
        sys.exit(0)
    if response == "s":
        print(f"    Skipped {company}.")
        return False

    # Find and click submit button
    submit_btn = page.locator(
        'button[type="submit"], '
        'button:has-text("Submit application"), '
        'button:has-text("Submit"), '
        'button:has-text("Apply"), '
        'button:has-text("Send application"), '
        'input[type="submit"]'
    )
    if submit_btn.count() > 0:
        submit_btn.first.click()
        time.sleep(3)
        screenshot(page, f"post_submit_{slug}")
        print(f"    SUBMITTED via browser: {company} — {role}")
        return True
    else:
        print("    No submit button found — please click submit manually in the browser.")
        input("    Press ENTER when done...")
        return True


def process_application(page, personal: dict, app: dict, dry_run: bool, browser_only: bool) -> bool:
    """Process a single application. Try API first, fall back to browser."""
    company = app["company"]
    role = app["role"]
    url = app["url"]
    platform = detect_platform(url)

    print(f"\n{'=' * 60}")
    print(f"  {company} — {role}")
    print(f"  Platform: {platform}")
    print(f"  URL: {url}")
    print(f"{'=' * 60}")

    # Verify files exist
    cv_path = PROJECT_ROOT / app["cv"]
    cl_path = PROJECT_ROOT / app["cover_letter"]
    if not cv_path.exists():
        print(f"  ERROR: CV not found: {cv_path}")
        return False
    if not cl_path.exists():
        print(f"  ERROR: Cover letter not found: {cl_path}")
        return False

    # ---- Try direct API first (Lever, Greenhouse) ----
    if not browser_only and platform == "lever":
        print("  Attempting Lever API submission...")
        result = submit_lever_api(personal, app, dry_run)
        if result["ok"]:
            if not dry_run:
                update_csv_status(company, role, "applied")
            return True
        else:
            print("  API failed, falling back to browser...")

    if not browser_only and platform == "greenhouse":
        print("  Attempting Greenhouse API submission...")
        result = submit_greenhouse_api(personal, app, dry_run)
        if result["ok"]:
            if not dry_run:
                update_csv_status(company, role, "applied")
            return True
        else:
            print("  API failed, falling back to browser...")

    # ---- Browser fallback ----
    if platform == "linkedin":
        print("  LinkedIn requires manual application — opening URL...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        print("  >>> Apply manually in the browser window.")
        if not dry_run:
            response = input("  >>> Press ENTER when done, 's' to skip: ").strip().lower()
            if response == "s":
                return False
            update_csv_status(company, role, "applied")
        return True

    handler = BROWSER_HANDLERS.get(platform, fill_generic_browser)
    try:
        handler(page, personal, app)
    except Exception as e:
        print(f"  ERROR filling form: {e}")
        slug = company.lower().replace(" ", "-")
        screenshot(page, f"error_{slug}")
        return False

    success = confirm_and_submit_browser(page, company, role, dry_run)
    if success and not dry_run:
        update_csv_status(company, role, "applied")
    return success


def main():
    parser = argparse.ArgumentParser(description="Auto-submit job applications (API + browser)")
    parser.add_argument("config", help="Path to applications-to-submit.yaml")
    parser.add_argument(
        "--dry-run", action="store_true", help="Fill forms / simulate API but don't submit"
    )
    parser.add_argument("--only", help="Only process applications matching this string")
    parser.add_argument(
        "--browser-only", action="store_true", help="Skip API attempts, use browser for everything"
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: {config_path} not found")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    personal = config["personal"]
    applications = config["applications"]

    if args.only:
        needle = args.only.lower()
        applications = [
            a for a in applications if needle in a["company"].lower() or needle in a["role"].lower()
        ]

    applications = [a for a in applications if a.get("status", "pending") == "pending"]

    if not applications:
        print("No pending applications to process.")
        sys.exit(0)

    # Separate API-eligible from browser-needed
    api_apps = []
    browser_apps = []
    for a in applications:
        p = detect_platform(a["url"])
        if not args.browser_only and p in ("lever", "greenhouse"):
            api_apps.append(a)
        else:
            browser_apps.append(a)

    print(f"\n{len(applications)} application(s) to process:")
    if api_apps:
        print(f"  {len(api_apps)} via direct API (fast):")
        for a in api_apps:
            print(f"    [{detect_platform(a['url'])}] {a['company']} — {a['role']}")
    if browser_apps:
        print(f"  {len(browser_apps)} via browser:")
        for a in browser_apps:
            print(f"    [{detect_platform(a['url'])}] {a['company']} — {a['role']}")

    if args.dry_run:
        print("\n  MODE: DRY RUN")
    print()

    submitted = 0
    errors = 0

    # ---- Phase 1: API submissions (no browser needed) ----
    if api_apps:
        print("=" * 60)
        print("PHASE 1: Direct API submissions")
        print("=" * 60)
        for app in api_apps:
            platform = detect_platform(app["url"])
            company = app["company"]
            role = app["role"]

            print(f"\n  {company} — {role} [{platform} API]")

            if platform == "lever":
                result = submit_lever_api(personal, app, args.dry_run)
            elif platform == "greenhouse":
                result = submit_greenhouse_api(personal, app, args.dry_run)
            else:
                result = {"ok": False, "detail": "unexpected platform"}

            if result["ok"]:
                submitted += 1
                app["status"] = "submitted" if not args.dry_run else "dry-run"
                app["method"] = result.get("method", "api")
                if not args.dry_run:
                    update_csv_status(company, role, "applied")
            else:
                # Move to browser queue for retry
                print("    → Moving to browser queue for retry")
                browser_apps.append(app)
                errors += 1

    # ---- Phase 2: Browser submissions ----
    if browser_apps:
        print(f"\n{'=' * 60}")
        print("PHASE 2: Browser submissions")
        print("=" * 60)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 900},
            )
            page = browser.new_page()

            for app in browser_apps:
                # Skip if already submitted via API retry
                if app.get("status") in ("submitted", "dry-run"):
                    continue

                result = process_application(page, personal, app, args.dry_run, args.browser_only)
                if result:
                    submitted += 1
                    app["status"] = "submitted" if not args.dry_run else "dry-run"
                    app["method"] = "browser"
                else:
                    errors += 1

            browser.close()

    # Save updated config
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\n{'=' * 60}")
    print(f"DONE: {submitted} submitted, {errors} errors")
    print(f"Config saved: {config_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
