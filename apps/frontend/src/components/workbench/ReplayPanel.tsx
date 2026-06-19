"use client";

import type { SimulateResponse } from "@restart/shared-types";
import { Pitch, ReplayPlayer } from "@restart/pitch-kit";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export interface ReplayPanelProps {
  /** The completed sim run to replay; null until the user has simulated. */
  runId: string | null;
}

type Sample = "worst" | "median" | "best";
const SAMPLES: Sample[] = ["worst", "median", "best"];

export function ReplayPanel({ runId }: ReplayPanelProps) {
  const [sample, setSample] = useState<Sample>("median");
  const [data, setData] = useState<SimulateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      <p className="text-sm opacity-50">
        Run a simulation first (press <kbd className="font-mono">S</kbd>), then replay the worst /
        median / best delivery here.
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
              className={`rounded border px-3 py-1 font-mono text-xs ${
                s === sample
                  ? "border-(--color-signal) text-(--color-signal)"
                  : "border-(--color-line)/20 opacity-70"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        {data && (
          <span className="font-mono text-xs opacity-60">· {data.outcome.replace(/_/g, " ")}</span>
        )}
      </div>

      {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}

      {data && (
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
    </div>
  );
}
