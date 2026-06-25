import Link from "next/link";

import { EnvironmentBadge } from "@/components/EnvironmentBadge";
import { HeroPitch } from "@/components/shell/HeroPitch";

// Home reads as a product surface: a plain statement of what the tool does,
// routes into the two working consoles, and three pillars that explain the
// simulate / measure / optimise loop in readable language.

const PILLARS = [
  {
    k: "01",
    verb: "Simulate",
    title: "Play the set piece out",
    body: "A deterministic engine flies the ball with real spin, drag and bounce, moves every attacker and defender, and resolves the delivery into a shot, a clearance or a scramble.",
    stat: "RK4",
    statLabel: "physics",
  },
  {
    k: "02",
    verb: "Measure",
    title: "Score it with real xG",
    body: "Each simulated chance is graded by an expected-goals model trained on real World Cup and Euros data, and reported with confidence intervals so noise never reads as a result.",
    stat: "real",
    statLabel: "xG model",
  },
  {
    k: "03",
    verb: "Optimise",
    title: "Search for the best routine",
    body: "An optimizer tunes the delivery, the runs and the timing across thousands of trials. Any routine it proposes has to beat random search before it counts as a finding.",
    stat: "vs random",
    statLabel: "benchmark",
  },
];

export default function Home() {
  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center gap-14 px-6 py-16">
      <section className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="stagger flex flex-col gap-6">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-(--color-line)/12 px-3 py-1 font-mono text-[11px] tracking-widest text-(--color-line-muted) uppercase">
              <span className="size-1 rounded-full bg-(--color-signal)/70" />
              World Cup 2026
            </span>
            <EnvironmentBadge environment="dev" />
          </div>

          <div className="flex flex-col gap-4">
            <h1 className="text-5xl leading-[1.05] font-semibold tracking-tight sm:text-6xl">
              Restart Lab
            </h1>
            <p className="max-w-2xl text-xl leading-snug font-medium text-(--color-line)/90">
              Find the highest-value way to take a corner or a free kick.
            </p>
          </div>

          <p className="max-w-2xl text-base leading-relaxed text-(--color-line)/70">
            Restart Lab plays a set piece out thousands of times in a physics engine, scores every
            chance it creates with a real-data expected-goals model, then searches for the routine
            that works best against a specific defence. It is an analyst&apos;s console, built
            around the 2026 World Cup.
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <Link href="/scenarios" className="btn btn-primary">
              Open the workbench
              <span aria-hidden>→</span>
            </Link>
            <Link href="/optimize" className="btn btn-ghost">
              Browse optimizations
            </Link>
          </div>
        </div>

        <div className="hidden lg:block">
          <HeroPitch />
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <p className="font-mono text-[11px] tracking-widest text-(--color-line-muted) uppercase">
          How it works
        </p>
        <div className="stagger grid gap-4 sm:grid-cols-3">
          {PILLARS.map((p) => (
            <article key={p.k} className="card card-interactive flex flex-col gap-3 p-5">
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-medium text-(--color-line)/90">{p.verb}</span>
                <span className="flex flex-col items-end leading-none">
                  <span className="font-mono text-sm text-(--color-signal) tabular-nums">
                    {p.stat}
                  </span>
                  <span className="mt-1 font-mono text-[10px] tracking-widest text-(--color-line-muted) uppercase">
                    {p.statLabel}
                  </span>
                </span>
              </div>
              <h2 className="text-base font-semibold tracking-tight">{p.title}</h2>
              <p className="text-sm leading-relaxed text-(--color-line)/65">{p.body}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
