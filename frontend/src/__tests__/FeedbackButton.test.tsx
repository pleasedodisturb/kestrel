import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { FeedbackButton } from "@/components/FeedbackButton";

describe("FeedbackButton", () => {
  it("renders the feedback button", () => {
    render(<FeedbackButton />);
    const button = screen.getByTestId("feedback-button");
    expect(button).toBeInTheDocument();
  });

  it("has accessible label", () => {
    render(<FeedbackButton />);
    const button = screen.getByLabelText("Send feedback");
    expect(button).toBeInTheDocument();
  });

  it("links to GitHub issues", () => {
    render(<FeedbackButton />);
    const link = screen.getByTestId("feedback-button") as HTMLAnchorElement;
    expect(link.href).toContain("github.com");
    expect(link.href).toContain("issues/new");
  });

  it("opens in new tab", () => {
    render(<FeedbackButton />);
    const link = screen.getByTestId("feedback-button");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("includes tooltip text", () => {
    render(<FeedbackButton />);
    expect(screen.getByText("Send feedback")).toBeInTheDocument();
  });

  it("includes system info in the issue URL", () => {
    render(<FeedbackButton />);
    const link = screen.getByTestId("feedback-button") as HTMLAnchorElement;
    // URL should contain the body parameter with system info
    expect(link.href).toContain("body=");
    expect(link.href).toContain("labels=feedback");
  });
});
