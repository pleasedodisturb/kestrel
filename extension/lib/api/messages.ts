/**
 * Typed contract for the extension's `chrome.runtime` message API and the
 * backend wire shapes it wraps. This is the single source of truth imported by
 * the popup (00-02) and the options page (00-03) — define everything here so
 * downstream entrypoints need no exploration.
 */

/** The four connection states the background worker can report. */
export type HealthState = "connected" | "unpaired" | "backend-down" | "bad-key";

/** Non-sensitive identity of the paired Kestrel instance. */
export interface InstanceInfo {
  name: string;
  version: string;
}

/**
 * Normalized job payload the extension captures and forwards to the backend.
 * Mirrors the backend `CaptureRequest` schema (Phase 0 stub target).
 */
export interface CapturePayload {
  url: string;
  title: string;
  company: string;
  description: string;
  location?: string | null;
  salary?: string | null;
  source?: string | null;
  /** Sent when structured extraction failed → backend LLM-parses it (01-02). */
  raw_text?: string | null;
}

/** Discriminated union of every message the background worker accepts. */
export type ExtMessage =
  | { type: "PAIR"; pairingCode: string }
  | { type: "HEALTH" }
  | { type: "CAPTURE"; payload: CapturePayload }
  | { type: "PROMOTE"; discoveredJobId: number }
  | { type: "STATUS" };

export interface PairResponse {
  ok: boolean;
  token?: string;
  instance?: InstanceInfo;
  error?: string;
}

export interface HealthResponse {
  ok: boolean;
  state: HealthState;
}

export interface CaptureResponse {
  ok: boolean;
  jobId?: string;
  error?: string;
  /** Score fields from the 01-02 backend; consumed by the 01-04 panel surface. */
  discoveredJobId?: number;
  fitScore?: number;
  letterGrade?: string;
  scoreBreakdown?: unknown[];
  gap?: string;
}

export interface StatusResponse {
  ok: boolean;
  instance?: InstanceInfo;
  error?: string;
}

/**
 * Result of promoting a captured job to the pipeline via
 * `POST /api/extension/promote` (from 01-02). Idempotent — a repeat promote of
 * the same job returns the same `applicationId`.
 */
export interface PromoteResponse {
  ok: boolean;
  applicationId?: number;
  status?: string;
  error?: string;
}

/** Discriminated union of every response the background worker returns. */
export type ExtResponse =
  | PairResponse
  | HealthResponse
  | CaptureResponse
  | PromoteResponse
  | StatusResponse;
