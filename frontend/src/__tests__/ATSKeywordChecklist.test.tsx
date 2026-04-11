/**
 * Tests for ATSKeywordChecklist component (#75).
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ATSKeywordChecklist } from "@/components/ATSKeywordChecklist";
import type { ATSKeyword } from "@/api/types";

const sampleKeywords: ATSKeyword[] = [
  { keyword: "Python", category: "technical", matched: true },
  { keyword: "Docker", category: "tool", matched: false },
  { keyword: "Communication", category: "soft_skill", matched: true },
  { keyword: "AWS Cert", category: "certification", matched: false },
];

describe("ATSKeywordChecklist", () => {
  it("renders nothing for an empty list", () => {
    const { container } = render(<ATSKeywordChecklist keywords={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("groups keywords by category and shows each keyword", () => {
    render(<ATSKeywordChecklist keywords={sampleKeywords} />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Docker")).toBeInTheDocument();
    expect(screen.getByText("Communication")).toBeInTheDocument();
    expect(screen.getByText("AWS Cert")).toBeInTheDocument();
    expect(screen.getByText("Technical")).toBeInTheDocument();
    expect(screen.getByText("Tools")).toBeInTheDocument();
    expect(screen.getByText("Soft Skills")).toBeInTheDocument();
    expect(screen.getByText("Certifications")).toBeInTheDocument();
  });

  it("distinguishes matched from unmatched with icon test IDs", () => {
    render(<ATSKeywordChecklist keywords={sampleKeywords} />);
    expect(screen.getByTestId("ats-match-Python")).toBeInTheDocument();
    expect(screen.getByTestId("ats-match-Communication")).toBeInTheDocument();
    expect(screen.getByTestId("ats-miss-Docker")).toBeInTheDocument();
    expect(screen.getByTestId("ats-miss-AWS Cert")).toBeInTheDocument();
  });

  it("shows matched count header", () => {
    render(<ATSKeywordChecklist keywords={sampleKeywords} />);
    expect(screen.getByText("2 of 4 keywords matched")).toBeInTheDocument();
  });
});
