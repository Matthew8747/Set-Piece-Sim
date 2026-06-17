/**
 * Pitch geometry + world→screen mapping (design doc 07: one canonical SVG
 * pitch, world = 105×68 m, origin centre, attack toward +x, goal at x = +52.5).
 *
 * The corner surface is a goal-end crop of the attacking third: looking at the
 * attacked goal from above (goal at the TOP), the length axis runs down the
 * screen and the width axis runs across it. Every track/ball point is
 * `[world_x, world_y(, z)]` — index 0 is the length axis, index 1 the width.
 */

export const PX_PER_M = 8; // px per metre — the only scale knob
export const GOAL_LINE_X = 52.5; // attacked goal line, in world metres
export const VIEW_X_MIN = 26; // crop the view to ~26 m out from goal
export const HALF_WIDTH = 34; // pitch is 68 m wide → ±34 m about centre

export const PITCH_W = 2 * HALF_WIDTH * PX_PER_M;
export const PITCH_H = (GOAL_LINE_X - VIEW_X_MIN) * PX_PER_M;

/** World width coordinate (`world_y`, −34..34) → screen x (touchline→touchline). */
export function screenX(worldY: number): number {
  return (worldY + HALF_WIDTH) * PX_PER_M;
}

/** World length coordinate (`world_x`, →52.5) → screen y (goal line at top). */
export function screenY(worldX: number): number {
  return (GOAL_LINE_X - worldX) * PX_PER_M;
}

/** Snap a metre value to the editor grid (doc 07: snap-to-grid 0.5 m). */
export function snap(value: number, grid = 0.5): number {
  return Math.round(value / grid) * grid;
}

export type Point = readonly number[]; // [x, y] or [x, y, z], world metres
export type Frame = readonly Point[]; // all players at one timestep
