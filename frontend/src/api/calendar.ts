/**
 * API client functions for Calendar Integration.
 *
 * Covers: VAL-CAL-001 through VAL-CAL-004
 */

const API_BASE = "/api/calendar";

// ---- Types ----

export interface CalendarEventCreate {
  profile_id: number;
  application_id?: number | null;
  follow_up_id?: number | null;
  event_type: "interview" | "follow_up" | "prep_reminder";
  title: string;
  description?: string | null;
  location?: string | null;
  start_time: string; // ISO 8601
  end_time: string;
  company?: string | null;
  role?: string | null;
  interview_type?: string | null;
  meeting_link?: string | null;
  prep_notes?: string | null;
  reminder_minutes_before?: number;
}

export interface CalendarEventUpdate {
  title?: string;
  description?: string;
  location?: string;
  start_time?: string;
  end_time?: string;
  interview_type?: string;
  meeting_link?: string;
  prep_notes?: string;
  reminder_minutes_before?: number;
}

export interface CalendarEventResponse {
  id: number;
  profile_id: number;
  application_id: number | null;
  follow_up_id: number | null;
  event_type: string;
  title: string;
  description: string | null;
  location: string | null;
  start_time: string;
  end_time: string;
  company: string | null;
  role: string | null;
  interview_type: string | null;
  meeting_link: string | null;
  prep_notes: string | null;
  reminder_minutes_before: number | null;
  uid: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarEventListResponse {
  events: CalendarEventResponse[];
  total: number;
}

export interface GoogleCalendarUrlResponse {
  url: string;
  event_id: number;
}

export interface FantasticalUrlResponse {
  url: string;
  event_id: number;
}

export interface CalendarProviderConfigResponse {
  event_id: number;
  providers: Record<string, string>;
}

// ---- API functions ----

/** Create a calendar event. */
export async function createCalendarEvent(
  data: CalendarEventCreate,
): Promise<CalendarEventResponse> {
  const res = await fetch(`${API_BASE}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to create calendar event: ${res.status}`,
    );
  }
  return res.json() as Promise<CalendarEventResponse>;
}

/** List calendar events for a profile. */
export async function fetchCalendarEvents(
  profileId: number,
  params?: { event_type?: string; application_id?: number },
): Promise<CalendarEventListResponse> {
  const searchParams = new URLSearchParams({
    profile_id: String(profileId),
  });
  if (params?.event_type) searchParams.set("event_type", params.event_type);
  if (params?.application_id != null)
    searchParams.set("application_id", String(params.application_id));

  const res = await fetch(`${API_BASE}/events?${searchParams.toString()}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch calendar events: ${res.status}`);
  }
  return res.json() as Promise<CalendarEventListResponse>;
}

/** Get a single calendar event. */
export async function fetchCalendarEvent(
  eventId: number,
  profileId: number,
): Promise<CalendarEventResponse> {
  const res = await fetch(
    `${API_BASE}/events/${eventId}?profile_id=${profileId}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch calendar event: ${res.status}`);
  }
  return res.json() as Promise<CalendarEventResponse>;
}

/** Update a calendar event. */
export async function updateCalendarEvent(
  eventId: number,
  profileId: number,
  data: CalendarEventUpdate,
): Promise<CalendarEventResponse> {
  const res = await fetch(
    `${API_BASE}/events/${eventId}?profile_id=${profileId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to update calendar event: ${res.status}`,
    );
  }
  return res.json() as Promise<CalendarEventResponse>;
}

/** Delete a calendar event. */
export async function deleteCalendarEvent(
  eventId: number,
  profileId: number,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/events/${eventId}?profile_id=${profileId}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(`Failed to delete calendar event: ${res.status}`);
  }
}

/** Create calendar event from follow-up. */
export async function createCalendarEventFromFollowUp(
  followUpId: number,
  profileId: number,
): Promise<CalendarEventResponse> {
  const res = await fetch(
    `${API_BASE}/events/from-follow-up/${followUpId}?profile_id=${profileId}`,
    { method: "POST" },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to create event from follow-up: ${res.status}`,
    );
  }
  return res.json() as Promise<CalendarEventResponse>;
}

/** Download .ics file for a single event. */
export function getICalExportUrl(
  eventId: number,
  profileId: number,
): string {
  return `${API_BASE}/events/${eventId}/ical?profile_id=${profileId}`;
}

/** Download .ics file for all events. */
export function getICalExportAllUrl(
  profileId: number,
  params?: { event_type?: string; application_id?: number },
): string {
  const searchParams = new URLSearchParams({
    profile_id: String(profileId),
  });
  if (params?.event_type) searchParams.set("event_type", params.event_type);
  if (params?.application_id != null)
    searchParams.set("application_id", String(params.application_id));
  return `${API_BASE}/export/ical?${searchParams.toString()}`;
}

/** Get Google Calendar URL. */
export async function fetchGoogleCalendarUrl(
  eventId: number,
  profileId: number,
): Promise<GoogleCalendarUrlResponse> {
  const res = await fetch(
    `${API_BASE}/events/${eventId}/google?profile_id=${profileId}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to get Google Calendar URL: ${res.status}`);
  }
  return res.json() as Promise<GoogleCalendarUrlResponse>;
}

/** Get Fantastical URL. */
export async function fetchFantasticalUrl(
  eventId: number,
  profileId: number,
): Promise<FantasticalUrlResponse> {
  const res = await fetch(
    `${API_BASE}/events/${eventId}/fantastical?profile_id=${profileId}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to get Fantastical URL: ${res.status}`);
  }
  return res.json() as Promise<FantasticalUrlResponse>;
}

/** Get all provider URLs for an event. */
export async function fetchEventProviders(
  eventId: number,
  profileId: number,
): Promise<CalendarProviderConfigResponse> {
  const res = await fetch(
    `${API_BASE}/events/${eventId}/providers?profile_id=${profileId}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to get calendar providers: ${res.status}`);
  }
  return res.json() as Promise<CalendarProviderConfigResponse>;
}
