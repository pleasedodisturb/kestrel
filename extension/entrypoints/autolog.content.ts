import { defineContentScript } from "#imports";
import type { ExtMessage } from "@/lib/api/messages";
import { getLastDiscoveredJobId } from "@/lib/storage";

/**
 * Auto-log-on-submit for recognized ATSes (Greenhouse / Lever / Ashby). When the
 * user submits an application, this script shows a VISIBLE, DISMISSIBLE banner
 * ("Log this application to Kestrel?") and only writes to the pipeline if the
 * user clicks Log. There is NO silent path — silent auto-logging (Simplify's
 * anti-pattern, threat T-01D-01) is exactly what we refuse to do.
 *
 * SCOPE GUARD: this NEVER fills a form, submits a form, or reads field values.
 * It reads submit/confirmation SIGNALS only (T-01D-03) and, on the user's
 * confirmation, promotes the previously-captured job through the background
 * worker — that is all "logging" means here.
 */

export type AtsId = "greenhouse" | "lever" | "ashby";

export interface DetectionContext {
  readonly host: string;
  readonly url: string;
  readonly doc: Document;
}

const BANNER_ID = "kestrel-autolog-banner";

/** Which ATS (if any) a host belongs to. */
function atsForHost(host: string): AtsId | null {
  const h = host.toLowerCase();
  if (h === "boards.greenhouse.io" || h.endsWith(".greenhouse.io") || h === "greenhouse.io") {
    return "greenhouse";
  }
  if (h === "jobs.lever.co" || h.endsWith(".lever.co") || h === "lever.co") {
    return "lever";
  }
  if (h === "jobs.ashbyhq.com" || h.endsWith(".ashbyhq.com") || h === "ashbyhq.com") {
    return "ashby";
  }
  return null;
}

/** Lowercased body text, defensively (no throw on a detached document). */
function bodyText(doc: Document): string {
  return (doc.body?.textContent ?? "").toLowerCase();
}

/** Per-ATS post-submit confirmation signal. */
function isConfirmed(ats: AtsId, ctx: DetectionContext): boolean {
  const url = ctx.url.toLowerCase();
  const text = bodyText(ctx.doc);
  switch (ats) {
    case "greenhouse":
      return (
        url.includes("/confirmation") ||
        ctx.doc.querySelector("#application_confirmation") !== null ||
        text.includes("thank you for applying") ||
        text.includes("your application has been submitted")
      );
    case "lever":
      return (
        /\/(apply\/)?thanks\b/.test(url) ||
        ctx.doc.querySelector("[data-qa='thanks'], .application-confirmation") !== null ||
        text.includes("thank you for applying") ||
        text.includes("application submitted")
      );
    case "ashby":
      return (
        url.includes("/application/success") ||
        ctx.doc.querySelector(
          "[data-testid='application-submitted'], .ashby-application-form-success",
        ) !== null ||
        text.includes("application submitted") ||
        text.includes("thanks for applying")
      );
  }
}

/**
 * PURE detection: returns the ATS whose application-submit confirmation is
 * present on the current page, or `null`. Never fires on an unrelated host or a
 * pre-submit application form (no confirmation signal yet).
 */
export function detectApplicationSubmit(ctx: DetectionContext): AtsId | null {
  const ats = atsForHost(ctx.host);
  if (!ats) {
    return null;
  }
  return isConfirmed(ats, ctx) ? ats : null;
}

/** The runtime message an auto-log confirmation sends (promote the captured job). */
export function buildAutologMessage(discoveredJobId: number): ExtMessage {
  return { type: "PROMOTE", discoveredJobId };
}

export interface BannerHandle {
  readonly host: HTMLElement;
  readonly remove: () => void;
}

export interface BannerOptions {
  readonly onLog: () => void;
  readonly onDismiss?: () => void;
}

/**
 * Inject the dismissible confirmation banner into a shadow root (so host-page CSS
 * cannot bleed in and page content cannot inject markup — T-01D-04: static text
 * only, never page-derived innerHTML). Returns a handle to remove it. Log and
 * Dismiss both remove the banner; only Log invokes `onLog`.
 */
