import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import ScenariosPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

afterEach(() => {
  vi.restoreAllMocks();
});

function stubScenarios(list: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/scenarios")) return new Response(JSON.stringify(list), { status: 200 });
      throw new Error(`unexpected ${url}`);
    }),
  );
}

test("empty store teaches and offers a new scenario", async () => {
  stubScenarios([]);
  render(<ScenariosPage />);
  expect(screen.getByRole("heading", { level: 1, name: /scenarios/i })).toBeDefined();
  expect(screen.getByRole("button", { name: /new scenario/i })).toBeDefined();
  await waitFor(() => {
    expect(screen.getByText(/canonical WC2026/i)).toBeDefined();
  });
});

test("lists persisted scenarios linking to the workbench", async () => {
  stubScenarios([
    {
      scenario_id: "abc",
      name: "England near-post",
      spec: { routine_id: "near_post", scheme_id: "zonal" },
      scenario_hash: "deadbeef",
      created_at: "2026-06-17T00:00:00Z",
    },
  ]);
  render(<ScenariosPage />);
  const link = await screen.findByRole("link", { name: /England near-post/i });
  expect(link.getAttribute("href")).toBe("/scenarios/abc");
});
