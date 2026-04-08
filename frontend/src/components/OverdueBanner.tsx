/**
 * OverdueBanner — shows a banner when there are overdue follow-ups.
 * Displayed at the top of the pipeline page / dashboard.
 */

import { useOverdueCount } from "@/hooks/useFollowUps";
import { AlertTriangle } from "lucide-react";

export function OverdueBanner() {
  const { data, isLoading } = useOverdueCount();

  if (isLoading || !data || data.count === 0) {
    return null;
  }

  return (
    <div
      data-testid="overdue-banner"
      className="mb-4 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3"
    >
      <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber-600" />
      <div className="flex-1">
        <p className="text-sm font-medium text-amber-800">
          You have{" "}
          <span data-testid="overdue-count" className="font-bold">
            {data.count}
          </span>{" "}
          overdue follow-up{data.count !== 1 ? "s" : ""}
        </p>
        <p className="text-xs text-amber-600">
          Check your follow-ups and take action to keep your pipeline moving.
        </p>
      </div>
    </div>
  );
}
