/**
 * RedFlagBadge — surfaces rule-based JD red flags on job cards and the
 * application detail page (#73).
 *
 * Two render modes:
 *  - ``compact`` (default, for list/card use): a single warning-triangle
 *    icon + count pill, colored by the worst severity present.
 *  - ``expanded`` (for the detail page): a stacked list of severity icon
 *    + description rows.
 *
 * Renders nothing when ``flags`` is null/undefined/empty.
 */

import { AlertTriangle } from "lucide-react";
import type { RedFlag, RedFlagSeverity } from "@/api/types";
import { cn } from "@/lib/utils";

const SEVERITY_ORDER: readonly RedFlagSeverity[] = [
  "info",
  "caution",
  "warning",
  "dealbreaker",
];

const SEVERITY_STYLES: Record<
  RedFlagSeverity,
  { pill: string; icon: string; row: string; label: string }
> = {
  info: {
    pill: "bg-gray-100 text-gray-700",
    icon: "text-gray-500",
    row: "border-gray-200 bg-gray-50",
    label: "Info",
  },
  caution: {
    pill: "bg-yellow-100 text-yellow-800",
    icon: "text-yellow-600",
    row: "border-yellow-200 bg-yellow-50",
    label: "Caution",
  },
  warning: {
    pill: "bg-orange-100 text-orange-800",
    icon: "text-orange-600",
    row: "border-orange-200 bg-orange-50",
    label: "Warning",
  },
  dealbreaker: {
    pill: "bg-red-100 text-red-800",
    icon: "text-red-600",
    row: "border-red-200 bg-red-50",
    label: "Dealbreaker",
  },
};

interface RedFlagBadgeProps {
  readonly flags: RedFlag[] | null | undefined;
  readonly mode?: "compact" | "expanded";
  readonly className?: string;
  readonly testId?: string;
}

function worstSeverity(flags: readonly RedFlag[]): RedFlagSeverity {
  let worst: RedFlagSeverity = "info";
  for (const flag of flags) {
    if (SEVERITY_ORDER.indexOf(flag.severity) > SEVERITY_ORDER.indexOf(worst)) {
      worst = flag.severity;
    }
  }
  return worst;
}

export function RedFlagBadge({
  flags,
  mode = "compact",
  className,
  testId,
}: RedFlagBadgeProps) {
  if (!flags || flags.length === 0) {
    return null;
  }

  if (mode === "compact") {
    const severity = worstSeverity(flags);
    const styles = SEVERITY_STYLES[severity];
    const title = flags
      .map((f) => `${SEVERITY_STYLES[f.severity].label}: ${f.description}`)
      .join("\n");
    return (
      <span
        data-testid={testId}
        title={title}
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
          styles.pill,
          className,
        )}
      >
        <AlertTriangle className={cn("h-3.5 w-3.5", styles.icon)} />
        <span>{flags.length}</span>
      </span>
    );
  }

  // Expanded mode
  return (
    <ul
      data-testid={testId}
      className={cn("flex flex-col gap-2", className)}
    >
      {flags.map((flag, idx) => {
        const styles = SEVERITY_STYLES[flag.severity];
        return (
          <li
            key={`${flag.flag_type}-${idx}`}
            className={cn(
              "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
              styles.row,
            )}
          >
            <AlertTriangle
              className={cn("mt-0.5 h-4 w-4 flex-shrink-0", styles.icon)}
            />
            <div>
              <div className="font-semibold text-gray-900">
                {styles.label}
                <span className="ml-2 text-xs font-normal text-gray-500">
                  {flag.flag_type}
                </span>
              </div>
              <div className="text-gray-700">{flag.description}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
