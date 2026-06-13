import { Workbench } from "@/components/Workbench";

export const metadata = {
  title: "Scenario Workbench · Restart Lab",
};

export default function WorkbenchPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-10">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Scenario Workbench</h1>
        <p className="text-sm opacity-60">
          Corner routine vs defensive scheme — simulate one delivery or a Monte Carlo batch. MVP
          slice (England vs Argentina demo squads).
        </p>
      </header>
      <Workbench />
    </main>
  );
}
