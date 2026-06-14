"""``restart-xg`` command line: train the xG bundle and render its model card.

    restart-xg train [--mart PATH] [--no-mlflow] [--splits 5]
    restart-xg card  [--out docs/model-cards/xg-v1.md]
    restart-xg version

``train`` writes the engine-loadable bundle + active pointer under data/models
and (re)renders the model card. ``make reproduce-xg`` wraps ``train`` to rebuild
any shipped number from the pinned mart snapshot (design doc 06 §4).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from restart_ml import ML_VERSION
from restart_ml.cards import write_model_card
from restart_ml.train import train_xg

_DEFAULT_CARD = Path("docs/model-cards/xg-v1.md")


def _echo(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cmd_train(args: argparse.Namespace) -> int:
    mart = Path(args.mart) if args.mart else None
    result = train_xg(
        mart_path=mart,
        n_splits=args.splits,
        use_mlflow=not args.no_mlflow,
        progress=_echo,
    )
    card = write_model_card(result, _DEFAULT_CARD)
    _echo(f"model card -> {card}")
    return 0


def cmd_card(args: argparse.Namespace) -> int:
    result = train_xg(use_mlflow=False, progress=_echo)
    dest = Path(args.out) if args.out else _DEFAULT_CARD
    write_model_card(result, dest)
    _echo(f"model card -> {dest}")
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(ML_VERSION)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="restart-xg", description="Restart Lab xG training")
    sub = p.add_subparsers(dest="command", required=True)

    pt = sub.add_parser("train", help="train the xG bundle + render the model card")
    pt.add_argument("--mart", help="path to mart_setpiece_shots.parquet")
    pt.add_argument("--splits", type=int, default=5, help="grouped-CV folds")
    pt.add_argument("--no-mlflow", action="store_true", help="skip MLflow logging")
    pt.set_defaults(func=cmd_train)

    pc = sub.add_parser("card", help="re-render the model card")
    pc.add_argument("--out", help="model card destination")
    pc.set_defaults(func=cmd_card)

    sub.add_parser("version", help="print ML version").set_defaults(func=cmd_version)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    func = args.func
    result: int = func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
