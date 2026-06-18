"""``restart-etl`` command line: the whole pipeline is a CLI (design doc 04 §4).

Commands::

    restart-etl fetch statsbomb [--competitions wc2022,euro2024]
    restart-etl stage         # raw JSON -> typed Parquet (105x68 coords)
    restart-etl marts         # staging -> analysis-ready marts (+ DuckDB load)
    restart-etl gates         # data-quality + license audit gates
    restart-etl all [--competitions ...]   # fetch -> stage -> marts -> gates
    restart-etl version

``all`` rebuilds the world from raw; the acceptance target is < 10 min on the
named corpus (doc 08 Phase 4). ``stage``/``marts``/``gates`` run offline against
the existing raw cache, so CI can exercise them on a frozen fixture snapshot
without network.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from restart_etl import ETL_VERSION
from restart_etl.config import default_paths, resolve_competitions
from restart_etl.marts.build import run_marts
from restart_etl.quality.gates import run_gates
from restart_etl.sources.statsbomb import StatsBombFetcher
from restart_etl.staging.build import run_staging


def _echo(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _comp_list(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [c for c in (s.strip() for s in raw.split(",")) if c]


def cmd_fetch(args: argparse.Namespace) -> int:
    if args.provider != "statsbomb":
        _echo(f"unknown provider {args.provider!r} (only 'statsbomb' supported)")
        return 2
    comps = resolve_competitions(_comp_list(args.competitions))
    paths = default_paths()
    _echo(f"fetch statsbomb -> {paths.statsbomb_raw} :: {[c.alias for c in comps]}")
    with StatsBombFetcher(paths, progress=_echo) as fetcher:
        manifest = fetcher.fetch(comps)
    _echo(f"cached {len(manifest.entries)} files; content_hash={manifest.content_hash()[:12]}")
    return 0


def cmd_stage(_: argparse.Namespace) -> int:
    paths = default_paths()
    res = run_staging(paths, progress=_echo)
    _echo(f"staging: {res.event_rows} events, {res.shot_rows} shots -> {paths.staging}")
    return 0


def cmd_marts(_: argparse.Namespace) -> int:
    paths = default_paths()
    res = run_marts(paths, progress=_echo)
    _echo(
        f"marts: {res.setpiece_shots} setpiece_shots, {res.players} players, "
        f"{res.player_attributes} attributes -> {paths.marts}"
    )
    return 0


def cmd_gates(_: argparse.Namespace) -> int:
    paths = default_paths()
    report = run_gates(paths)
    for line in report.lines():
        _echo(line)
    return 0 if report.passed else 1


def cmd_all(args: argparse.Namespace) -> int:
    rc = cmd_fetch(args)
    if rc != 0:
        return rc
    rc = cmd_stage(args)
    if rc != 0:
        return rc
    rc = cmd_marts(args)
    if rc != 0:
        return rc
    return cmd_gates(args)


def cmd_load_postgres(args: argparse.Namespace) -> int:
    # Drop-in Postgres target (ADR-007 d1); psycopg is the optional extra.
    from restart_etl.marts.load_postgres import load_all_marts_postgres

    marts = Path(args.marts_dir) if args.marts_dir else default_paths().marts
    loaded = load_all_marts_postgres(args.dsn, marts)
    for table, n in loaded.items():
        _echo(f"load-postgres: {n} rows -> {table}")
    if not loaded:
        _echo(f"load-postgres: no mart parquet found under {marts}")
        return 1
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(ETL_VERSION)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="restart-etl", description="Restart Lab data pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("fetch", help="fetch raw source data into the cache")
    pf.add_argument("provider", choices=["statsbomb"])
    pf.add_argument("--competitions", help="comma list of aliases (default: wc2022,euro2024)")
    pf.set_defaults(func=cmd_fetch)

    sub.add_parser("stage", help="raw -> typed Parquet staging").set_defaults(func=cmd_stage)
    sub.add_parser("marts", help="staging -> marts").set_defaults(func=cmd_marts)
    sub.add_parser("gates", help="run data-quality + license gates").set_defaults(func=cmd_gates)

    pa = sub.add_parser("all", help="fetch -> stage -> marts -> gates")
    pa.add_argument("--competitions", help="comma list of aliases (default: wc2022,euro2024)")
    pa.set_defaults(func=cmd_all)

    pp = sub.add_parser("load-postgres", help="load committed marts into Postgres (drop-in)")
    pp.add_argument(
        "--dsn", required=True, help="Postgres DSN, e.g. postgresql://user:pass@host/db"
    )
    pp.add_argument("--marts-dir", help="override the marts directory (default: data/marts)")
    pp.set_defaults(func=cmd_load_postgres)

    sub.add_parser("version", help="print ETL version").set_defaults(func=cmd_version)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = args.func
    result: int = func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
