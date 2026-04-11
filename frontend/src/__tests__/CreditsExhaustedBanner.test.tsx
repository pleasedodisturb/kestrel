/**
 * Tests for CreditsExhaustedBanner (#28).
 *
 * Covers:
 * - Returns null when no flag is set
 * - Renders when sessionStorage.credits_exhausted === "true"
 * - Dismiss button persists credits_exhausted_dismissed flag
 */

import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { CreditsExhaustedBanner } from "@/components/CreditsExhaustedBanner";

describe("CreditsExhaustedBanner", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("renders nothing when flag is unset", () => {
    const { container } = render(<CreditsExhaustedBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders banner when credits_exhausted flag is set", () => {
    sessionStorage.setItem("credits_exhausted", "true");
    render(<CreditsExhaustedBanner />);
    expect(screen.getByTestId("credits-exhausted-banner")).toBeInTheDocument();
    expect(
      screen.getByText(/AI scoring stopped.*openrouter\.ai/i),
    ).toBeInTheDocument();
  });

  it("has a link to openrouter.ai", () => {
    sessionStorage.setItem("credits_exhausted", "true");
    render(<CreditsExhaustedBanner />);
    const link = screen.getByTestId("credits-exhausted-link");
    expect(link).toHaveAttribute("href", "https://openrouter.ai");
  });

  it("dismiss hides the banner and persists the dismissed flag", () => {
    sessionStorage.setItem("credits_exhausted", "true");
    const { queryByTestId, getByTestId } = render(<CreditsExhaustedBanner />);
    act(() => {
      getByTestId("credits-exhausted-dismiss").click();
    });
    expect(queryByTestId("credits-exhausted-banner")).not.toBeInTheDocument();
    expect(sessionStorage.getItem("credits_exhausted_dismissed")).toBe("true");
  });

  it("stays hidden when already dismissed", () => {
    sessionStorage.setItem("credits_exhausted", "true");
    sessionStorage.setItem("credits_exhausted_dismissed", "true");
    const { container } = render(<CreditsExhaustedBanner />);
    expect(container.firstChild).toBeNull();
  });
});
