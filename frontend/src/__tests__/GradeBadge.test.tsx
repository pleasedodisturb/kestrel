/**
 * Tests for GradeBadge component (#71).
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { GradeBadge } from "@/components/GradeBadge";
import { scoreToLetterGrade } from "@/lib/gradeUtils";

describe("scoreToLetterGrade", () => {
  it.each([
    [0.0, "F"],
    [2.9, "F"],
    [3.0, "D"],
    [3.9, "D"],
    [4.0, "C"],
    [5.0, "C+"],
    [6.0, "B"],
    [7.0, "B+"],
    [8.0, "A-"],
    [8.9, "A-"],
    [9.0, "A"],
    [10.0, "A"],
  ])("maps %s to %s", (score, expected) => {
    expect(scoreToLetterGrade(score)).toBe(expected);
  });

  it("returns null for null", () => {
    expect(scoreToLetterGrade(null)).toBeNull();
  });
});

describe("GradeBadge", () => {
  it("renders the letter grade and score for a valid score", () => {
    render(<GradeBadge score={8.5} testId="gb" />);
    const badge = screen.getByTestId("gb");
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toContain("A-");
    expect(badge.textContent).toContain("8.5");
  });

  it("renders nothing when score is null", () => {
    const { container } = render(<GradeBadge score={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when score is undefined", () => {
    const { container } = render(<GradeBadge score={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("uses provided letterGrade prop as override", () => {
    render(<GradeBadge score={8.5} letterGrade="CUSTOM" testId="gb" />);
    const badge = screen.getByTestId("gb");
    expect(badge.textContent).toContain("CUSTOM");
  });

  it("applies green background classes for A grade", () => {
    render(<GradeBadge score={9.5} testId="gb" />);
    const badge = screen.getByTestId("gb");
    expect(badge.className).toContain("bg-green-100");
    expect(badge.className).toContain("text-green-800");
  });

  it("applies red background classes for F grade", () => {
    render(<GradeBadge score={1.5} testId="gb" />);
    const badge = screen.getByTestId("gb");
    expect(badge.className).toContain("bg-red-100");
    expect(badge.className).toContain("text-red-800");
  });
});
