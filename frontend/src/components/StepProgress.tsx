/**
 * StepProgress -- accessible progress bar for the welcome step flow.
 *
 * Fixed at top of viewport. Shows filled/unfilled segments and "Step N of M" label.
 * Uses role="progressbar" with aria-valuenow/min/max per UI-SPEC accessibility requirements.
 */

import { cn } from "@/lib/utils";

interface StepProgressProps {
  current: number;
  total: number;
  className?: string;
}

export function StepProgress({ current, total, className }: StepProgressProps) {
  const pct = Math.round((current / total) * 100);

  return (
    <div
      className={cn("fixed top-0 left-0 right-0 z-10", className)}
      data-testid="step-progress"
    >
      <div
        className="h-1 w-full bg-[hsl(var(--secondary))]"
        role="progressbar"
        aria-valuenow={current}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={`Step ${current} of ${total}`}
      >
        <div
          className="h-full bg-[hsl(var(--primary))] transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 text-center text-sm text-[hsl(var(--muted-foreground))]">
        Step {current} of {total}
      </p>
    </div>
  );
}
