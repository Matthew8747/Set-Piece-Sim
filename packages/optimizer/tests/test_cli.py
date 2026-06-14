"""CLI surface: the parser exposes the documented commands and version prints."""

import pytest

from restart_opt import OPT_VERSION
from restart_opt.cli import build_parser, main


def test_version_command(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["version"])
    assert rc == 0
    assert OPT_VERSION in capsys.readouterr().out


def test_canonical_parser_defaults() -> None:
    args = build_parser().parse_args(["canonical"])
    assert args.trials == 40
    assert args.screen == 250
    assert args.confirm == 3000
    assert args.k == 3
    assert args.no_prune is False


def test_requires_subcommand() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
