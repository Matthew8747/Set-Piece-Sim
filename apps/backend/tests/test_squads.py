"""Real squads from the marts -> pure restart.Team (ADR-007 d2).

The loader reads committed, provenance-tagged marts (no scraped ratings) and
emits a pure domain Team; the pure core never touches the filesystem. Selection
of an XI from the multi-match pool is deterministic so results are reproducible.
"""

from pathlib import Path

import pytest

from restart.players.player import PositionGroup
from restart.players.team import Team
from restart_api.squads.loader import MartSquadLoader, team_slug

MARTS = Path(__file__).resolve().parents[3] / "data" / "marts"


@pytest.fixture(scope="module")
def loader() -> MartSquadLoader:
    return MartSquadLoader(MARTS)


def test_loads_real_team_as_pure_domain_team(loader: MartSquadLoader) -> None:
    team = loader.team("England")
    assert isinstance(team, Team)
    assert len(team.players) == 11
    assert sum(p.position_group is PositionGroup.GK for p in team.players) == 1
    # Names are real StatsBomb identities, not synthetic "Player N".
    assert all(
        p.display_name and not p.display_name.startswith("England Player") for p in team.players
    )


def test_canonical_opponent_loads(loader: MartSquadLoader) -> None:
    team = loader.team("Argentina")
    assert isinstance(team, Team)
    assert len(team.players) == 11


def test_team_selection_is_deterministic(loader: MartSquadLoader) -> None:
    a = [p.player_id for p in loader.team("England").players]
    b = [p.player_id for p in loader.team("England").players]
    assert a == b


def test_squad_has_the_4_4_2_outfield_shape(loader: MartSquadLoader) -> None:
    groups = [p.position_group for p in loader.team("England").players]
    assert groups.count(PositionGroup.DF) == 4
    assert groups.count(PositionGroup.MF) == 4
    assert groups.count(PositionGroup.FW) == 2


def test_list_teams_includes_canonical_matchup(loader: MartSquadLoader) -> None:
    slugs = {t.team_id for t in loader.list_teams()}
    assert team_slug("England") in slugs
    assert team_slug("Argentina") in slugs


def test_get_by_slug_matches_name_lookup(loader: MartSquadLoader) -> None:
    by_name = [p.player_id for p in loader.team("England").players]
    by_slug = [p.player_id for p in loader.team_by_id(team_slug("England")).players]
    assert by_name == by_slug


def test_unknown_team_raises(loader: MartSquadLoader) -> None:
    with pytest.raises(ValueError, match="unknown team"):
        loader.team("Atlantis")
