/**
 * API client functions for the voice discussion mode.
 */

import { DEFAULT_PROFILE_ID } from "./applications";

const API_BASE = "/api/voice";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface VoiceMessage {
  id: number;
  session_id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface VoiceSession {
  id: number;
  profile_id: number;
  application_id: number | null;
  mode: "cover_letter" | "coaching" | "job_evaluation";
  title: string | null;
  status: "active" | "completed";
  messages: VoiceMessage[];
  created_at: string;
  updated_at: string;
}

export interface VoiceSessionListResponse {
  sessions: VoiceSession[];
  total: number;
}

export interface VoiceSendResponse {
  user_message: VoiceMessage;
  assistant_message: VoiceMessage;
  session: VoiceSession;
}

export type VoiceMode = "cover_letter" | "coaching" | "job_evaluation";

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function createVoiceSession(params: {
  mode: VoiceMode;
  application_id?: number;
  title?: string;
}): Promise<VoiceSession> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile_id: DEFAULT_PROFILE_ID,
      ...params,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to create voice session: ${res.status}`,
    );
  }
  return res.json() as Promise<VoiceSession>;
}

export async function fetchVoiceSessions(
  mode?: VoiceMode,
): Promise<VoiceSessionListResponse> {
  const params = new URLSearchParams({
    profile_id: String(DEFAULT_PROFILE_ID),
  });
  if (mode) params.set("mode", mode);

  const res = await fetch(`${API_BASE}/sessions?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch voice sessions: ${res.status}`);
  }
  return res.json() as Promise<VoiceSessionListResponse>;
}

export async function fetchVoiceSession(
  sessionId: number,
): Promise<VoiceSession> {
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}?profile_id=${DEFAULT_PROFILE_ID}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch voice session: ${res.status}`);
  }
  return res.json() as Promise<VoiceSession>;
}

export async function sendVoiceMessage(
  sessionId: number,
  content: string,
): Promise<VoiceSendResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile_id: DEFAULT_PROFILE_ID,
      content,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to send voice message: ${res.status}`,
    );
  }
  return res.json() as Promise<VoiceSendResponse>;
}

export async function completeVoiceSession(
  sessionId: number,
): Promise<VoiceSession> {
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}/complete?profile_id=${DEFAULT_PROFILE_ID}`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(`Failed to complete voice session: ${res.status}`);
  }
  return res.json() as Promise<VoiceSession>;
}
