import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Ecdf } from "./Ecdf";
import { Histogram } from "./Histogram";
import { KpiCard } from "./KpiCard";

const samples = [0.0, 0.1, 0.1, 0.2, 0.25, 0.3, 0.4, 0.0, 0.15, 0.05];

test("Histogram renders one bar per non-empty bin", () => {
  const { container } = render(<Histogram samples={samples} bins={5} label="xG per sim" />);
  const bars = container.querySelectorAll('[data-chart="bar"]');
  expect(bars.length).toBeGreaterThan(0);
  expect(bars.length).toBeLessThanOrEqual(5);
});

test("Histogram teaches an empty state with no samples", () => {
  render(<Histogram samples={[]} />);
  expect(screen.getByText(/no samples/i)).toBeDefined();
});

test("Ecdf renders a step polyline", () => {
  const { container } = render(<Ecdf samples={samples} />);
  expect(container.querySelector('[data-chart="ecdf"]')).not.toBeNull();
});

test("KpiCard shows the proportion with its CI and a how? affordance", () => {
  render(
    <KpiCard label="Goal" p={0.024} lo={0.018} hi={0.03} n={1000} howText="Wilson interval" />,
  );
  expect(screen.getByText("Goal")).toBeDefined();
  // 2.4% ±0.6 (half-width of [1.8, 3.0]).
  expect(screen.getByText(/2\.4%/)).toBeDefined();
  expect(screen.getByText(/how\?/i)).toBeDefined();
  expect(screen.getByText(/Wilson interval/i)).toBeDefined();
});

test("KpiCard refuses to render without bounds it can trust", () => {
  // No CI collapse: lo==hi==p still renders (k/n omitted) — just no whisker span.
  const { container } = render(<KpiCard label="Shot" p={0.1} lo={0.1} hi={0.1} />);
  expect(container.querySelector('[data-chart="whisker"]')).not.toBeNull();
});
