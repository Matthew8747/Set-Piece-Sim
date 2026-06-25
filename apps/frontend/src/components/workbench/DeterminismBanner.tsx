/**
 * Reproducibility as visible craft (doc 07 §4): every result panel shows
 * `engine <v> · seed <n> · n=<count>` in mono. The engine version is whatever
 * the API reports (currently sim/0.4.0 - Phase 6 touches no engine behaviour).
 */
export function DeterminismBanner({
  engineVersion,
  seed,
  nSims,
}: {
  engineVersion: string;
  seed: number;
  nSims: number;
}) {
  return (
    <p
      data-testid="determinism"
      className="inline-flex w-fit items-center gap-2 rounded-lg border border-(--color-line)/10 bg-(--color-surface-raised)/50 px-3 py-1.5 font-mono text-xs tabular-nums text-(--color-line)/70"
    >
      <span
        aria-hidden
        className="size-1.5 rounded-full bg-(--color-signal)"
        title="deterministic"
      />
      engine {engineVersion} · seed {seed} · n={nSims.toLocaleString()}
    </p>
  );
}
