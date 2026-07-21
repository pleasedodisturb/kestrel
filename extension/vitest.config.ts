import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

// Standalone vitest config (independent of the WXT/Vite build). We alias the WXT
// `#imports` virtual module to a tiny stub so background.ts can be imported and
// unit-tested without the full WXT runtime, and map the `@/` alias to the
// extension root to mirror tsconfig.
export default defineConfig({
  resolve: {
    alias: {
      "#imports": resolve(__dirname, "test/imports-stub.ts"),
      "@": resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["test/setup.ts"],
    include: ["__tests__/**/*.test.ts", "__tests__/**/*.test.tsx"],
  },
});
