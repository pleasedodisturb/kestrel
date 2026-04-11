/**
 * Unit tests for the scoring API client functions.
 *
 * Covers the null-on-404 contract of `getApplicationScore`, which is what
 * ApplicationDetail relies on to hide the dimensional / ATS UI sections
 * gracefully when an application has not been scored yet.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { getApplicationScore } from "@/api/scoring";

describe("getApplicationScore", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal("fetch", mockFetch);
  });

  it("returns null when the backend responds 404", async () => {
    mockFetch.mockResolvedValue({
      status: 404,
      ok: false,
    });
    const result = await getApplicationScore(42, 1);
    expect(result).toBeNull();
  });

  it("returns the parsed body on a successful response", async () => {
    const payload = {
      fit_score: 8.2,
      readiness_score: 70,
      career_alignment: 7.5,
      reasoning: "x".repeat(120),
      letter_grade: "A-",
      dimensional_scores: {
        technical_fit: 8,
        seniority_alignment: 7,
        compensation_fit: 6,
        location_fit: 9,
        career_trajectory: 8,
        company_fit: 5,
      },
      ats_keywords: [],
      red_flags: [],
    };
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: () => Promise.resolve(payload),
    });
    const result = await getApplicationScore(42, 1);
    expect(result).toEqual(payload);
  });

  it("throws on non-404 error responses", async () => {
    mockFetch.mockResolvedValue({
      status: 500,
      ok: false,
    });
    await expect(getApplicationScore(42, 1)).rejects.toThrow(
      /Failed to fetch score/,
    );
  });

  it("targets the expected URL", async () => {
    mockFetch.mockResolvedValue({
      status: 404,
      ok: false,
    });
    await getApplicationScore(42, 7);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/score/application/42?profile_id=7",
    );
  });
});
