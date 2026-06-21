import { describe, expect, it } from "vitest";

import { CAMERA_PRESETS, frameIndex, worldToScene } from "./replay3d-util";

describe("replay3d-util", () => {
  it("maps the goal line to scene z=0 and width to scene x", () => {
    // A point on the goal line (x=52.5) at centre (y=0), on the ground (z=0).
    expect(worldToScene([52.5, 0, 0])).toEqual([0, 0, 0]);
    // 6 m out from goal, 4 m to the right, 2 m high.
    expect(worldToScene([46.5, 4, 2])).toEqual([4, 2, 6]);
  });

  it("treats a 2D track point as ground height 0", () => {
    expect(worldToScene([50, -3])).toEqual([-3, 0, 2.5]);
  });

  it("clamps frame index to the track bounds", () => {
    expect(frameIndex(0, 10)).toBe(0);
    expect(frameIndex(1, 10)).toBe(9);
    expect(frameIndex(0.5, 11)).toBe(5);
    expect(frameIndex(0.5, 0)).toBe(0); // empty track never indexes out of range
  });

  it("offers the three documented camera presets", () => {
    expect(Object.keys(CAMERA_PRESETS).sort()).toEqual(["behind-goal", "broadcast", "gk"]);
  });
});
