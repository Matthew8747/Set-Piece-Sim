import type { OptimizationDetail } from "@restart/shared-types";
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { InsightsPanel } from "./InsightsPanel";
import { SensitivityBanner } from "./SensitivityBanner";
import { StudyDetail } from "./StudyDetail";

const baseDetail: OptimizationDetail = {
  id: "england-vs-argentina",
  name: "England corners vs Argentina zonal",
  matchup: { attacking: "England", defending: "Argentina", scheme: "zonal" },
  engine_version: "sim/0.4.0",
  created_at: "2026-06-14T00:00:00Z",
  stale: false,
  convergence_tpe: [
    { trial: 1, best_so_far: 0.01 },
    { trial: 2, best_so_far: 0.03 },
  ],
  convergence_random: [
    { trial: 1, best_so_far: 0.008 },
    { trial: 2, best_so_far: 0.02 },
  ],
  baseline_mean_xg: 0.0104,
  baseline_ci: [0.0078, 0.013],
  trials: [
    { params: { speed_ms: 22, delivery_type: "inswinger" }, value: 0.01, state: "COMPLETE" },
    { params: { speed_ms: 28, delivery_type: "outswinger" }, value: 0.03, state: "COMPLETE" },
  ],
  axes: [
    { name: "speed_ms", kind: "continuous", domain: [22, 28], categories: null, importance: 0.4 },
    {
      name: "delivery_type",
      kind: "categorical",
      domain: null,
      categories: ["inswinger", "outswinger"],
      importance: 0.1,
    },
  ],
  confirm: [{ params: { speed_ms: 28 }, mean_xg: 0.025, ci_lo: 0.023, ci_hi: 0.027, n_sims: 400 }],
  feature_importance: { speed_ms: 0.4, delivery_type: 0.1 },
  insights: ["delivery_type=outswinger is the strongest setting for mean xG (SHAP 0.005)."],
  sensitivity: {
    verdict: "report-routine-classes",
    top1_stable: false,
    rankings_flip: true,
    flipped: ["+10%"],
  },
  winner: {
    mean_xg: 0.0327,
    ci: [0.0327, 0.0295, 0.036],
    beats_baseline: true,
    boundary_flags: ["target_y"],
    face_validity_flags: [],
  },
};

test("SensitivityBanner reports routine classes when the ranking flips", () => {
  render(<SensitivityBanner sensitivity={baseDetail.sensitivity} />);
  const banner = screen.getByTestId("sensitivity-banner");
  expect(banner.getAttribute("data-flip")).toBe("true");
  expect(banner.textContent).toMatch(/routine classes/i);
});

test("SensitivityBanner reports routine-precise when nothing flips", () => {
  render(
    <SensitivityBanner
      sensitivity={{ ...baseDetail.sensitivity, rankings_flip: false, top1_stable: true }}
    />,
  );
  const banner = screen.getByTestId("sensitivity-banner");
  expect(banner.getAttribute("data-flip")).toBe("false");
  expect(banner.textContent).toMatch(/routine-precise/i);
});

test("InsightsPanel renders plain-language findings with a how? link", () => {
  render(<InsightsPanel insights={baseDetail.insights} />);
  expect(screen.getByText(/outswinger is the strongest/i)).toBeDefined();
  expect(screen.getByText(/how\?/i)).toBeDefined();
});

test("StudyDetail shows a beats-baseline badge and the search-space view", () => {
  const { container } = render(<StudyDetail detail={baseDetail} />);
  expect(screen.getByTestId("beats-badge")).toBeDefined();
  // Convergence + parallel-coords primitives rendered from the study.
  expect(container.querySelectorAll('[data-chart="convergence-line"]').length).toBe(2);
  expect(container.querySelectorAll('[data-chart="pc-trial"]').length).toBe(2);
});

test("StudyDetail withholds the badge when the winner has no significant edge", () => {
  render(
    <StudyDetail
      detail={{ ...baseDetail, winner: { ...baseDetail.winner, beats_baseline: false } }}
    />,
  );
  expect(screen.queryByTestId("beats-badge")).toBeNull();
  expect(screen.getByTestId("no-sig-badge")).toBeDefined();
});
