/**
 * React Query hooks for the applications pipeline.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchApplications,
  fetchApplicationDetail,
  createApplication,
  updateApplication,
  archiveApplication,
} from "@/api/applications";
import type { ApplicationCreate, ApplicationUpdate } from "@/api/types";

const APPLICATIONS_KEY = ["applications"] as const;

/**
 * Fetch all applications for the pipeline board.
 * Supports optional filter/sort params.
 */
export function useApplications(params?: {
  status?: string;
  search?: string;
  sort?: string;
  order?: string;
}) {
  return useQuery({
    queryKey: [...APPLICATIONS_KEY, params],
    queryFn: () => fetchApplications(params),
  });
}

/**
 * Fetch a single application detail with activity log.
 */
export function useApplicationDetail(id: number) {
  return useQuery({
    queryKey: ["application", id],
    queryFn: () => fetchApplicationDetail(id),
    enabled: id > 0,
  });
}

/**
 * Create a new application.
 */
export function useCreateApplication() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ApplicationCreate) => createApplication(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: APPLICATIONS_KEY });
    },
  });
}

/**
 * Mutate an application (e.g. status change from drag-and-drop).
 * Uses optimistic updates for instant UI feedback on Kanban drag.
 */
export function useUpdateApplication() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApplicationUpdate }) =>
      updateApplication(id, data),
    onMutate: async (variables) => {
      // Cancel in-flight queries so they don't overwrite our optimistic update
      await queryClient.cancelQueries({ queryKey: APPLICATIONS_KEY });

      // Snapshot previous data for rollback
      const previousData = queryClient.getQueriesData({
        queryKey: APPLICATIONS_KEY,
      });

      // Optimistically update the cache
      queryClient.setQueriesData(
        { queryKey: APPLICATIONS_KEY },
        (old: { applications?: { id: number; status: string }[]; total?: number } | undefined) => {
          if (!old?.applications) return old;
          return {
            ...old,
            applications: old.applications.map((app) =>
              app.id === variables.id
                ? { ...app, ...variables.data }
                : app,
            ),
          };
        },
      );

      return { previousData };
    },
    onError: (_err, _variables, context) => {
      // Rollback on error
      if (context?.previousData) {
        for (const [queryKey, data] of context.previousData) {
          queryClient.setQueryData(queryKey, data);
        }
      }
    },
    onSettled: (_data, _error, variables) => {
      // Always refetch after mutation settles
      queryClient.invalidateQueries({ queryKey: APPLICATIONS_KEY });
      queryClient.invalidateQueries({
        queryKey: ["application", variables.id],
      });
    },
  });
}

/**
 * Archive (soft-delete) an application.
 * Invalidates both the list and the individual detail query so that
 * navigating to /applications/{id} after archive shows a 404/removed state.
 */
export function useArchiveApplication() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => archiveApplication(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: APPLICATIONS_KEY });
      queryClient.invalidateQueries({ queryKey: ["application", id] });
    },
  });
}
