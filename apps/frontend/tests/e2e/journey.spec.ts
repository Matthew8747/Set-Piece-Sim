import { expect, test } from "@playwright/test";

/**
 * The 3-minute reviewer journey (PRD §6), at the reduced deterministic budget
 * (n_sims=24 — ADR-007 throughput reality): build → run → distributions →
 * replay, end to end against the real backend + real squads.
 */
test("build → simulate (24) → distributions → replay", async ({ page }) => {
  // Library → create the canonical scenario and land in its workbench.
  await page.goto("/scenarios");
  await page.getByRole("button", { name: /new scenario/i }).click();
  await expect(page).toHaveURL(/\/scenarios\/[\w-]+$/);

  // Build mode is the entry point.
  await expect(page.getByRole("button", { name: /save as new scenario/i })).toBeVisible();

  // Simulate at the reduced budget.
  await page.getByRole("button", { name: /^Simulate/ }).click();
  await page.getByLabel("Simulations").fill("24");
  await page.getByRole("button", { name: /Run 24/ }).click();

  // Distributions render with the determinism banner (seed + n surfaced).
  const banner = page.getByTestId("determinism");
  await expect(banner).toContainText("n=24", { timeout: 60_000 });
  await expect(banner).toContainText("seed");
  await expect(page.getByText("Goal", { exact: true })).toBeVisible();
  await expect(page.locator('[data-chart="bar"]').first()).toBeVisible();

  // Replay the median sample; the scrubber advances.
  await page.getByRole("button", { name: /^Replay/ }).click();
  const scrubber = page.getByRole("slider", { name: "Replay scrubber" });
  await expect(scrubber).toBeVisible({ timeout: 30_000 });
  await expect(scrubber).toHaveValue("0");
  await page.getByRole("group", { name: "Replay" }).press("ArrowRight");
  await expect(scrubber).not.toHaveValue("0");
});
