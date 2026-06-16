"""Shared adapter singletons + filesystem locators for the web layer.

Built once (``lru_cache``) and imported by routers so a single mart-backed
``TeamRepository`` serves every request. The marts directory is located by
walking up to the repository root (the dir that holds both ``pyproject.toml``
and ``data/marts``), mirroring the xG adapter's locator.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from restart_api.repositories.file import MartTeamRepository

_MARTS_REL = Path("data") / "marts"


@lru_cache
def default_marts_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / _MARTS_REL).is_dir():
            return parent / _MARTS_REL
    # Fallback: repo root is four levels above apps/backend/src/restart_api.
    return here.parents[4] / _MARTS_REL


@lru_cache
def team_repository() -> MartTeamRepository:
    return MartTeamRepository(default_marts_dir())
