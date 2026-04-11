/**
 * GradeBadge — a pill badge showing the letter grade + numeric fit score.
 *
 * Derives the letter grade from ``score`` (falls back to ``letterGrade`` prop
 * if provided, which is useful when the backend sends its own value).
 * Renders nothing when ``score`` is null/undefined.
 */

import { cn } from "@/lib/utils";
import { gradeBadgeClasses, scoreToLetterGrade } from "@/lib/gradeUtils";

interface GradeBadgeProps {
  readonly score: number | null | undefined;
  readonly letterGrade?: string | null;
  readonly className?: string;
  readonly testId?: string;
}

export function GradeBadge({
  score,
  letterGrade,
  className,
  testId,
}: GradeBadgeProps) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return null;
  }
  const grade = letterGrade ?? scoreToLetterGrade(score);
  return (
    <span
      data-testid={testId}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
        gradeBadgeClasses(grade),
        className,
      )}
      title={`Fit score ${score.toFixed(1)} (${grade ?? "—"})`}
    >
      <span>{grade ?? "—"}</span>
      <span className="font-normal opacity-80">{score.toFixed(1)}</span>
    </span>
  );
}
