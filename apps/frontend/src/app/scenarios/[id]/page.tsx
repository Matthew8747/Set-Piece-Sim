"use client";

import { useParams } from "next/navigation";

import { ScenarioWorkbench } from "@/components/workbench/ScenarioWorkbench";

export default function ScenarioWorkbenchPage() {
  // Client component so the workbench owns mode state + keyboard without a
  // server/client boundary in the middle of the stateful surface (doc 07: the
  // workbench is one surface, three modes).
  const params = useParams<{ id: string }>();
  const id = params?.id;
  if (!id) return null;
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-10">
      <ScenarioWorkbench scenarioId={id} />
    </main>
  );
}
