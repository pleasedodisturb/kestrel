import "@testing-library/jest-dom/vitest";

// Node.js 25+ ships an experimental webstorage global that shadows jsdom's
// proper Web Storage implementation. Its shape varies by Node version:
// Node 25 exposes a localStorage object whose methods (clear, setItem,
// getItem, removeItem) are undefined; Node 26 exposes a getter that
// evaluates to `undefined` entirely (unless --localstorage-file is set),
// while still occupying the global so jsdom's version never installs
// (G-1427). Polyfill whenever a WORKING Storage is absent, covering both
// shapes.
if (
  typeof localStorage === "undefined" ||
  typeof localStorage.clear !== "function"
) {
  const store = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, String(value)),
      removeItem: (key: string) => store.delete(key),
      clear: () => store.clear(),
      get length() {
        return store.size;
      },
      key: (index: number) => [...store.keys()][index] ?? null,
    },
    writable: true,
    configurable: true,
  });
}

if (
  typeof sessionStorage === "undefined" ||
  typeof sessionStorage.clear !== "function"
) {
  const store = new Map<string, string>();
  Object.defineProperty(globalThis, "sessionStorage", {
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, String(value)),
      removeItem: (key: string) => store.delete(key),
      clear: () => store.clear(),
      get length() {
        return store.size;
      },
      key: (index: number) => [...store.keys()][index] ?? null,
    },
    writable: true,
    configurable: true,
  });
}
