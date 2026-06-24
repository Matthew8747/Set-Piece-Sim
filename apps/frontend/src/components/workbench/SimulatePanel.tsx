"use client";

import type { ProportionCI, SimRunResult, SimRunStatus } from "@restart/shared-types";
import { Ecdf, Histogram, KpiCard } from "@restart/pitch-kit";
import { useState } from "react";

import { api } from "@/lib/api";

import { DeterminismBanner } from "./DeterminismBanner";

export interface SimulatePanelProps {
  scenarioId: string;
  /** Lift the completed run so Replay can fetch its representative trajectories. */
  onComplete: (runId: string, result: SimRunResult) => void;
}

const METRICS: { key: keyof SimRunResult; label: string; how: string }[] = [
  { key: "p_goal", label: "Goal", how: "Share of sims ending in a goal; Wilson 95% interval." },
  { key: "p_shot", label: "Shot", how: "Share of sims producing a shot attempt." },
  { key: "p_header_shot", label: "Header shot", how: "Shots taken with the head." },
  {
    key: "p_first_contact_attack",
    label: "Attack 1st contact",
    how: "Attacker wins the first contact on the delivery.",
  },
  { key: "p_clearance", label: "Cleared", how: "Defence clears the set-piece." },
  {
    key: "p_possession_recovered",
    label: "Possession kept",
    how: "Attacking team retains possession after the phase.",
  },
];

export function SimulatePanel({ scenarioId, onComplete }: SimulatePanelProps) {
  const [nSims, setNSims] = useState(200);
  const [seed, setSeed] = useState(7);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SimRunStatus | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    setProgress(0);
    setStatus(null);
    try {
      const created = await api.createSimRun({
        scenario_id: scenarioId,
        n_sims: nSims,
        root_seed: seed,
      });
      // An idempotency hit returns 200 + a completed run immediately; otherwise
      // poll the queued/running job to completion (ADR-007 d3/d4).
      const final =
        created.status === "complete"
          ? created
          : await api.pollSimRun(created.run_id, (s) => setProgress(s.progress));
      setProgress(1);
      setStatus(final);
      if (final.result) onComplete(final.run_id, final.result);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const result = status?.result ?? null;

  return (
    <div className="flex flex-col gap-5">
      <div className="card flex flex-wrap items-end gap-4 p-4">
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-mono text-[11px] tracking-widest text-(--color-line-muted) uppercase">
            Simulations
          </span>
          <input
            type="number"
            min={1}
            max={2000}
            value={nSims}
            onChange={(e) => setNSims(Number(e.target.value))}
            className="w-28 rounded-lg border border-(--color-line)/15 bg-(--color-surface) px-3 py-2 font-mono tabular-nums transition-colors focus:border-(--color-signal)/50"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-mono text-[11px] tracking-widest text-(--color-line-muted) uppercase">
            Seed
          </span>
          <input
            type="number"
            min={0}
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
            className="w-28 rounded-lg border border-(--color-line)/15 bg-(--color-surface) px-3 py-2 font-mono tabular-nums transition-colors focus:border-(--color-signal)/50"
          />
        </label>
        <button type="button" onClick={run} disabled={busy} className="btn btn-primary ml-auto">
          {busy ? "running…" : `Run ${nSims}×`}
        </button>
      </div>

      {busy && (
        <div className="flex flex-col gap-1">
          <div className="h-1.5 w-full overflow-hidden rounded bg-(--color-line)/10">
            <div
              className="h-full bg-(--color-signal) transition-[width]"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
          <span className="font-mono text-xs opacity-60">{Math.round(progress * 100)}%</span>
        </div>
      )}
      {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}

      {status && result && (
        <div className="flex flex-col gap-5">
          <DeterminismBanner
            engineVersion={status.engine_version}
            seed={status.root_seed}
            nSims={status.n_sims}
          />

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {METRICS.map((m) => {
              const ci = result[m.key] as ProportionCI;
              return (
                <KpiCard
                  key={m.key}
                  label={m.label}
                  p={ci.p}
                  lo={ci.lo}
                  hi={ci.hi}
                  k={ci.k}
                  n={ci.n}
                  howText={m.how}
                />
              );
            })}
          </div>

          <div className="grid gap-6 sm:grid-cols-2">
            <figure className="flex flex-col gap-1">
              <figcaption className="font-mono text-xs opacity-60">
                xG per sim · histogram (mean {result.mean_xg.toFixed(3)})
              </figcaption>
              <Histogram samples={result.xg_samples} label="xG per sim" />
            </figure>
            <figure className="flex flex-col gap-1">
              <figcaption className="font-mono text-xs opacity-60">xG per sim · ECDF</figcaption>
              <Ecdf samples={result.xg_samples} label="xG per sim" />
            </figure>
          </div>
        </div>
      )}
    </div>
  );
}
