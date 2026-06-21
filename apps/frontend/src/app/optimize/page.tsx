"use client";

import type { OptimizationSummary } from "@restart/shared-types";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

// Studies library (doc 07 IA): convergence/parallel-coords live on the detail
// page; here we list the persisted studies with the honest headline — a "beats
// baseline" badge only when the winner's CI clears the baseline's (the stats
// policy, enforced by the backend's beats_baseline flag).

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

export default function OptimizePage() {
  const [studies, setStudies] = useState<OptimizationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .optimizations()
      .then(setStudies)
      .catch((e: unknown) => setError(String(e)));
  }, []);

  const empty = studies !== null && studies.length === 0;

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Optimization studies</h1>
        <p className="text-sm opacity-60">
          Routine searches against a defensive scheme — convergence, the search space, and what beat
          the library baseline.
        </p>
      </header>

      {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}

      {empty && (
        <section className="rounded-lg border border-dashed border-(--color-line)/20 p-8 text-center">
          <p className="text-lg">No studies yet.</p>
          <p className="mt-2 text-sm opacity-60">
            Studies are produced offline by <span className="font-mono">restart-opt</span> and
            surfaced here read-only.
          </p>
        </section>
      )}

      {studies && studies.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2">
          {studies.map((s) => (
            <li key={s.id}>
              <Link
                href={`/optimize/${s.id}`}
                className="flex flex-col gap-2 rounded-lg border border-(--color-line)/15 p-4 transition hover:border-(--color-signal)/40"
              >
                <span className="font-medium">{s.name}</span>
                <span className="font-mono text-xs opacity-50">
                  {s.matchup.attacking} vs {s.matchup.defending} {s.matchup.scheme}
                </span>
                <span className="flex items-center gap-2">
                  <span className="font-mono text-sm tabular-nums">{pct(s.winner_mean_xg)}</span>
                  {s.beats_baseline ? (
                    <span
                      data-testid="beats-badge"
                      className="rounded bg-(--color-signal)/15 px-2 py-0.5 text-[10px] font-medium text-(--color-signal)"
                    >
                      beats baseline
                    </span>
                  ) : (
                    <span
                      data-testid="no-sig-badge"
                      className="rounded border border-(--color-line)/20 px-2 py-0.5 text-[10px] opacity-60"
                    >
                      no significant edge
                    </span>
                  )}
                </span>
                <span className="font-mono text-[10px] opacity-30">
                  {s.engine_version} · {s.n_trials} trials
                  {s.stale ? " · ⚠ engine drift" : ""}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {studies === null && !error && <p className="font-mono text-xs opacity-50">loading…</p>}
    </main>
  );
}
