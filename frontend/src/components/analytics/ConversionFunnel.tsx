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
import type { FunnelStage } from "@/api/analytics";

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

interface Props {
  readonly data: FunnelStage[];
}

export function ConversionFunnel({ data }: Props) {
  const chartData = data.map((d) => ({
    ...d,
    label: STATUS_LABELS[d.stage] ?? d.stage,
  }));

  const hasData = chartData.some((d) => d.count > 0);

  return (
    <div className="rounded-lg border bg-white p-6" data-testid="conversion-funnel">
      <h2 className="text-lg font-semibold text-gray-900">Conversion Funnel</h2>
      <p className="mt-1 text-sm text-gray-500">
        Applications by pipeline stage (percentages show stage-to-stage conversion)
      </p>

      {hasData ? (
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
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
              />
              <Tooltip
                formatter={(value, _name, { payload }: { payload: { percentage: number } }) => [
                  `${value} (${payload.percentage}%)`,
                  "Count",
                ]}
                contentStyle={{
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                  fontSize: "13px",
                }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.stage}
                    fill={STATUS_COLORS[entry.stage] ?? "#94a3b8"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Summary table below the chart */}
      {hasData && (
        <div className="mt-4 grid grid-cols-4 gap-2 text-center text-xs">
          {chartData
            .filter((d) => d.count > 0)
            .map((d) => (
              <div key={d.stage} className="rounded bg-gray-50 px-2 py-1">
                <span className="font-medium text-gray-700">{d.label}</span>
                <br />
                <span className="text-gray-500">
                  {d.count} ({d.percentage}%)
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
