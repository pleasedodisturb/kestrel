/**
 * Tiered job extractor. Given a page `Document`, returns an {@link ExtractedJob}
 * using the first tier that yields a usable result:
 *
 *   1. JSON-LD `JobPosting`  → structured (primary)
 *   2. OpenGraph / meta      → structured when title + company derivable
 *   3. raw visible page text → raw; the backend LLM parses it (01-02 fallback)
 *
 * Pure and defensive: it only READS the untrusted DOM, never throws on
 * malformed markup, and never re-injects page-provided strings as HTML.
 */

import { hostOf, pageUrl } from "./dom";
import { fromJsonLd, hasJobPosting } from "./jsonld";
import { fromOpenGraph } from "./opengraph";
import { rawBodyText } from "./rawtext";
import type { ExtractedJob } from "./types";

export type { ExtractedJob } from "./types";
export { hasJobPosting } from "./jsonld";

/** True when the document looks like a job posting (JSON-LD JobPosting present). */
export function isJobPage(doc: Document): boolean {
  return hasJobPosting(doc);
}

export function extractJob(doc: Document): ExtractedJob {
  const url = pageUrl(doc);
  const source = hostOf(url);
  const base = { url, source };

  // Tier 1: JSON-LD JobPosting.
  const jsonLd = fromJsonLd(doc);
  if (jsonLd && (jsonLd.title || jsonLd.company)) {
    return {
      title: jsonLd.title ?? "",
      company: jsonLd.company ?? "",
      description: jsonLd.description || rawBodyText(doc),
      location: jsonLd.location ?? null,
      salary: jsonLd.salary ?? null,
      confidence: "structured",
      ...base,
    };
  }

  // Tier 2: OpenGraph / meta — structured only when title AND company derive.
  const og = fromOpenGraph(doc);
  if (og && og.title && og.company) {
    return {
      title: og.title,
      company: og.company,
      description: og.description || rawBodyText(doc),
      location: og.location ?? null,
      salary: og.salary ?? null,
      confidence: "structured",
      ...base,
    };
  }

  // Tier 3: raw text for the backend LLM fallback.
  return {
    title: "",
    company: "",
    description: rawBodyText(doc),
    location: null,
    salary: null,
    confidence: "raw",
    ...base,
  };
}
