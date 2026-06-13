import { EnvironmentBadge } from "@/components/EnvironmentBadge";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6">
      <EnvironmentBadge environment="dev" />
      <h1 className="text-4xl font-semibold tracking-tight">Restart Lab</h1>
      <p className="max-w-xl text-lg leading-relaxed opacity-80">
        AI-assisted set-piece optimization for international football. Physics-grounded simulation,
        Monte Carlo experimentation, and machine-learning routine search — built around the 2026
        World Cup.
      </p>
      <a
        href="/workbench"
        className="w-fit rounded bg-(--color-signal) px-4 py-2 font-medium text-black"
      >
        Open the Scenario Workbench →
      </a>
      <p className="font-mono text-sm opacity-60">Phase 3 MVP · corner simulation + Monte Carlo</p>
    </main>
  );
}
