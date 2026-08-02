/** Regression tests for the test-environment Web Storage shim (G-1427).
 *
 * Node 25+ ships an experimental webstorage global that shadows jsdom's
 * localStorage/sessionStorage; without the shim in test-setup.ts, every
 * component touching Web Storage fails on newer local Node versions while
 * CI (Node 22) stays green. These assertions pin that the environment
 * always provides a WORKING Storage, whatever Node exposes natively.
 */

import { describe, expect, it } from "vitest";

describe("vitest environment Web Storage (G-1427)", () => {
  it("localStorage supports the full round-trip", () => {
    localStorage.setItem("g1427-key", "value");
    expect(localStorage.getItem("g1427-key")).toBe("value");
    localStorage.removeItem("g1427-key");
    expect(localStorage.getItem("g1427-key")).toBeNull();
    localStorage.setItem("g1427-a", "1");
    localStorage.clear();
    expect(localStorage.getItem("g1427-a")).toBeNull();
  });

  it("sessionStorage supports the full round-trip", () => {
    sessionStorage.setItem("g1427-key", "value");
    expect(sessionStorage.getItem("g1427-key")).toBe("value");
    sessionStorage.clear();
    expect(sessionStorage.getItem("g1427-key")).toBeNull();
  });
});
