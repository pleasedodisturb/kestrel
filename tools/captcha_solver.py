"""Anti-Captcha hCaptcha solver for job application forms.

Uses anti-captcha.com API to solve hCaptcha challenges programmatically.
Cost: ~$2/1000 solves. Balance check: getBalance endpoint.

Usage:
    from captcha_solver import solve_hcaptcha
    token = await solve_hcaptcha(page)  # returns token string or None
"""

import asyncio
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

ANTICAPTCHA_KEY = os.getenv("ANTICAPTCHA_KEY", "")
if not ANTICAPTCHA_KEY:
    logger.warning("ANTICAPTCHA_KEY not set - captcha solving will not work")

API_URL = "https://api.anti-captcha.com"


async def solve_hcaptcha(page, timeout: int = 120) -> str | None:
    """Solve hCaptcha on the current page using Anti-Captcha API.

    Args:
        page: Playwright page with an hCaptcha challenge
        timeout: Max seconds to wait for solution (default 120)

    Returns:
        The captcha response token, or None if failed
    """
    # Extract hCaptcha sitekey from the page
    sitekey = await page.evaluate("""() => {
        const div = document.querySelector('div[data-sitekey], .h-captcha[data-sitekey]');
        if (div) return div.getAttribute('data-sitekey');
        // Try iframe src
        const iframe = document.querySelector('iframe[src*="hcaptcha"]');
        if (iframe) {
            const match = iframe.src.match(/sitekey=([^&]+)/);
            return match ? match[1] : null;
        }
        return null;
    }""")

    if not sitekey:
        print("    [captcha] No hCaptcha sitekey found on page")
        return None

    page_url = page.url
    print(f"    [captcha] hCaptcha detected (sitekey: {sitekey[:12]}...)")
    print(f"    [captcha] Sending to Anti-Captcha API...")

    # Create task
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{API_URL}/createTask", json={
            "clientKey": ANTICAPTCHA_KEY,
            "task": {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
            }
        })
        result = resp.json()

        if result.get("errorId", 0) != 0:
            print(f"    [captcha] API error: {result.get('errorDescription', 'unknown')}")
            return None

        task_id = result["taskId"]
        print(f"    [captcha] Task created: {task_id}. Waiting for solution...")

        # Poll for result
        start = time.time()
        while time.time() - start < timeout:
            await asyncio.sleep(5)
            resp = await client.post(f"{API_URL}/getTaskResult", json={
                "clientKey": ANTICAPTCHA_KEY,
                "taskId": task_id,
            })
            result = resp.json()

            if result.get("errorId", 0) != 0:
                print(f"    [captcha] Poll error: {result.get('errorDescription', 'unknown')}")
                return None

            status = result.get("status")
            if status == "ready":
                token = result["solution"]["gRecaptchaResponse"]
                elapsed = int(time.time() - start)
                cost = result.get("cost", "?")
                print(f"    [captcha] Solved in {elapsed}s (cost: ${cost})")
                return token

            print(f"    [captcha] Still solving... ({int(time.time() - start)}s)")

        print(f"    [captcha] Timeout after {timeout}s")
        return None


async def inject_captcha_token(page, token: str) -> bool:
    """Inject the solved captcha token into the page's hCaptcha response field.

    Args:
        page: Playwright page
        token: The captcha response token from Anti-Captcha

    Returns:
        True if injection succeeded
    """
    success = await page.evaluate("""(token) => {
        // Method 1: Set hidden textareas (standard hCaptcha response fields)
        const textareas = document.querySelectorAll(
            'textarea[name="h-captcha-response"], textarea[name="g-recaptcha-response"]'
        );
        let found = false;
        for (const ta of textareas) {
            ta.value = token;
            ta.style.display = 'block';  // make visible briefly for event dispatch
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
            ta.style.display = '';
            found = true;
        }

        // Method 2: Create the textarea if it doesn't exist (headless mode)
        if (!found) {
            const hcDiv = document.querySelector('.h-captcha, div[data-sitekey]');
            if (hcDiv) {
                const ta = document.createElement('textarea');
                ta.name = 'h-captcha-response';
                ta.value = token;
                ta.style.display = 'none';
                hcDiv.appendChild(ta);
                found = true;
            }
        }

        // Method 3: Try the hcaptcha JS API
        try {
            if (window.hcaptcha) {
                const widgetIds = window.hcaptcha.getAllResponseIDs
                    ? window.hcaptcha.getAllResponseIDs()
                    : [];
                if (widgetIds.length > 0) {
                    for (const wid of widgetIds) {
                        window.hcaptcha.setResponse(wid, token);
                    }
                    found = true;
                }
            }
        } catch (e) {}

        // Method 4: Find and set ALL hidden inputs/textareas that look captcha-related
        if (!found) {
            document.querySelectorAll('input[name*="captcha"], textarea[name*="captcha"]').forEach(el => {
                el.value = token;
                found = true;
            });
        }

        // Method 5: Trigger hCaptcha callback to validate the token
        try {
            // Find the submit callback that hCaptcha fires on success
            const forms = document.querySelectorAll('form');
            for (const form of forms) {
                // Trigger any onsubmit handlers
                const event = new Event('submit', { bubbles: true, cancelable: true });
                // Don't actually submit - just trigger the hcaptcha verification
            }

            // Try executing hcaptcha callback directly
            if (window.hcaptcha) {
                const containers = document.querySelectorAll('.h-captcha, div[data-sitekey]');
                for (const container of containers) {
                    const callback = container.getAttribute('data-callback');
                    if (callback && window[callback]) {
                        window[callback](token);
                        found = true;
                    }
                }
            }
        } catch (e) {}

        return found;
    }""", token)

    if success:
        print(f"    [captcha] Token injected into page")
    else:
        print(f"    [captcha] Failed to inject token - no response textarea found")

    return success


async def solve_and_inject(page, timeout: int = 120) -> bool:
    """Full flow: detect hCaptcha, solve it, inject the token.

    Returns True if captcha was solved and injected (or no captcha found).
    """
    # Check if there's a captcha at all
    has_captcha = await page.evaluate("""() => {
        return !!(
            document.querySelector('iframe[src*="hcaptcha"]') ||
            document.querySelector('div.h-captcha') ||
            document.querySelector('div[data-sitekey]')
        );
    }""")

    if not has_captcha:
        print("    [captcha] No captcha detected - proceeding")
        return True

    token = await solve_hcaptcha(page, timeout=timeout)
    if not token:
        return False

    return await inject_captcha_token(page, token)
