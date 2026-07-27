/**
 * Shared shape produced by the tiered job extractor. `confidence` tells the
 * caller whether the fields are structured (JSON-LD / OpenGraph) or a raw-text
 * fallback that the backend must LLM-parse.
 */
export interface ExtractedJob {
  company: string;
  title: string;
  description: string;
  location: string | null;
  salary: string | null;
  url: string;
  source: string | null;
  confidence: "structured" | "raw";
}

/** Fields a structured tier can contribute; merged into a full ExtractedJob. */
export type PartialJob = Partial<
  Pick<ExtractedJob, "company" | "title" | "description" | "location" | "salary">
>;

/** Max characters of raw page text sent to the backend (mirrors extension_max_jd_chars=30000). */
export const RAW_TEXT_CAP = 30000;
