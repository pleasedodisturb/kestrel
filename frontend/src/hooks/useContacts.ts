/**
 * React Query hooks for the Networking CRM (M6).
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchContacts,
  fetchContactDetail,
  createContact,
  updateContact,
  archiveContact,
  logInteraction,
  linkContactToApplication,
} from "@/api/contacts";
import type { ContactCreate, ContactUpdate } from "@/api/types";

const CONTACTS_KEY = ["contacts"] as const;

export function useContacts(params?: {
  company?: string;
  relationship_type?: string;
  warmth?: string;
  needs_follow_up?: boolean;
  search?: string;
}) {
  return useQuery({
    queryKey: [...CONTACTS_KEY, params],
    queryFn: () => fetchContacts(params),
  });
}

export function useContactDetail(id: number) {
  return useQuery({
    queryKey: ["contact", id],
    queryFn: () => fetchContactDetail(id),
    enabled: id > 0,
  });
}

export function useCreateContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ContactCreate) => createContact(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: CONTACTS_KEY });
    },
  });
}

export function useUpdateContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ContactUpdate }) =>
      updateContact(id, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: CONTACTS_KEY });
      void queryClient.invalidateQueries({
        queryKey: ["contact", variables.id],
      });
    },
  });
}

export function useArchiveContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => archiveContact(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: CONTACTS_KEY });
    },
  });
}

export function useLogInteraction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      contactId,
      data,
    }: {
      contactId: number;
      data: {
        interaction_type: string;
        direction: string;
        subject?: string;
        notes?: string;
      };
    }) => logInteraction(contactId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: CONTACTS_KEY });
      void queryClient.invalidateQueries({
        queryKey: ["contact", variables.contactId],
      });
    },
  });
}

export function useLinkContactToApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      contactId,
      data,
    }: {
      contactId: number;
      data: { application_id: number; role: string; notes?: string };
    }) => linkContactToApplication(contactId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: CONTACTS_KEY });
      void queryClient.invalidateQueries({ queryKey: ["applications"] });
    },
  });
}
