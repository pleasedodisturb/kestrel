/**
 * Letter-grade helpers derived from a 0-10 fit score.
 *
 * Mirrors the backend helper in ``src/career_os/schemas/scoring.py``.
 * Keep the two in sync.
 */

/** Map a numeric fit_score (0-10) to a letter grade. */
export function scoreToLetterGrade(score: number | null): string | null {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return null;
  }
  if (score >= 9.0) return "A";
  if (score >= 8.0) return "A-";
  if (score >= 7.0) return "B+";
  if (score >= 6.0) return "B";
  if (score >= 5.0) return "C+";
  if (score >= 4.0) return "C";
  if (score >= 3.0) return "D";
  return "F";
}

/**
 * Tailwind classes (background + text) for a letter grade pill badge.
 * Returns a gray fallback for null/unknown grades.
 */
export function gradeBadgeClasses(grade: string | null | undefined): string {
  switch (grade) {
    case "A":
    case "A-":
      return "bg-green-100 text-green-800";
    case "B+":
    case "B":
      return "bg-emerald-100 text-emerald-800";
    case "C+":
    case "C":
      return "bg-yellow-100 text-yellow-800";
    case "D":
      return "bg-orange-100 text-orange-800";
    case "F":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-600";
  }
}
