/**
 * Reproducibility as visible craft (doc 07 §4): every result panel shows
 * `engine <v> · seed <n> · n=<count>` in mono. The engine version is whatever
 * the API reports (currently sim/0.4.0 — Phase 6 touches no engine behaviour).
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
    <p data-testid="determinism" className="font-mono text-xs tabular-nums opacity-70">
      engine {engineVersion} · seed {seed} · n={nSims.toLocaleString()}
    </p>
  );
}
