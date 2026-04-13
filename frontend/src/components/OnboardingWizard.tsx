/**
 * OnboardingWizard — welcome overlay shown on the first visit to an empty
 * Kanban board. Offers three CTAs: edit profile, add first app, try Discovery.
 *
 * Dismissal persists via `localStorage.kestrel.wizard_dismissed=true`.
 * Once dismissed, the wizard never reappears.
 *
 * Issue: #20
 */

import { useNavigate } from "react-router-dom";
import { User, Plus, Sparkles, X } from "lucide-react";

export const WIZARD_DISMISSED_KEY = "kestrel.wizard_dismissed";

export interface OnboardingWizardProps {
  onClose: () => void;
  onAddApplication: () => void;
}

export function OnboardingWizard({
  onClose,
  onAddApplication,
}: Readonly<OnboardingWizardProps>) {
  const navigate = useNavigate();

  const handleDismiss = () => {
    localStorage.setItem(WIZARD_DISMISSED_KEY, "true");
    onClose();
  };

  const goProfile = () => {
    handleDismiss();
    navigate("/settings");
  };

  const goAdd = () => {
    handleDismiss();
    onAddApplication();
  };

  const goDiscovery = () => {
    handleDismiss();
    navigate("/discovery");
  };

  return (
    <div
      data-testid="onboarding-overlay"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <button
        type="button"
        className="absolute inset-0 h-full w-full cursor-default bg-black/50"
        onClick={handleDismiss}
        onKeyDown={(e) => {
          if (e.key === "Escape") handleDismiss();
        }}
        aria-label="Close onboarding"
        tabIndex={-1}
        aria-hidden="true"
      />
      <div
        data-testid="onboarding-wizard"
        className="relative w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
      >
        <div className="flex items-start justify-between">
          <div>
            <h2
              id="onboarding-title"
              className="text-lg font-semibold text-gray-900"
            >
              Welcome to Kestrel
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Here are three ways to get started:
            </p>
          </div>
          <button
            data-testid="onboarding-close"
            onClick={handleDismiss}
            aria-label="Close onboarding"
            className="flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 space-y-3">
          <button
            data-testid="onboarding-edit-profile"
            onClick={goProfile}
            className="flex w-full items-center gap-3 rounded-md border border-gray-200 bg-white px-4 py-3 text-left text-sm shadow-sm hover:border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-1"
          >
            <User className="h-5 w-5 flex-shrink-0 text-gray-500" />
            <div className="flex-1">
              <p className="font-medium text-gray-900">Set up your profile</p>
              <p className="text-xs text-gray-500">
                Tell Kestrel who you are so scoring can personalize to you.
              </p>
            </div>
          </button>

          <button
            data-testid="onboarding-add-app"
            onClick={goAdd}
            className="flex w-full items-center gap-3 rounded-md border border-gray-200 bg-white px-4 py-3 text-left text-sm shadow-sm hover:border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-1"
          >
            <Plus className="h-5 w-5 flex-shrink-0 text-gray-500" />
            <div className="flex-1">
              <p className="font-medium text-gray-900">
                Add your first application
              </p>
              <p className="text-xs text-gray-500">
                Paste a job link or enter details manually.
              </p>
            </div>
          </button>

          <button
            data-testid="onboarding-try-discovery"
            onClick={goDiscovery}
            className="flex w-full items-center gap-3 rounded-md border border-gray-200 bg-white px-4 py-3 text-left text-sm shadow-sm hover:border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-1"
          >
            <Sparkles className="h-5 w-5 flex-shrink-0 text-gray-500" />
            <div className="flex-1">
              <p className="font-medium text-gray-900">
                Let Kestrel find jobs for you
              </p>
              <p className="text-xs text-gray-500">
                Discovery automatically scans sources and scores matches.
              </p>
            </div>
          </button>
        </div>

        <button
          data-testid="onboarding-dismiss"
          onClick={handleDismiss}
          className="mt-5 w-full text-center text-xs text-gray-500 hover:text-gray-700"
        >
          Don&apos;t show this again
        </button>
      </div>
    </div>
  );
}
