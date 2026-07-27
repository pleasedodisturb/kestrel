import { beforeEach, describe, expect, it, vi } from "vitest";
import { handleMessage } from "@/entrypoints/background";
import type { CapturePayload, HealthResponse } from "@/lib/api/messages";
import { setBackendUrl } from "@/lib/storage";

// ---------------------------------------------------------------------------
// Test doubles: in-memory chrome.storage.local + a mockable global fetch.
// ---------------------------------------------------------------------------

function installFakeStorage(): Record<string, unknown> {
  const store: Record<string, unknown> = {};
  // One backing object shared by `local` and `session`: the keys never collide
  // (extensionToken/backendUrl vs lastCapture), so a single record keeps the
  // fake tiny while letting tests assert `store.lastCapture` from session.set.
  const area = {
    get: vi.fn(async (key: string) => (key in store ? { [key]: store[key] } : {})),
    set: vi.fn(async (items: Record<string, unknown>) => {
      Object.assign(store, items);
    }),
  };
  (globalThis as unknown as { chrome: unknown }).chrome = {
    storage: { local: area, session: area },
  };
  return store;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

type Route = Response | "network";

function routeFetch(routes: Record<string, Route>): ReturnType<typeof vi.fn> {
  const mock = vi.fn(async (input: string | URL) => {
    const url = String(input);
    for (const [fragment, route] of Object.entries(routes)) {
      if (url.includes(fragment)) {
        if (route === "network") {
          throw new Error("network failure");
        }
        // Clone so multiple reads in one test don't consume the body.
        return route.clone();
      }
    }
    throw new Error(`unrouted fetch: ${url}`);
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

const SAMPLE_PAYLOAD: CapturePayload = {
  url: "https://jobs.example.com/123",
  title: "Staff Engineer",
  company: "Acme",
  description: "Build things.",
};

const INSTANCE = { name: "Kestrel", version: "0.20.0" };

let store: Record<string, unknown>;

beforeEach(() => {
  vi.restoreAllMocks();
  store = installFakeStorage();
});

describe("PAIR", () => {
  it("stores the returned token and echoes instance info", async () => {
    routeFetch({
      "/api/extension/pair": jsonResponse({ token: "tok-123", instance: INSTANCE }),
    });

    const res = await handleMessage({ type: "PAIR", pairingCode: "123456" });

    expect(res).toEqual({ ok: true, token: "tok-123", instance: INSTANCE });
    expect(store.extensionToken).toBe("tok-123");
  });

  it("returns an error on an invalid pairing code and stores nothing", async () => {
    routeFetch({ "/api/extension/pair": jsonResponse({ detail: "nope" }, 401) });

    const res = await handleMessage({ type: "PAIR", pairingCode: "000000" });

    expect(res.ok).toBe(false);
    expect(store.extensionToken).toBeUndefined();
  });
});

describe("CAPTURE", () => {
  it("errors and never calls fetch when there is no stored token", async () => {
    const fetchMock = routeFetch({});

    const res = await handleMessage({ type: "CAPTURE", payload: SAMPLE_PAYLOAD });

    expect(res).toEqual({ ok: false, error: "not-paired" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends a cookie-less bearer request when a token is present", async () => {
    store.extensionToken = "tok-xyz";
    const fetchMock = routeFetch({
      "/api/extension/capture": jsonResponse({ job_id: "job-1", status: "accepted", scored: false }),
    });

    const res = await handleMessage({ type: "CAPTURE", payload: SAMPLE_PAYLOAD });

    expect(res).toEqual({ ok: true, jobId: "job-1" });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("omit");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok-xyz");
  });

  it("passes the score fields through when the backend scores the capture", async () => {
    store.extensionToken = "tok-xyz";
    routeFetch({
      "/api/extension/capture": jsonResponse({
        job_id: "42",
        status: "scored",
        scored: true,
        discovered_job_id: 42,
        fit_score: 7.5,
        letter_grade: "B",
        score_breakdown: [{ factor: "skills", score: 3 }],
        gap: "missing: Kubernetes, Go; seniority ✓",
      }),
    });

    const res = await handleMessage({ type: "CAPTURE", payload: SAMPLE_PAYLOAD });

    expect(res).toEqual({
      ok: true,
      jobId: "42",
      discoveredJobId: 42,
      fitScore: 7.5,
      letterGrade: "B",
      scoreBreakdown: [{ factor: "skills", score: 3 }],
      gap: "missing: Kubernetes, Go; seniority ✓",
    });
    // The score is stashed in session storage for the sidePanel to read on open.
    expect(store.lastCapture).toEqual(res);
  });

  it("forwards a raw_text payload and tolerates a null score_breakdown", async () => {
    store.extensionToken = "tok-xyz";
    const fetchMock = routeFetch({
      "/api/extension/capture": jsonResponse({
        job_id: "9",
        status: "scored",
        scored: true,
        discovered_job_id: 9,
        fit_score: 5,
        letter_grade: "C",
        score_breakdown: null,
        gap: "no major keyword gaps; seniority ✓",
      }),
    });

    const rawPayload: CapturePayload = {
      url: "https://jobs.example.com/raw",
      title: "",
      company: "",
      description: "Whole page text.",
      raw_text: "Whole page text.",
    };
    const res = (await handleMessage({ type: "CAPTURE", payload: rawPayload })) as {
      ok: boolean;
      scoreBreakdown?: unknown[];
      gap?: string;
    };

    expect(res.ok).toBe(true);
    expect(res.scoreBreakdown).toBeUndefined();
    expect(res.gap).toBe("no major keyword gaps; seniority ✓");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string).raw_text).toBe("Whole page text.");
  });
});

describe("PROMOTE", () => {
  it("errors and never calls fetch when there is no stored token", async () => {
    const fetchMock = routeFetch({});

    const res = await handleMessage({ type: "PROMOTE", discoveredJobId: 42 });

    expect(res).toEqual({ ok: false, error: "not-paired" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("promotes a captured job through the worker and returns the application id", async () => {
    store.extensionToken = "tok-xyz";
    const fetchMock = routeFetch({
      "/api/extension/promote": jsonResponse({ application_id: 7, status: "discovered" }),
    });

    const res = await handleMessage({ type: "PROMOTE", discoveredJobId: 42 });

    expect(res).toEqual({ ok: true, applicationId: 7, status: "discovered" });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("omit");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok-xyz");
    expect(JSON.parse(init.body as string).discovered_job_id).toBe(42);
  });

  it("maps a 401 to bad-key", async () => {
    store.extensionToken = "stale";
    routeFetch({ "/api/extension/promote": jsonResponse({ detail: "no" }, 401) });

    const res = await handleMessage({ type: "PROMOTE", discoveredJobId: 42 });

    expect(res).toEqual({ ok: false, error: "bad-key" });
  });
});

describe("STATUS", () => {
  it("returns instance info for a paired extension", async () => {
    store.extensionToken = "tok-xyz";
    routeFetch({ "/api/extension/status": jsonResponse({ ok: true, instance: INSTANCE }) });

    const res = await handleMessage({ type: "STATUS" });

    expect(res).toEqual({ ok: true, instance: INSTANCE });
  });
});

describe("HEALTH", () => {
  async function healthState(routes: Record<string, Route>, token?: string): Promise<string> {
    if (token) {
      store.extensionToken = token;
    }
    routeFetch(routes);
    const res = (await handleMessage({ type: "HEALTH" })) as HealthResponse;
    return res.state;
  }

  it("resolves connected when backend is up, token present, status 200", async () => {
    const state = await healthState(
      {
        "/health": jsonResponse({ status: "ok", database: "connected" }),
        "/api/extension/status": jsonResponse({ ok: true, instance: INSTANCE }),
      },
      "tok-xyz",
    );
    expect(state).toBe("connected");
  });

  it("resolves unpaired when backend is up but no token is stored", async () => {
    const state = await healthState({
      "/health": jsonResponse({ status: "ok", database: "connected" }),
    });
    expect(state).toBe("unpaired");
  });

  it("resolves backend-down when /health is unreachable", async () => {
    const state = await healthState({ "/health": "network" });
    expect(state).toBe("backend-down");
  });

  it("resolves bad-key when backend is up but status returns 401", async () => {
    const state = await healthState(
      {
        "/health": jsonResponse({ status: "ok", database: "connected" }),
        "/api/extension/status": jsonResponse({ detail: "not paired" }, 401),
      },
      "stale-token",
    );
    expect(state).toBe("bad-key");
  });
});

describe("storage URL guard", () => {
  it("rejects a non-localhost http:// backend URL", async () => {
    await expect(setBackendUrl("http://evil.example.com:8100")).rejects.toThrow(/Insecure/);
  });

  it("accepts localhost http:// and remote https://", async () => {
    await expect(setBackendUrl("http://localhost:8100")).resolves.toBeUndefined();
    await expect(setBackendUrl("https://kestrel.example.com")).resolves.toBeUndefined();
  });
});
