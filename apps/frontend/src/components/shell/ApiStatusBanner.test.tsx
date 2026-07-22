import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ApiStatusBanner } from "./ApiStatusBanner";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("stays invisible when the backend is healthy", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 })),
  );
  const { container } = render(<ApiStatusBanner />);
  // Give the mount probe a tick to resolve, then assert nothing rendered.
  await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  expect(container.textContent).toBe("");
});

test("explains an unreachable backend instead of failing silently", async () => {
  // A rejected fetch is exactly how a sleeping / undeployed backend surfaces.
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }),
  );
  render(<ApiStatusBanner />);
  const banner = await screen.findByRole("status", {}, { timeout: 3000 });
  expect(banner.textContent).toMatch(/backend isn.t reachable/i);
  // The visitor is given a way to re-check rather than reloading.
  expect(screen.getByRole("button", { name: /retry/i })).toBeDefined();
});
