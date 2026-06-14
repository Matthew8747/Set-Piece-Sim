"""``restart-opt`` command line: run the routine optimizer studies.

    restart-opt canonical [--seed N] [--trials N] [--screen N] [--confirm N]
                          [--k N] [--no-prune] [--no-mlflow] [--out DIR]
    restart-opt version

``canonical`` runs the England-corners-vs-Argentina-zonal study end to end and
writes ``optimization_studies/england-vs-argentina/study.json``. It is the
one-command reproduction of any shipped study number (design doc 06 sec4):
``restart-opt canonical --seed N`` rebuilds the study deterministically.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from restart_opt import OPT_VERSION
from restart_opt.canonical import CanonicalConfig, run_canonical


def _echo(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cmd_canonical(args: argparse.Namespace) -> int:
    cfg = CanonicalConfig(
        n_trials=args.trials,
        n_screen=args.screen,
        k=args.k,
        n_confirm=args.confirm,
        sensitivity_sims=args.sens,
        seed=args.seed,
        prune=not args.no_prune,
    )
    _echo(
        f"canonical study: trials={cfg.n_trials} screen={cfg.n_screen} "
        f"k={cfg.k} confirm={cfg.n_confirm} seed={cfg.seed} prune={cfg.prune}"
    )
    out = Path(args.out) if args.out else None
    document = run_canonical(cfg, out_root=out)

    if not args.no_mlflow:
        try:
            from restart_opt.mlflow_log import log_study

            log_study(document)
            _echo("logged study to MLflow")
        except Exception as exc:  # pragma: no cover - MLflow optional at runtime
            _echo(f"MLflow logging skipped: {exc}")

    winner = document["winner"]
    _echo(
        f"winner mean_xg={winner['mean_xg']:.4f} beats_baseline={winner['beats_baseline']} "
        f"flags={winner['face_validity_flags']}"
    )
    _echo(f"insights: {document['insights']}")
    _echo(f"sensitivity: {document['sensitivity']['verdict']}")
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(OPT_VERSION)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="restart-opt", description="Restart Lab routine optimizer")
    sub = p.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("canonical", help="run the England-vs-Argentina canonical study")
    pc.add_argument("--seed", type=int, default=0)
    pc.add_argument("--trials", type=int, default=40, help="screen trials per sampler")
    pc.add_argument("--screen", type=int, default=250, help="sims per screen trial")
    pc.add_argument("--confirm", type=int, default=3000, help="sims per confirm candidate")
    pc.add_argument("--k", type=int, default=3, help="top-k confirmed")
    pc.add_argument("--sens", type=int, default=200, help="sims per sensitivity evaluation")
    pc.add_argument("--no-prune", action="store_true", help="disable median pruning on the screen")
    pc.add_argument("--no-mlflow", action="store_true", help="skip MLflow logging")
    pc.add_argument("--out", help="study output root (default optimization_studies/)")
    pc.set_defaults(func=cmd_canonical)

    sub.add_parser("version", help="print optimizer version").set_defaults(func=cmd_version)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    func = args.func
    result: int = func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
