"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

export interface ReplayEvent {
  time_s: number;
  kind: string;
}

export interface ReplayPlayerProps {
  /** Number of replay frames (length of the player tracks). */
  frameCount: number;
  /** Per-frame timestamps (seconds), for the readout + event marker mapping. */
  times?: readonly number[];
  /** Discrete events (kick/contact/shot) marked on the scrubber. */
  events?: readonly ReplayEvent[];
  /** Replay cadence; tracks are decimated to ~10 Hz upstream. */
  fps?: number;
  autoPlay?: boolean;
  onFrame?: (frame: number) => void;
  /** Render-prop: draw the scene (e.g. a Pitch) at the current frame. */
  children: (frame: number) => ReactNode;
}

// Replay easing = simulation kinematics, never decorative tweening (doc 07 §1).
// Reduced-motion users get step mode (no auto-advance) per doc 07 §5.
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);
  return reduced;
}

function nearestFrame(times: readonly number[] | undefined, t: number): number {
  if (!times || times.length === 0) return 0;
  let best = 0;
  let bestErr = Infinity;
  for (let i = 0; i < times.length; i++) {
    const err = Math.abs((times[i] ?? 0) - t);
    if (err < bestErr) {
      bestErr = err;
      best = i;
    }
  }
  return best;
}

export function ReplayPlayer({
  frameCount,
  times,
  events,
  fps = 20,
  autoPlay = false,
  onFrame,
  children,
}: ReplayPlayerProps) {
  const reduced = usePrefersReducedMotion();
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(autoPlay && frameCount > 1);

  // Keep the latest onFrame without retriggering the effect each render.
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;
  useEffect(() => {
    onFrameRef.current?.(frame);
  }, [frame]);

  // Reduced motion forces step mode — never auto-advance.
  const canAutoPlay = !reduced;
  useEffect(() => {
    if (reduced && playing) setPlaying(false);
  }, [reduced, playing]);

  useEffect(() => {
    if (!playing || frameCount <= 1) return;
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      if (now - last >= 1000 / fps) {
        last = now;
        setFrame((f) => {
          if (f + 1 >= frameCount) {
            setPlaying(false);
            return f;
          }
          return f + 1;
        });
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, frameCount, fps]);

  const last = frameCount > 0 ? frameCount - 1 : 0;
  const lastTime = times && times.length > 0 ? (times[times.length - 1] ?? 0) : 0;

  function scrubTo(f: number) {
    setPlaying(false);
    setFrame(Math.max(0, Math.min(last, f)));
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === " " || e.code === "Space") {
      e.preventDefault();
      if (canAutoPlay) {
        // Replaying from the end restarts the clip.
        if (frame >= last) setFrame(0);
        setPlaying((p) => !p);
      }
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      scrubTo(frame + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      scrubTo(frame - 1);
    }
  }

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <div
      role="group"
      aria-label="Replay"
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="flex flex-col gap-3 outline-none"
    >
      {children(frame)}

      <div className="flex items-center gap-3 font-mono text-xs">
        {canAutoPlay ? (
          <button
            type="button"
            onClick={() => {
              if (frame >= last) setFrame(0);
              setPlaying((p) => !p);
            }}
            className="rounded border border-(--color-signal)/40 px-3 py-1 text-(--color-signal)"
          >
            {playing ? "pause" : "play"}
          </button>
        ) : (
          <div className="flex gap-1">
            <button
              type="button"
              aria-label="step back"
              onClick={() => scrubTo(frame - 1)}
              className="rounded border border-(--color-signal)/40 px-2 py-1 text-(--color-signal)"
            >
              ←
            </button>
            <button
              type="button"
              aria-label="step forward"
              onClick={() => scrubTo(frame + 1)}
              className="rounded border border-(--color-signal)/40 px-2 py-1 text-(--color-signal)"
            >
              →
            </button>
          </div>
        )}

        {/* scrubber + event markers */}
        <div className="relative flex-1">
          <input
            type="range"
            min={0}
            max={last}
            value={frame}
            onChange={(e) => scrubTo(Number(e.target.value))}
            className="w-full"
            aria-label="Replay scrubber"
          />
          {events && lastTime > 0 && (
            <div className="pointer-events-none absolute inset-x-0 top-0 h-full">
              {events.map((ev, i) => (
                <button
                  key={`${ev.kind}-${i}`}
                  type="button"
                  aria-label={`${ev.kind} at ${ev.time_s.toFixed(2)}s`}
                  title={`${ev.kind} · ${ev.time_s.toFixed(2)}s`}
                  onClick={() => scrubTo(nearestFrame(times, ev.time_s))}
                  className="pointer-events-auto absolute top-0 h-2 w-0.5 -translate-x-1/2 bg-(--color-warn)"
                  style={{ left: `${(ev.time_s / lastTime) * 100}%` }}
                />
              ))}
            </div>
          )}
        </div>

        <span className="tabular-nums opacity-70">{(times?.[frame] ?? 0).toFixed(2)}s</span>
      </div>
    </div>
  );
}
