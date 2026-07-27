import { defineContentScript } from "#imports";
import type { CapturePayload, CaptureResponse } from "@/lib/api/messages";
import { extractJob } from "@/lib/extraction";

/**
 * Content script for "the eye": on a recognized job posting it injects a single
 * floating "Capture to Kestrel" button (in a shadow root, so host-page CSS can't
 * bleed in and page CSS can't restyle ours). On click — or on a CAPTURE_ACTIVE_TAB
 * request from the popup — it runs the tiered extractor and hands the payload to
 * the background worker (the ONLY backend caller). This script NEVER fetches the
 * backend and NEVER auto-fires: capture is strictly user-action-only.
 *
 * The score-bearing response is re-dispatched as a `kestrel:capture-result`
 * DOM CustomEvent so the 01-04 panel surface can render it in either an overlay
 * or the side panel without coupling to this script.
 */

const HOST_ID = "kestrel-capture-host";
const RESULT_EVENT = "kestrel:capture-result";
const ACTIVE_TAB_MESSAGE = "CAPTURE_ACTIVE_TAB";

/** Build the wire payload from the current page via tiered extraction. */
function buildPayload(): CapturePayload {
  const job = extractJob(document);
  return {
    url: job.url,
    title: job.title,
    company: job.company,
    description: job.description,
    location: job.location,
    salary: job.salary,
    source: job.source,
    // Raw tier: send the page text so the backend LLM parses it (01-02).
    raw_text: job.confidence === "raw" ? job.description : null,
  };
}

/** Extract → send CAPTURE through the worker → broadcast the result. */
async function sendCapture(): Promise<CaptureResponse> {
  let res: CaptureResponse;
  try {
    res = (await chrome.runtime.sendMessage({
      type: "CAPTURE",
      payload: buildPayload(),
    })) as CaptureResponse;
  } catch {
    res = { ok: false, error: "worker-unavailable" };
  }
  document.dispatchEvent(new CustomEvent(RESULT_EVENT, { detail: res }));
  return res;
}

/** Compact acknowledgement label for the floating button (01-04 owns the panel). */
function labelFor(res: CaptureResponse): string {
  if (!res.ok) {
    return "Capture failed — retry";
  }
  if (res.fitScore != null && res.letterGrade) {
    return `Scored ✓ ${res.letterGrade} · ${res.fitScore}`;
  }
  return "Captured ✓";
}

/** Inject the floating trigger button once, isolated inside a shadow root. */
function mountButton(): void {
  if (document.getElementById(HOST_ID) || !document.body) {
    return;
  }
  const host = document.createElement("div");
  host.id = HOST_ID;
  Object.assign(host.style, {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    zIndex: "2147483647",
  });
  const shadow = host.attachShadow({ mode: "open" });

  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "Capture to Kestrel";
  btn.style.cssText =
    "font: 600 13px system-ui, sans-serif; padding: 10px 14px; border: 0;" +
    "border-radius: 8px; background: #1f2937; color: #fff; cursor: pointer;" +
    "box-shadow: 0 2px 8px rgba(0,0,0,.25);";
  btn.addEventListener("click", () => {
    btn.disabled = true;
    btn.textContent = "Capturing…";
    void sendCapture().then((res) => {
      btn.textContent = labelFor(res);
      btn.disabled = false;
    });
  });

  shadow.appendChild(btn);
  document.body.appendChild(host);
}

/** Narrow an unknown runtime message to the popup's capture request. */
function isActiveTabCapture(message: unknown): boolean {
  return (
    typeof message === "object" &&
    message !== null &&
    (message as { type?: unknown }).type === ACTIVE_TAB_MESSAGE
  );
}

export default defineContentScript({
  // Explicit ATS allowlist — never a wildcard or broad-host match. The content
  // script only runs on these recognized job hosts; that IS the "host in
  // allowlist" recognition signal, so the button mounts on every matched page.
  matches: [
    "*://*.linkedin.com/jobs/*",
    "*://boards.greenhouse.io/*",
    "*://*.greenhouse.io/*",
    "*://jobs.lever.co/*",
    "*://*.ashbyhq.com/*",
  ],
  main() {
    mountButton();

    // Popup path: the popup uses activeTab to ask the content script to capture
    // the tab it is viewing. Extraction stays here (single source), routed
    // through the same worker call.
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (isActiveTabCapture(message)) {
        void sendCapture().then(sendResponse);
        return true; // async response
      }
      return undefined;
    });
  },
});
