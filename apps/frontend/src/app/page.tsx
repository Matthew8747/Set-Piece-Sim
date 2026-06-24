import Link from "next/link";

import { EnvironmentBadge } from "@/components/EnvironmentBadge";

// The home view reads as a product surface, not a placeholder: a hero that
// states the thesis and routes to the two working consoles (Scenarios,
// Optimization), with the three capability pillars surfaced as cards.

const PILLARS = [
  {
    k: "01",
    title: "Physics-grounded simulation",
    body: "RK4 ball flight with Magnus, drag-crisis and bounce; agent runs, an aerial contest and a discrete keeper model — one deterministic engine.",
    stat: "sim/0.5.0",
    statLabel: "engine",
  },
  {
    k: "02",
    title: "Monte Carlo experimentation",
    body: "Thousands of common-random-number trials per routine, aggregated to mean xG with honest Wilson confidence intervals.",
    stat: "CRN",
    statLabel: "seeding",
  },
  {
    k: "03",
    title: "Machine-learning routine search",
    body: "TPE, CMA-ES and an NSGA-II genetic search evolve routines generation by generation — every winner benchmarked against a random baseline.",
    stat: "3×",
    statLabel: "samplers",
  },
];

export default function Home() {
  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center gap-16 px-6 py-16">
      <section className="stagger flex flex-col gap-6">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-(--color-line)/12 px-3 py-1 font-mono text-[11px] tracking-widest text-(--color-line-muted) uppercase">
            <span className="size-1 rounded-full bg-(--color-signal)/70" />
            World Cup 2026
          </span>
          <EnvironmentBadge environment="dev" />
        </div>

        <h1 className="max-w-3xl text-5xl leading-[1.05] font-semibold tracking-tight sm:text-6xl">
          Restart Lab
        </h1>

        <p className="max-w-2xl text-lg leading-relaxed text-(--color-line)/75">
          AI-assisted set-piece optimization for international football. Physics-grounded
          simulation, Monte Carlo experimentation, and machine-learning routine search — an
          analyst&apos;s console for the corners and free kicks that decide tournaments.
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Link href="/scenarios" className="btn btn-primary">
            Open a scenario
            <span aria-hidden>→</span>
          </Link>
          <Link href="/optimize" className="btn btn-ghost">
            View optimizations
          </Link>
        </div>
      </section>

      <section className="stagger grid gap-4 sm:grid-cols-3">
        {PILLARS.map((p) => (
          <article key={p.k} className="card card-interactive flex flex-col gap-3 p-5">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-xs text-(--color-line-muted)">{p.k}</span>
              <span className="flex flex-col items-end leading-none">
                <span className="font-mono text-sm text-(--color-signal) tabular-nums">
                  {p.stat}
                </span>
                <span className="mt-1 font-mono text-[10px] tracking-widest text-(--color-line-muted) uppercase">
                  {p.statLabel}
                </span>
              </span>
            </div>
            <h2 className="text-lg font-semibold tracking-tight">{p.title}</h2>
            <p className="text-sm leading-relaxed text-(--color-line)/65">{p.body}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
