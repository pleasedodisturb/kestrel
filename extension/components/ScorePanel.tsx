import { useState } from "react";
import type { CaptureResponse } from "@/lib/api/messages";

/**
 * Surface-agnostic score/gap presentation for "the eye". PURE — it takes a
 * capture result via props and emits an `onPromote` callback; it makes NO
 * `chrome.*` calls, so it unit-tests with props alone and mounts unchanged in
 * EITHER the MV3 sidePanel OR an in-page shadow-DOM overlay fallback (01-04
 * LOCKED design decision).
 *
 * It renders Kestrel's fit score + letter grade, a defensively-narrowed score
 * breakdown, the plain-language gap string, and a one-click "Add to pipeline"
 * button that promotes the captured job through the caller's `onPromote`.
 */

/** The capture result this panel renders (the 01-03 CAPTURE response shape). */
export type CaptureResult = CaptureResponse;

export interface ScorePanelProps {
  readonly result: CaptureResult;
  readonly onPromote: (discoveredJobId: number) => Promise<void> | void;
}

/** One row of the score breakdown, narrowed from the untyped backend JSON. */
interface BreakdownRow {
  readonly label: string;
  readonly score?: number;
  readonly weight?: number;
}

/**
 * Narrow one untyped `scoreBreakdown` item to a renderable row, or `null` if it
 * is malformed. The backend factor dicts are `{factor|label|name, score, weight}`
 * shaped, but the wire type is `unknown[]` — never trust it, narrow at the boundary.
 */
function narrowRow(item: unknown): BreakdownRow | null {
  if (typeof item !== "object" || item === null) {
    return null;
  }
  const rec = item as Record<string, unknown>;
  const rawLabel = rec.factor ?? rec.label ?? rec.name;
  if (typeof rawLabel !== "string" || rawLabel.trim() === "") {
    return null;
  }
  return {
    label: rawLabel,
    score: typeof rec.score === "number" ? rec.score : undefined,
    weight: typeof rec.weight === "number" ? rec.weight : undefined,
  };
}

type PromoteState = "idle" | "pending" | "done" | "error";

const PROMOTE_LABEL: Record<PromoteState, string> = {
  idle: "Add to pipeline",
  pending: "Adding…",
  done: "Added ✓",
  error: "Failed — retry",
};

export function ScorePanel({ result, onPromote }: ScorePanelProps) {
  const [promoteState, setPromoteState] = useState<PromoteState>("idle");

  if (!result.ok) {
    return (
      <section
        style={{ padding: 16, fontFamily: "system-ui, sans-serif", color: "#842029" }}
        role="alert"
      >
        <h1 style={{ fontSize: 15, margin: "0 0 6px" }}>Kestrel</h1>
        <p style={{ fontSize: 13, margin: 0 }}>
          {result.error === "not-paired"
            ? "Not paired — open Options to pair first."
            : `Capture failed${result.error ? ` (${result.error})` : ""}. Try again.`}
        </p>
      </section>
    );
  }

  const rows = (result.scoreBreakdown ?? [])
    .map(narrowRow)
    .filter((row): row is BreakdownRow => row !== null);

  const canPromote =
    typeof result.discoveredJobId === "number" && promoteState !== "pending" && promoteState !== "done";

  async function handlePromote() {
    if (typeof result.discoveredJobId !== "number") {
      return;
    }
    setPromoteState("pending");
    try {
      await onPromote(result.discoveredJobId);
      setPromoteState("done");
    } catch {
      setPromoteState("error");
    }
  }

  return (
    <section style={{ padding: 16, fontFamily: "system-ui, sans-serif", color: "#1f2937" }}>
      <h1 style={{ fontSize: 15, margin: "0 0 12px" }}>Kestrel score</h1>

      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 34, fontWeight: 700, lineHeight: 1 }} data-testid="letter-grade">
          {result.letterGrade ?? "—"}
        </span>
        {result.fitScore != null && (
          <span style={{ fontSize: 15, color: "#4b5563" }} data-testid="fit-score">
            fit {result.fitScore}
          </span>
        )}
      </div>

      {rows.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, margin: "0 0 12px" }} data-testid="breakdown">
          {rows.map((row, i) => (
            <li
              key={`${row.label}-${i}`}
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 13,
                padding: "3px 0",
                borderBottom: "1px solid #f0f0f0",
              }}
            >
              <span>{row.label}</span>
              <span style={{ color: "#4b5563" }}>
                {row.score != null ? row.score : "—"}
                {row.weight != null ? ` ×${row.weight}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}

      {result.gap && (
        <p
          style={{
            fontSize: 13,
            lineHeight: 1.4,
            background: "#f9fafb",
            border: "1px solid #eef0f2",
            borderRadius: 6,
            padding: "8px 10px",
            margin: "0 0 14px",
          }}
          data-testid="gap"
        >
          {result.gap}
        </p>
      )}

      <button
        type="button"
        onClick={handlePromote}
        disabled={!canPromote}
        style={{
          width: "100%",
          padding: "9px 12px",
          fontSize: 13,
          fontWeight: 600,
          border: 0,
          borderRadius: 8,
          background: canPromote ? "#1f2937" : "#9ca3af",
          color: "#fff",
          cursor: canPromote ? "pointer" : "default",
        }}
      >
        {typeof result.discoveredJobId === "number"
          ? PROMOTE_LABEL[promoteState]
          : "Add to pipeline (capture first)"}
      </button>
    </section>
  );
}
