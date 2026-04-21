import "@testing-library/jest-dom/vitest";

// Node.js 25+ provides a built-in localStorage global where methods
// (clear, setItem, getItem, removeItem) are undefined. This conflicts
// with jsdom's proper Web Storage implementation. Polyfill the missing
// methods to ensure tests can use localStorage/sessionStorage normally.
if (
  typeof localStorage !== "undefined" &&
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
  typeof sessionStorage !== "undefined" &&
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
