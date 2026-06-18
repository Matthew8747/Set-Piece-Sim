import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// Playwright loads this config as CommonJS, so use __dirname (not import.meta).
const frontendDir = __dirname;
const repoRoot = path.resolve(__dirname, "../..");
const isCI = !!process.env.CI;

/**
 * E2E boots BOTH servers as webServers: the FastAPI backend (test env,
 * in-process job queue — ADR-007 d2) and the Next dev server. The journey runs
 * at the reduced deterministic budget (n_sims=24, ~8 s) over the identical
 * build → run → distributions → replay path (throughput reality, ADR-007).
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: isCI ? 1 : 0,
  reporter: isCI ? "github" : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "uv run uvicorn restart_api.main:app --app-dir apps/backend/src --host 127.0.0.1 --port 8000",
      cwd: repoRoot,
      url: "http://127.0.0.1:8000/healthz",
      reuseExistingServer: !isCI,
      timeout: 120_000,
      env: {
        RESTART_APP_ENV: "test",
        // Isolate the E2E SQLite store from the developer's data dir.
        RESTART_DATA_DIR: ".e2e-data",
        // Generous write bucket so the scripted journey never trips the limiter.
        RESTART_RATE_LIMIT_WRITE: "200/minute",
      },
    },
    {
      command: "npm run dev",
      cwd: frontendDir,
      url: "http://localhost:3000",
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
  ],
});
