"use client";

import type { OptimizationDetail } from "@restart/shared-types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { StudyDetail } from "@/components/optimize/StudyDetail";
import { api } from "@/lib/api";

export default function OptimizeDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [detail, setDetail] = useState<OptimizationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .optimization(id)
      .then(setDetail)
      .catch((e: unknown) => setError(String(e)));
  }, [id]);

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-12">
      <Link href="/optimize" className="font-mono text-xs text-(--color-signal)/80 hover:underline">
        ← studies
      </Link>
      {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}
      {detail ? (
        <StudyDetail detail={detail} />
      ) : (
        !error && <p className="font-mono text-xs opacity-50">loading…</p>
      )}
    </main>
  );
}
