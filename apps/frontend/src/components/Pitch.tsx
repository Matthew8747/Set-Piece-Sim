"use client";

import type { SimulateResponse } from "@restart/shared-types";
import { useEffect, useMemo, useRef, useState } from "react";

/**
 * Goal-end 2D pitch view for corner replay (design doc 07: one canonical SVG
 * pitch, world = 105x68 m, origin centre, attack toward +x).
 *
 * Screen mapping (looking at the attacked goal from above, goal at top):
 *   sx = (world_y + 34) * S      touchline -> touchline (68 m wide)
 *   sy = (52.5 - world_x) * S    goal line (top) down to ~26 m out
 */
const S = 8; // px per metre
const X_MIN = 26;
const PITCH_W = 68 * S;
const PITCH_H = (52.5 - X_MIN) * S;

function sx(worldY: number): number {
  return (worldY + 34) * S;
}
function sy(worldX: number): number {
  return (52.5 - worldX) * S;
}

export function Pitch({ result }: { result: SimulateResponse | null }) {
  const nTicks = result?.track_times_s.length ?? 0;
  // Initialised fresh each mount; Workbench remounts via `key` per new sim,
  // so no reset effect is needed (avoids setState-in-effect cascades).
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(result !== null);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    if (!playing || nTicks === 0) return;
    let last = performance.now();
    const tick = (now: number) => {
      if (now - last >= 50) {
        // ~20 fps replay (tracks are decimated to 10 Hz upstream)
        last = now;
        setFrame((f) => {
          if (f + 1 >= nTicks) {
            setPlaying(false);
            return f;
          }
          return f + 1;
        });
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current);
    };
  }, [playing, nTicks]);

  const ballPoint = useMemo(() => {
    if (!result || nTicks === 0) return null;
    // Map the replay frame onto the ball path samples by time fraction.
    const frac = nTicks > 1 ? frame / (nTicks - 1) : 0;
    const bi = Math.min(
      result.ball_path.length - 1,
      Math.round(frac * (result.ball_path.length - 1)),
    );
    return result.ball_path[bi] ?? null;
  }, [result, frame, nTicks]);

  return (
    <div className="flex flex-col gap-3">
      <svg
        viewBox={`-6 -6 ${PITCH_W + 12} ${PITCH_H + 12}`}
        className="w-full rounded-lg"
        style={{ background: "var(--color-surface-raised)" }}
        role="img"
        aria-label="Corner replay pitch view"
      >
        {/* pitch outline + goal-end markings */}
        <rect
          x={0}
          y={0}
          width={PITCH_W}
          height={PITCH_H}
          fill="none"
          stroke="var(--color-line)"
          strokeOpacity={0.35}
        />
        {/* penalty box: 40.32 wide, 16.5 deep from goal line */}
        <rect
          x={sx(-20.16)}
          y={sy(52.5)}
          width={40.32 * S}
          height={16.5 * S}
          fill="none"
          stroke="var(--color-line)"
          strokeOpacity={0.25}
        />
        {/* six-yard box: 18.32 wide, 5.5 deep */}
        <rect
          x={sx(-9.16)}
          y={sy(52.5)}
          width={18.32 * S}
          height={5.5 * S}
          fill="none"
          stroke="var(--color-line)"
          strokeOpacity={0.2}
        />
        {/* goal mouth (posts at y = +/- 3.66) */}
        <line
          x1={sx(-3.66)}
          y1={sy(52.5)}
          x2={sx(3.66)}
          y2={sy(52.5)}
          stroke="var(--color-line)"
          strokeWidth={3}
        />

        {/* ball flight path (faint) */}
        {result && (
          <polyline
            points={result.ball_path.map((p) => `${sx(p[1]!)},${sy(p[0]!)}`).join(" ")}
            fill="none"
            stroke="var(--color-signal)"
            strokeOpacity={0.3}
            strokeDasharray="2 3"
          />
        )}

        {/* defenders (amber) */}
        {result?.def_tracks[frame]?.map((p, i) => (
          <circle
            key={`d${i}`}
            cx={sx(p[1]!)}
            cy={sy(p[0]!)}
            r={4.5}
            fill="var(--color-warn)"
            fillOpacity={0.85}
          />
        ))}
        {/* attackers (signal green) */}
        {result?.att_tracks[frame]?.map((p, i) => (
          <circle key={`a${i}`} cx={sx(p[1]!)} cy={sy(p[0]!)} r={4.5} fill="var(--color-signal)" />
        ))}
        {/* ball */}
        {ballPoint && <circle cx={sx(ballPoint[1]!)} cy={sy(ballPoint[0]!)} r={3} fill="#ffffff" />}
      </svg>

      {nTicks > 0 && (
        <div className="flex items-center gap-3 font-mono text-xs">
          <button
            type="button"
            onClick={() => {
              if (frame + 1 >= nTicks) setFrame(0);
              setPlaying((p) => !p);
            }}
            className="rounded border border-(--color-signal)/40 px-3 py-1 text-(--color-signal)"
          >
            {playing ? "pause" : "play"}
          </button>
          <input
            type="range"
            min={0}
            max={nTicks - 1}
            value={frame}
            onChange={(e) => {
              setPlaying(false);
              setFrame(Number(e.target.value));
            }}
            className="flex-1"
            aria-label="Replay scrubber"
          />
          <span className="tabular-nums opacity-70">
            {(result?.track_times_s[frame] ?? 0).toFixed(2)}s
          </span>
        </div>
      )}
    </div>
  );
}
