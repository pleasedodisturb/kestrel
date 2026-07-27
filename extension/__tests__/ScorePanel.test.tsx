import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ScorePanel } from "@/components/ScorePanel";
import type { CaptureResponse } from "@/lib/api/messages";

// ---------------------------------------------------------------------------
// ScorePanel is PURE (props-only, no chrome.*), so it tests with props alone —
// exactly what lets it mount unchanged in the sidePanel or an overlay fallback.
// ---------------------------------------------------------------------------

const SCORED: CaptureResponse = {
  ok: true,
  jobId: "42",
  discoveredJobId: 42,
  fitScore: 7.5,
  letterGrade: "B",
  scoreBreakdown: [
    { factor: "skills", score: 3, weight: 2 },
    { label: "seniority", score: 5 },
  ],
  gap: "missing: Kubernetes, Go; seniority ✓",
};

describe("ScorePanel — score/breakdown/gap render", () => {
  it("renders the letter grade, fit score, breakdown rows, and gap verbatim", () => {
    render(<ScorePanel result={SCORED} onPromote={vi.fn()} />);

    expect(screen.getByTestId("letter-grade")).toHaveTextContent("B");
    expect(screen.getByTestId("fit-score")).toHaveTextContent("7.5");
    expect(screen.getByText("skills")).toBeInTheDocument();
    expect(screen.getByText("seniority")).toBeInTheDocument();
    expect(screen.getByTestId("gap")).toHaveTextContent(
      "missing: Kubernetes, Go; seniority ✓",
    );
  });

  it("tolerates an undefined breakdown and still renders score + gap", () => {
    const noBreakdown: CaptureResponse = { ...SCORED, scoreBreakdown: undefined };
    render(<ScorePanel result={noBreakdown} onPromote={vi.fn()} />);

    expect(screen.getByTestId("letter-grade")).toHaveTextContent("B");
    expect(screen.getByTestId("gap")).toBeInTheDocument();
    expect(screen.queryByTestId("breakdown")).not.toBeInTheDocument();
  });

  it("skips malformed breakdown items without throwing", () => {
    const messy: CaptureResponse = {
      ...SCORED,
      scoreBreakdown: [null, 7, { nope: true }, { factor: "culture", score: 4 }],
    };
    render(<ScorePanel result={messy} onPromote={vi.fn()} />);

    const rows = screen.getByTestId("breakdown").querySelectorAll("li");
    expect(rows).toHaveLength(1);
    expect(screen.getByText("culture")).toBeInTheDocument();
  });
});

describe("ScorePanel — error state", () => {
  it("renders an alert when the capture failed", () => {
    render(<ScorePanel result={{ ok: false, error: "backend-unreachable" }} onPromote={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("backend-unreachable");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("ScorePanel — Add to pipeline", () => {
  it("invokes onPromote with the discoveredJobId and shows the added acknowledgement", async () => {
    const onPromote = vi.fn().mockResolvedValue(undefined);
    render(<ScorePanel result={SCORED} onPromote={onPromote} />);

    fireEvent.click(screen.getByRole("button", { name: /add to pipeline/i }));

    expect(onPromote).toHaveBeenCalledWith(42);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /added/i })).toBeInTheDocument(),
    );
  });

  it("shows a retry state when onPromote rejects", async () => {
    const onPromote = vi.fn().mockRejectedValue(new Error("bad-key"));
    render(<ScorePanel result={SCORED} onPromote={onPromote} />);

    fireEvent.click(screen.getByRole("button", { name: /add to pipeline/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /failed/i })).toBeInTheDocument(),
    );
  });

  it("disables the button when there is no discoveredJobId", () => {
    const noId: CaptureResponse = { ...SCORED, discoveredJobId: undefined };
    render(<ScorePanel result={noId} onPromote={vi.fn()} />);

    expect(screen.getByRole("button")).toBeDisabled();
  });
});
