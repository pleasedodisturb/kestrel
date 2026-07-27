/**
 * Tier 2 — OpenGraph / meta. Best-effort structured fields from `og:*` and
 * common meta tags when no JSON-LD JobPosting exists. Company is the weakest
 * signal (og:site_name is often the board, not the employer), so a page that
 * yields a title but no company is left for the raw tier to decide.
 */

import { metaContent } from "./dom";
import type { PartialJob } from "./types";

/**
 * Extract OG/meta fields. Returns null when there is no usable title signal at
 * all. `company` may be "" — the caller decides confidence from title+company.
 */
export function fromOpenGraph(doc: Document): PartialJob | null {
  const title =
    metaContent(doc, 'meta[property="og:title"]') ||
    metaContent(doc, 'meta[name="twitter:title"]');
  if (!title) {
    return null;
  }
  const description =
    metaContent(doc, 'meta[property="og:description"]') ||
    metaContent(doc, 'meta[name="description"]');
  const company =
    metaContent(doc, 'meta[property="og:site_name"]') ||
    metaContent(doc, 'meta[name="author"]');

  return { title, company, description, location: null, salary: null };
}
