/**
 * Tier 1 — JSON-LD. Parses `<script type="application/ld+json">` blocks for a
 * schema.org `JobPosting` (directly, inside an array, or inside an `@graph`).
 * Every parse is wrapped in try/catch: malformed JSON is ignored, never thrown.
 */

import { stripHtml } from "./dom";
import type { PartialJob } from "./types";

type Json = Record<string, unknown>;

function isRecord(value: unknown): value is Json {
  return typeof value === "object" && value !== null;
}

/** True if a node's `@type` is or includes "JobPosting". */
function isJobPosting(node: unknown): node is Json {
  if (!isRecord(node)) {
    return false;
  }
  const type = node["@type"];
  if (typeof type === "string") {
    return type === "JobPosting";
  }
  if (Array.isArray(type)) {
    return type.includes("JobPosting");
  }
  return false;
}

/** Flatten a parsed JSON-LD value into candidate nodes (unwrapping @graph). */
function candidates(parsed: unknown): unknown[] {
  const out: unknown[] = [];
  const visit = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (isRecord(value)) {
      out.push(value);
      if (Array.isArray(value["@graph"])) {
        (value["@graph"] as unknown[]).forEach(visit);
      }
    }
  };
  visit(parsed);
  return out;
}

/** Every JobPosting node found across all JSON-LD scripts in the document. */
function jobPostingNodes(doc: Document): Json[] {
  const nodes: Json[] = [];
  for (const script of doc.querySelectorAll('script[type="application/ld+json"]')) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(script.textContent ?? "");
    } catch {
      continue; // malformed JSON-LD → ignore, fall through to lower tiers
    }
    for (const node of candidates(parsed)) {
      if (isJobPosting(node)) {
        nodes.push(node);
      }
    }
  }
  return nodes;
}

/** True when the page carries at least one JSON-LD JobPosting. */
export function hasJobPosting(doc: Document): boolean {
  return jobPostingNodes(doc).length > 0;
}

function orgName(hiring: unknown): string {
  if (typeof hiring === "string") {
    return hiring.trim();
  }
  if (isRecord(hiring) && typeof hiring.name === "string") {
    return hiring.name.trim();
  }
  return "";
}

function locationText(jobLocation: unknown): string {
  const first = Array.isArray(jobLocation) ? jobLocation[0] : jobLocation;
  if (!isRecord(first)) {
    return "";
  }
  const address = isRecord(first.address) ? first.address : first;
  const parts = [address.addressLocality, address.addressRegion, address.addressCountry]
    .filter((p): p is string => typeof p === "string" && p.length > 0)
    .map((p) => p.trim());
  return parts.join(", ");
}

function salaryText(baseSalary: unknown): string {
  if (!isRecord(baseSalary)) {
    return "";
  }
  const currency =
    typeof baseSalary.currency === "string"
      ? baseSalary.currency
      : typeof baseSalary.salaryCurrency === "string"
        ? baseSalary.salaryCurrency
        : "";
  const value = isRecord(baseSalary.value) ? baseSalary.value : baseSalary;
  const min = value.minValue ?? value.value;
  const max = value.maxValue;
  const unit = typeof value.unitText === "string" ? value.unitText : "";
  let amount = "";
  if (min != null && max != null) {
    amount = `${min}-${max}`;
  } else if (min != null) {
    amount = `${min}`;
  }
  if (!amount) {
    return "";
  }
  return [currency, amount].filter(Boolean).join(" ") + (unit ? `/${unit}` : "");
}

/** Extract structured fields from the first JSON-LD JobPosting, or null. */
export function fromJsonLd(doc: Document): PartialJob | null {
  const node = jobPostingNodes(doc)[0];
  if (!node) {
    return null;
  }
  return {
    title: typeof node.title === "string" ? node.title.trim() : "",
    company: orgName(node.hiringOrganization),
    description: stripHtml(node.description),
    location: locationText(node.jobLocation) || null,
    salary: salaryText(node.baseSalary) || null,
  };
}
