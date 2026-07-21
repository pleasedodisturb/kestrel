import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "@/entrypoints/options/App";
import type { ExtMessage, ExtResponse, HealthState, PairResponse } from "@/lib/api/messages";

// ---------------------------------------------------------------------------
// Mock at the module boundary (frontend rule): the storage helpers and
// chrome.runtime.sendMessage. The options page must reach the backend ONLY
// through the worker, so we never mock a fetch here — there is none to mock.
// ---------------------------------------------------------------------------

vi.mock("@/lib/storage", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/storage")>();
  return {
    // Keep the real guard so the non-localhost http:// rejection is exercised.
    assertValidBackendUrl: actual.assertValidBackendUrl,
    getBackendUrl: vi.fn(async () => "http://localhost:8100"),
    setBackendUrl: vi.fn(async (url: string) => {
      actual.assertValidBackendUrl(url);
    }),
    getToken: vi.fn(async () => null),
    setToken: vi.fn(async () => {}),
  };
});

const INSTANCE = { name: "Kestrel", version: "0.20.0" };

interface Responses {
  readonly PAIR?: PairResponse;
  readonly HEALTH?: { ok: boolean; state: HealthState };
}

/** Install a routed chrome.runtime.sendMessage returning canned responses per type. */
function installChrome(responses: Responses): ReturnType<typeof vi.fn> {
  const sendMessage = vi.fn(async (message: ExtMessage): Promise<ExtResponse> => {
    if (message.type === "PAIR") {
      return responses.PAIR ?? { ok: false, error: "no-pair-mock" };
    }
    if (message.type === "HEALTH") {
      return responses.HEALTH ?? { ok: false, state: "unpaired" };
    }
    return { ok: false, error: "unrouted" };
  });
  (globalThis as unknown as { chrome: unknown }).chrome = { runtime: { sendMessage } };
  return sendMessage;
}

/** Render the options page (mirrors the frontend `render*` helper convention). */
function renderOptions() {
  return render(<App />);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("pairing", () => {
  it("sends a PAIR message and shows instance info on success", async () => {
    const sendMessage = installChrome({
      PAIR: { ok: true, token: "tok-123", instance: INSTANCE },
      HEALTH: { ok: true, state: "connected" },
    });
    renderOptions();

    fireEvent.change(screen.getByLabelText(/pairing code/i), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: /^pair$/i }));

    expect(await screen.findByText(/Paired with Kestrel v0\.20\.0/)).toBeInTheDocument();
    expect(sendMessage).toHaveBeenCalledWith({ type: "PAIR", pairingCode: "123456" });
  });

  it("shows the error on a bad code and renders no success/instance state", async () => {
    installChrome({
      PAIR: { ok: false, error: "Invalid or expired pairing code" },
      HEALTH: { ok: false, state: "unpaired" },
    });
    renderOptions();

    fireEvent.change(screen.getByLabelText(/pairing code/i), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: /^pair$/i }));

    expect(await screen.findByText(/Invalid or expired pairing code/)).toBeInTheDocument();
    expect(screen.queryByText(/Paired with/)).not.toBeInTheDocument();
  });
});

describe("health badge", () => {
  const cases: ReadonlyArray<readonly [HealthState, RegExp]> = [
    ["connected", /Connected to Kestrel/],
    ["unpaired", /Not paired yet/],
    ["backend-down", /Kestrel not running/],
    ["bad-key", /Pairing expired — pair again/],
  ];

  it.each(cases)("renders the %s label", async (state, label) => {
    installChrome({ HEALTH: { ok: state === "connected", state } });
    renderOptions();

    expect(await screen.findByText(label)).toBeInTheDocument();
  });
});

describe("backend URL guard", () => {
  it("surfaces the guard's validation error for a non-localhost http:// URL", async () => {
    installChrome({ HEALTH: { ok: false, state: "unpaired" } });
    renderOptions();

    const input = screen.getByLabelText(/backend URL/i, { selector: "input" });
    fireEvent.change(input, { target: { value: "http://evil.example.com:8100" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(await screen.findByText(/Insecure backend URL/)).toBeInTheDocument();
  });

  it("saves a localhost http:// URL without error", async () => {
    installChrome({ HEALTH: { ok: false, state: "unpaired" } });
    renderOptions();

    const input = screen.getByLabelText(/backend URL/i, { selector: "input" });
    fireEvent.change(input, { target: { value: "http://localhost:8100" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(screen.getByText(/Backend URL saved/)).toBeInTheDocument());
    expect(screen.queryByText(/Insecure/)).not.toBeInTheDocument();
  });
});
