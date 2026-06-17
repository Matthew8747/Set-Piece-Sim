import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    // Globals enable @testing-library/react's automatic DOM cleanup between
    // tests (it registers an afterEach hook) — same setup as the frontend.
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
