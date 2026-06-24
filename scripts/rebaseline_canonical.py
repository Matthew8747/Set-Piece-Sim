"""Safe, observable re-baseline of the canonical optimization study (Phase 8).

The canonical run is long (the 7-attacker template is ~2.5x slower than the
4-attacker one and the reference engine is ~3 sims/s). Running it blindly once
hard-locked a terminal, so this wrapper makes it *observable and bounded*:

* **Per-trial progress** - Optuna's INFO logging is enabled, so each screen
  trial prints a line.
* **Liveness heartbeat** - a daemon thread writes "alive, elapsed Ns" every 30 s,
  so the non-Optuna phases (confirm / sensitivity / surrogate) still report and
  the process can never go silent for long.
* **Hard watchdog** - a wall-clock cap aborts the process rather than letting it
  hang indefinitely.

All progress goes to stdout *and* a scoped status file under the project's
``optimization_studies/`` directory (never a filesystem-wide search). The study
is written by ``run_canonical`` to ``optimization_studies/<name>/study.json``.

Usage (from repo root):
    uv run python scripts/rebaseline_canonical.py \
        --trials 24 --screen 40 --confirm 400 --k 3 --sens 60 --max-seconds 5400
"""

from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

import optuna

from restart_opt.canonical import CanonicalConfig, run_canonical

STATUS_FILE = Path("optimization_studies") / "_rebaseline_status.log"


def _log(message: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    print(line, flush=True)
    with STATUS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _heartbeat(start: float, stop: threading.Event) -> None:
    while not stop.wait(30.0):
        _log(f"heartbeat: alive, elapsed {int(time.time() - start)}s")


def _watchdog(start: float, max_seconds: int) -> None:
    # Daemon thread: if wall-clock exceeds the cap, abort hard rather than hang.
    import os

    while True:
        time.sleep(5.0)
        if time.time() - start > max_seconds:
            _log(f"WATCHDOG: exceeded {max_seconds}s - aborting to avoid an indefinite hang")
            os._exit(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Observable canonical re-baseline")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--trials", type=int, default=24)
    parser.add_argument("--screen", type=int, default=40)
    parser.add_argument("--confirm", type=int, default=400)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--sens", type=int, default=60)
    parser.add_argument("--max-seconds", type=int, default=5400, help="hard wall-clock cap")
    parser.add_argument(
        "--out",
        default=None,
        help="study output root (default optimization_studies/); use a temp dir for smoke tests",
    )
    args = parser.parse_args()

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text("", encoding="utf-8")

    # Per-trial visibility: Optuna's default handler logs each trial at INFO.
    optuna.logging.set_verbosity(optuna.logging.INFO)

    start = time.time()
    stop = threading.Event()
    threading.Thread(target=_heartbeat, args=(start, stop), daemon=True).start()
    threading.Thread(target=_watchdog, args=(start, args.max_seconds), daemon=True).start()

    config = CanonicalConfig(
        n_trials=args.trials,
        n_screen=args.screen,
        k=args.k,
        n_confirm=args.confirm,
        sensitivity_sims=args.sens,
        seed=args.seed,
        prune=True,
    )
    _log(
        f"START trials={config.n_trials} screen={config.n_screen} "
        f"confirm={config.n_confirm} k={config.k} sens={config.sensitivity_sims} "
        f"cap={args.max_seconds}s"
    )
    out_root = Path(args.out) if args.out else None
    try:
        # Phase markers make the long non-Optuna phases (confirm/sensitivity)
        # visible, so a stall there is distinguishable from progress.
        run_canonical(
            config,
            out_root=out_root,  # None -> optimization_studies/<name>/study.json
            on_phase=lambda label: _log(f"PHASE: {label}"),
        )
    except Exception as exc:
        _log(f"FAILED: {exc!r}")
        return 1
    finally:
        stop.set()

    _log(
        f"DONE in {int(time.time() - start)}s -> optimization_studies/england-vs-argentina/study.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
