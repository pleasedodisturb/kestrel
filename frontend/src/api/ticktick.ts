/**
 * API client functions for TickTick bidirectional sync.
 */

export interface TickTickSyncTask {
  id: number;
  entity_type: string;
  entity_id: number;
  ticktick_task_id: string;
  title: string;
  status: "synced" | "completed" | "error";
  last_synced_at: string | null;
  error_message: string | null;
}

export interface TickTickSyncStatus {
  total_tasks: number;
  synced: number;
  completed: number;
  errors: number;
  last_sync_at: string | null;
  tasks: TickTickSyncTask[];
}

export interface TickTickPushRequest {
  entity_type: "follow_up" | "learning_goal" | "pipeline_action";
  entity_id: number;
  profile_id: number;
}

export interface TickTickPushResponse {
  success: boolean;
  message: string;
  sync_task: TickTickSyncTask | null;
}

export interface TickTickPullResponse {
  success: boolean;
  message: string;
  synced: number;
  errors: number;
  skipped: number;
}

export interface TickTickConnectionTest {
  success: boolean;
  message: string;
  tested_at: string;
}

const API_BASE = "/api/ticktick";

/** Fetch TickTick sync status for a profile. */
export async function fetchTickTickStatus(
  profileId: number,
): Promise<TickTickSyncStatus> {
  const res = await fetch(`${API_BASE}/status?profile_id=${profileId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch TickTick status: ${res.status}`);
  }
  return res.json() as Promise<TickTickSyncStatus>;
}

/** Push an entity to TickTick. */
export async function pushToTickTick(
  data: TickTickPushRequest,
): Promise<TickTickPushResponse> {
  const res = await fetch(`${API_BASE}/push`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to push to TickTick: ${res.status}`,
    );
  }
  return res.json() as Promise<TickTickPushResponse>;
}

/** Pull completed tasks from TickTick. */
export async function pullFromTickTick(
  profileId: number,
): Promise<TickTickPullResponse> {
  const res = await fetch(`${API_BASE}/pull?profile_id=${profileId}`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to pull from TickTick: ${res.status}`,
    );
  }
  return res.json() as Promise<TickTickPullResponse>;
}

/** Test TickTick API connection. */
export async function testTickTickConnection(): Promise<TickTickConnectionTest> {
  const res = await fetch(`${API_BASE}/test`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to test TickTick connection: ${res.status}`,
    );
  }
  return res.json() as Promise<TickTickConnectionTest>;
}
