import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 8101,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://localhost:8100",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.VITE_API_URL || "http://localhost:8100",
        changeOrigin: true,
      },
      "/docs": {
        target: process.env.VITE_API_URL || "http://localhost:8100",
        changeOrigin: true,
      },
      "/openapi.json": {
        target: process.env.VITE_API_URL || "http://localhost:8100",
        changeOrigin: true,
      },
    },
  },
});
