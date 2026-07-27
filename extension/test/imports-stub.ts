// Test-only stub for WXT's `#imports` virtual module. In the real build WXT
// provides `defineBackground`; under vitest we only need the identity behaviour
// so importing background.ts does not require the WXT runtime. The registered
// callback is intentionally NOT invoked here — tests exercise `handleMessage`
// directly.
export function defineBackground<T>(main: T): T {
  return main;
}

// Identity stub for content-script entrypoints so `autolog.content.ts` can be
// imported to unit-test its exported pure helpers (the registered `main()` is
// never invoked under vitest).
export function defineContentScript<T>(def: T): T {
  return def;
}
