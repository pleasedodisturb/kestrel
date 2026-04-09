/**
 * API client functions for AI scoring.
 */

const SCORE_API = "/api/score";

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

  if (resp.status === 402) {
    sessionStorage.setItem("credits_exhausted", "true");
    throw new Error(
      "AI scoring credits exhausted. Add credits at openrouter.ai",
    );
  }

  if (!resp.ok) throw new Error(`Batch scoring failed: ${resp.status}`);

  const data: BatchScoreResponse = await resp.json();

  if (data.credits_exhausted) {
    sessionStorage.setItem("credits_exhausted", "true");
  }

  return data;
}
