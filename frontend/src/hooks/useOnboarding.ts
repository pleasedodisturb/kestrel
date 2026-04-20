/**
 * React Query hooks for onboarding status.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchOnboardingStatus,
  patchOnboardingStep,
  DEFAULT_PROFILE_ID,
} from "@/api/onboarding";
import type { OnboardingStatus } from "@/api/onboarding";

const ONBOARDING_KEY = ["onboarding-status"] as const;

/** Fetch onboarding status for the default profile. */
export function useOnboardingStatus(profileId: number = DEFAULT_PROFILE_ID) {
  return useQuery<OnboardingStatus>({
    queryKey: [...ONBOARDING_KEY, profileId],
    queryFn: () => fetchOnboardingStatus(profileId),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

/** Mark an onboarding step complete and invalidate cache. */
export function usePatchOnboardingStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ profileId, step }: { profileId: number; step: string }) =>
      patchOnboardingStep(profileId, step),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [...ONBOARDING_KEY, variables.profileId],
      });
    },
  });
}
