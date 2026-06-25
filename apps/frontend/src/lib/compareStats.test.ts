import { describe, expect, it } from "vitest";

import { compareStats } from "./compareStats";

describe("compareStats (common-random-number paired difference)", () => {
  it("flags a real, consistent difference as significant", () => {
    const a = Array(200).fill(0.1);
    const b = Array(200).fill(0.02);
    const r = compareStats(a, b);
    expect(r.meanDiff).toBeCloseTo(0.08);
    expect(r.significant).toBe(true);
    expect(r.ciLo).toBeGreaterThan(0);
  });

  it("does not flag paired noise as significant", () => {
    const a = [0.1, 0.0, 0.2, 0.0];
    const b = [0.0, 0.1, 0.0, 0.2];
    const r = compareStats(a, b);
    expect(r.significant).toBe(false);
    // CI straddles zero.
    expect(r.ciLo).toBeLessThan(0);
    expect(r.ciHi).toBeGreaterThan(0);
  });

  it("reports the negative direction when B wins", () => {
    const a = Array(200).fill(0.02);
    const b = Array(200).fill(0.1);
    const r = compareStats(a, b);
    expect(r.meanDiff).toBeCloseTo(-0.08);
    expect(r.significant).toBe(true);
    expect(r.ciHi).toBeLessThan(0);
  });

  it("throws on unpaired lengths - CRN requires same seed + n", () => {
    expect(() => compareStats([0.1], [0.1, 0.2])).toThrow();
  });

  it("throws on empty input", () => {
    expect(() => compareStats([], [])).toThrow();
  });
});
