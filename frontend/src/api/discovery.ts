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
  if (params.q) searchParams.set("q", params.q);
  if (params.source) searchParams.set("source", params.source);
  if (params.remote != null) searchParams.set("remote", String(params.remote));
  if (params.salary_min != null) searchParams.set("salary_min", String(params.salary_min));
  if (params.salary_max != null) searchParams.set("salary_max", String(params.salary_max));
  if (params.score_min != null) searchParams.set("score_min", String(params.score_min));
  if (params.score_max != null) searchParams.set("score_max", String(params.score_max));
  if (params.date_from) searchParams.set("date_from", params.date_from);
  if (params.date_to) searchParams.set("date_to", params.date_to);
  if (params.company) searchParams.set("company", params.company);
  if (params.location) searchParams.set("location", params.location);
  if (params.sort) searchParams.set("sort", params.sort);
  if (params.order) searchParams.set("order", params.order);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));

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
