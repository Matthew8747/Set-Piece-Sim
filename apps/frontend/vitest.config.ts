import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirror the "@/*" path alias from tsconfig.json (Vite doesn't read it).
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    // Globals are required for @testing-library/react's automatic DOM
    // cleanup between tests (it registers an afterEach hook).
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
