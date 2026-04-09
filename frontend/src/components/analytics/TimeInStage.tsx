import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { TimeInStage as TimeInStageData } from "@/api/analytics";

const STATUS_LABELS: Record<string, string> = {
  discovered: "Discovered",
  interested: "Interested",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  accepted: "Accepted",
  rejected: "Rejected",
  ghosted: "Ghosted",
};

const STATUS_COLORS: Record<string, string> = {
  discovered: "#94a3b8",
  interested: "#60a5fa",
  applied: "#818cf8",
  interviewing: "#f59e0b",
  offer: "#34d399",
  accepted: "#22c55e",
  rejected: "#ef4444",
  ghosted: "#9ca3af",
};

interface Props {
  readonly data: TimeInStageData[];
}

export function TimeInStage({ data }: Props) {
  const hasData = data.some((d) => d.avg_days !== null);

  const chartData = data.map((d) => ({
    stage: d.stage,
    label: STATUS_LABELS[d.stage] ?? d.stage,
    avg_days: d.avg_days ?? 0,
    hasData: d.avg_days !== null,
  }));

  return (
    <div className="rounded-lg border bg-white p-6" data-testid="time-in-stage">
      <h2 className="text-lg font-semibold text-gray-900">Time in Stage</h2>
      <p className="mt-1 text-sm text-gray-500">
        Average days applications spend in each stage
      </p>

      {!hasData ? (
        <div className="flex items-center justify-center py-12">
          <p className="text-sm text-gray-400" data-testid="time-in-stage-empty">
            No data available
          </p>
        </div>
      ) : (
        <div className="mt-4 h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="horizontal"
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12, fill: "#64748b" }}
                tickLine={false}
                axisLine={{ stroke: "#e2e8f0" }}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "#64748b" }}
                tickLine={false}
                axisLine={{ stroke: "#e2e8f0" }}
                allowDecimals={false}
                label={{
                  value: "Days",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "#94a3b8", fontSize: 12 },
                }}
              />
              <Tooltip
                formatter={(value, _name, { payload }: { payload: { hasData: boolean } }) => {
                  if (!payload.hasData) return ["No data", "Avg. Days"];
                  return [`${Number(value).toFixed(1)} days`, "Avg. Days"];
                }}
                contentStyle={{
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                  fontSize: "13px",
                }}
              />
              <Bar dataKey="avg_days" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.stage}
                    fill={
                      entry.hasData
                        ? (STATUS_COLORS[entry.stage] ?? "#94a3b8")
                        : "#e5e7eb"
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Summary badges */}
      {hasData && (
        <div className="mt-4 flex flex-wrap gap-2">
          {data.map((d) => (
            <span
              key={d.stage}
              className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600"
            >
              {STATUS_LABELS[d.stage] ?? d.stage}:{" "}
              <span className="ml-1 font-medium">
                {d.avg_days !== null ? `${d.avg_days.toFixed(1)}d` : "No data"}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
