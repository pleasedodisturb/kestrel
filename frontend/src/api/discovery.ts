/**
 * API client functions for discovery search & filter.
 */

import type {
  JobSearchParams,
  JobSearchResponse,
  SavedSearch,
  SavedSearchCreate,
  SavedSearchListResponse,
} from "./types";

const JOBS_API = "/api/jobs";
const SAVED_SEARCHES_API = "/api/saved-searches";
const DISCOVERY_RUNS_API = "/api/discovery-runs";

export interface DiscoveryRunLatest {
  id: number;
  new_jobs: number;
  completed_at: string | null;
}

/**
 * Get the latest completed discovery run for a profile.
 */
export async function fetchLatestDiscoveryRun(
  profileId: number,
): Promise<DiscoveryRunLatest | null> {
  const resp = await fetch(
    `${DISCOVERY_RUNS_API}/latest?profile_id=${profileId}`,
  );
  if (!resp.ok) return null;
  const data = await resp.json();
  return data;
}

/**
 * Search, filter, sort, and paginate discovered jobs.
 */
export async function searchJobs(
  params: JobSearchParams,
): Promise<JobSearchResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("profile_id", String(params.profile_id));

  const optionalParams: [string, string | number | boolean | null | undefined][] = [
    ["q", params.q],
    ["source", params.source],
    ["remote", params.remote],
    ["salary_min", params.salary_min],
    ["salary_max", params.salary_max],
    ["score_min", params.score_min],
    ["score_max", params.score_max],
    ["date_from", params.date_from],
    ["date_to", params.date_to],
    ["company", params.company],
    ["location", params.location],
    ["sort", params.sort],
    ["order", params.order],
    ["page", params.page],
    ["page_size", params.page_size],
  ];

  for (const [key, value] of optionalParams) {
    if (value != null) searchParams.set(key, String(value));
  }

  const resp = await fetch(`${JOBS_API}?${searchParams}`);
  if (!resp.ok) throw new Error(`Failed to search jobs: ${resp.status}`);
  return resp.json();
}

/**
 * List saved searches for a profile.
 */
export async function fetchSavedSearches(
  profileId: number,
): Promise<SavedSearchListResponse> {
  const resp = await fetch(
    `${SAVED_SEARCHES_API}?profile_id=${profileId}`,
  );
  if (!resp.ok) throw new Error(`Failed to fetch saved searches: ${resp.status}`);
  return resp.json();
}

/**
 * Create a saved search.
 */
export async function createSavedSearch(
  data: SavedSearchCreate,
): Promise<SavedSearch> {
  const resp = await fetch(SAVED_SEARCHES_API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error(`Failed to create saved search: ${resp.status}`);
  return resp.json();
}

/**
 * Delete a saved search.
 */
export async function deleteSavedSearch(
  searchId: number,
  profileId: number,
): Promise<void> {
  const resp = await fetch(
    `${SAVED_SEARCHES_API}/${searchId}?profile_id=${profileId}`,
    { method: "DELETE" },
  );
  if (!resp.ok) throw new Error(`Failed to delete saved search: ${resp.status}`);
}
