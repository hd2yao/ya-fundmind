/// <reference types="vitest/config" />

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8768"
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: true
  },
  build: {
    outDir: "../fund_agent/web_static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/recharts/") || id.includes("/node_modules/d3-")) {
            return "charts";
          }
          if (id.includes("/node_modules/lucide-react/")) {
            return "icons";
          }
          if (
            id.includes("/node_modules/react/") ||
            id.includes("/node_modules/react-dom/") ||
            id.includes("/node_modules/react-router")
          ) {
            return "react";
          }
          return undefined;
        }
      }
    }
  }
});
