"use client";

import type { ScenarioDTO } from "@restart/shared-types";
import { Histogram } from "@restart/pitch-kit";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { compareStats, type CompareResult } from "@/lib/compareStats";

// Compare two scenarios under COMMON RANDOM NUMBERS. Both runs use the same seed
// and n_sims, so sim i of each sees the identical per-sim seed (the montecarlo
// determinism contract) — the per-sim xG vectors are paired and the difference
// is signal, not seed luck. No winner is shown unless the paired-difference CI
// excludes zero (doc 07 §4 stats policy). Sharing one set of inputs for both
// runs makes the same-seed/same-n requirement structural, not a checkbox.

export interface ComparePanelProps {
  scenarioA: ScenarioDTO;
}

interface Outcome {
  cmp: CompareResult;
  meanA: number;
  meanB: number;
  samplesA: number[];
  samplesB: number[];
  nameB: string;
}

const fmt = (v: number) => v.toFixed(3);

export function ComparePanel({ scenarioA }: ComparePanelProps) {
  const [scenarios, setScenarios] = useState<ScenarioDTO[] | null>(null);
  const [bId, setBId] = useState<string>("");
  const [nSims, setNSims] = useState(200);
  const [seed, setSeed] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  useEffect(() => {
    api
      .scenarios()
      .then((all) => {
        const others = all.filter((s) => s.scenario_id !== scenarioA.scenario_id);
        setScenarios(others);
        setBId((prev) => prev || others[0]?.scenario_id || "");
      })
      .catch((e: unknown) => setError(String(e)));
  }, [scenarioA.scenario_id]);

  async function runOne(scenarioId: string): Promise<number[]> {
    const created = await api.createSimRun({
      scenario_id: scenarioId,
      n_sims: nSims,
      root_seed: seed,
    });
    const final = created.status === "complete" ? created : await api.pollSimRun(created.run_id);
    if (!final.result) throw new Error(`run for ${scenarioId} produced no result`);
    return final.result.xg_samples;
  }

  async function compare() {
    if (!bId) return;
    setBusy(true);
    setError(null);
    setOutcome(null);
    try {
      // Same seed + n_sims for both → common random numbers → paired samples.
      const [samplesA, samplesB] = await Promise.all([runOne(scenarioA.scenario_id), runOne(bId)]);
      const cmp = compareStats(samplesA, samplesB);
      const mean = (xs: number[]) => xs.reduce((s, x) => s + x, 0) / (xs.length || 1);
      const nameB = scenarios?.find((s) => s.scenario_id === bId)?.name ?? bId;
      setOutcome({ cmp, meanA: mean(samplesA), meanB: mean(samplesB), samplesA, samplesB, nameB });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const empty = scenarios !== null && scenarios.length === 0;

  // Shared x-domain so the two histograms are read off one scale (doc 07 §3).
  const domain: [number, number] | undefined = outcome
    ? [
        Math.min(...outcome.samplesA, ...outcome.samplesB),
        Math.max(...outcome.samplesA, ...outcome.samplesB),
      ]
    : undefined;

  return (
    <div className="flex flex-col gap-5">
      {empty ? (
        <p className="text-sm opacity-60">
          Save a second scenario to compare against — there is nothing to compare yet.
        </p>
      ) : (
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Scenario B
            <select
              value={bId}
              onChange={(e) => setBId(e.target.value)}
              className="w-64 rounded border border-(--color-line)/20 bg-(--color-surface-raised) px-2 py-1.5"
            >
              {scenarios?.map((s) => (
                <option key={s.scenario_id} value={s.scenario_id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Simulations
            <input
              type="number"
              min={1}
              max={2000}
              value={nSims}
              onChange={(e) => setNSims(Number(e.target.value))}
              className="w-28 rounded border border-(--color-line)/20 bg-(--color-surface-raised) px-2 py-1.5 font-mono"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Seed (shared)
            <input
              type="number"
              min={0}
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              className="w-28 rounded border border-(--color-line)/20 bg-(--color-surface-raised) px-2 py-1.5 font-mono"
            />
          </label>
          <button
            type="button"
            onClick={compare}
            disabled={busy || !bId}
            className="rounded bg-(--color-signal) px-4 py-2 font-medium text-black disabled:opacity-40"
          >
            {busy ? "running both…" : "Compare"}
          </button>
        </div>
      )}

      {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}

      {outcome && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3" data-testid="compare-verdict">
            <span className="font-mono text-sm tabular-nums">
              A − B = {outcome.cmp.meanDiff >= 0 ? "+" : ""}
              {fmt(outcome.cmp.meanDiff)} xG [{fmt(outcome.cmp.ciLo)}, {fmt(outcome.cmp.ciHi)}]
            </span>
            {outcome.cmp.significant ? (
              <span
                data-testid="winner-badge"
                className="rounded bg-(--color-signal)/15 px-2 py-0.5 text-xs font-medium text-(--color-signal)"
              >
                {outcome.cmp.meanDiff > 0 ? scenarioA.name : outcome.nameB} wins · 95% CI
              </span>
            ) : (
              <span
                data-testid="no-winner"
                className="rounded border border-(--color-line)/20 px-2 py-0.5 text-xs opacity-60"
              >
                no significant difference (CI spans 0)
              </span>
            )}
          </div>
          <p className="font-mono text-[10px] opacity-40">
            common random numbers · seed {seed} · n={outcome.cmp.n} paired sims · same per-sim seed
            stream
          </p>

          <div className="grid gap-6 sm:grid-cols-2">
            <figure className="flex flex-col gap-1">
              <figcaption className="font-mono text-xs opacity-60">
                A · {scenarioA.name} (mean {fmt(outcome.meanA)})
              </figcaption>
              <Histogram samples={outcome.samplesA} label="A xG per sim" domain={domain} />
            </figure>
            <figure className="flex flex-col gap-1">
              <figcaption className="font-mono text-xs opacity-60">
                B · {outcome.nameB} (mean {fmt(outcome.meanB)})
              </figcaption>
              <Histogram
                samples={outcome.samplesB}
                label="B xG per sim"
                color="var(--color-warn)"
                domain={domain}
              />
            </figure>
          </div>
        </div>
      )}
    </div>
  );
}
