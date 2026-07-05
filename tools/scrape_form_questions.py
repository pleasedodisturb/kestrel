#!/usr/bin/env python3
"""Scrape application form questions from all ATS platforms.

Visits each application URL, extracts custom questions/fields,
and outputs a structured report for human review.

Usage:
    .venv/bin/python tools/scrape_form_questions.py
    .venv/bin/python tools/scrape_form_questions.py --platform lever
    .venv/bin/python tools/scrape_form_questions.py --only nimbusworks
"""

import argparse
import asyncio
import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

STANDARD_FIELDS = {
    "name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "location",
    "resume",
    "cover_letter",
    "linkedin",
    "github",
    "website",
    "twitter",
    "current_company",
    "org",
    "current_title",
}


def detect_platform(url: str) -> str:
    from career_os.utils.url_validation import detect_platform as _detect

    result = _detect(url)
    return "other" if result == "unknown" else result


async def scrape_lever_questions(page, url: str) -> list[dict]:
    """Extract custom questions from a Lever application form."""
    apply_url = url.rstrip("/") + "/apply"
    await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    questions = []

    # Lever custom questions are in divs with class "application-question"
    # or in labeled sections after the standard fields
    # Look for all labeled form groups
    labels = await page.locator("label").all()
    for label in labels:
        text = (await label.inner_text()).strip()
        if not text:
            continue

        # Skip standard fields
        lower = text.lower()
        if any(
            s in lower
            for s in [
                "full name",
                "email",
                "phone",
                "resume",
                "cv",
                "cover letter",
                "linkedin url",
                "github url",
                "twitter url",
                "current company",
                "google scholar",
                "design portfolio",
            ]
        ):
            continue

        # Check if it has an associated input/textarea/select
        parent = label.locator("..")
        inputs = await parent.locator(
            "input:not([type='file']):not([type='hidden']), textarea, select"
        ).count()

        if inputs > 0:
            # Get field type
            textarea = await parent.locator("textarea").count()
            select = await parent.locator("select").count()

            field_type = "textarea" if textarea > 0 else "select" if select > 0 else "text"

            # Get select options if applicable
            options = []
            if select > 0:
                option_els = await parent.locator("select option").all()
                for opt in option_els:
                    opt_text = (await opt.inner_text()).strip()
                    if opt_text and opt_text != "Select...":
                        options.append(opt_text)

            # Check if required
            required = await parent.locator("[required], .required").count() > 0
            asterisk = "*" in text

            questions.append(
                {
                    "label": text.replace("*", "").strip(),
                    "type": field_type,
                    "required": required or asterisk,
                    "options": options if options else None,
                }
            )

    # Also check for section headers that indicate custom question groups
    sections = await page.locator("h3, h4, .section-header").all()
    for section in sections:
        text = (await section.inner_text()).strip()
        if text and text not in ["Submit your application", "Links", "Additional information"]:
            if text not in [q["label"] for q in questions]:
                # This is a section header, not a question - but note it
                pass

    return questions


async def scrape_greenhouse_questions(page, url: str) -> list[dict]:
    """Extract custom questions from a Greenhouse application form."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    # Click Apply button if present
    apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")')
    if await apply_btn.count() > 0:
        await apply_btn.first.click()
        await page.wait_for_timeout(2000)

    questions = []
    labels = await page.locator("label").all()
    for label in labels:
        text = (await label.inner_text()).strip()
        if not text:
            continue

        lower = text.lower()
        if any(
            s in lower
            for s in [
                "first name",
                "last name",
                "email",
                "phone",
                "resume",
                "cover letter",
                "linkedin",
                "location",
            ]
        ):
            continue

        parent = label.locator("..")
        inputs = await parent.locator(
            "input:not([type='file']):not([type='hidden']), textarea, select"
        ).count()

        if inputs > 0:
            textarea = await parent.locator("textarea").count()
            select = await parent.locator("select").count()
            field_type = "textarea" if textarea > 0 else "select" if select > 0 else "text"

            options = []
            if select > 0:
                option_els = await parent.locator("select option").all()
                for opt in option_els:
                    opt_text = (await opt.inner_text()).strip()
                    if opt_text:
                        options.append(opt_text)

            required = "*" in text or await parent.locator("[required]").count() > 0

            questions.append(
                {
                    "label": text.replace("*", "").strip(),
                    "type": field_type,
                    "required": required,
                    "options": options if options else None,
                }
            )

    return questions


async def scrape_ashby_questions(page, url: str) -> list[dict]:
    """Extract custom questions from an Ashby application form."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    # Click Apply button if present
    apply_btn = page.locator('button:has-text("Apply"), a:has-text("Apply")')
    if await apply_btn.count() > 0:
        await apply_btn.first.click()
        await page.wait_for_timeout(2000)

    questions = []
    # Ashby uses aria-label and data-testid extensively
    labels = await page.locator("label, [data-testid*='question']").all()
    for label in labels:
        text = (await label.inner_text()).strip()
        if not text:
            continue

        lower = text.lower()
        if any(
            s in lower
            for s in [
                "name",
                "email",
                "phone",
                "resume",
                "cv",
                "cover letter",
                "linkedin",
                "location",
                "how did you hear",
            ]
        ):
            continue

        parent = label.locator("..")
        inputs = await parent.locator(
            "input:not([type='file']):not([type='hidden']), textarea, select"
        ).count()

        if inputs > 0:
            textarea = await parent.locator("textarea").count()
            select = await parent.locator("select").count()
            field_type = "textarea" if textarea > 0 else "select" if select > 0 else "text"

            required = "*" in text or await parent.locator("[required]").count() > 0

            questions.append(
                {
                    "label": text.replace("*", "").strip(),
                    "type": field_type,
                    "required": required,
                    "options": None,
                }
            )

    return questions


