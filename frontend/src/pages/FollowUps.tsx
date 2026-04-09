/**
 * FollowUps — global follow-ups list page.
 *
 * Shows all due/overdue/upcoming follow-ups across applications, linked to
 * their applications. Accessible from the nav bar.
 */

import { useCallback } from "react";
import { Link } from "react-router-dom";
import { useFollowUps, useCompleteFollowUp } from "@/hooks/useFollowUps";
import {
  Bell,
  Check,
  Clock,
  AlertTriangle,
  ExternalLink,
  CalendarClock,
} from "lucide-react";
import { cn } from "@/lib/utils";

function formatDate(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function getDaysUntilDue(dueDateStr: string): number {
  const now = new Date();
  const dueDate = new Date(dueDateStr);
  // Reset to start of day for accurate day diff
  now.setHours(0, 0, 0, 0);
  dueDate.setHours(0, 0, 0, 0);
  return Math.floor((dueDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

function getBorderColor(daysDiff: number): string {
  if (daysDiff < 0) return "border-red-200";
  if (daysDiff === 0) return "border-amber-200";
  return "border-gray-200";
}

function getStatusInfo(daysDiff: number): {
  label: string;
  className: string;
  icon: typeof AlertTriangle;
} {
  if (daysDiff < 0) {
    return {
      label: `${Math.abs(daysDiff)}d overdue`,
      className: "bg-red-100 text-red-700",
      icon: AlertTriangle,
    };
  }
  if (daysDiff === 0) {
    return {
      label: "Due today",
      className: "bg-amber-100 text-amber-700",
      icon: AlertTriangle,
    };
  }
  return {
    label: `In ${daysDiff}d`,
    className: "bg-green-100 text-green-700",
    icon: CalendarClock,
  };
}

export function FollowUps() {
  const { data, isLoading, error } = useFollowUps();
  const completeMutation = useCompleteFollowUp();

  const handleComplete = useCallback(
    (id: number) => {
      completeMutation.mutate(id);
    },
    [completeMutation],
  );

  if (isLoading) {
    return (
      <div
        data-testid="follow-ups-loading"
        className="flex items-center justify-center py-20"
      >
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="follow-ups-error" className="py-20 text-center">
        <p className="text-lg font-medium text-red-700">
          {error instanceof Error ? error.message : String(error)}
        </p>
      </div>
    );
  }

  // Filter out completed follow-ups and sort: overdue first, then due today, then upcoming
  const pendingFollowUps = (data?.follow_ups ?? [])
    .filter((fu) => !fu.completed_at)
    .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());

  const overdueCount = pendingFollowUps.filter(
    (fu) => getDaysUntilDue(fu.due_date) < 0,
  ).length;
  const dueTodayCount = pendingFollowUps.filter(
    (fu) => getDaysUntilDue(fu.due_date) === 0,
  ).length;
  const upcomingCount = pendingFollowUps.filter(
    (fu) => getDaysUntilDue(fu.due_date) > 0,
  ).length;

  return (
    <section data-testid="follow-ups-page" className="space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bell className="h-6 w-6 text-gray-700" />
          <h1 className="text-2xl font-bold text-gray-900">Follow-Ups</h1>
        </div>
      </header>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-700">Overdue</p>
          <p data-testid="overdue-count" className="text-2xl font-bold text-red-900">
            {overdueCount}
          </p>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-700">Due Today</p>
          <p data-testid="due-today-count" className="text-2xl font-bold text-amber-900">
            {dueTodayCount}
          </p>
        </div>
        <div className="rounded-lg border border-green-200 bg-green-50 p-4">
          <p className="text-sm font-medium text-green-700">Upcoming</p>
          <p data-testid="upcoming-count" className="text-2xl font-bold text-green-900">
            {upcomingCount}
          </p>
        </div>
      </div>

      {/* Follow-ups list */}
      {pendingFollowUps.length === 0 ? (
        <div
          data-testid="follow-ups-empty"
          className="rounded-lg border border-gray-200 bg-white py-16 text-center"
        >
          <Bell className="mx-auto h-12 w-12 text-gray-300" />
          <p className="mt-4 text-lg font-medium text-gray-600">
            No pending follow-ups
          </p>
          <p className="mt-1 text-sm text-gray-400">
            Create follow-ups from application detail pages to track them here.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {pendingFollowUps.map((fu) => {
            const daysDiff = getDaysUntilDue(fu.due_date);
            const statusInfo = getStatusInfo(daysDiff);
            const StatusIcon = statusInfo.icon;

            return (
              <div
                key={fu.id}
                data-testid={`follow-up-row-${fu.id}`}
                className={cn(
                  "flex items-center gap-4 rounded-lg border bg-white px-4 py-3 shadow-sm transition-colors",
                  getBorderColor(daysDiff),
                )}
              >
                {/* Complete button */}
                <button
                  data-testid={`complete-follow-up-${fu.id}`}
                  onClick={() => handleComplete(fu.id)}
                  disabled={completeMutation.isPending}
                  className={cn(
                    "flex-shrink-0 rounded-full border p-1.5",
                    daysDiff < 0
                      ? "border-red-300 text-red-500 hover:bg-red-100"
                      : "border-gray-300 text-gray-400 hover:bg-gray-100",
                  )}
                >
                  <Check className="h-4 w-4" />
                </button>

                {/* Main content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium capitalize text-gray-800">
                      {fu.follow_up_type}
                    </span>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                        statusInfo.className,
                      )}
                    >
                      <StatusIcon className="h-3 w-3" />
                      {statusInfo.label}
                    </span>
                  </div>
                  {fu.notes && (
                    <p className="mt-0.5 text-sm text-gray-600 truncate">
                      {fu.notes}
                    </p>
                  )}
                  <div className="mt-1 flex items-center gap-1 text-xs text-gray-400">
                    <Clock className="h-3 w-3" />
                    Due {formatDate(fu.due_date)}
                  </div>
                </div>

                {/* Application link */}
                {fu.application_company && (
                  <Link
                    to={`/applications/${fu.application_id}`}
                    data-testid={`follow-up-app-link-${fu.id}`}
                    className="flex items-center gap-1.5 rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 flex-shrink-0"
                  >
                    <span className="truncate max-w-[150px]">
                      {fu.application_company}
                      {fu.application_role ? ` — ${fu.application_role}` : ""}
                    </span>
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
