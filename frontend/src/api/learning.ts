/**
 * Learning Paths API client.
 */

import type {
  GapRecommendationsResponse,
  LearningResource,
  LearningResourceCreate,
  LearningStatusUpdate,
} from "./types";

/**
 * Fetch learning recommendations for a specific gap.
 */
export async function fetchGapRecommendations(
  gapId: number,
  profileId: number,
): Promise<GapRecommendationsResponse> {
  const params = new URLSearchParams({ profile_id: String(profileId) });
  const resp = await fetch(
    `/api/gaps/${gapId}/recommendations?${params}`,
  );
  if (!resp.ok) {
    throw new Error(`Failed to fetch recommendations: ${resp.status}`);
  }
  return resp.json();
}

/**
 * Add a learning resource (recommendation) to a gap.
 */
export async function createRecommendation(
  gapId: number,
  data: LearningResourceCreate,
): Promise<LearningResource> {
  const resp = await fetch(`/api/gaps/${gapId}/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to create recommendation: ${resp.status}`,
    );
  }
  return resp.json();
}

/**
 * Update the status of a learning resource.
 */
export async function updateLearningStatus(
  resourceId: number,
  data: LearningStatusUpdate,
): Promise<LearningResource> {
  const resp = await fetch(`/api/learning/${resourceId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to update status: ${resp.status}`,
    );
  }
  return resp.json();
}
