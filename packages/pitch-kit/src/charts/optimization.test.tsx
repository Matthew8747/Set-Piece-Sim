import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { ConvergencePlot } from "./ConvergencePlot";
import { ParallelCoordinates, normAxis } from "./ParallelCoordinates";
import { TopKTable } from "./TopKTable";

const tpe = [
  { trial: 1, bestSoFar: 0.1 },
  { trial: 2, bestSoFar: 0.3 },
  { trial: 3, bestSoFar: 0.3 },
];
const random = [
  { trial: 1, bestSoFar: 0.05 },
  { trial: 2, bestSoFar: 0.2 },
  { trial: 3, bestSoFar: 0.2 },
];

test("ConvergencePlot draws a line per sampler plus a winner CI band", () => {
  const { container } = render(
    <ConvergencePlot
      tpe={tpe}
      random={random}
      baseline={{ mean: 0.15, ci: [0.12, 0.18] }}
      winnerCi={[0.26, 0.34]}
    />,
  );
  expect(container.querySelectorAll('[data-chart="convergence-line"]').length).toBe(2);
  expect(container.querySelector('[data-series="tpe"]')).not.toBeNull();
  expect(container.querySelector('[data-chart="baseline"]')).not.toBeNull();
  expect(container.querySelector('[data-chart="winner-band"]')).not.toBeNull();
});

test("ConvergencePlot teaches an empty state with no trials", () => {
  render(<ConvergencePlot tpe={[]} random={[]} baseline={{ mean: 0, ci: [0, 0] }} />);
  expect(screen.getByText(/no trials/i)).toBeDefined();
});

test("normAxis maps continuous domain ends to 0 and 1", () => {
  const axis = { name: "speed_ms", kind: "continuous" as const, domain: [20, 30], importance: 0.4 };
  expect(normAxis(axis, 20)).toBeCloseTo(0);
  expect(normAxis(axis, 30)).toBeCloseTo(1);
  expect(normAxis(axis, 25)).toBeCloseTo(0.5);
});

test("normAxis ladders a categorical axis by its category order", () => {
  const axis = {
    name: "delivery_type",
    kind: "categorical" as const,
    categories: ["inswinger", "floated", "driven"],
    importance: 0.1,
  };
  expect(normAxis(axis, "inswinger")).toBeCloseTo(0);
  expect(normAxis(axis, "driven")).toBeCloseTo(1);
  expect(normAxis(axis, "floated")).toBeCloseTo(0.5);
});

test("ParallelCoordinates draws one polyline per trial", () => {
  const axes = [
    { name: "speed_ms", kind: "continuous" as const, domain: [20, 30], importance: 0.4 },
    {
      name: "delivery_type",
      kind: "categorical" as const,
      categories: ["inswinger", "floated"],
      importance: 0.1,
    },
  ];
  const trials = [
    { params: { speed_ms: 22, delivery_type: "inswinger" }, value: 0.01 },
    { params: { speed_ms: 28, delivery_type: "floated" }, value: 0.03 },
  ];
  const { container } = render(<ParallelCoordinates trials={trials} axes={axes} />);
  expect(container.querySelectorAll('[data-chart="pc-trial"]').length).toBe(2);
  expect(container.querySelectorAll('[data-chart="pc-axis"]').length).toBe(2);
});

test("TopKTable flags a row that beats the baseline by non-overlapping CI", () => {
  const { container } = render(
    <TopKTable
      rows={[
        { label: "best", meanXg: 0.3, ciLo: 0.26, ciHi: 0.34 }, // lo 0.26 > baseline hi 0.18
        { label: "tie", meanXg: 0.16, ciLo: 0.14, ciHi: 0.2 }, // overlaps baseline
      ]}
      baseline={{ mean: 0.15, ci: [0.12, 0.18] }}
    />,
  );
  const beats = container.querySelectorAll('[data-beats="true"]');
  const ties = container.querySelectorAll('[data-beats="false"]');
  expect(beats.length).toBe(1);
  expect(ties.length).toBe(1);
});
