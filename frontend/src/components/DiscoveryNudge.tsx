/**
 * DiscoveryNudge — subtle prompt for users who manually track many jobs
 * but have never visited the Discovery page.
 *
 * Detection logic lives in the parent (KanbanBoard). This component only
 * renders the banner UI and owns the dismiss action.
 *
 * Dismissal persists via `localStorage.kestrel.discovery_nudge_dismissed`.
 *
 * Issue: #30
 */

import { Sparkles, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

export const NUDGE_DISMISSED_KEY = "kestrel.discovery_nudge_dismissed";

export interface DiscoveryNudgeProps {
  onDismiss: () => void;
}

export function DiscoveryNudge({ onDismiss }: Readonly<DiscoveryNudgeProps>) {
  const navigate = useNavigate();

  const handleDismiss = () => {
    localStorage.setItem(NUDGE_DISMISSED_KEY, "true");
    onDismiss();
  };

  const handleTry = () => {
    handleDismiss();
    navigate("/discovery");
  };

  return (
    <div
      data-testid="discovery-nudge"
      className="mb-4 flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3"
    >
      <Sparkles className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600" />
      <div className="flex-1">
        <p className="text-sm font-medium text-blue-900">
          Did you know Kestrel can find jobs for you automatically?
        </p>
        <p className="mt-0.5 text-xs text-blue-700">
          Discovery scans job boards and scores matches against your profile.
        </p>
        <button
          data-testid="discovery-nudge-try"
          onClick={handleTry}
          className="mt-2 inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1 text-xs font-medium text-white shadow-sm hover:bg-blue-700"
        >
          Try Discovery
        </button>
      </div>
      <button
        data-testid="discovery-nudge-dismiss"
        onClick={handleDismiss}
        aria-label="Dismiss Discovery nudge"
        className="flex-shrink-0 rounded p-1 text-blue-700 hover:bg-blue-100 hover:text-blue-900"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
