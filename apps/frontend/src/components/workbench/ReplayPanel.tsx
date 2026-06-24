"use client";

import type { SimulateResponse } from "@restart/shared-types";
import { Pitch, ReplayPlayer } from "@restart/pitch-kit";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

import type { CameraPreset } from "./replay3d-util";

// R3F + three load on demand only: the 3D view stays out of the default bundle,
// and 2D remains the default + the SVG-only fallback (doc 07 §5, ADR-008).
const Replay3D = dynamic(() => import("./Replay3D"), {
  ssr: false,
  loading: () => <p className="font-mono text-xs opacity-50">loading 3D…</p>,
});

export interface ReplayPanelProps {
  /** The completed sim run to replay; null until the user has simulated. */
  runId: string | null;
}

type Sample = "worst" | "median" | "best";
const SAMPLES: Sample[] = ["worst", "median", "best"];

type View = "2d" | "3d";
const PRESETS: { preset: CameraPreset; label: string }[] = [
  { preset: "broadcast", label: "broadcast" },
  { preset: "behind-goal", label: "behind goal" },
  { preset: "gk", label: "GK" },
];

export function ReplayPanel({ runId }: ReplayPanelProps) {
  const [sample, setSample] = useState<Sample>("median");
  const [view, setView] = useState<View>("2d");
  const [preset, setPreset] = useState<CameraPreset>("broadcast");
  const [reducedMotion, setReducedMotion] = useState(false);
  const [data, setData] = useState<SimulateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Guard: jsdom (and very old browsers) lack matchMedia — degrade to motion on.
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReducedMotion(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!runId) return;
    // Apply results only in the async callbacks (no synchronous setState in the
    // effect body — avoids cascading renders) and ignore a stale in-flight fetch
    // when the run or sample changes mid-request.
    let active = true;
    api
      .simRunEvents(runId, sample)
      .then((d) => {
        if (active) {
          setData(d);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (active) {
          setError(String(e));
          setData(null);
        }
      });
    return () => {
      active = false;
    };
  }, [runId, sample]);

  if (!runId) {
    return (
      <p className="card flex items-center gap-2 p-6 text-sm text-(--color-line)/60">
        Run a simulation first (press{" "}
        <kbd className="rounded bg-(--color-line)/8 px-1.5 py-0.5 font-mono text-[11px]">S</kbd>),
        then replay the worst / median / best delivery here.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <span className="text-sm opacity-60">Sample</span>
        <div className="flex gap-1">
          {SAMPLES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSample(s)}
              aria-pressed={s === sample}
              className={`rounded-md border px-3 py-1 font-mono text-xs transition-colors ${
                s === sample
                  ? "border-(--color-signal)/50 bg-(--color-signal)/10 text-(--color-signal)"
                  : "border-(--color-line)/15 text-(--color-line-muted) hover:border-(--color-line)/30 hover:text-(--color-line)"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        {data && (
          <span className="font-mono text-xs opacity-60">· {data.outcome.replace(/_/g, " ")}</span>
        )}
        <div className="ml-auto flex gap-1" role="group" aria-label="Replay view">
          {(["2d", "3d"] as View[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              aria-pressed={v === view}
              className={`rounded-md border px-3 py-1 font-mono text-xs transition-colors uppercase ${
                v === view
                  ? "border-(--color-signal)/50 bg-(--color-signal)/10 text-(--color-signal)"
                  : "border-(--color-line)/15 text-(--color-line-muted) hover:border-(--color-line)/30 hover:text-(--color-line)"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {view === "3d" && data && (
        <div className="flex items-center gap-2">
          <span className="text-sm opacity-60">Camera</span>
          <div className="flex gap-1">
            {PRESETS.map((p) => (
              <button
                key={p.preset}
                type="button"
                onClick={() => setPreset(p.preset)}
                aria-pressed={p.preset === preset}
                className={`rounded-md border px-3 py-1 font-mono text-xs transition-colors ${
                  p.preset === preset
                    ? "border-(--color-signal) text-(--color-signal)"
                    : "border-(--color-line)/20 opacity-70"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}

      {data && view === "2d" && (
        <ReplayPlayer
          frameCount={data.track_times_s.length}
          times={data.track_times_s}
          events={data.events.map((e) => ({ time_s: e.time_s, kind: e.kind }))}
        >
          {(frame) => (
            <Pitch
              ariaLabel={`Replay (${sample})`}
              attTracks={data.att_tracks}
              defTracks={data.def_tracks}
              ballPath={data.ball_path}
              frame={frame}
            />
          )}
        </ReplayPlayer>
      )}

      {data && view === "3d" && (
        <Replay3D data={data} preset={preset} reducedMotion={reducedMotion} />
      )}
    </div>
  );
}
