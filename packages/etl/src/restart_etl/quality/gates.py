"""Data-quality + license gates run in CI on every pipeline change (doc 04 §5).

Three severities: FAIL (impossible data or a license violation — build red),
FLAG (drift outside an expected band — surfaced, not fatal), PASS. Licensing is
enforced *mechanically* here, not by a policy document: every mart row's
``source`` must be in the approved allow-list.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from restart_etl.config import APPROVED_SOURCES, FORBIDDEN_SOURCES, DataPaths
from restart_etl.marts import calibration, players, schemes, setpiece_shots
from restart_etl.pq import read_rows
from restart_etl.transforms.coords import HALF_LENGTH_M, HALF_WIDTH_M

# Historical set-piece conversion bands (per shot). Goal rate well below open play;
# wide enough to flag corruption, tight enough to catch a label/transform bug.
GOAL_RATE_BAND = (0.01, 0.20)
# Expected row-count range for the named corpus (wc2022 + euro2024); flag if a
# fetch silently truncated. Lower bound guards against an empty/partial cache.
SHOT_COUNT_RANGE = (300, 4000)


class Severity(StrEnum):
    PASS = "PASS"
    FLAG = "FLAG"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    check: str
    detail: str


@dataclass
class GateReport:
    findings: list[Finding]

    @property
    def passed(self) -> bool:
        return all(f.severity is not Severity.FAIL for f in self.findings)

    def lines(self) -> list[str]:
        out = [f"[{f.severity.value}] {f.check}: {f.detail}" for f in self.findings]
        verdict = "PASS" if self.passed else "FAIL"
        out.append(f"== gates {verdict} ({len(self.findings)} checks) ==")
        return out


def _license_audit(rows: list[dict[str, Any]], mart: str, findings: list[Finding]) -> None:
    sources = {str(r.get("source", "")) for r in rows}
    forbidden = sources & FORBIDDEN_SOURCES
    if forbidden:
        findings.append(
            Finding(Severity.FAIL, "license", f"{mart}: forbidden source(s) {sorted(forbidden)}")
        )
    unapproved = {s for s in sources if s not in APPROVED_SOURCES}
    if unapproved:
        findings.append(
            Finding(Severity.FAIL, "license", f"{mart}: unapproved source(s) {sorted(unapproved)}")
        )
    if not forbidden and not unapproved:
        findings.append(
            Finding(Severity.PASS, "license", f"{mart}: all sources approved {sorted(sources)}")
        )


def run_gates(paths: DataPaths) -> GateReport:
    findings: list[Finding] = []
    marts = paths.marts

    shots_path = marts / setpiece_shots.MART_FILE
    if not shots_path.is_file():
        return GateReport([Finding(Severity.FAIL, "exists", f"missing {shots_path}; build marts")])

    shots = read_rows(shots_path)
    calib = read_rows(marts / calibration.MART_FILE)
    attrs = read_rows(marts / players.ATTRIBUTES_FILE)
    scheme_rows = read_rows(marts / schemes.MART_FILE)

    # --- license audit (mechanical) ---------------------------------------
    for name, rows in (
        ("mart_setpiece_shots", shots),
        ("mart_calibration_targets", calib),
        ("mart_player_attributes", attrs),
        ("mart_defensive_schemes", scheme_rows),
    ):
        _license_audit(rows, name, findings)

    # --- distribution: shot coordinates on the pitch (impossible => FAIL) --
    oob = [
        r
        for r in shots
        if abs(float(r["x_m"])) > HALF_LENGTH_M + 0.5 or abs(float(r["y_m"])) > HALF_WIDTH_M + 0.5
    ]
    if oob:
        findings.append(
            Finding(Severity.FAIL, "coords", f"{len(oob)} shots off the pitch (transform bug)")
        )
    else:
        findings.append(Finding(Severity.PASS, "coords", "all shot coords within pitch bounds"))

    # --- distribution: freeze-frame player counts plausible (<= 22) --------
    bad_ff = [r for r in shots if int(r["n_defenders"]) + int(r["n_teammates"]) > 22]
    if bad_ff:
        findings.append(
            Finding(Severity.FAIL, "freeze_frame", f"{len(bad_ff)} shots with > 22 tracked players")
        )
    else:
        findings.append(Finding(Severity.PASS, "freeze_frame", "freeze-frame counts <= 22"))

    # --- distribution: goal rate in band (out-of-band => FLAG) ------------
    n = len(shots)
    goals = sum(int(r["is_goal"]) for r in shots)
    rate = goals / n if n else 0.0
    lo, hi = GOAL_RATE_BAND
    if rate < 0 or rate > 1:
        findings.append(Finding(Severity.FAIL, "goal_rate", f"impossible goal rate {rate:.3f}"))
    elif not (lo <= rate <= hi):
        findings.append(
            Finding(Severity.FLAG, "goal_rate", f"{rate:.3f} outside band {GOAL_RATE_BAND}")
        )
    else:
        findings.append(
            Finding(Severity.PASS, "goal_rate", f"{rate:.3f} ({goals}/{n}) within band")
        )

    # --- reproducibility: row count in the pinned range -------------------
    rlo, rhi = SHOT_COUNT_RANGE
    if not (rlo <= n <= rhi):
        findings.append(
            Finding(Severity.FLAG, "row_count", f"{n} shots outside expected {SHOT_COUNT_RANGE}")
        )
    else:
        findings.append(Finding(Severity.PASS, "row_count", f"{n} shots within expected range"))

    # --- attribute bounds: derived attrs respect engine rails -------------
    bad_attr = [
        r
        for r in attrs
        if r["attribute"] in ("heading", "delivery", "marking", "agility")
        and not (0.0 <= float(r["value"]) <= 1.0)
    ]
    if bad_attr:
        findings.append(
            Finding(Severity.FAIL, "attr_bounds", f"{len(bad_attr)} attributes out of [0,1]")
        )
    else:
        findings.append(Finding(Severity.PASS, "attr_bounds", "derived attributes within bounds"))

    return GateReport(findings)


def gate_paths_default() -> DataPaths:  # pragma: no cover - convenience
    from restart_etl.config import default_paths

    return default_paths()


def _exists(p: Path) -> bool:  # pragma: no cover - reserved for richer checks
    return p.is_file()
