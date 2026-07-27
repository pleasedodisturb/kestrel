import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  type DetectionContext,
  buildAutologMessage,
  detectApplicationSubmit,
  logApplication,
  showConfirmationBanner,
  startAutolog,
} from "@/entrypoints/autolog.content";

// ---------------------------------------------------------------------------
// The detection heuristics are PURE (no network, no chrome) and run against
// jsdom Document/URL fixtures. The banner + logApplication are exercised with a
// small chrome fake.
// ---------------------------------------------------------------------------

function ctx(overrides: Partial<DetectionContext>): DetectionContext {
  return {
    host: "boards.greenhouse.io",
    url: "https://boards.greenhouse.io/acme/jobs/123",
    doc: document,
    ...overrides,
  };
}

beforeEach(() => {
  document.body.innerHTML = "";
});

afterEach(() => {
  vi.restoreAllMocks();
  const banner = document.getElementById("kestrel-autolog-banner");
  banner?.remove();
});

describe("detectApplicationSubmit — fires on a real submit confirmation", () => {
  it("Greenhouse: confirmation URL", () => {
    expect(
      detectApplicationSubmit(
        ctx({ url: "https://boards.greenhouse.io/acme/jobs/123/confirmation" }),
      ),
    ).toBe("greenhouse");
  });

  it("Greenhouse: thank-you body text", () => {
    document.body.textContent = "Thank you for applying to Acme!";
    expect(detectApplicationSubmit(ctx({}))).toBe("greenhouse");
  });

  it("Lever: /thanks confirmation path", () => {
    expect(
      detectApplicationSubmit(
        ctx({ host: "jobs.lever.co", url: "https://jobs.lever.co/acme/abc-uuid/thanks" }),
      ),
    ).toBe("lever");
  });

  it("Ashby: submitted DOM marker (SPA, no navigation)", () => {
    document.body.innerHTML = '<div data-testid="application-submitted">ok</div>';
    expect(
      detectApplicationSubmit(
        ctx({ host: "jobs.ashbyhq.com", url: "https://jobs.ashbyhq.com/acme/uuid/application" }),
      ),
    ).toBe("ashby");
  });
});

describe("detectApplicationSubmit — never fires spuriously", () => {
  it("does not fire on a Greenhouse application form before submit", () => {
    document.body.innerHTML = '<form id="application_form"><input name="email" /></form>';
    expect(
      detectApplicationSubmit(ctx({ url: "https://boards.greenhouse.io/acme/jobs/123" })),
    ).toBeNull();
  });

  it("does not fire on an unrelated host even with 'application submitted' text", () => {
    document.body.textContent = "application submitted";
    expect(
      detectApplicationSubmit(ctx({ host: "www.example.com", url: "https://www.example.com/x" })),
    ).toBeNull();
  });
});

describe("showConfirmationBanner — visible + dismissible, never silent", () => {
  function shadowButton(action: "log" | "dismiss"): HTMLButtonElement {
    const host = document.getElementById("kestrel-autolog-banner");
    const btn = host?.shadowRoot?.querySelector<HTMLButtonElement>(`[data-action='${action}']`);
    if (!btn) {
      throw new Error(`banner ${action} button not found`);
    }
    return btn;
  }

  it("injects a banner asking to log, in a shadow root with static text", () => {
    showConfirmationBanner({ onLog: vi.fn() });
    const host = document.getElementById("kestrel-autolog-banner");
    expect(host).not.toBeNull();
    expect(host?.shadowRoot?.textContent).toContain("Log this application to Kestrel?");
  });

  it("names the job (title + company) when a jobLabel is provided (MED-02)", () => {
    showConfirmationBanner({ onLog: vi.fn(), jobLabel: "Senior Backend Engineer · Acme" });
    const host = document.getElementById("kestrel-autolog-banner");
    expect(host?.shadowRoot?.textContent).toContain("Senior Backend Engineer · Acme");
  });

  it("Dismiss removes the banner and sends nothing", () => {
    const onLog = vi.fn();
    const onDismiss = vi.fn();
    showConfirmationBanner({ onLog, onDismiss });

    shadowButton("dismiss").click();

    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onLog).not.toHaveBeenCalled();
    expect(document.getElementById("kestrel-autolog-banner")).toBeNull();
  });

  it("Log invokes onLog and removes the banner", () => {
    const onLog = vi.fn();
    showConfirmationBanner({ onLog });

    shadowButton("log").click();

    expect(onLog).toHaveBeenCalledOnce();
    expect(document.getElementById("kestrel-autolog-banner")).toBeNull();
  });
});

