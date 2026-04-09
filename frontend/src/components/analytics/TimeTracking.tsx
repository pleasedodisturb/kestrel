/**
 * Time tracking analytics component for the Analytics dashboard.
 *
 * Displays:
 * - Total hours and session count
 * - Category breakdown pie/bar chart
 * - 4-week trend chart
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import type { PieLabelRenderProps } from "recharts";
import type { TimeAnalyticsData } from "@/api/timingsapp";

const CATEGORY_COLORS: Record<string, string> = {
  applying: "#818cf8", // indigo
  researching: "#60a5fa", // blue
  prepping: "#f59e0b", // amber
  networking: "#34d399", // emerald
  learning: "#f472b6", // pink
};

const CATEGORY_LABELS: Record<string, string> = {
  applying: "Applying",
  researching: "Researching",
  prepping: "Prepping",
  networking: "Networking",
  learning: "Learning",
};

interface Props {
  readonly data: TimeAnalyticsData;
}

export function TimeTracking({ data }: Props) {
  const hasData = data.total_sessions > 0;

  // Prepare category breakdown data for the pie chart
  const pieData = data.category_breakdown
    .filter((cb) => cb.total_hours > 0)
    .map((cb) => ({
      name: CATEGORY_LABELS[cb.category] ?? cb.category,
      value: cb.total_hours,
      percentage: cb.percentage,
      sessions: cb.session_count,
      fill: CATEGORY_COLORS[cb.category] ?? "#94a3b8",
    }));

  // Prepare weekly trend data for the stacked bar chart
  const trendData = data.weekly_trend.map((w) => {
    const weekDate = new Date(w.week);
    const label = weekDate.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
    return {
      week: label,
      ...Object.fromEntries(
        Object.entries(w.category_hours).map(([cat, hrs]) => [cat, hrs]),
      ),
      total: w.total_hours,
    };
  });

  return (
    <div className="space-y-6">
      {/* Header with summary stats */}
      <div className="rounded-lg border bg-white p-6">
        <h2 className="text-lg font-semibold text-gray-900">
          ⏱️ Time Tracking
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Job search time analytics (last 4 weeks)
        </p>

        {!hasData ? (
          <div
            className="mt-6 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 py-8"
            data-testid="time-tracking-empty"
          >
            <p className="text-sm font-medium text-gray-600">
              No time sessions recorded yet
            </p>
            <p className="mt-1 text-xs text-gray-500">
              Start tracking your job search activities to see analytics here.
            </p>
          </div>
        ) : (
          <>
            {/* Summary cards */}
            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div className="rounded-lg bg-indigo-50 p-4">
                <p className="text-2xl font-bold text-indigo-700">
                  {data.total_hours.toFixed(1)}h
                </p>
                <p className="text-xs text-indigo-600">Total Hours</p>
              </div>
              <div className="rounded-lg bg-blue-50 p-4">
                <p className="text-2xl font-bold text-blue-700">
                  {data.total_sessions}
                </p>
                <p className="text-xs text-blue-600">Sessions</p>
              </div>
              <div className="rounded-lg bg-emerald-50 p-4">
                <p className="text-2xl font-bold text-emerald-700">
                  {data.avg_daily_hours.toFixed(1)}h
                </p>
                <p className="text-xs text-emerald-600">Avg Daily</p>
              </div>
              <div className="rounded-lg bg-amber-50 p-4">
                <p className="text-2xl font-bold text-amber-700">
                  {(data.total_hours / (data.weekly_trend.length || 1)).toFixed(
                    1,
                  )}
                  h
                </p>
                <p className="text-xs text-amber-600">Avg Weekly</p>
              </div>
            </div>
          </>
        )}
      </div>

      {hasData && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Category Breakdown Pie Chart */}
          <div className="rounded-lg border bg-white p-6">
            <h3 className="text-sm font-semibold text-gray-700">
              Category Breakdown
            </h3>
            {pieData.length === 0 ? (
              <p className="mt-4 text-sm text-gray-500">No data</p>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    dataKey="value"
                    label={({ name: rawName, ...rest }: PieLabelRenderProps & { percentage?: number }) => {
                      const name = String(rawName ?? "");
                      const pct = Number(rest.percentage ?? 0);
                      return `${name} ${pct.toFixed(0)}%`;
                    }}
                    labelLine={false}
                  >
                    {pieData.map((entry, idx) => (
                      <Cell key={`cell-${idx}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value, _name, { payload }: { payload: { sessions: number; name: string } }) => {
                      const numValue = Number(value) || 0;
                      return [
                        `${numValue.toFixed(1)}h (${payload.sessions} sessions)`,
                        payload.name,
                      ];
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* 4-Week Trend Stacked Bar Chart */}
          <div className="rounded-lg border bg-white p-6">
            <h3 className="text-sm font-semibold text-gray-700">
              4-Week Trend
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  label={{
                    value: "Hours",
                    angle: -90,
                    position: "insideLeft",
                    style: { fontSize: 12 },
                  }}
                />
                <Tooltip
                  formatter={(value, name) => {
                    const numValue = Number(value) || 0;
                    const strName = String(name);
                    return [
                      `${numValue.toFixed(1)}h`,
                      CATEGORY_LABELS[strName] ?? strName,
                    ];
                  }}
                />
                <Legend
                  formatter={(value: string) =>
                    CATEGORY_LABELS[value] ?? value
                  }
                />
                {Object.entries(CATEGORY_COLORS).map(([cat, color]) => (
                  <Bar
                    key={cat}
                    dataKey={cat}
                    stackId="hours"
                    fill={color}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
