/**
 * Tests for the StepProgress component.
 *
 * Covers:
 * - Rendering progress bar with correct ARIA attributes
 * - Step counter text display
 * - Percentage calculation
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StepProgress } from "@/components/StepProgress";

describe("StepProgress", () => {
  it("renders a progressbar with correct ARIA attributes", () => {
    render(<StepProgress current={2} total={6} />);

    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toBeInTheDocument();
    expect(progressbar).toHaveAttribute("aria-valuenow", "2");
    expect(progressbar).toHaveAttribute("aria-valuemin", "0");
    expect(progressbar).toHaveAttribute("aria-valuemax", "6");
    expect(progressbar).toHaveAttribute("aria-label", "Step 2 of 6");
  });

  it("displays the step counter text", () => {
    render(<StepProgress current={3} total={6} />);

    expect(screen.getByText("Step 3 of 6")).toBeInTheDocument();
  });

  it("renders the data-testid attribute", () => {
    render(<StepProgress current={1} total={6} />);

    expect(screen.getByTestId("step-progress")).toBeInTheDocument();
  });

  it("calculates correct percentage width for the fill bar", () => {
    const { container } = render(<StepProgress current={3} total={6} />);

    const fillBar = container.querySelector(
      "[role='progressbar'] > div",
    ) as HTMLElement;
    expect(fillBar).toHaveStyle({ width: "50%" });
  });

  it("shows 100% at the last step", () => {
    const { container } = render(<StepProgress current={6} total={6} />);

    const fillBar = container.querySelector(
      "[role='progressbar'] > div",
    ) as HTMLElement;
    expect(fillBar).toHaveStyle({ width: "100%" });
  });

  it("shows 0% at the first step", () => {
    const { container } = render(<StepProgress current={0} total={6} />);

    const fillBar = container.querySelector(
      "[role='progressbar'] > div",
    ) as HTMLElement;
    expect(fillBar).toHaveStyle({ width: "0%" });
  });

  it("applies custom className", () => {
    render(<StepProgress current={1} total={6} className="custom-class" />);

    expect(screen.getByTestId("step-progress")).toHaveClass("custom-class");
  });
});
