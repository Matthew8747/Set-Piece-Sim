"""Team + player catalog from the marts (ADR-007 d2).

Real squads replace the demo squads: identities and attributes are
StatsBomb-derived and provenance-tagged. ``/players`` returns the selected XI
(the same 11 the sim runs), so the workbench shows exactly who plays.
"""

from fastapi import APIRouter

from restart_api.deps import team_repository
from restart_api.schemas import PlayerDTO, TeamSummaryDTO

router = APIRouter(tags=["teams"])

# Every mart attribute is derived from open data (no scraped ratings).
_PROVENANCE = "StatsBomb Open Data (derived attributes)"


@router.get("/teams", response_model=list[TeamSummaryDTO])
def list_teams() -> list[TeamSummaryDTO]:
    return [
        TeamSummaryDTO(team_id=s.team_id, name=s.name, country=s.country, n_players=s.n_players)
        for s in team_repository().list_teams()
    ]


@router.get("/players", response_model=list[PlayerDTO])
def players(team: str) -> list[PlayerDTO]:
    squad = team_repository().get(team)
    return [
        PlayerDTO(
            player_id=p.player_id,
            display_name=p.display_name,
            position_group=p.position_group.value,
            heading=p.attributes.heading,
            delivery=p.attributes.delivery,
            jump_reach_m=p.attributes.jump_reach_m,
            height_m=p.attributes.height_m,
            source=_PROVENANCE,
        )
        for p in squad.players
    ]