SCRAPERS = {
    "lever": scrape_lever_questions,
    "greenhouse": scrape_greenhouse_questions,
    "ashby": scrape_ashby_questions,
}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", help="Only scrape this platform")
    parser.add_argument("--only", help="Only scrape matching company/role")
    parser.add_argument("yaml_file", nargs="?", default="batch-apply.yaml")
    args = parser.parse_args()

    config = yaml.safe_load((PROJECT_ROOT / args.yaml_file).read_text())
    applications = [a for a in config["applications"] if a.get("status") == "pending"]

    if args.platform:
        applications = [a for a in applications if detect_platform(a["url"]) == args.platform]
    if args.only:
        needle = args.only.lower()
        applications = [
            a
            for a in applications
            if needle in a.get("company", "").lower()
            or needle in a.get("role", "").lower()
            or needle in a.get("slug", "").lower()
        ]

    scrapeable = [a for a in applications if detect_platform(a["url"]) in SCRAPERS]
    print(f"Scraping {len(scrapeable)} application forms for custom questions...\n")

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        all_results = []
        for i, app in enumerate(scrapeable, 1):
            platform = detect_platform(app["url"])
            slug = app.get("slug", app.get("company", "unknown"))
            role = app.get("role", "")

            print(f"[{i}/{len(scrapeable)}] {slug} ({platform})...", end=" ", flush=True)

            context = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await context.new_page()

            try:
                scraper = SCRAPERS[platform]
                questions = await scraper(page, app["url"])
                custom = [q for q in questions if q["label"]]
                print(f"{len(custom)} custom question(s)")

                all_results.append(
                    {
                        "slug": slug,
                        "company": app.get("company", ""),
                        "role": role,
                        "platform": platform,
                        "url": app["url"],
                        "questions": custom,
                    }
                )
            except Exception as e:
                print(f"ERROR: {e}")
                all_results.append(
                    {
                        "slug": slug,
                        "company": app.get("company", ""),
                        "role": role,
                        "platform": platform,
                        "url": app["url"],
                        "questions": [],
                        "error": str(e),
                    }
                )
            finally:
                await context.close()

        await browser.close()

    # Output report
    out_path = PROJECT_ROOT / "batch-questions-2026-03-27.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)

    # Print summary
    print(f"\n{'=' * 60}")
    print("FORM QUESTIONS REPORT")
    print(f"{'=' * 60}")

    has_questions = [r for r in all_results if r["questions"]]
    no_questions = [r for r in all_results if not r["questions"] and "error" not in r]
    errors = [r for r in all_results if "error" in r]

    for r in all_results:
        if r["questions"]:
            print(f"\n{r['slug']} ({r['platform']})")
            print(f"  {r['role']}")
            for q in r["questions"]:
                req = " [REQUIRED]" if q["required"] else ""
                opts = f" Options: {q['options']}" if q.get("options") else ""
                print(f"  {'>'} {q['label']} ({q['type']}){req}{opts}")

    print(f"\n{'=' * 60}")
    print(f"With custom questions: {len(has_questions)}")
    print(f"Standard form only: {len(no_questions)}")
    print(f"Errors: {len(errors)}")
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
