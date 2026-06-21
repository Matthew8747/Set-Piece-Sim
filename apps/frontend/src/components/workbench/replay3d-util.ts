// Pure geometry + camera math for the 3D replay, kept out of the R3F component
// so it is unit-testable without a WebGL context. World is 105×68 m, attack
// toward +x, goal at x = +52.5 (same truth as pitch-kit geometry). We map to a
// scene where the goal sits at z = 0 and play arrives from +z; world width
// (y) is scene x; ball height (z) is scene y.

import { GOAL_LINE_X } from "@restart/pitch-kit";

export type Vec3 = [number, number, number];

/** World `[x, y(, z)]` → scene `[x, y, z]`. Tracks are 2D (height 0); the ball
 *  carries its z (flight height), so the arc is real, not faked. */
export function worldToScene(point: readonly number[]): Vec3 {
  const x = point[0] ?? 0;
  const y = point[1] ?? 0;
  const z = point[2] ?? 0;
  return [y, z, GOAL_LINE_X - x];
}

/** Normalized progress [0,1] → a clamped frame index into a track of `count`. */
export function frameIndex(progress: number, count: number): number {
  if (count <= 0) return 0;
  const i = Math.round(progress * (count - 1));
  return Math.max(0, Math.min(count - 1, i));
}

export type CameraPreset = "broadcast" | "behind-goal" | "gk";

export interface CameraView {
  position: Vec3;
  target: Vec3;
}

// Camera presets (doc 07 §3): broadcast (high angled), behind-goal, GK-eye.
// Targets sit just in front of the goal mouth where corner contact happens.
export const CAMERA_PRESETS: Record<CameraPreset, CameraView> = {
  broadcast: { position: [22, 20, 30], target: [0, 1, 8] },
  "behind-goal": { position: [0, 7, -14], target: [0, 1.5, 10] },
  gk: { position: [0, 1.8, 1], target: [0, 2.5, 16] },
};
