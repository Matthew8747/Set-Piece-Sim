"use client";

import type {
  MonteCarloResponse,
  ProportionCI,
  RoutineSummary,
  SchemeSummary,
  SimulateResponse,
} from "@restart/shared-types";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { Pitch } from "@/components/Pitch";

function pct(ci: ProportionCI): string {
  return `${(ci.p * 100).toFixed(1)}% ±${(((ci.hi - ci.lo) / 2) * 100).toFixed(1)}`;
}

const METRICS: { key: keyof MonteCarloResponse; label: string }[] = [
  { key: "p_goal", label: "Goal" },
  { key: "p_shot", label: "Shot" },
  { key: "p_header_shot", label: "Header" },
  { key: "p_first_contact_attack", label: "Attack 1st contact" },
  { key: "p_clearance", label: "Cleared" },
  { key: "p_possession_recovered", label: "Possession kept" },
];

export function Workbench() {
  const [routines, setRoutines] = useState<RoutineSummary[]>([]);
  const [schemes, setSchemes] = useState<SchemeSummary[]>([]);
  const [routineId, setRoutineId] = useState("");
  const [schemeId, setSchemeId] = useState("");
  const [seed, setSeed] = useState(7);
  const [nSims, setNSims] = useState(200);
  const [sim, setSim] = useState<SimulateResponse | null>(null);
  const [mc, setMc] = useState<MonteCarloResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.routines(), api.schemes()])
      .then(([r, s]) => {
        setRoutines(r);
        setSchemes(s);
        setRoutineId(r[0]?.routine_id ?? "");
        setSchemeId(s[0]?.scheme_id ?? "");
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  async function run<T>(fn: () => Promise<T>, set: (v: T) => void): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      set(await fn());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const ready = routineId !== "" && schemeId !== "";

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      {/* --- control column --- */}
      <section className="flex flex-col gap-4">
        <h2 className="font-mono text-xs uppercase tracking-widest opacity-60">Build</h2>

        <label className="flex flex-col gap-1 text-sm">
          Routine
          <select
            value={routineId}
            onChange={(e) => setRoutineId(e.target.value)}
            className="rounded border border-(--color-line)/20 bg-(--color-surface-raised) px-2 py-1.5"
          >
            {routines.map((r) => (
              <option key={r.routine_id} value={r.routine_id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Defensive scheme
          <select
            value={schemeId}
            onChange={(e) => setSchemeId(e.target.value)}
            className="rounded border border-(--color-line)/20 bg-(--color-surface-raised) px-2 py-1.5"
          >
            {schemes.map((s) => (
              <option key={s.scheme_id} value={s.scheme_id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Seed
            <input
              type="number"
              value={seed}
              min={0}
              onChange={(e) => setSeed(Number(e.target.value))}
              className="rounded border border-(--color-line)/20 bg-(--color-surface-raised) px-2 py-1.5 font-mono"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Sims
            <input
              type="number"
              value={nSims}
              min={1}
              max={2000}
              onChange={(e) => setNSims(Number(e.target.value))}
              className="rounded border border-(--color-line)/20 bg-(--color-surface-raised) px-2 py-1.5 font-mono"
            />
          </label>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            disabled={!ready || busy}
            onClick={() =>
              run(() => api.simulate({ routine_id: routineId, scheme_id: schemeId, seed }), setSim)
            }
            className="flex-1 rounded bg-(--color-signal) px-3 py-2 font-medium text-black disabled:opacity-40"
          >
            Simulate one
          </button>
          <button
            type="button"
            disabled={!ready || busy}
            onClick={() =>
              run(
                () =>
                  api.montecarlo({
                    routine_id: routineId,
                    scheme_id: schemeId,
                    n_sims: nSims,
                    root_seed: seed,
                  }),
                setMc,
              )
            }
            className="flex-1 rounded border border-(--color-signal)/50 px-3 py-2 font-medium text-(--color-signal) disabled:opacity-40"
          >
            Run {nSims}×
          </button>
        </div>

        {busy && <p className="font-mono text-xs opacity-60">running…</p>}
        {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}

        {/* Monte Carlo results */}
        {mc && (
          <div className="flex flex-col gap-2 rounded-lg border border-(--color-line)/15 p-3">
            <h3 className="font-mono text-xs uppercase tracking-widest opacity-60">
              {mc.n_sims} sims · {mc.engine_version}
            </h3>
            <table className="w-full text-sm">
              <tbody>
                {METRICS.map((m) => (
                  <tr key={m.key} className="border-b border-(--color-line)/10 last:border-0">
                    <td className="py-1 opacity-80">{m.label}</td>
                    <td className="py-1 text-right font-mono tabular-nums text-(--color-signal)">
                      {pct(mc[m.key] as ProportionCI)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* --- pitch + replay + event timeline --- */}
      <section className="flex flex-col gap-4">
        <h2 className="font-mono text-xs uppercase tracking-widest opacity-60">
          Replay {sim && <span className="text-(--color-signal)">· {sim.outcome}</span>}
        </h2>
        <Pitch
          key={sim ? `${sim.seed}-${sim.outcome}-${sim.events.length}` : "empty"}
          result={sim}
        />
        {sim && (
          <ol className="flex flex-wrap gap-2 font-mono text-xs">
            {sim.events.map((e, i) => (
              <li
                key={i}
                className="rounded border border-(--color-line)/15 px-2 py-1"
                title={e.player_id ?? ""}
              >
                <span className="opacity-50">{e.time_s.toFixed(2)}s</span> {e.kind}
                {e.team && <span className="opacity-50"> ({e.team})</span>}
              </li>
            ))}
          </ol>
        )}
        {!sim && !busy && (
          <p className="text-sm opacity-50">
            Pick a routine and scheme, then simulate to see the replay.
          </p>
        )}
      </section>
    </div>
  );
}
