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
      <p className="font-mono text-sm opacity-60">
        Phase 0 scaffold · the Scenario Workbench arrives in Phase 6
      </p>
    </main>
  );
}
