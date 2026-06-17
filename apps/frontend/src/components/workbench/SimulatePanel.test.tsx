import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { SimulatePanel } from "./SimulatePanel";

afterEach(() => {
  vi.restoreAllMocks();
});

const ci = (p: number) => ({ p, lo: p * 0.6, hi: p * 1.4, k: Math.round(p * 200), n: 200 });

const completedRun = {
  run_id: "run1",
  scenario_id: "abc",
  status: "complete",
  progress: 1,
  n_sims: 200,
  root_seed: 7,
  engine_version: "sim/0.4.0",
  created_at: "2026-06-17T00:00:00Z",
  result: {
    engine_version: "sim/0.4.0",
    root_seed: 7,
    n_sims: 200,
    p_goal: ci(0.05),
    p_shot: ci(0.3),
    p_header_shot: ci(0.18),
    p_first_contact_attack: ci(0.45),
    p_clearance: ci(0.4),
    p_possession_recovered: ci(0.25),
    outcome_counts: { goal: 10 },
    mean_xg: 0.12,
    n_xg_scored: 10,
    xg_model: "lgbm",
    xg_samples: [0, 0.05, 0.1, 0.2, 0.3, 0.0, 0.15],
    replay_seeds: { worst: 1, median: 2, best: 3 },
  },
};

test("running surfaces the determinism banner, KPI CIs, and distributions", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      // Idempotency-hit path: POST returns a completed run immediately.
      if (url.includes("/sim-runs") && init?.method === "POST") {
        return new Response(JSON.stringify(completedRun), { status: 200 });
      }
      throw new Error(`unexpected ${url}`);
    }),
  );

  const onComplete = vi.fn();
  const { container } = render(<SimulatePanel scenarioId="abc" onComplete={onComplete} />);

  fireEvent.click(screen.getByRole("button", { name: /Run 200/i }));

  // Determinism surfaced in mono (doc 07 §4).
  expect(await screen.findByTestId("determinism")).toHaveProperty(
    "textContent",
    "engine sim/0.4.0 · seed 7 · n=200",
  );
  // KPI with CI (anchored so it doesn't also match "25.0%").
  expect(screen.getByText("Goal")).toBeDefined();
  expect(screen.getByText(/^5\.0%/)).toBeDefined();
  // Distribution chart rendered from xg_samples.
  expect(container.querySelectorAll('[data-chart="bar"]').length).toBeGreaterThan(0);
  expect(onComplete).toHaveBeenCalledWith("run1", completedRun.result);
});
