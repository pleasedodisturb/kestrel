#!/usr/bin/env python3
"""Batch apply to jobs via Playwright browser automation.

All ATS APIs are locked down (Lever 403, Greenhouse 401).
This script uses Playwright to fill application forms directly.

Usage:
    .venv/bin/python tools/batch_apply_browser.py --platform lever
    .venv/bin/python tools/batch_apply_browser.py --platform greenhouse
    .venv/bin/python tools/batch_apply_browser.py --platform ashby
    .venv/bin/python tools/batch_apply_browser.py --all
    .venv/bin/python tools/batch_apply_browser.py --only mistral
    .venv/bin/python tools/batch_apply_browser.py --dry-run
    .venv/bin/python tools/batch_apply_browser.py --test-url https://jobs.lever.co/mistral/abc123
"""

import argparse
import asyncio
import os
import re
import sqlite3
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots" / "batch-2026-03-27"
CV_PATH = PROJECT_ROOT / "cv" / os.getenv("CV_FILENAME", "cv.pdf")


def _load_personal_config():
    """Load personal details from config/personal.yaml."""
    config_path = PROJECT_ROOT / "config" / "personal.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Personal config not found at {config_path}. "
            "Copy config/personal.yaml.example to config/personal.yaml and fill in your details."
        )
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return {
        "first_name": cfg["name"]["first"],
        "last_name": cfg["name"]["last"],
        "full_name": cfg["name"]["full"],
        "email": cfg["contact"]["email"],
        "phone": cfg["contact"]["phone"],
        "linkedin": cfg["contact"]["linkedin"],
        "github": cfg["contact"]["github"],
        "location": cfg["location"],
    }


PERSONAL = _load_personal_config()


def detect_platform(url: str) -> str:
    # NOTE: Lever pages are fully client-side rendered JS. WebFetch and
    # non-browser tools cannot extract content. Many companies have also
    # migrated off jobs.lever.co (returns 404). The Playwright-based
    # fill_lever handler still works for companies that remain on Lever.
    from career_os.utils.url_validation import detect_platform as _detect

    result = _detect(url)
    return "other" if result == "unknown" else result


def get_cover_letter_text(cl_md_path: Path) -> str:
    """Extract plain text body from cover letter markdown.

    Returns the full body after the second '---' frontmatter delimiter,
    including the closing signature (e.g. "the applicant"). This is intentional -
    the full cover letter body goes into the form textarea as-is.
    """
    if not cl_md_path.exists():
        return ""
    text = cl_md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "---" and i > 2:
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    body = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
    return body