describe("logApplication — promotes the captured job through the worker", () => {
  function installChrome(lastCapture?: unknown): ReturnType<typeof vi.fn> {
    const store: Record<string, unknown> = {};
    if (lastCapture !== undefined) {
      store.lastCapture = lastCapture;
    }
    const sendMessage = vi.fn(async () => ({ ok: true }));
    (globalThis as unknown as { chrome: unknown }).chrome = {
      storage: {
        session: {
          get: vi.fn(async (key: string) => (key in store ? { [key]: store[key] } : {})),
        },
      },
      runtime: { sendMessage },
    };
    return sendMessage;
  }

  it("sends PROMOTE with the last captured discoveredJobId", async () => {
    const sendMessage = installChrome({ ok: true, discoveredJobId: 99 });

    await logApplication();

    expect(sendMessage).toHaveBeenCalledWith({ type: "PROMOTE", discoveredJobId: 99 });
  });

  it("sends nothing when no job was captured (no silent create)", async () => {
    const sendMessage = installChrome(undefined);

    await logApplication();

    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("buildAutologMessage builds the PROMOTE message", () => {
    expect(buildAutologMessage(7)).toEqual({ type: "PROMOTE", discoveredJobId: 7 });
  });
});

describe("startAutolog — main() load path (HIGH-01 TDZ regression)", () => {
  function installChrome(lastCapture?: unknown): void {
    const store: Record<string, unknown> = {};
    if (lastCapture !== undefined) {
      store.lastCapture = lastCapture;
    }
    (globalThis as unknown as { chrome: unknown }).chrome = {
      storage: {
        session: {
          get: vi.fn(async (key: string) => (key in store ? { [key]: store[key] } : {})),
        },
      },
      runtime: { sendMessage: vi.fn(async () => ({ ok: true })) },
    };
  }

  // Regression guard for HIGH-01: on a full-navigation confirmation page the very
  // first synchronous maybeConfirm() reaches observer.disconnect(). Before the
  // fix `observer` was a `const` declared AFTER that call, so this path threw
  // `ReferenceError: Cannot access 'observer' before initialization`, the banner
  // never rendered, and auto-log was dead on its headline flow. This drives the
  // real main() wiring (not just the pure helpers) so it can't regress.
  it("renders the banner without throwing when a confirmation page is caught on load", async () => {
    installChrome({
      ok: true,
      discoveredJobId: 5,
      title: "Senior Backend Engineer",
      company: "Acme",
    });
    document.body.innerHTML = '<div id="application_confirmation">Thanks for applying</div>';
    const getContext = (): DetectionContext =>
      ctx({ url: "https://boards.greenhouse.io/acme/jobs/123/confirmation" });

    // The TDZ regression (HIGH-01) throws synchronously inside startAutolog, so
    // asserting "does not throw" still guards it even though the banner now
    // renders after an async label read.
    let teardown: () => void = () => {};
    expect(() => {
      teardown = startAutolog(getContext);
    }).not.toThrow();

    await vi.waitFor(() => {
      expect(document.getElementById("kestrel-autolog-banner")).not.toBeNull();
    });
    // MED-02: the caught-on-load banner names the captured job.
    const host = document.getElementById("kestrel-autolog-banner");
    expect(host?.shadowRoot?.textContent).toContain("Senior Backend Engineer");
    expect(host?.shadowRoot?.textContent).toContain("Acme");
    teardown();
  });

  it("does not render a banner on a pre-submit form (no confirmation signal)", () => {
    installChrome({ ok: true, discoveredJobId: 5 });
    document.body.innerHTML = '<form id="application_form"><input name="email" /></form>';
    const getContext = (): DetectionContext =>
      ctx({ url: "https://boards.greenhouse.io/acme/jobs/123" });

    let teardown: () => void = () => {};
    expect(() => {
      teardown = startAutolog(getContext);
    }).not.toThrow();
    expect(document.getElementById("kestrel-autolog-banner")).toBeNull();
    teardown();
  });
});
