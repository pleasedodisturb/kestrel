/**
 * OnboardingGuard -- route wrapper that redirects to /welcome if onboarding is incomplete.
 *
 * Checks GET /api/onboarding/status via React Query cache. If welcome_completed_at is null,
 * redirects to /welcome. Otherwise renders Layout with Outlet (D-09, D-11).
 * Loading state: blank white screen (no spinner per UI-SPEC).
 * Error state: fail open (let user through if API unreachable).
 */

import { Navigate } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { useOnboardingStatus } from "@/hooks/useOnboarding";

export function OnboardingGuard() {
  const { data, isLoading, isError } = useOnboardingStatus();

  // Blank screen during loading (UI-SPEC: no spinner, no text)
  if (isLoading) return null;

  // Fail open: if API is unreachable, let user through (D-09)
  if (isError) return <Layout />;

  // Redirect if welcome not completed (D-09)
  if (!data?.welcome_completed_at) {
    return <Navigate to="/welcome" replace />;
  }

  // Pass through to Layout (D-11)
  return <Layout />;
}
