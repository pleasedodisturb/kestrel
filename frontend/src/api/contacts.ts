/**
 * API client functions for the Networking CRM (M6).
 */

import type {
  Contact,
  ContactCreate,
  ContactDetailResponse,
  ContactListResponse,
  ContactUpdate,
  ContactInteraction,
  ContactApplicationLink,
} from "./types";

const API_BASE = "/api/contacts";
export const DEFAULT_PROFILE_ID = 1;

export async function fetchContacts(params?: {
  company?: string;
  relationship_type?: string;
  warmth?: string;
  needs_follow_up?: boolean;
  search?: string;
}): Promise<ContactListResponse> {
  const searchParams = new URLSearchParams({
    profile_id: String(DEFAULT_PROFILE_ID),
  });
  if (params?.company) searchParams.set("company", params.company);
  if (params?.relationship_type)
    searchParams.set("relationship_type", params.relationship_type);
  if (params?.warmth) searchParams.set("warmth", params.warmth);
  if (params?.needs_follow_up)
    searchParams.set("needs_follow_up", "true");
  if (params?.search) searchParams.set("search", params.search);

  const res = await fetch(`${API_BASE}?${searchParams.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch contacts: ${res.status}`);
  return res.json() as Promise<ContactListResponse>;
}

export async function fetchContactDetail(
  id: number,
): Promise<ContactDetailResponse> {
  const res = await fetch(
    `${API_BASE}/${id}?profile_id=${DEFAULT_PROFILE_ID}`,
  );
  if (!res.ok) {
    if (res.status === 404) throw new Error("Contact not found");
    throw new Error(`Failed to fetch contact: ${res.status}`);
  }
  return res.json() as Promise<ContactDetailResponse>;
}

export async function createContact(data: ContactCreate): Promise<Contact> {
  const res = await fetch(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, profile_id: DEFAULT_PROFILE_ID }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to create contact: ${res.status}`,
    );
  }
  return res.json() as Promise<Contact>;
}

export async function updateContact(
  id: number,
  data: ContactUpdate,
): Promise<Contact> {
  const res = await fetch(
    `${API_BASE}/${id}?profile_id=${DEFAULT_PROFILE_ID}`,
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
        `Failed to update contact: ${res.status}`,
    );
  }
  return res.json() as Promise<Contact>;
}

export async function archiveContact(id: number): Promise<void> {
  const res = await fetch(
    `${API_BASE}/${id}?profile_id=${DEFAULT_PROFILE_ID}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Failed to archive contact: ${res.status}`);
}

export async function logInteraction(
  contactId: number,
  data: {
    interaction_type: string;
    direction: string;
    subject?: string;
    notes?: string;
  },
): Promise<ContactInteraction> {
  const res = await fetch(`${API_BASE}/${contactId}/interactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to log interaction: ${res.status}`);
  return res.json() as Promise<ContactInteraction>;
}

export async function linkContactToApplication(
  contactId: number,
  data: { application_id: number; role: string; notes?: string },
): Promise<ContactApplicationLink> {
  const res = await fetch(`${API_BASE}/${contactId}/applications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to link contact: ${res.status}`,
    );
  }
  return res.json() as Promise<ContactApplicationLink>;
}
