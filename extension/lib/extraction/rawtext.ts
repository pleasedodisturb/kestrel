/**
 * Tier 3 — raw text. The last resort: hand the backend LLM the visible page
 * text (capped) so it can parse company/title/JD itself. `innerText` is
 * preferred in a real browser (respects visibility); jsdom lacks it, so we fall
 * back to `textContent`.
 */

import { RAW_TEXT_CAP } from "./types";

/** Trimmed, length-capped visible text of the page body. */
export function rawBodyText(doc: Document): string {
  const body = doc.body as (HTMLElement & { innerText?: string }) | null;
  const text = body?.innerText ?? body?.textContent ?? "";
  return text.replace(/\s+/g, " ").trim().slice(0, RAW_TEXT_CAP);
}
