/**
 * Skills Intelligence API client.
 */

import type {
  IngestRequest,
  IngestResponse,
  Skill,
  SkillCreate,
  SkillHistoryEntry,
  SkillListResponse,
  SkillUpdate,
} from "./types";

const API_BASE = "/api/skills";

export async function fetchSkills(
  profileId: number,
  params?: {
    category?: string;
    source?: string;
    proficiency?: string;
    q?: string;
    page?: number;
    page_size?: number;
  }
): Promise<SkillListResponse> {
  const searchParams = new URLSearchParams({
    profile_id: String(profileId),
  });
  if (params?.category) searchParams.set("category", params.category);
  if (params?.source) searchParams.set("source", params.source);
  if (params?.proficiency) searchParams.set("proficiency", params.proficiency);
  if (params?.q) searchParams.set("q", params.q);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));

  const resp = await fetch(`${API_BASE}?${searchParams}`);
  if (!resp.ok) throw new Error(`Failed to fetch skills: ${resp.status}`);
  return resp.json();
}

export async function createSkill(data: SkillCreate): Promise<Skill> {
  const resp = await fetch(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error(`Failed to create skill: ${resp.status}`);
  return resp.json();
}

export async function updateSkill(
  skillId: number,
  profileId: number,
  data: SkillUpdate
): Promise<Skill> {
  const resp = await fetch(
    `${API_BASE}/${skillId}?profile_id=${profileId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!resp.ok) throw new Error(`Failed to update skill: ${resp.status}`);
  return resp.json();
}

export async function fetchSkillHistory(
  skillId: number,
  profileId: number
): Promise<SkillHistoryEntry[]> {
  const resp = await fetch(
    `${API_BASE}/${skillId}/history?profile_id=${profileId}`
  );
  if (!resp.ok) throw new Error(`Failed to fetch skill history: ${resp.status}`);
  return resp.json();
}

export async function ingestSkills(data: IngestRequest): Promise<IngestResponse> {
  const resp = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error(`Failed to ingest skills: ${resp.status}`);
  return resp.json();
}
