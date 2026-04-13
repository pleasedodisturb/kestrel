/**
 * React Query hooks for follow-ups.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createFollowUp,
  completeFollowUp,
  fetchFollowUps,
  fetchOverdueCount,
} from "@/api/followUps";
import type { FollowUpCreate } from "@/api/types";

const FOLLOW_UPS_KEY = ["follow-ups"] as const;
const OVERDUE_COUNT_KEY = ["follow-ups", "overdue-count"] as const;

/**
 * Fetch all follow-ups, optionally overdue only.
 */
export function useFollowUps(params?: { overdue?: boolean }) {
  return useQuery({
    queryKey: [...FOLLOW_UPS_KEY, params],
    queryFn: () => fetchFollowUps(params),
  });
}

/**
 * Fetch the count of overdue follow-ups.
 */
export function useOverdueCount() {
  return useQuery({
    queryKey: OVERDUE_COUNT_KEY,
    queryFn: fetchOverdueCount,
    refetchInterval: 60_000, // Refresh every minute
  });
}

/**
 * Create a new follow-up.
 */
export function useCreateFollowUp() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Omit<FollowUpCreate, "profile_id">) =>
      createFollowUp(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: FOLLOW_UPS_KEY });
      queryClient.invalidateQueries({ queryKey: OVERDUE_COUNT_KEY });
      // Also refresh application detail since follow_ups are embedded
      queryClient.invalidateQueries({ queryKey: ["application"] });
    },
  });
}

/**
 * Complete a follow-up.
 */
export function useCompleteFollowUp() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => completeFollowUp(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: FOLLOW_UPS_KEY });
      queryClient.invalidateQueries({ queryKey: OVERDUE_COUNT_KEY });
      queryClient.invalidateQueries({ queryKey: ["application"] });
    },
  });
}
