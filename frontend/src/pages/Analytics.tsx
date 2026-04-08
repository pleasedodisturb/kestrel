import { useQuery } from "@tanstack/react-query";
import { fetchAnalytics } from "@/api/analytics";
import type { AnalyticsData } from "@/api/analytics";
import { fetchTimeAnalytics } from "@/api/timingsapp";
import type { TimeAnalyticsData } from "@/api/timingsapp";
import { ConversionFunnel } from "@/components/analytics/ConversionFunnel";
import { ResponseRate } from "@/components/analytics/ResponseRate";
import { TimeInStage } from "@/components/analytics/TimeInStage";
import { ApplicationsOverTime } from "@/components/analytics/ApplicationsOverTime";
import { ScoreDistribution } from "@/components/analytics/ScoreDistribution";
import { TimeTracking } from "@/components/analytics/TimeTracking";
import { TimeTrackerControls } from "@/components/TimeTrackerControls";

export function Analytics() {
  const {
    data: analytics,
    isLoading,
    error,
  } = useQuery<AnalyticsData>({
    queryKey: ["analytics"],
    queryFn: fetchAnalytics,
  });

  const { data: timeAnalytics } = useQuery<TimeAnalyticsData>({
    queryKey: ["timeAnalytics"],
    queryFn: () => fetchTimeAnalytics(4),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-gray-500">Loading analytics…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-red-500">
          Failed to load analytics. Please try again.
        </p>
      </div>
    );
  }

  if (!analytics) {
    return null;
  }

  const totalApplications = analytics.conversion_funnel.reduce(
    (sum, s) => sum + s.count,
    0,
  );

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
          <p className="mt-1 text-sm text-gray-500">
            Your application pipeline analytics and insights.
          </p>
        </div>
        <TimeTrackerControls />
      </div>

      {totalApplications === 0 ? (
        <div
          className="mt-8 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 py-16"
          data-testid="analytics-empty-state"
        >
          <p className="text-lg font-medium text-gray-600">
            No applications yet
          </p>
          <p className="mt-2 text-sm text-gray-500">
            Start adding applications to your pipeline to see analytics here.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-6">
          {/* Row 1: Funnel + Response Rate */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <ConversionFunnel data={analytics.conversion_funnel} />
            </div>
            <div>
              <ResponseRate rate={analytics.response_rate} />
            </div>
          </div>

          {/* Row 2: Time in Stage */}
          <TimeInStage data={analytics.time_in_stage} />

          {/* Row 3: Over Time + Score Distribution */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ApplicationsOverTime data={analytics.applications_over_time} />
            <ScoreDistribution data={analytics.score_distribution} />
          </div>
        </div>
      )}

      {/* Prep & Notification Metrics (VAL-CROSS-007) */}
      {(analytics.prep_metrics || analytics.notification_metrics) && (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Prep Completion Rate */}
          {analytics.prep_metrics && (
            <div className="rounded-lg border bg-white p-6" data-testid="prep-metrics">
              <h2 className="text-lg font-semibold text-gray-900">
                📋 Interview Prep
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Prep session completion metrics
              </p>
              {analytics.prep_metrics.total_sessions === 0 ? (
                <p className="mt-4 text-sm text-gray-400">
                  No prep sessions created yet.
                </p>
              ) : (
                <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <div className="rounded-lg bg-indigo-50 p-3">
                    <p className="text-xl font-bold text-indigo-700">
                      {analytics.prep_metrics.total_sessions}
                    </p>
                    <p className="text-xs text-indigo-600">Total Sessions</p>
                  </div>
                  <div className="rounded-lg bg-emerald-50 p-3">
                    <p className="text-xl font-bold text-emerald-700">
                      {analytics.prep_metrics.completion_rate != null
                        ? `${analytics.prep_metrics.completion_rate}%`
                        : "N/A"}
                    </p>
                    <p className="text-xs text-emerald-600">Completion Rate</p>
                  </div>
                  <div className="rounded-lg bg-blue-50 p-3">
                    <p className="text-xl font-bold text-blue-700">
                      {analytics.prep_metrics.completed_items}/{analytics.prep_metrics.total_items}
                    </p>
                    <p className="text-xs text-blue-600">Items Done</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Notification Delivery Counts */}
          {analytics.notification_metrics && (
            <div className="rounded-lg border bg-white p-6" data-testid="notification-metrics">
              <h2 className="text-lg font-semibold text-gray-900">
                🔔 Notifications
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Notification delivery counts
              </p>
              {analytics.notification_metrics.total_sent === 0 &&
              analytics.notification_metrics.total_queued === 0 &&
              analytics.notification_metrics.total_failed === 0 ? (
                <p className="mt-4 text-sm text-gray-400">
                  No notifications sent yet.
                </p>
              ) : (
                <>
                  <div className="mt-4 grid grid-cols-3 gap-4">
                    <div className="rounded-lg bg-emerald-50 p-3">
                      <p className="text-xl font-bold text-emerald-700">
                        {analytics.notification_metrics.total_sent}
                      </p>
                      <p className="text-xs text-emerald-600">Sent</p>
                    </div>
                    <div className="rounded-lg bg-amber-50 p-3">
                      <p className="text-xl font-bold text-amber-700">
                        {analytics.notification_metrics.total_queued}
                      </p>
                      <p className="text-xs text-amber-600">Queued</p>
                    </div>
                    <div className="rounded-lg bg-red-50 p-3">
                      <p className="text-xl font-bold text-red-700">
                        {analytics.notification_metrics.total_failed}
                      </p>
                      <p className="text-xs text-red-600">Failed</p>
                    </div>
                  </div>
                  {Object.keys(analytics.notification_metrics.by_category).length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-gray-500 mb-2">By Category:</p>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(analytics.notification_metrics.by_category).map(
                          ([cat, count]) => (
                            <span
                              key={cat}
                              className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700"
                            >
                              {cat}: {count}
                            </span>
                          ),
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* Time Tracking Section — always shown regardless of applications */}
      {timeAnalytics && (
        <div className="mt-8">
          <TimeTracking data={timeAnalytics} />
        </div>
      )}
    </div>
  );
}
