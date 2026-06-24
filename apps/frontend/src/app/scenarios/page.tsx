"use client";

import type { ScenarioDTO } from "@restart/shared-types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

// The canonical seed (doc 07: "empty states teach" — a new scenario opens
// pre-loaded with a sensible routine vs zonal defense, not a blank pitch).
const CANONICAL = {
  name: "WC2026 · England corner vs Argentina",
  attacking_team_id: "england",
  defending_team_id: "argentina",
};

export default function ScenariosPage() {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<ScenarioDTO[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .scenarios()
      .then(setScenarios)
      .catch((e: unknown) => setError(String(e)));
  }, []);

  // Create the canonical scenario from the first catalog routine vs zonal scheme,
  // then jump into its workbench. A scenario is an immutable named spec; Build
  // forks a new one rather than mutating (no update endpoint by design).
  async function newScenario() {
    setBusy(true);
    setError(null);
    try {
      const [routines, schemes] = await Promise.all([api.routines(), api.schemes()]);
      const routineId = routines[0]?.routine_id;
      const schemeId =
        schemes.find((s) => /zonal/i.test(s.name))?.scheme_id ?? schemes[0]?.scheme_id;
      if (!routineId || !schemeId) throw new Error("catalog is empty");
      const created = await api.createScenario({
        name: CANONICAL.name,
        routine_id: routineId,
        scheme_id: schemeId,
        attacking_team_id: CANONICAL.attacking_team_id,
        defending_team_id: CANONICAL.defending_team_id,
      });
      router.push(`/scenarios/${created.scenario_id}`);
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

  const empty = scenarios !== null && scenarios.length === 0;

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-(--color-line)/10 pb-6">
        <div className="flex flex-col gap-2">
          <span className="font-mono text-[11px] tracking-widest text-(--color-line-muted) uppercase">
            Workbench
          </span>
          <h1 className="text-3xl font-semibold tracking-tight">Scenarios</h1>
          <p className="text-sm text-(--color-line)/60">
            Canonical World Cup 2026 set-pieces and your saved scenarios.
          </p>
        </div>
        <button type="button" onClick={newScenario} disabled={busy} className="btn btn-primary">
          {busy ? "creating…" : "New scenario"}
          {!busy && <span aria-hidden>→</span>}
        </button>
      </header>

      {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}

      {empty && (
        <section className="card flex flex-col items-center gap-2 border-dashed p-10 text-center">
          <p className="text-lg font-medium">No scenarios yet.</p>
          <p className="max-w-md text-sm text-(--color-line)/60">
            Start from the <span className="text-(--color-signal)">canonical WC2026</span> corner
            (England&apos;s near-post routine against Argentina&apos;s zonal scheme), then tweak the
            squads, simulate, and replay.
          </p>
        </section>
      )}

      {scenarios && scenarios.length > 0 && (
        <ul className="stagger grid gap-3 sm:grid-cols-2">
          {scenarios.map((s) => (
            <li key={s.scenario_id}>
              <Link
                href={`/scenarios/${s.scenario_id}`}
                className="card card-interactive group flex flex-col gap-2 p-4"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-medium">{s.name}</span>
                  <span
                    aria-hidden
                    className="translate-x-0 text-(--color-line-muted) opacity-0 transition-all group-hover:translate-x-0.5 group-hover:text-(--color-signal) group-hover:opacity-100"
                  >
                    →
                  </span>
                </span>
                <span className="font-mono text-xs text-(--color-line-muted)">
                  {s.spec.routine_id} · {s.spec.scheme_id}
                </span>
                <span className="font-mono text-[10px] text-(--color-line)/30">
                  #{s.scenario_hash.slice(0, 12)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {scenarios === null && !error && <p className="font-mono text-xs opacity-50">loading…</p>}
    </main>
  );
}
