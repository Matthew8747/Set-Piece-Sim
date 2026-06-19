import { render } from "@testing-library/react";
import { expect, test } from "vitest";

import { Pitch } from "./Pitch";
import type { Frame } from "./geometry";

// One timestep with three attackers and two defenders (world [x, y] metres).
const att: Frame[] = [
  [
    [48, -8],
    [50, 0],
    [49, 6],
  ],
];
const def: Frame[] = [
  [
    [52, -2],
    [51, 3],
  ],
];

test("renders a labelled pitch SVG with penalty geometry", () => {
  const { container } = render(<Pitch ariaLabel="Corner replay" />);
  const svg = container.querySelector("svg");
  expect(svg).not.toBeNull();
  expect(svg?.getAttribute("role")).toBe("img");
  expect(svg?.getAttribute("aria-label")).toBe("Corner replay");
  expect(svg?.getAttribute("viewBox")).toBeTruthy();
  // Goal mouth is the load-bearing penalty marking for a corner view.
  expect(container.querySelector('[data-pitch="goal"]')).not.toBeNull();
  expect(container.querySelector('[data-pitch="penalty-box"]')).not.toBeNull();
});

test("renders one marker per player at the given frame", () => {
  const { container } = render(<Pitch attTracks={att} defTracks={def} frame={0} />);
  expect(container.querySelectorAll('[data-pitch="attacker"]')).toHaveLength(3);
  expect(container.querySelectorAll('[data-pitch="defender"]')).toHaveLength(2);
});

test("renders a build overlay when provided", () => {
  const { getByTestId } = render(<Pitch overlay={<g data-testid="handle" />} />);
  expect(getByTestId("handle")).toBeDefined();
});