async def fill_source_field(page) -> None:
    """Fill 'How did you hear about us?' / 'Where did you find this job?' fields.

    Common across all ATS platforms. Called BEFORE company-specific custom questions
    so that custom handlers can override if needed.
    """
    # Try input fields with source-related names
    for sel in [
        'input[name*="source" i]',
        'input[name*="hear" i]',
        'input[name*="found" i]',
        'input[name*="referral_source" i]',
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            tag = await loc.first.evaluate("el => el.tagName.toLowerCase()")
            input_type = await loc.first.get_attribute("type") or "text"
            if tag == "select":
                for option_label in ["Job board", "Job Board", "Online Job Board", "Other"]:
                    try:
                        await loc.first.select_option(label=option_label)
                        print("    [source] Selected dropdown option for source field")
                        return
                    except Exception:
                        continue
            elif input_type in ("text", "search", ""):
                await loc.first.fill("Job board")
                print("    [source] Filled source input: Job board")
                return

    # Try select elements with source-related names
    for sel in [
        'select[name*="source" i]',
        'select[name*="hear" i]',
        'select[name*="found" i]',
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            for option_label in ["Job board", "Job Board", "Online Job Board", "Other"]:
                try:
                    await loc.first.select_option(label=option_label)
                    print("    [source] Selected dropdown: source field")
                    return
                except Exception:
                    continue

    # Try label-based approach for "How did you hear" style questions
    for label_text in ["How did you hear", "Where did you find", "How did you find"]:
        try:
            label_loc = page.locator(f'label:has-text("{label_text}")')
            if await label_loc.count() > 0:
                label_el = label_loc.first
                for_attr = await label_el.get_attribute("for")
                if for_attr:
                    target = page.locator(f"#{for_attr}")
                    if await target.count() > 0:
                        tag = await target.first.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            for opt in ["Job board", "Job Board", "Online Job Board", "Other"]:
                                try:
                                    await target.first.select_option(label=opt)
                                    print(f"    [source] Selected '{opt}' via label '{label_text}'")
                                    return
                                except Exception:
                                    continue
                        else:
                            await target.first.fill("Job board")
                            print(f"    [source] Filled via label '{label_text}': Job board")
                            return
                # Fallback: sibling input/select
                for tag_sel in ["select", "input", "textarea"]:
                    sibling = label_loc.first.locator(f".. >> {tag_sel}")
                    if await sibling.count() > 0:
                        tag = await sibling.first.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            for opt in ["Job board", "Job Board", "Online Job Board", "Other"]:
                                try:
                                    await sibling.first.select_option(label=opt)
                                    print(f"    [source] Selected '{opt}' via label sibling")
                                    return
                                except Exception:
                                    continue
                        else:
                            await sibling.first.fill("Job board")
                            print("    [source] Filled via label sibling: Job board")
                            return
        except Exception:
            continue


async def fill_lever(page, app: dict, dry_run: bool) -> bool:
    """Fill a Lever application form."""
    apply_url = app["url"].rstrip("/") + "/apply"
    await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    # Upload resume FIRST - Lever auto-parses and fills fields
    file_inputs = page.locator('input[type="file"]')
    if await file_inputs.count() > 0:
        await file_inputs.first.set_input_files(str(CV_PATH))
        # Wait for auto-parse to complete
        await page.wait_for_timeout(3000)

    # Now overwrite with correct values (auto-parse may have gotten them wrong)
    name_input = page.locator('input[name="name"]')
    if await name_input.count() > 0:
        await name_input.fill("")
        await name_input.fill(PERSONAL["full_name"])

    email_input = page.locator('input[name="email"]')
    if await email_input.count() > 0:
        await email_input.fill("")
        await email_input.fill(PERSONAL["email"])

    phone_input = page.locator('input[name="phone"]')
    if await phone_input.count() > 0:
        await phone_input.fill("")
        await phone_input.fill(PERSONAL["phone"])

    # Fill LinkedIn
    for sel in [
        'input[name="urls[LinkedIn]"]',
        'input[name="urls[LinkedIn URL]"]',
        'input[placeholder*="LinkedIn"]',
        'input[placeholder*="linkedin"]',
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(PERSONAL["linkedin"])
            break

    # Fill GitHub
    for sel in [
        'input[name="urls[GitHub]"]',
        'input[placeholder*="GitHub"]',
        'input[placeholder*="github"]',
        'input[placeholder*="Portfolio"]',
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(PERSONAL["github"])
            break

    # Fill additional info / comments with cover letter text
    cl_md = PROJECT_ROOT / app["cover_letter"].replace(".pdf", ".md")
    cl_text = get_cover_letter_text(cl_md)
    if cl_text:
        textarea = page.locator('textarea[name="comments"], textarea[name="additional"]')
        if await textarea.count() > 0:
            await textarea.first.fill(cl_text)

    # Fill current company (leave blank)
    company_input = page.locator('input[name="org"]')
    if await company_input.count() > 0:
        await company_input.fill("")

    # Fill "How did you hear about us?" if present
    await fill_source_field(page)

    # Fill company-specific custom questions
    await fill_custom_questions(page, app)

    return True


async def fill_greenhouse(page, app: dict, dry_run: bool) -> bool:
    """Fill a Greenhouse application form."""
    url = app["url"]
    # Greenhouse apply URLs: append #app or navigate to apply page
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    # Look for Apply button and click it
    apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")')
    if await apply_btn.count() > 0:
        await apply_btn.first.click()
        await page.wait_for_timeout(2000)

    # Fill first name
    for sel in [
        'input[id*="first_name"]',
        'input[name*="first_name"]',
        'input[placeholder*="First"]',
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(PERSONAL["first_name"])
            break

    # Fill last name
    for sel in ['input[id*="last_name"]', 'input[name*="last_name"]', 'input[placeholder*="Last"]']:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(PERSONAL["last_name"])
            break

    # Fill email
    for sel in ['input[id*="email"]', 'input[name*="email"]', 'input[type="email"]']:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(PERSONAL["email"])
            break

    # Fill phone
    for sel in ['input[id*="phone"]', 'input[name*="phone"]', 'input[type="tel"]']:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(PERSONAL["phone"])
            break

    # Fill location
    for sel in ['input[id*="location"]', 'input[name*="location"]']:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(PERSONAL["location"])
            break

    # Upload resume
    resume_input = page.locator('input[type="file"]').first
    if await resume_input.count() > 0:
        await resume_input.set_input_files(str(CV_PATH))
        await page.wait_for_timeout(1000)

    # Upload cover letter if second file input exists
    cl_pdf = PROJECT_ROOT / app["cover_letter"]
    file_inputs = page.locator('input[type="file"]')
    if await file_inputs.count() > 1 and cl_pdf.exists():
        await file_inputs.nth(1).set_input_files(str(cl_pdf))
        await page.wait_for_timeout(1000)

    # Fill LinkedIn URL field if present
    for sel in [
        'input[id*="linkedin"]',
        'input[name*="linkedin"]',
        'input[placeholder*="LinkedIn"]',
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(PERSONAL["linkedin"])
            break

    # Fill "How did you hear about us?" if present
    await fill_source_field(page)

    # Fill company-specific custom questions
    await fill_custom_questions(page, app)

    return True


async def fill_ashby(page, app: dict, dry_run: bool) -> bool:
    """Fill an Ashby application form."""
    url = app["url"]
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    # Click Apply button if on job description page
    apply_btn = page.locator('button:has-text("Apply"), a:has-text("Apply")')
    if await apply_btn.count() > 0:
        await apply_btn.first.click()
        await page.wait_for_timeout(2000)

    # Fill name (Ashby often has single name field or first/last)
    name_input = page.locator('input[name="name"], input[name="_systemfield_name"]')
    if await name_input.count() > 0:
        await name_input.first.fill(PERSONAL["full_name"])
    else:
        # Try first/last
        first = page.locator('input[name="firstName"], input[name="_systemfield_first_name"]')
        if await first.count() > 0:
            await first.first.fill(PERSONAL["first_name"])
        last = page.locator('input[name="lastName"], input[name="_systemfield_last_name"]')
        if await last.count() > 0:
            await last.first.fill(PERSONAL["last_name"])

    # Fill email
    email_input = page.locator(
        'input[name="email"], input[name="_systemfield_email"], input[type="email"]'
    )
    if await email_input.count() > 0:
        await email_input.first.fill(PERSONAL["email"])

    # Fill phone
    phone_input = page.locator(
        'input[name="phone"], input[name="_systemfield_phone"], input[type="tel"]'
    )
    if await phone_input.count() > 0:
        await phone_input.first.fill(PERSONAL["phone"])

    # Fill LinkedIn
    linkedin = page.locator('input[name*="linkedin" i], input[placeholder*="LinkedIn" i]')
    if await linkedin.count() > 0:
        await linkedin.first.fill(PERSONAL["linkedin"])

    # Upload resume
    file_inputs = page.locator('input[type="file"]')
    if await file_inputs.count() > 0:
        await file_inputs.first.set_input_files(str(CV_PATH))
        await page.wait_for_timeout(1000)

    # Upload cover letter to second file input if available
    cl_pdf = PROJECT_ROOT / app["cover_letter"]
    if await file_inputs.count() > 1 and cl_pdf.exists():
        await file_inputs.nth(1).set_input_files(str(cl_pdf))
        await page.wait_for_timeout(1000)

    # Fill current company
    company = page.locator('input[name*="company" i], input[name*="org" i]')
    if await company.count() > 0:
        await company.first.fill("")

    # Fill location
    location = page.locator('input[name*="location" i]')
    if await location.count() > 0:
        await location.first.fill(PERSONAL["location"])

    # Fill "How did you hear about us?" if present
    await fill_source_field(page)

    # Fill company-specific custom questions
    await fill_custom_questions(page, app)

    return True


# ---------------------------------------------------------------------------
# Company-specific custom question handlers
# ---------------------------------------------------------------------------

ANTHROPIC_WHY = (
    "I use Claude Code every day. Not casually - I run multiple sessions in "
    "Ghostty, sometimes nine hours straight, with SSH to a Mac mini and cloud "
    "instances running in parallel. I've built an entire platform this way. So "
    "the product conviction is real.\n\n"
    "But the honest reason is values. Anthropic operates at the Godzilla vs "
    "Kong level of AI, and from what I can see, you're making hard decisions "
    "responsibly when you could just maximize for money at your scale. Every "
    "company this big has some blood on the floor. But you also have real "
    "signals that you're thinking about what this technology does to people, "
    "not just what it does for revenue.\n\n"
    "I'm not naive about AI - it's neither the all-consuming thing fearmongers "
    "say, nor something you can ignore. The question I keep coming back to is: "
    "how do we use the atom for nuclear reactors and not for atomic bombs? I "
    "want to work with people who are actually facing that question, not "
    "avoiding it. You can't fix what you can't face. I'd like to join "
    "Anthropic in facing the hard decisions and maybe solving some of the "
    "unsolvable ones."
)

ANTHROPIC_AI_POLICY = (
    "I use AI to structure and organize my text, not to generate content. "
    "I write my own answers and use AI to fit them into format constraints."
)

ANTHROPIC_CLAUDE_CODE_EXP = (
    "Yes - daily power user. Multiple parallel sessions in Ghostty, SSH to "
    "Mac mini, cloud instances. Built entire CareerOS platform in Claude Code."
)

N8N_WHY = (
    "n8n sits at this overlap of AI and no-code and actual programming that I "
    "find really interesting. It's not just automation like Zapier never "
    "became - it's an enablement platform. You have decision trees, building "
    "blocks, and real logic, but with a graphical interface that makes it "
    "accessible. I built a workflow diagram for a previous application and it "
    "was ridiculously easy. Everything I do now in code talking to Claude Code, "
    "n8n does with a visual layer on top. Also - it's European, it's German, "
    "and it's here. That matters to me."
)


async def _fill_field_by_label(page, label_text: str, value: str, exact: bool = False) -> bool:
    """Find an input/textarea/select near a label containing `label_text` and fill it.

    Returns True if field was found and filled, False otherwise.
    """
    # Try textarea first (for long-form answers)
    if exact:
        label_loc = page.locator(f'label:text-is("{label_text}")')
    else:
        label_loc = page.locator(f'label:has-text("{label_text}")')

    if await label_loc.count() > 0:
        label_el = label_loc.first
        # Check for 'for' attribute pointing to an input
        for_attr = await label_el.get_attribute("for")
        if for_attr:
            target = page.locator(f"#{for_attr}")
            if await target.count() > 0:
                tag = await target.first.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    await target.first.select_option(label=value)
                else:
                    await target.first.fill(value)
                return True

        # Fallback: find sibling/child input or textarea
        for tag_sel in ["textarea", "input", "select"]:
            sibling = label_loc.first.locator(f".. >> {tag_sel}")
            if await sibling.count() > 0:
                tag = await sibling.first.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    await sibling.first.select_option(label=value)
                else:
                    await sibling.first.fill(value)
                return True

    # Fallback: search by placeholder or aria-label
    for sel in [
        f'textarea[aria-label*="{label_text}" i]',
        f'input[aria-label*="{label_text}" i]',
        f'textarea[placeholder*="{label_text}" i]',
        f'input[placeholder*="{label_text}" i]',
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(value)
            return True

    return False


async def _click_radio_by_label(page, label_text: str) -> bool:
    """Click a radio button or option whose visible label matches `label_text`.

    Works for standard HTML radios AND Ashby-style custom React components where
    radio options are rendered as <div> elements with role="radio" or <label>
    wrapping hidden inputs - not standard HTML radios.

    Three-stage approach:
    1. Standard CSS selectors (plain HTML forms)
    2. Playwright built-in text matching (Ashby custom components)
    3. JS fallback - find any clickable element whose text matches

    Returns True if clicked, False otherwise.
    """
    # Stage 1: Try standard CSS selectors
    for sel in [
        f'label:has-text("{label_text}") >> input[type="radio"]',
        f'div[role="radio"]:has-text("{label_text}")',
        f'div[role="option"]:has-text("{label_text}")',
        f'label:has-text("{label_text}")',
        f'span:has-text("{label_text}")',
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.click()
            return True

    # Stage 2: Playwright built-in text matching (handles Ashby custom components)
    try:
        text_loc = page.get_by_text(label_text, exact=False)
        if await text_loc.count() > 0:
            await text_loc.first.click()
            return True
    except Exception:
        pass

    # Stage 3: JS fallback - find any clickable element whose textContent matches
    try:
        clicked = await page.evaluate(
            """(searchText) => {
            const allElements = document.querySelectorAll(
                '[role="radio"], [role="option"], label, '
                + 'div[class*="option"], div[class*="radio"], '
                + 'div[class*="choice"], span[class*="option"]'
            );
            for (const el of allElements) {
                if (el.textContent.trim().includes(searchText)) {
                    el.click();
                    return true;
                }
            }
            return false;
        }""",
            label_text,
        )
        if clicked:
            return True
    except Exception:
        pass

    return False


async def _select_dropdown_option(page, label_text: str, option_text: str) -> bool:
    """For Ashby-style custom dropdowns: click the dropdown near `label_text`,
    then select the option matching `option_text`.
    Returns True if successful.
    """
    # Find the dropdown trigger near the label
    label_loc = page.locator(f'label:has-text("{label_text}")')
    if await label_loc.count() == 0:
        # Try finding by text in a parent div
        label_loc = page.locator(f'div:has-text("{label_text}")')
    if await label_loc.count() == 0:
        return False

    # Click on the dropdown/select element near the label
    parent = label_loc.first.locator("..")
    dropdown = parent.locator('select, [role="combobox"], [role="listbox"], button')
    if await dropdown.count() > 0:
        el = dropdown.first
        tag = await el.evaluate("el => el.tagName.toLowerCase()")
        if tag == "select":
            await el.select_option(label=option_text)
            return True
        # Custom dropdown: click to open, then click option
        await el.click()
        await page.wait_for_timeout(500)
        option = page.locator(
            f'[role="option"]:has-text("{option_text}"), li:has-text("{option_text}")'
        )
        if await option.count() > 0:
            await option.first.click()
            return True

    return False


async def fill_custom_questions(page, app: dict) -> None:
    """Fill company-specific custom form questions based on URL/slug.

    Each field fill is wrapped in try/except so missing fields are silently skipped.
    """
    url = app.get("url", "")
    slug = app.get("slug", app.get("company", "")).lower()

    # ---- Lever: Mistral ----
    if "lever.co" in url and "mistral" in url.lower():
        # Fill "Current location" field
        try:
            await _fill_field_by_label(page, "Current location", "Frankfurt, Germany")
        except Exception as e:
            print(f"    [custom] Lever/Mistral: could not fill 'Current location': {e}")

        # Fill custom textareas by scanning all textareas on the page
        # and matching by nearby text content
        product_exp = (
            "At Wolt, I built an AI-augmented program management system from scratch - "
            "6 LLMs (Claude, OpenAI, Gemini) orchestrated through 4 enterprise APIs "
            "(Atlassian, GSuite, Slack, Glean). B2B internal tooling, enterprise-grade, "
            "built for a post-M&A environment with no existing infrastructure.\n\n"
            "At Amazon Ring, I shipped Ring Ultra - a radar-based security camera from "
            "sensor research to 800k-2M units. B2C hardware product, 10 teams, 5 countries, "
            "full hardware/ML/firmware/software stack.\n\n"
            "Currently building CareerOS - a full-stack career operations platform "
            "(Python/FastAPI backend, React frontend, multi-agent AI scoring pipelines, "
            "CI/CD, automated job scraping). Solo-built in Claude Code."
        )
        try:
            # Use JavaScript to find textareas and check nearby text
            await page.evaluate("""() => {
                // Tag textareas AND selects by walking up to find their section context
                const fields = document.querySelectorAll('textarea, select');
                for (const field of fields) {
                    let el = field;
                    let sectionText = '';
                    while (el && el !== document.body) {
                        el = el.parentElement;
                        if (el) sectionText = el.textContent.substring(0, 200).toUpperCase();
                        if (sectionText.includes('LOCATION') && (sectionText.includes('PARIS') || sectionText.includes('LONDON'))) {
                            field.setAttribute('data-field-type', 'location');
                            break;
                        }
                        if (sectionText.includes('PRODUCT EXPERIENCE')) {
                            field.setAttribute('data-field-type', 'product-experience');
                            break;
                        }
                        if (sectionText.includes('DEV REL') && sectionText.includes('INFLUENCE')) {
                            field.setAttribute('data-field-type', 'devrel-influence');
                            break;
                        }
                    }
                }
            }""")

            # Location may be a textarea OR a select dropdown
            loc_select = page.locator('select[data-field-type="location"]')
            loc_ta = page.locator('textarea[data-field-type="location"]')
            if await loc_select.count() > 0:
                # Try selecting "London" option by label (partial match)
                try:
                    await loc_select.first.select_option(label="London")
                    print("    [custom] Selected Location dropdown: London")
                except Exception:
                    # Fallback: try option value containing "london"
                    options = await loc_select.first.evaluate(
                        """sel => Array.from(sel.options).map(o => ({value: o.value, text: o.text}))"""
                    )
                    london_opt = next(
                        (o for o in options if "london" in o["text"].lower()),
                        None,
                    )
                    if london_opt:
                        await loc_select.first.select_option(value=london_opt["value"])
                        print(f"    [custom] Selected Location dropdown: {london_opt['text']}")
                    else:
                        print(
                            f"    [custom] Location dropdown options: {options} - no London match"
                        )
            elif await loc_ta.count() > 0:
                await loc_ta.first.fill("London (UK) or Paris (France)")
                print("    [custom] Filled Location textarea: London (UK) or Paris (France)")

            prod_ta = page.locator('textarea[data-field-type="product-experience"]')
            if await prod_ta.count() > 0:
                await prod_ta.first.fill(product_exp)
                print(f"    [custom] Filled Product Experience ({len(product_exp)} chars)")

            # DEV REL - INFLUENCE (required on DevRel role)
            devrel_ta = page.locator('textarea[data-field-type="devrel-influence"]')
            if await devrel_ta.count() > 0:
                devrel_text = (
                    "operations platform solo in Claude Code: Python/FastAPI backend, React "
                    "frontend, multi-agent AI scoring, CI/CD pipeline, automated job scraping "
                    "across 6 sources. It runs daily, scores 200+ jobs per scan, and sends "
                    "push notifications. I built it because the tools I needed didn't exist, "
                    "and I wanted to show what one person can ship with AI-native workflows. "
                    "The repo itself is the proof."
                )
                await devrel_ta.first.fill(devrel_text)
                print(f"    [custom] Filled DevRel Influence ({len(devrel_text)} chars)")

        except Exception as e:
            print(f"    [custom] Lever/Mistral: textarea fill error: {e}")

        # Fill right-to-work question if present (Yes/No radio on some Mistral roles)
        # IMPORTANT: only click "Yes" near the right-to-work question, not any random "Yes"
        try:
            clicked = await page.evaluate("""() => {
                const keywords = ['right to work', 'authorized to work', 'eligible to work',
                                  'legally authorized', 'work permit', 'work authorisation',
                                  'legally eligible', 'right to live and work'];
                // Find all elements containing right-to-work text
                const allEls = document.querySelectorAll('label, span, div, p, li');
                for (const el of allEls) {
                    const text = el.textContent.toLowerCase();
                    const isMatch = keywords.some(kw => text.includes(kw));
                    if (!isMatch) continue;
                    // Found the question section - now find "Yes" radio/label nearby
                    const parent = el.closest('.application-question, .custom-question, div');
                    if (!parent) continue;
                    // Look for radio input with "Yes" label inside same container
                    const labels = parent.querySelectorAll('label');
                    for (const lbl of labels) {
                        if (lbl.textContent.trim() === 'Yes' || lbl.textContent.trim() === 'yes') {
                            const radio = lbl.querySelector('input[type="radio"]') ||
                                          document.getElementById(lbl.getAttribute('for'));
                            if (radio) { radio.click(); return true; }
                            lbl.click();
                            return true;
                        }
                    }
                    // Also try radio buttons with value "Yes"
                    const radios = parent.querySelectorAll('input[type="radio"]');
                    for (const r of radios) {
                        if (r.value.toLowerCase() === 'yes') {
                            r.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            if clicked:
                print("    [custom] Clicked 'Yes' for right-to-work question")
            else:
                print("    [custom] No right-to-work question found (skipped)")
        except Exception as e:
            print(f"    [custom] Right-to-work radio error: {e}")

    # ---- Greenhouse: Anthropic ----
    from career_os.utils.url_validation import url_has_domain

    if url_has_domain(url, "greenhouse.io") and ("anthropic" in slug or "anthropic" in url.lower()):
        gh_fields = [
            # (label_text, value, exact_match)
            ("Country", "United Kingdom", False),
            ("open to working in-person 25%", "Yes", False),
            ("Why Anthropic", ANTHROPIC_WHY, False),
            ("AI Policy", ANTHROPIC_AI_POLICY, False),
            ("Earliest start", "2-3 weeks from offer", False),
            ("Require visa sponsorship", "No", False),
            ("Will you require sponsorship", "No", False),
            ("interviewed at Anthropic before", "No", False),
            ("experience with Claude Code", ANTHROPIC_CLAUDE_CODE_EXP, False),
            ("Working address", "Frankfurt, Germany", False),
        ]
        for label, value, exact in gh_fields:
            try:
                filled = await _fill_field_by_label(page, label, value, exact=exact)
                if not filled:
                    # Try as a select/dropdown for yes/no/country fields
                    await _select_dropdown_option(page, label, value)
                # Small delay between fields to avoid overwhelming the form
                await page.wait_for_timeout(300)
            except Exception as e:
                print(f"    [custom] Greenhouse/Anthropic: could not fill '{label}': {e}")

        # Greenhouse React dynamic forms fallback: Greenhouse (especially Anthropic)
        # uses React-based forms with dynamically generated IDs. The label-based
        # approach above may miss fields because inputs are not direct siblings of
        # labels. This JS fallback finds fields by their question text within
        # Greenhouse's <div class="field"> blocks.
        try:
            field_data = [(label, value) for label, value, exact in gh_fields]
            await page.evaluate(
                """(fieldData) => {
                const fields = document.querySelectorAll('.field, [class*="field"]');
                for (const field of fields) {
                    const text = field.textContent;
                    for (const [searchText, value] of fieldData) {
                        if (text.includes(searchText)) {
                            const input = field.querySelector(
                                'textarea, input:not([type="file"]):not([type="hidden"]), select'
                            );
                            if (input) {
                                if (input.tagName === 'SELECT') {
                                    for (const opt of input.options) {
                                        if (opt.text.includes(value)) {
                                            input.value = opt.value;
                                            input.dispatchEvent(new Event('change', { bubbles: true }));
                                            break;
                                        }
                                    }
                                } else {
                                    const setter =
                                        Object.getOwnPropertyDescriptor(
                                            window.HTMLInputElement.prototype, 'value'
                                        ).set ||
                                        Object.getOwnPropertyDescriptor(
                                            window.HTMLTextAreaElement.prototype, 'value'
                                        ).set;
                                    setter.call(input, value);
                                    input.dispatchEvent(new Event('input', { bubbles: true }));
                                    input.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            }
                        }
                    }
                }
            }""",
                field_data,
            )
            print("    [custom] Greenhouse/Anthropic: JS fallback applied for React dynamic fields")
        except Exception as e:
            print(f"    [custom] Greenhouse/Anthropic: JS fallback error: {e}")

        # Leave "Additional Information" empty (cover letter is attached as PDF)
        # No action needed - just skip it

    # ---- Ashby: n8n Head of DevRel ----
    elif url_has_domain(url, "ashbyhq.com") and (
        "n8n" in slug or "n8n" in url.lower() or "a8aea5b5" in url
    ):
        ashby_fields = [
            # Text/textarea fields: (label_text, value)
            ("Expected yearly salary", "150,000 - 180,000 EUR"),
            ("What about n8n caught your attention", N8N_WHY),
            ("Notice period", "Available immediately, can start within 2 weeks"),
        ]
        for label, value in ashby_fields:
            try:
                await _fill_field_by_label(page, label, value)
                await page.wait_for_timeout(300)
            except Exception as e:
                print(f"    [custom] Ashby/n8n: could not fill '{label}': {e}")

        # Location dropdown/radio
        try:
            ok = await _click_radio_by_label(
                page, "I can be based in Germany and do not need visa support"
            )
            if not ok:
                await _select_dropdown_option(
                    page, "Location", "I can be based in Germany and do not need visa support"
                )
            await page.wait_for_timeout(300)
        except Exception as e:
            print(f"    [custom] Ashby/n8n: could not fill Location: {e}")

        # Radio/select style questions: (question_label, answer_label)
        ashby_radio_fields = [
            ("worked in PE/VC backed startup", "Yes"),
            ("n8n experience", "I've been building workflows with n8n for 1-3 months"),
            ("Coding", "I code weekly"),
            ("On-camera", "Very active (monthly or more)"),
            ("ICs managed", "9+"),
            ("Functions managed", "None of the above"),
            ("Video program", "I contributed but did not own it"),
            (
                "Technical demos",
                "Advanced (multi-step orchestration, agents/tools, evals, repos with tests/templates)",
            ),
        ]
        for question, answer in ashby_radio_fields:
            try:
                ok = await _click_radio_by_label(page, answer)
                if not ok:
                    # Try dropdown approach
                    await _select_dropdown_option(page, question, answer)
                await page.wait_for_timeout(300)
            except Exception as e:
                print(f"    [custom] Ashby/n8n: could not fill '{question}': {e}")

    # ---- Ashby: Cohere (IDs 108, 109) ----
    # Scraper found 0 custom questions for Cohere on Ashby.
    # Standard Ashby fill (name, email, phone, linkedin, resume) handles these.
    # No custom question handler needed.

    # ---- Ashby: Ashby self (ID 44) ----
    # Scraper found 0 custom questions for Ashby's own job postings.
    # Standard Ashby fill (name, email, phone, linkedin, resume) handles these.
    # No custom question handler needed.


FILLERS = {
    "lever": fill_lever,
    "greenhouse": fill_greenhouse,
    "ashby": fill_ashby,
}


async def process_application(browser, app: dict, index: int, total: int, dry_run: bool) -> dict:
    """Process a single application in its own browser context."""
    platform = detect_platform(app["url"])
    slug = app.get("slug", app.get("company", "unknown"))
    role = app.get("role", "")

    print(f"\n[{index}/{total}] {slug} - {role}")
    print(f"  Platform: {platform}")
    print(f"  URL: {app['url']}")

    if platform not in FILLERS:
        print(f"  SKIP: no automation for {platform} (needs manual apply)")
        return {"slug": slug, "status": "skipped", "reason": f"no {platform} automation"}

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    context = await browser.new_context(viewport={"width": 1280, "height": 900})
    page = await context.new_page()

    try:
        filler = FILLERS[platform]
        success = await filler(page, app, dry_run)

        # Screenshot
        screenshot_path = SCREENSHOTS_DIR / f"{slug}_{int(time.time())}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"  Screenshot: {screenshot_path.name}")

        if dry_run:
            print("  [DRY RUN] Form filled, not submitting")
            return {"slug": slug, "status": "dry-run", "screenshot": str(screenshot_path)}

        if success:
            # Solve captcha automatically via Anti-Captcha API
            from captcha_solver import solve_and_inject

            captcha_ok = await solve_and_inject(page, timeout=120)

            if not captcha_ok:
                print("  Captcha solve failed - skipping")
                return {
                    "slug": slug,
                    "status": "captcha-failed",
                    "screenshot": str(screenshot_path),
                }

            # Submit the form via direct form.submit() or fetch, bypassing hCaptcha widget
            submitted_via_js = await page.evaluate("""() => {
                // Approach 1: Find the form and submit it directly
                const form = document.querySelector('form.application-form, form[action*="apply"], form');
                if (form) {
                    // Ensure the h-captcha-response is in the form
                    let captchaField = form.querySelector('textarea[name="h-captcha-response"]');
                    if (!captchaField) {
                        captchaField = document.querySelector('textarea[name="h-captcha-response"]');
                        if (captchaField) form.appendChild(captchaField.cloneNode(true));
                    }
                    // Use the native submit to bypass JS validation
                    const submitBtn = form.querySelector('button[type="submit"]:not(.hidden):not(.awli-button)');
                    if (submitBtn) {
                        // Temporarily remove hcaptcha validation handlers
                        const oldOnsubmit = form.onsubmit;
                        form.onsubmit = null;
                        submitBtn.click();
                        return true;
                    }
                    // Fallback: use HTMLFormElement.submit() which skips validation
                    form.submit();
                    return true;
                }
                return false;
            }""")
            print(f"  Submit via form.submit(): {submitted_via_js}")

            if submitted_via_js:
                await page.wait_for_timeout(4000)

                # Check for confirmation page
                page_text = await page.inner_text("body")
                submitted = any(
                    phrase in page_text.lower()
                    for phrase in [
                        "thank you",
                        "application received",
                        "successfully submitted",
                        "thanks for applying",
                        "we've received",
                        "application has been",
                    ]
                )

                post_path = SCREENSHOTS_DIR / f"{slug}_submitted_{int(time.time())}.png"
                await page.screenshot(path=str(post_path), full_page=True)

                if submitted:
                    print("  SUBMITTED! Confirmation detected.")
                else:
                    # May have hit validation error - check for error messages
                    has_error = any(
                        phrase in page_text.lower()
                        for phrase in [
                            "error",
                            "required",
                            "please fill",
                            "invalid",
                        ]
                    )
                    if has_error:
                        print(f"  VALIDATION ERROR - check screenshot: {post_path.name}")
                        return {
                            "slug": slug,
                            "status": "validation-error",
                            "screenshot": str(post_path),
                        }
                    print(f"  Clicked submit - check screenshot: {post_path.name}")

                return {
                    "slug": slug,
                    "status": "submitted" if submitted else "clicked-submit",
                    "screenshot": str(post_path),
                }
            else:
                print("  No visible submit button found - check screenshot")

        return {"slug": slug, "status": "filled", "screenshot": str(screenshot_path)}

    except Exception as e:
        err_path = SCREENSHOTS_DIR / f"{slug}_error_{int(time.time())}.png"
        try:
            await page.screenshot(path=str(err_path), full_page=True)
        except Exception:
            pass
        print(f"  ERROR: {e}")
        return {"slug": slug, "status": "error", "error": str(e)}

    finally:
        await context.close()


async def _run_test_url(url: str, headless: bool = False) -> None:
    """Open a single URL, run the appropriate filler, screenshot, and exit.

    Useful for testing form filling on expired or live postings without submitting.
    """
    platform = detect_platform(url)
    if platform not in FILLERS:
        print(f"No filler for platform '{platform}' (URL: {url})")
        print(f"Supported: {', '.join(FILLERS.keys())}")
        return

    # Build a fake app dict with minimal fields
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    slug = path_parts[0] if path_parts else "test"
    fake_app = {
        "url": url,
        "slug": slug,
        "company": slug,
        "role": "test",
        # Dummy cover letter path - fill functions handle missing files gracefully
        "cover_letter": "cv/applications/test/cover_letter.pdf",
    }

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[TEST MODE] URL: {url}")
    print(f"  Platform: {platform}")
    print(f"  Slug: {slug}")

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        try:
            filler = FILLERS[platform]
            success = await filler(page, fake_app, dry_run=True)

            screenshot_path = SCREENSHOTS_DIR / f"test_{slug}_{int(time.time())}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"  Screenshot: {screenshot_path}")
            print(f"  Fill result: {'OK' if success else 'FAILED'}")
            print("  [TEST MODE] Done. No submission attempted.")
        except Exception as e:
            err_path = SCREENSHOTS_DIR / f"test_{slug}_error_{int(time.time())}.png"
            try:
                await page.screenshot(path=str(err_path), full_page=True)
            except Exception:
                pass
            print(f"  ERROR: {e}")
        finally:
            await context.close()
            await browser.close()


async def main():
    parser = argparse.ArgumentParser(description="Batch apply via browser")
    parser.add_argument("--platform", help="Only process this platform (lever/greenhouse/ashby)")
    parser.add_argument("--only", help="Only process matching company/role")
    parser.add_argument("--dry-run", action="store_true", help="Fill forms but don't submit")
    parser.add_argument("--headless", action="store_true", help="Run headless (no visible browser)")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Parallel contexts (default 1, use 3+ for headless)",
    )
    parser.add_argument(
        "--test-url", help="Test form filling on a single URL (no submit, no YAML needed)"
    )
    parser.add_argument("yaml_file", nargs="?", default="batch-apply-2026-03-27.yaml")
    args = parser.parse_args()

    # --test-url mode: open one URL, fill, screenshot, exit (no submission)
    if args.test_url:
        await _run_test_url(args.test_url, headless=args.headless)
        return

    config = yaml.safe_load((PROJECT_ROOT / args.yaml_file).read_text())
    applications = config["applications"]

    # Filter
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

    applications = [a for a in applications if a.get("status") == "pending"]

    automatable = [a for a in applications if detect_platform(a["url"]) in FILLERS]
    manual = [a for a in applications if detect_platform(a["url"]) not in FILLERS]

    print(f"Total: {len(applications)} pending")
    print(f"  Automatable (Lever/Greenhouse/Ashby): {len(automatable)}")
    print(f"  Manual (LinkedIn/other): {len(manual)}")

    if manual:
        print("\n  Manual apply needed:")
        for a in manual:
            print(f"    {a.get('slug', a['company'])} - {a['role']} ({detect_platform(a['url'])})")

    if not automatable:
        print("\nNo automatable applications to process.")
        return

    print(f"\nLaunching browser ({'headless' if args.headless else 'visible'})...")

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless)

        results = []
        yaml_path = PROJECT_ROOT / args.yaml_file

        def save_status(slug: str, new_status: str):
            """Persist status back to YAML and DB immediately."""
            cfg = yaml.safe_load(yaml_path.read_text())
            db_id = None
            for a in cfg["applications"]:
                if a.get("slug") == slug:
                    a["status"] = new_status
                    db_id = a.get("db_id")
                    break
            yaml_path.write_text(
                yaml.dump(cfg, default_flow_style=False, allow_unicode=True, sort_keys=False)
            )

            # Update pipeline DB
            if db_id and new_status == "submitted":
                try:
                    db_path = PROJECT_ROOT / "data" / "career_os.db"
                    conn = sqlite3.connect(str(db_path))
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE applications SET status = 'applied', date_applied = ? WHERE id = ?",
                        (date.today().isoformat(), db_id),
                    )
                    conn.commit()
                    conn.close()
                    print(f"    DB updated: application #{db_id} -> applied")
                except Exception as e:
                    print(f"    DB update failed: {e}")

        # Process in batches
        for i in range(0, len(automatable), args.batch_size):
            batch = automatable[i : i + args.batch_size]
            tasks = [
                process_application(browser, app, i + j + 1, len(automatable), args.dry_run)
                for j, app in enumerate(batch)
            ]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            # Persist status after each batch
            for r in batch_results:
                if r.get("status") and r["status"] != "dry-run":
                    save_status(r["slug"], r["status"])
                    print(f"  [{r['slug']}] status saved: {r['status']}")

        await browser.close()

    # Summary
    submitted = [r for r in results if r["status"] == "submitted"]
    errors = [r for r in results if r["status"] == "error"]
    skipped = [r for r in results if r["status"] == "skipped"]

    print(f"\n{'=' * 60}")
    print(f"DONE: {len(submitted)} submitted, {len(errors)} errors, {len(skipped)} skipped")
    if errors:
        print("\nErrors:")
        for r in errors:
            print(f"  {r['slug']}: {r.get('error', '?')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
