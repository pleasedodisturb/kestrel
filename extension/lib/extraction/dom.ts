/**
 * Small DOM/text helpers shared by the extraction tiers. All are defensive:
 * they never throw on missing nodes and only READ the (untrusted) page DOM —
 * page-provided strings are turned into plain text, never re-injected as HTML.
 */

/** Strip HTML tags and collapse whitespace to plain text (no innerHTML sink). */
export function stripHtml(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\s+/g, " ")
    .trim();
}

/** Read a `<meta property=... | name=...>` content attribute, or "". */
export function metaContent(doc: Document, selector: string): string {
  const el = doc.querySelector(selector);
  return el?.getAttribute("content")?.trim() ?? "";
}

/** Best-effort canonical URL for the page: location → canonical link → og:url. */
export function pageUrl(doc: Document): string {
  const href = doc.location?.href;
  if (href && /^https?:\/\//i.test(href)) {
    return href;
  }
  const canonical = doc.querySelector('link[rel="canonical"]')?.getAttribute("href");
  if (canonical) {
    return canonical;
  }
  return metaContent(doc, 'meta[property="og:url"]');
}

/** Host of a URL, or null when it cannot be parsed. */
export function hostOf(url: string): string | null {
  try {
    return new URL(url).host;
  } catch {
    return null;
  }
}
