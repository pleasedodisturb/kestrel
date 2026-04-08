/**
 * API client for STAR Stories.
 */

import type {
  StarStory,
  StarStoryListResponse,
  StarStoryCreate,
  StarStoryUpdate,
  RecommendedStoriesResponse,
  StoryGapsResponse,
} from "./types";

const API_BASE = "/api";

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export async function fetchStarStories(
  profileId: number,
): Promise<StarStoryListResponse> {
  const res = await fetch(
    `${API_BASE}/star-stories?profile_id=${profileId}`,
  );
  if (!res.ok) throw new Error(`Failed to fetch stories: ${res.statusText}`);
  return res.json();
}

export async function fetchStarStory(
  storyId: number,
  profileId: number,
): Promise<StarStory> {
  const res = await fetch(
    `${API_BASE}/star-stories/${storyId}?profile_id=${profileId}`,
  );
  if (!res.ok) throw new Error(`Failed to fetch story: ${res.statusText}`);
  return res.json();
}

export async function createStarStory(
  profileId: number,
  data: StarStoryCreate,
): Promise<StarStory> {
  const res = await fetch(
    `${API_BASE}/star-stories?profile_id=${profileId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) throw new Error(`Failed to create story: ${res.statusText}`);
  return res.json();
}

export async function updateStarStory(
  storyId: number,
  profileId: number,
  data: StarStoryUpdate,
): Promise<StarStory> {
  const res = await fetch(
    `${API_BASE}/star-stories/${storyId}?profile_id=${profileId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) throw new Error(`Failed to update story: ${res.statusText}`);
  return res.json();
}

export async function deleteStarStory(
  storyId: number,
  profileId: number,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/star-stories/${storyId}?profile_id=${profileId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Failed to delete story: ${res.statusText}`);
}

// ---------------------------------------------------------------------------
// Application-scoped
// ---------------------------------------------------------------------------

export async function fetchRecommendedStories(
  applicationId: number,
  profileId: number,
): Promise<RecommendedStoriesResponse> {
  const res = await fetch(
    `${API_BASE}/applications/${applicationId}/recommended-stories?profile_id=${profileId}`,
  );
  if (!res.ok)
    throw new Error(`Failed to fetch recommended stories: ${res.statusText}`);
  return res.json();
}

export async function fetchStoryGaps(
  applicationId: number,
  profileId: number,
): Promise<StoryGapsResponse> {
  const res = await fetch(
    `${API_BASE}/applications/${applicationId}/story-gaps?profile_id=${profileId}`,
  );
  if (!res.ok)
    throw new Error(`Failed to fetch story gaps: ${res.statusText}`);
  return res.json();
}
