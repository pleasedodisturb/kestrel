/**
 * API client functions for AI scoring.
 */

import type { ScoreResponseShape } from "./types";

const SCORE_API = "/api/score";

/**
 * Fetch the most recent score for an application. Returns `null` when no
 * score has been computed yet (404 from the backend).
 */
export async function getApplicationScore(
  applicationId: number,
  profileId: number,
): Promise<ScoreResponseShape | null> {
  const resp = await fetch(
    `${SCORE_API}/application/${applicationId}?profile_id=${profileId}`,
  );
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`Failed to fetch score: ${resp.status}`);
  return (await resp.json()) as ScoreResponseShape;
}


export interface BatchScoreRequest {
  profile_id: number;
  discovered_job_ids?: number[];
  rescore_stale?: boolean;
}

export interface BatchScoreResponse {
  scored_count: number;
  total_time_seconds: number;
  credits_exhausted: boolean;
  errors: Array<{ discovered_job_id: string; error: string }>;
}

/**
 * Batch score discovered jobs. Returns partial results if credits run out.
 */
export async function batchScore(
  params: BatchScoreRequest,
): Promise<BatchScoreResponse> {
  const resp = await fetch(`${SCORE_API}/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (resp.status === 402 || resp.status === 429) {
    sessionStorage.setItem("credits_exhausted", "true");
    throw new Error(
      "AI scoring stopped — add credits at openrouter.ai",
    );
  }

  if (resp.status === 422) {
    const body = await resp.json();
    sessionStorage.setItem("profile_incomplete", body.detail || "true");
    throw new Error(body.detail || "Profile incomplete for scoring");
  }

  if (!resp.ok) throw new Error(`Batch scoring failed: ${resp.status}`);

  const data: BatchScoreResponse = await resp.json();

  if (data.credits_exhausted) {
    sessionStorage.setItem("credits_exhausted", "true");
  } else {
    // A fully-successful scoring run means credits are flowing again;
    // clear the flag + any prior dismissal so the banner can resurface
    // next time scoring breaks.
    sessionStorage.removeItem("credits_exhausted");
    sessionStorage.removeItem("credits_exhausted_dismissed");
  }

  return data;
}
