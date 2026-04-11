/**
 * CreditsExhaustedBanner — surfaces OpenRouter 402/429 failures to the user.
 *
 * The banner reads from sessionStorage flags set by the API clients
 * (scoring.ts / aiHealth.ts). It's mounted on Kanban, Discovery, and the
 * AI Health dashboard so the user sees it wherever scoring might fail.
 *
 * Issue: #28
 */

import { useEffect, useState } from "react";
import { XCircle, X } from "lucide-react";

const FLAG_KEY = "credits_exhausted";
const DISMISS_KEY = "credits_exhausted_dismissed";

export function CreditsExhaustedBanner() {
  const [exhausted, setExhausted] = useState(
    () => sessionStorage.getItem(FLAG_KEY) === "true",
  );
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISS_KEY) === "true",
  );

  // Re-read sessionStorage when the window regains focus — the flag may
  // have been set by a scoring call in a different tab.
  useEffect(() => {
    const refresh = () => {
      setExhausted(sessionStorage.getItem(FLAG_KEY) === "true");
      setDismissed(sessionStorage.getItem(DISMISS_KEY) === "true");
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, []);

  if (!exhausted || dismissed) return null;

  const handleDismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, "true");
    setDismissed(true);
  };

  return (
    <div
      data-testid="credits-exhausted-banner"
      className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3"
    >
      <XCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
      <div className="flex-1">
        <p className="text-sm font-medium text-red-800">
          AI scoring stopped — add credits at openrouter.ai
        </p>
        <p className="mt-0.5 text-xs text-red-700">
          OpenRouter returned a credits/rate-limit error. Top up at{" "}
          <a
            data-testid="credits-exhausted-link"
            href="https://openrouter.ai"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            openrouter.ai
          </a>{" "}
          to resume scoring.
        </p>
      </div>
      <button
        data-testid="credits-exhausted-dismiss"
        onClick={handleDismiss}
        aria-label="Dismiss credits exhausted banner"
        className="flex-shrink-0 rounded p-1 text-red-700 hover:bg-red-100 hover:text-red-900"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
