/**
 * Unit tests for scoreColor helper extracted from KanbanCard.
 *
 * Verifies the three-tier color thresholds used for fit_score and
 * readiness_score badges.
 */

import { describe, it, expect } from "vitest";
import { scoreColor } from "@/lib/utils";

describe("scoreColor", () => {
  // --- fit_score thresholds (high=8, mid=5) ---

  it("returns green for values >= high threshold", () => {
    expect(scoreColor(8, 8, 5)).toBe("bg-green-100 text-green-800");
    expect(scoreColor(9.5, 8, 5)).toBe("bg-green-100 text-green-800");
    expect(scoreColor(10, 8, 5)).toBe("bg-green-100 text-green-800");
  });

  it("returns yellow for values >= mid but < high", () => {
    expect(scoreColor(5, 8, 5)).toBe("bg-yellow-100 text-yellow-800");
    expect(scoreColor(7.9, 8, 5)).toBe("bg-yellow-100 text-yellow-800");
    expect(scoreColor(6, 8, 5)).toBe("bg-yellow-100 text-yellow-800");
  });

  it("returns red for values < mid threshold", () => {
    expect(scoreColor(4.9, 8, 5)).toBe("bg-red-100 text-red-800");
    expect(scoreColor(0, 8, 5)).toBe("bg-red-100 text-red-800");
    expect(scoreColor(1, 8, 5)).toBe("bg-red-100 text-red-800");
  });

  // --- readiness_score thresholds (high=80, mid=50) ---

  it("works with readiness thresholds (80/50)", () => {
    expect(scoreColor(80, 80, 50)).toBe("bg-green-100 text-green-800");
    expect(scoreColor(95, 80, 50)).toBe("bg-green-100 text-green-800");
    expect(scoreColor(50, 80, 50)).toBe("bg-yellow-100 text-yellow-800");
    expect(scoreColor(79, 80, 50)).toBe("bg-yellow-100 text-yellow-800");
    expect(scoreColor(49, 80, 50)).toBe("bg-red-100 text-red-800");
    expect(scoreColor(0, 80, 50)).toBe("bg-red-100 text-red-800");
  });

  // --- edge cases ---

  it("handles exact boundary values correctly", () => {
    // Exactly at high threshold → green
    expect(scoreColor(8, 8, 5)).toBe("bg-green-100 text-green-800");
    // Exactly at mid threshold → yellow
    expect(scoreColor(5, 8, 5)).toBe("bg-yellow-100 text-yellow-800");
  });

  it("handles negative values", () => {
    expect(scoreColor(-1, 8, 5)).toBe("bg-red-100 text-red-800");
  });
});