export function showConfirmationBanner(options: BannerOptions): BannerHandle {
  const existing = document.getElementById(BANNER_ID);
  if (existing) {
    existing.remove();
  }

  const host = document.createElement("div");
  host.id = BANNER_ID;
  Object.assign(host.style, {
    position: "fixed",
    bottom: "20px",
    left: "20px",
    zIndex: "2147483647",
  });
  const shadow = host.attachShadow({ mode: "open" });

  const card = document.createElement("div");
  card.style.cssText =
    "font: 500 13px system-ui, sans-serif; color: #111; background: #fff;" +
    "border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px 14px;" +
    "box-shadow: 0 4px 16px rgba(0,0,0,.18); display: flex; gap: 10px; align-items: center;";

  const label = document.createElement("span");
  label.textContent = "Log this application to Kestrel?";

  const logBtn = document.createElement("button");
  logBtn.type = "button";
  logBtn.textContent = "Log";
  logBtn.setAttribute("data-action", "log");
  logBtn.style.cssText =
    "font: 600 13px system-ui; padding: 6px 12px; border: 0; border-radius: 7px;" +
    "background: #1f2937; color: #fff; cursor: pointer;";

  const dismissBtn = document.createElement("button");
  dismissBtn.type = "button";
  dismissBtn.textContent = "Dismiss";
  dismissBtn.setAttribute("data-action", "dismiss");
  dismissBtn.style.cssText =
    "font: 600 13px system-ui; padding: 6px 12px; border: 1px solid #d1d5db;" +
    "border-radius: 7px; background: #fff; color: #374151; cursor: pointer;";

  const handle: BannerHandle = {
    host,
    remove: () => host.remove(),
  };

  logBtn.addEventListener("click", () => {
    options.onLog();
    handle.remove();
  });
  dismissBtn.addEventListener("click", () => {
    options.onDismiss?.();
    handle.remove();
  });

  card.append(label, logBtn, dismissBtn);
  shadow.appendChild(card);
  document.body.appendChild(host);
  return handle;
}

/**
 * On the user's Log confirmation: promote the previously-captured job through the
 * worker. If nothing was captured (no discoveredJobId in session), there is
 * nothing to promote — we do nothing rather than guess (auto-log only LOGS a job
 * the user already captured; it never creates from scraped form data).
 */
export async function logApplication(): Promise<void> {
  const discoveredJobId = await getLastDiscoveredJobId();
  if (typeof discoveredJobId !== "number") {
    return;
  }
  await chrome.runtime.sendMessage(buildAutologMessage(discoveredJobId));
}

export default defineContentScript({
  // Explicit ATS application-host allowlist — NEVER a wildcard or broad-host
  // match. This script runs only on recognized ATS pages to watch for a submit.
  matches: [
    "*://boards.greenhouse.io/*",
    "*://*.greenhouse.io/*",
    "*://jobs.lever.co/*",
    "*://*.ashbyhq.com/*",
  ],
  main() {
    let bannerShown = false;

    const ctx = (): DetectionContext => ({
      host: location.hostname,
      url: location.href,
      doc: document,
    });

    const maybeConfirm = (): void => {
      if (bannerShown || !document.body) {
        return;
      }
      if (detectApplicationSubmit(ctx()) === null) {
        return;
      }
      bannerShown = true;
      observer.disconnect();
      showConfirmationBanner({
        onLog: () => void logApplication(),
        onDismiss: () => {
          bannerShown = false;
        },
      });
    };

    // 1) A full-navigation confirmation page (Greenhouse/Lever) is caught on load.
    maybeConfirm();

    // 2) An in-page/AJAX submit (Ashby SPA, Lever): re-check shortly after submit.
    document.addEventListener(
      "submit",
      () => {
        setTimeout(maybeConfirm, 800);
      },
      true,
    );

    // 3) SPA success states that swap DOM without navigation: observe until shown.
    const observer = new MutationObserver(() => maybeConfirm());
    observer.observe(document.documentElement, { childList: true, subtree: true });
  },
});
