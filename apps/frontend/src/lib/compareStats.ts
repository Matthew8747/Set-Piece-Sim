// Common-random-number compare: scenarios A and B run at the SAME seed + n_sims
// see the identical per-sim seed stream (the montecarlo determinism contract,
// runner.py: sim_seeds is scenario-independent). So the per-sim xG vectors are
// PAIRED — the honest difference is the mean of (a_i - b_i), and its uncertainty
// is a large-sample CI on that paired mean. No winner is declared unless the CI
// excludes zero (the stats policy, doc 07 §4 / Sim-Architecture §5.4).

export interface CompareResult {
  meanDiff: number; // mean(a_i - b_i): A minus B, in xG
  ciLo: number;
  ciHi: number;
  significant: boolean; // CI excludes 0
  n: number;
}

const Z = 1.96; // 95% two-sided

export function compareStats(a: readonly number[], b: readonly number[]): CompareResult {
  if (a.length !== b.length) {
    throw new Error(
      `compareStats needs paired samples (same seed + n_sims): got ${a.length} vs ${b.length}`,
    );
  }
  const n = a.length;
  if (n === 0) throw new Error("compareStats needs at least one paired sample");

  const diffs = a.map((ai, i) => ai - b[i]!);
  const meanDiff = diffs.reduce((s, d) => s + d, 0) / n;

  if (n < 2) {
    // No spread to estimate — report the point difference, never significant.
    return { meanDiff, ciLo: meanDiff, ciHi: meanDiff, significant: false, n };
  }

  const variance = diffs.reduce((s, d) => s + (d - meanDiff) ** 2, 0) / (n - 1);
  const se = Math.sqrt(variance) / Math.sqrt(n);
  const ciLo = meanDiff - Z * se;
  const ciHi = meanDiff + Z * se;
  return { meanDiff, ciLo, ciHi, significant: ciLo > 0 || ciHi < 0, n };
}
