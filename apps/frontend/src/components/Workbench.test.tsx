import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { Workbench } from "./Workbench";

afterEach(() => {
  vi.restoreAllMocks();
});

test("workbench loads the routine and scheme catalog on mount", async () => {
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/routines")) {
      return new Response(
        JSON.stringify([{ routine_id: "near_post", name: "Near post", set_piece: "corner" }]),
        { status: 200 },
      );
    }
    if (url.endsWith("/schemes")) {
      return new Response(JSON.stringify([{ scheme_id: "zonal", name: "Zonal 6+2" }]), {
        status: 200,
      });
    }
    throw new Error(`unexpected ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<Workbench />);

  await waitFor(() => {
    expect(screen.getByRole("option", { name: "Near post" })).toBeDefined();
  });
  expect(screen.getByRole("option", { name: "Zonal 6+2" })).toBeDefined();
  expect(screen.getByRole("button", { name: /Simulate one/ })).toBeDefined();
});
