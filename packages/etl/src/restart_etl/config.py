"""Data-lake paths and the approved-source / competition registries.

Single source of truth for *where* data lives and *what* we are allowed to
ingest. The competition registry is an allow-list: ``restart-etl fetch`` only
pulls competitions named here, and the license gate only accepts mart rows
whose ``source`` is in :data:`APPROVED_SOURCES`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def repo_root() -> Path:
    """Locate the repository root from this file (``packages/etl/src/...``).

    Walks up until a directory containing ``data/`` and ``pyproject.toml`` is
    found, so the CLI works from any cwd and from an installed wheel checkout.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    # Fallback: four levels up is packages/etl/src/restart_etl -> repo root.
    return here.parents[3]


@dataclass(frozen=True, slots=True)
class DataPaths:
    """Resolved three-layer lake paths (design doc 04 §4)."""

    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def staging(self) -> Path:
        return self.root / "data" / "staging"

    @property
    def marts(self) -> Path:
        return self.root / "data" / "marts"

    @property
    def statsbomb_raw(self) -> Path:
        return self.raw / "statsbomb"

    def ensure(self) -> None:
        for p in (self.raw, self.staging, self.marts, self.statsbomb_raw):
            p.mkdir(parents=True, exist_ok=True)


def default_paths() -> DataPaths:
    return DataPaths(root=repo_root())


# --- Source allow-list (license gate; design doc 04 §5) --------------------
# Every mart row's ``source`` must be in this set or the build fails. This is
# the *mechanical* licensing enforcement the design calls for.
APPROVED_SOURCES: frozenset[str] = frozenset(
    {
        "statsbomb_open_data",  # events, freeze frames, lineups (attributed)
        "fbref",  # biographical + aggregate rates (cached, attributed)
        "wikidata",  # biographical fallback (CC BY-SA)
        "derived",  # attributes computed from the above with a documented method
        "literature_prior",  # population priors (sprint/reaction-time literature)
        "curated",  # explicit analyst curation, tagged as such
    }
)

# Explicitly forbidden — scraped game ratings (design doc 04 §2). Listed so the
# license gate can name the violation, not just reject silently.
FORBIDDEN_SOURCES: frozenset[str] = frozenset({"ea_fc", "sofifa", "fifa_game"})


@dataclass(frozen=True, slots=True)
class Competition:
    """A StatsBomb (competition_id, season_id) pair under a short alias."""

    alias: str
    competition_id: int
    season_id: int
    label: str


# Allow-list of competitions we ingest. WC 2022 + Euro 2024 are the design's
# named corpus (doc 04 §2: "WC 2022 + Euro 2024 alone ~= 1,500+ corners with
# freeze frames"). Add an alias here to widen ingestion; nothing else fetches.
COMPETITIONS: dict[str, Competition] = {
    "wc2022": Competition("wc2022", 43, 106, "FIFA World Cup 2022"),
    "euro2024": Competition("euro2024", 55, 282, "UEFA Euro 2024"),
    "wc2018": Competition("wc2018", 43, 3, "FIFA World Cup 2018"),
    "euro2020": Competition("euro2020", 55, 43, "UEFA Euro 2020"),
}

DEFAULT_COMPETITIONS: tuple[str, ...] = ("wc2022", "euro2024")

STATSBOMB_LICENSE = "StatsBomb Open Data (non-commercial, attribution required)"


def resolve_competitions(aliases: list[str] | None) -> list[Competition]:
    """Map CLI aliases to Competition records; default = the named corpus."""
    names = list(aliases) if aliases else list(DEFAULT_COMPETITIONS)
    out: list[Competition] = []
    for name in names:
        key = name.strip().lower()
        if key not in COMPETITIONS:
            known = ", ".join(sorted(COMPETITIONS))
            raise ValueError(f"unknown competition alias {name!r}; known: {known}")
        out.append(COMPETITIONS[key])
    return out
