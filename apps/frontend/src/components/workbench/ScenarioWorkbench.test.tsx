import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ScenarioWorkbench } from "./ScenarioWorkbench";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

afterEach(() => {
  vi.restoreAllMocks();
});

function stubApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/scenarios/")) {
        return json({
          scenario_id: "abc",
          name: "England near-post",
          spec: {
            routine_id: "near_post",
            scheme_id: "zonal",
            attacking_team_id: "england",
            defending_team_id: "argentina",
          },
          scenario_hash: "deadbeef",
          created_at: "2026-06-17T00:00:00Z",
        });
      }
      if (url.endsWith("/routines"))
        return json([{ routine_id: "near_post", name: "Near post", set_piece: "corner" }]);
      if (url.endsWith("/schemes")) return json([{ scheme_id: "zonal", name: "Zonal 6+2" }]);
      if (url.includes("/teams"))
        return json([
          { team_id: "england", name: "England", country: "England", n_players: 11 },
          { team_id: "argentina", name: "Argentina", country: "Argentina", n_players: 11 },
        ]);
      if (url.includes("/players")) return json([]);
      throw new Error(`unexpected ${url}`);
    }),
  );
}

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200 });
}

test("loads the scenario and starts in Build", async () => {
  stubApi();
  render(<ScenarioWorkbench scenarioId="abc" />);
  await waitFor(() => expect(screen.getByText("England near-post")).toBeDefined());
  expect(screen.getByRole("button", { name: /save as new scenario/i })).toBeDefined();
});

test("B/S/R keys switch modes", async () => {
  stubApi();
  render(<ScenarioWorkbench scenarioId="abc" />);
  await waitFor(() => expect(screen.getByText("England near-post")).toBeDefined());

  fireEvent.keyDown(document.body, { key: "s" });
  expect(screen.getByRole("button", { name: /Run 200/i })).toBeDefined();

  fireEvent.keyDown(document.body, { key: "r" });
  expect(screen.getByText(/run a simulation first/i)).toBeDefined();

  fireEvent.keyDown(document.body, { key: "b" });
  expect(screen.getByRole("button", { name: /save as new scenario/i })).toBeDefined();
});

test("mode buttons switch modes too", async () => {
  stubApi();
  render(<ScenarioWorkbench scenarioId="abc" />);
  await waitFor(() => expect(screen.getByText("England near-post")).toBeDefined());
  fireEvent.click(screen.getByRole("button", { name: /^Simulate/ }));
  expect(screen.getByRole("button", { name: /Run 200/i })).toBeDefined();
});
