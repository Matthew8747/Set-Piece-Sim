import type { ScenarioDTO } from "@restart/shared-types";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ComparePanel } from "./ComparePanel";

afterEach(() => {
  vi.restoreAllMocks();
});

const scenarioA = {
  scenario_id: "abc",
  name: "Near post",
  spec: { routine_id: "r1", scheme_id: "zonal" },
  scenario_hash: "hashA",
} as unknown as ScenarioDTO;

const scenarioB = {
  scenario_id: "def",
  name: "Back post",
  spec: { routine_id: "r2", scheme_id: "zonal" },
  scenario_hash: "hashB",
} as unknown as ScenarioDTO;

function runWith(scenarioId: string, samples: number[]) {
  return {
    run_id: `run-${scenarioId}`,
    scenario_id: scenarioId,
    status: "complete",
    progress: 1,
    n_sims: samples.length,
    root_seed: 7,
    engine_version: "sim/0.4.0",
    created_at: "2026-06-20T00:00:00Z",
    result: { xg_samples: samples, mean_xg: 0, replay_seeds: {} },
  };
}

/** Stub fetch: GET /scenarios → [A, B]; POST /sim-runs → samples keyed by scenario. */
function stubFetch(samplesById: Record<string, number[]>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/scenarios") && (!init || init.method !== "POST")) {
        return new Response(JSON.stringify([scenarioA, scenarioB]), { status: 200 });
      }
      if (url.includes("/sim-runs") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as { scenario_id: string };
        return new Response(
          JSON.stringify(runWith(body.scenario_id, samplesById[body.scenario_id]!)),
          {
            status: 200,
          },
        );
      }
      throw new Error(`unexpected ${url}`);
    }),
  );
}

test("declares a winner only on a separated paired difference", async () => {
  stubFetch({ abc: Array(80).fill(0.1), def: Array(80).fill(0.02) });
  render(<ComparePanel scenarioA={scenarioA} />);

  fireEvent.click(await screen.findByRole("button", { name: /compare/i }));

  const badge = await screen.findByTestId("winner-badge");
  // A (Near post) beats B by +0.08 xG with a CI clear of zero.
  expect(badge.textContent).toMatch(/Near post wins/i);
});

test("withholds a winner when the CI spans zero", async () => {
  // Perfectly paired-equal samples → mean difference 0, CI on 0 → no winner.
  stubFetch({ abc: [0.1, 0.0, 0.2, 0.05], def: [0.1, 0.0, 0.2, 0.05] });
  render(<ComparePanel scenarioA={scenarioA} />);

  fireEvent.click(await screen.findByRole("button", { name: /compare/i }));

  await waitFor(() => expect(screen.getByTestId("no-winner")).toBeDefined());
  expect(screen.queryByTestId("winner-badge")).toBeNull();
});
