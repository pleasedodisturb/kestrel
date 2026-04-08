/**
 * React Query hooks for profile management.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchProfiles,
  fetchProfile,
  createProfile,
  updateProfile,
  deleteProfile,
} from "@/api/profiles";
import type { ProfileCreate, ProfileUpdate } from "@/api/profiles";

const PROFILES_KEY = ["profiles"] as const;

/** Fetch all profiles. */
export function useProfiles() {
  return useQuery({
    queryKey: [...PROFILES_KEY],
    queryFn: fetchProfiles,
  });
}

/** Fetch a single profile by ID. */
export function useProfile(id: number) {
  return useQuery({
    queryKey: ["profile", id],
    queryFn: () => fetchProfile(id),
    enabled: id > 0,
  });
}

/** Create a new profile. */
export function useCreateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProfileCreate) => createProfile(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PROFILES_KEY });
    },
  });
}

/** Update a profile. */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProfileUpdate }) =>
      updateProfile(id, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: PROFILES_KEY });
      void queryClient.invalidateQueries({
        queryKey: ["profile", variables.id],
      });
    },
  });
}

/** Delete a profile. */
export function useDeleteProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteProfile(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PROFILES_KEY });
    },
  });
}
