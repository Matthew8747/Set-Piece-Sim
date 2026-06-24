"use client";

import type { OptimizationDetail } from "@restart/shared-types";
import {
  ConvergencePlot,
  ParallelCoordinates,
  TopKTable,
  type PcAxis,
  type PcTrial,
} from "@restart/pitch-kit";

import { InsightsPanel } from "./InsightsPanel";
import { SensitivityBanner } from "./SensitivityBanner";

// The /optimize/:id surface: convergence, the parallel-coordinates "wow" view,
// the SHAP insights panel, the sensitivity honesty banner, and the top-k vs
// baseline table — all over the persisted study, derived server-side.

export interface StudyDetailProps {
  detail: OptimizationDetail;
}

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

export function StudyDetail({ detail }: StudyDetailProps) {
  const tpe = detail.convergence_tpe.map((p) => ({ trial: p.trial, bestSoFar: p.best_so_far }));
  const random = detail.convergence_random.map((p) => ({
    trial: p.trial,
    bestSoFar: p.best_so_far,
  }));
  // winner.ci is [mean, lo, hi]; the convergence band wants [lo, hi].
  const winnerCi: [number, number] | undefined =
    detail.winner.ci.length >= 3 ? [detail.winner.ci[1]!, detail.winner.ci[2]!] : undefined;

  const axes: PcAxis[] = detail.axes.map((a) => ({
    name: a.name,
    kind: a.kind,
    domain: a.domain ?? undefined,
    categories: a.categories ?? undefined,
    importance: a.importance,
  }));
  const trials: PcTrial[] = detail.trials.map((t) => ({ params: t.params, value: t.value }));

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-(--color-line)/10 pb-6">
        <div className="flex flex-col gap-2">
          <span className="font-mono text-[11px] tracking-widest text-(--color-line-muted) uppercase">
            Study
          </span>
          <h1 className="text-3xl font-semibold tracking-tight">{detail.name}</h1>
          <p className="text-sm text-(--color-line)/60">
            {detail.matchup.attacking} attacking · {detail.matchup.defending}{" "}
            {detail.matchup.scheme} defense
          </p>
        </div>
        <div className="card flex flex-col items-end gap-1 px-4 py-3">
          <span className="font-mono text-[10px] tracking-widest text-(--color-line-muted) uppercase">
            winner mean xG
          </span>
          <div className="flex items-center gap-2">
            <span className="font-mono text-2xl tabular-nums">{pct(detail.winner.mean_xg)}</span>
            {detail.winner.beats_baseline ? (
              <span
                data-testid="beats-badge"
                className="rounded-md bg-(--color-signal)/15 px-2 py-0.5 text-xs font-medium text-(--color-signal)"
              >
                beats baseline
              </span>
            ) : (
              <span
                data-testid="no-sig-badge"
                className="rounded-md border border-(--color-line)/20 px-2 py-0.5 text-xs text-(--color-line)/60"
              >
                no significant edge
              </span>
            )}
          </div>
          <span className="font-mono text-[10px] text-(--color-line)/40">
            {detail.engine_version} · {detail.trials.length} trials
            {detail.stale ? " · ⚠ engine drift" : ""}
          </span>
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card flex flex-col gap-3 p-5">
          <h3 className="text-sm font-semibold tracking-tight">Convergence (best-so-far)</h3>
          <ConvergencePlot
            tpe={tpe}
            random={random}
            baseline={{
              mean: detail.baseline_mean_xg,
              ci: [detail.baseline_ci[0]!, detail.baseline_ci[1]!],
            }}
            winnerCi={winnerCi}
          />
          <p className="font-mono text-[10px] opacity-40">
            <span className="text-(--color-signal)">TPE</span> vs{" "}
            <span className="opacity-70">random</span> · dashed = library baseline · band = winner
            95% CI
          </p>
        </div>
        <InsightsPanel insights={detail.insights} />
      </section>

      <section className="card flex flex-col gap-3 p-5">
        <h3 className="text-sm font-semibold tracking-tight">Search space (every trial)</h3>
        <ParallelCoordinates trials={trials} axes={axes} />
      </section>

      <SensitivityBanner sensitivity={detail.sensitivity} />

      <section className="card flex flex-col gap-3 p-5">
        <h3 className="text-sm font-semibold tracking-tight">Confirmed routines vs baseline</h3>
        <TopKTable
          rows={detail.confirm.map((c, i) => ({
            label: `#${i + 1}`,
            meanXg: c.mean_xg,
            ciLo: c.ci_lo,
            ciHi: c.ci_hi,
          }))}
          baseline={{
            mean: detail.baseline_mean_xg,
            ci: [detail.baseline_ci[0]!, detail.baseline_ci[1]!],
          }}
          flags={{
            boundary: detail.winner.boundary_flags,
            faceValidity: detail.winner.face_validity_flags,
          }}
        />
      </section>
    </div>
  );
}
