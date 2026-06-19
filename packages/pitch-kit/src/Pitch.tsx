"use client";

import type { ReactNode } from "react";

import {
  GOAL_LINE_X,
  PITCH_H,
  PITCH_W,
  PX_PER_M,
  screenX,
  screenY,
  type Frame,
  type Point,
} from "./geometry";

export interface PitchProps {
  /** Attacker tracks, shape (T, na): one frame per replay timestep. */
  attTracks?: readonly Frame[];
  /** Defender tracks, shape (T, nd). */
  defTracks?: readonly Frame[];
  /** Ball flight path samples `[x, y(, z)]` (its own sample rate). */
  ballPath?: readonly Point[];
  /** Controlled frame index into the tracks (the ReplayPlayer owns this). */
  frame?: number;
  /** SVG annotations drawn over the pitch (Build-mode handles, heat layers). */
  overlay?: ReactNode;
  ariaLabel?: string;
  className?: string;
}

// Penalty-area truth (doc 07): box 40.32 m wide × 16.5 m deep; six-yard box
// 18.32 × 5.5; goal mouth posts at ±3.66 m. All measured from the goal line.
function ballAt(
  ballPath: readonly Point[] | undefined,
  frame: number,
  nFrames: number,
): Point | null {
  if (!ballPath || ballPath.length === 0) return null;
  // Map the replay frame onto the ball samples by time fraction, since the ball
  // path is sampled independently of the (decimated) player tracks.
  const frac = nFrames > 1 ? frame / (nFrames - 1) : 1;
  const idx = Math.min(ballPath.length - 1, Math.round(frac * (ballPath.length - 1)));
  return ballPath[idx] ?? null;
}

export function Pitch({
  attTracks,
  defTracks,
  ballPath,
  frame = 0,
  overlay,
  ariaLabel = "Pitch view",
  className,
}: PitchProps) {
  const att = attTracks?.[frame];
  const def = defTracks?.[frame];
  const nFrames = Math.max(attTracks?.length ?? 0, defTracks?.length ?? 0);
  const ball = ballAt(ballPath, frame, nFrames);

  return (
    <svg
      viewBox={`-6 -6 ${PITCH_W + 12} ${PITCH_H + 12}`}
      className={className}
      style={{ background: "var(--color-surface-raised)" }}
      role="img"
      aria-label={ariaLabel}
    >
      {/* pitch outline */}
      <rect
        x={0}
        y={0}
        width={PITCH_W}
        height={PITCH_H}
        fill="none"
        stroke="var(--color-line)"
        strokeOpacity={0.35}
      />
      {/* penalty box */}
      <rect
        data-pitch="penalty-box"
        x={screenX(-20.16)}
        y={screenY(GOAL_LINE_X)}
        width={40.32 * PX_PER_M}
        height={16.5 * PX_PER_M}
        fill="none"
        stroke="var(--color-line)"
        strokeOpacity={0.25}
      />
      {/* six-yard box */}
      <rect
        data-pitch="six-yard-box"
        x={screenX(-9.16)}
        y={screenY(GOAL_LINE_X)}
        width={18.32 * PX_PER_M}
        height={5.5 * PX_PER_M}
        fill="none"
        stroke="var(--color-line)"
        strokeOpacity={0.2}
      />
      {/* goal mouth */}
      <line
        data-pitch="goal"
        x1={screenX(-3.66)}
        y1={screenY(GOAL_LINE_X)}
        x2={screenX(3.66)}
        y2={screenY(GOAL_LINE_X)}
        stroke="var(--color-line)"
        strokeWidth={3}
      />

      {/* ball flight path (faint) */}
      {ballPath && ballPath.length > 1 && (
        <polyline
          points={ballPath.map((p) => `${screenX(p[1] ?? 0)},${screenY(p[0] ?? 0)}`).join(" ")}
          fill="none"
          stroke="var(--color-signal)"
          strokeOpacity={0.3}
          strokeDasharray="2 3"
        />
      )}

      {/* defenders (amber) */}
      {def?.map((p, i) => (
        <circle
          key={`d${i}`}
          data-pitch="defender"
          cx={screenX(p[1] ?? 0)}
          cy={screenY(p[0] ?? 0)}
          r={4.5}
          fill="var(--color-warn)"
          fillOpacity={0.85}
        />
      ))}
      {/* attackers (signal green) */}
      {att?.map((p, i) => (
        <circle
          key={`a${i}`}
          data-pitch="attacker"
          cx={screenX(p[1] ?? 0)}
          cy={screenY(p[0] ?? 0)}
          r={4.5}
          fill="var(--color-signal)"
        />
      ))}
      {/* ball */}
      {ball && (
        <circle
          data-pitch="ball"
          cx={screenX(ball[1] ?? 0)}
          cy={screenY(ball[0] ?? 0)}
          r={3}
          fill="#ffffff"
        />
      )}

      {overlay}
    </svg>
  );
}
