/**
 * Unit tests for the discovery API client functions.
 *
 * Covers:
 * - VAL-SEARCH-004 regression: null params must not be serialized as "null" string
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { searchJobs } from "@/api/discovery";
import type { JobSearchParams } from "@/api/types";

describe("searchJobs", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          jobs: [],
          total: 0,
          page: 1,
          page_size: 20,
          total_pages: 0,
        }),
    });
    vi.stubGlobal("fetch", mockFetch);
  });

  it("omits null numeric params from query string", async () => {
    const params: JobSearchParams = {
      profile_id: 1,
      salary_min: null as unknown as undefined,
      salary_max: null as unknown as undefined,
      score_min: null as unknown as undefined,
      score_max: null as unknown as undefined,
      page: null as unknown as undefined,
      page_size: null as unknown as undefined,
    };

    await searchJobs(params);

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain("salary_min");
    expect(calledUrl).not.toContain("salary_max");
    expect(calledUrl).not.toContain("score_min");
    expect(calledUrl).not.toContain("score_max");
    // Should not contain "null" as a string value
    expect(calledUrl).not.toContain("=null");
    // Should contain profile_id
    expect(calledUrl).toContain("profile_id=1");
  });

  it("includes valid numeric params in query string", async () => {
    const params: JobSearchParams = {
      profile_id: 1,
      salary_min: 80000,
      salary_max: 120000,
      score_min: 7,
      score_max: 10,
    };

    await searchJobs(params);

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("salary_min=80000");
    expect(calledUrl).toContain("salary_max=120000");
    expect(calledUrl).toContain("score_min=7");
    expect(calledUrl).toContain("score_max=10");
  });

  it("omits undefined params from query string", async () => {
    const params: JobSearchParams = {
      profile_id: 1,
      q: undefined,
      source: undefined,
      salary_min: undefined,
    };

    await searchJobs(params);

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain("q=");
    expect(calledUrl).not.toContain("source=");
    expect(calledUrl).not.toContain("salary_min");
  });

  it("handles zero values correctly (not omitted)", async () => {
    const params: JobSearchParams = {
      profile_id: 1,
      salary_min: 0,
      score_min: 0,
      page: 0,
    };

    await searchJobs(params);

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("salary_min=0");
    expect(calledUrl).toContain("score_min=0");
    expect(calledUrl).toContain("page=0");
  });

  it("does not serialize remote=null", async () => {
    const params: JobSearchParams = {
      profile_id: 1,
      remote: null as unknown as undefined,
    };

    await searchJobs(params);

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain("remote");
  });
});
