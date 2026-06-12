"""Deterministic synthetic demo squads for testing and development.

WARNING: These are algorithmically generated players, NOT real athletes.
No real player names, ratings, or biographical data are used. All attributes
are synthetic draws within the PlayerAttributes bounds.

Licensing note (doc 04): real rating data (EA Sports, SoFIFA, etc.) is
forbidden in this codebase. Demo squads exist solely for unit tests,
development iteration, and visual demos with no licence exposure.
"""

from restart.players.attributes import PlayerAttributes
from restart.players.player import Player, PositionGroup
from restart.players.team import Team
from restart.simulation.rng import spawn_rng


def demo_team(team_id: str, name: str, seed: int) -> Team:
    """Build a deterministic synthetic 11-player squad (doc 04: no real players).

    Squad composition: 1 GK + 4 DF + 4 MF + 2 FW.
    One MF or FW is assigned delivery >= 0.8 as the designated set-piece kicker.
    Attribute draws have position flavour within PlayerAttributes bounds:

    - GK: tall, higher jump_reach, modest field attrs
    - DF: higher heading/strength/jump_reach/height
    - MF: higher agility/awareness_off/awareness_def
    - FW: higher heading/strength; at least one gets delivery >= 0.8

    Parameters
    ----------
    team_id : str  Short identifier, used as prefix in player_id (e.g. "HOM")
    name    : str  Display name for the team
    seed    : int  RNG seed; same seed always produces identical output.

    Returns
    -------
    Team  Validated squad; passes all Team validators.
    """
    rng = spawn_rng(seed, 0)

    def _uniform(lo: float, hi: float) -> float:
        return float(rng.uniform(lo, hi))

    positions: list[PositionGroup] = (
        [PositionGroup.GK]
        + [PositionGroup.DF] * 4
        + [PositionGroup.MF] * 4
        + [PositionGroup.FW] * 2
    )

    players: list[Player] = []
    kicker_assigned = False

    for i, pos_group in enumerate(positions):
        player_id = f"{team_id}-{i:02d}"
        display_name = f"{name} Player {i + 1}"

        if pos_group is PositionGroup.GK:
            attrs = PlayerAttributes(
                top_speed_ms=_uniform(6.0, 7.5),
                accel_ms2=_uniform(2.5, 4.5),
                reaction_time_s=_uniform(0.15, 0.25),
                agility=_uniform(0.3, 0.6),
                jump_reach_m=_uniform(2.65, 3.00),
                heading=_uniform(0.3, 0.6),
                strength=_uniform(0.4, 0.7),
                marking=_uniform(0.2, 0.5),
                awareness_off=_uniform(0.2, 0.5),
                awareness_def=_uniform(0.5, 0.9),
                delivery=_uniform(0.2, 0.5),
                height_m=_uniform(1.85, 2.05),
            )
        elif pos_group is PositionGroup.DF:
            attrs = PlayerAttributes(
                top_speed_ms=_uniform(6.5, 8.5),
                accel_ms2=_uniform(3.0, 6.0),
                reaction_time_s=_uniform(0.20, 0.35),
                agility=_uniform(0.3, 0.65),
                jump_reach_m=_uniform(2.55, 2.95),
                heading=_uniform(0.55, 1.0),
                strength=_uniform(0.55, 1.0),
                marking=_uniform(0.55, 1.0),
                awareness_off=_uniform(0.2, 0.6),
                awareness_def=_uniform(0.55, 1.0),
                delivery=_uniform(0.1, 0.5),
                height_m=_uniform(1.78, 2.00),
            )
        elif pos_group is PositionGroup.MF:
            # Check if this MF should be the kicker (first MF if no kicker yet)
            is_kicker = not kicker_assigned and (i == 5)  # first MF slot
            delivery_lo = 0.8 if is_kicker else 0.2
            delivery_hi = 1.0 if is_kicker else 0.75
            if is_kicker:
                kicker_assigned = True
            attrs = PlayerAttributes(
                top_speed_ms=_uniform(7.0, 9.0),
                accel_ms2=_uniform(3.5, 6.5),
                reaction_time_s=_uniform(0.18, 0.30),
                agility=_uniform(0.55, 1.0),
                jump_reach_m=_uniform(2.35, 2.75),
                heading=_uniform(0.3, 0.7),
                strength=_uniform(0.3, 0.7),
                marking=_uniform(0.4, 0.8),
                awareness_off=_uniform(0.55, 1.0),
                awareness_def=_uniform(0.55, 1.0),
                delivery=_uniform(delivery_lo, delivery_hi),
                height_m=_uniform(1.68, 1.88),
            )
        else:  # FW
            # If no kicker yet (edge case), assign to first FW
            is_kicker = not kicker_assigned
            delivery_lo = 0.8 if is_kicker else 0.2
            delivery_hi = 1.0 if is_kicker else 0.85
            if is_kicker:
                kicker_assigned = True
            attrs = PlayerAttributes(
                top_speed_ms=_uniform(7.5, 9.8),
                accel_ms2=_uniform(4.0, 8.0),
                reaction_time_s=_uniform(0.17, 0.28),
                agility=_uniform(0.45, 0.85),
                jump_reach_m=_uniform(2.50, 2.95),
                heading=_uniform(0.55, 1.0),
                strength=_uniform(0.45, 0.85),
                marking=_uniform(0.2, 0.55),
                awareness_off=_uniform(0.55, 1.0),
                awareness_def=_uniform(0.25, 0.65),
                delivery=_uniform(delivery_lo, delivery_hi),
                height_m=_uniform(1.70, 1.95),
            )

        players.append(
            Player(
                player_id=player_id,
                display_name=display_name,
                position_group=pos_group,
                attributes=attrs,
            )
        )

    return Team(team_id=team_id, name=name, players=tuple(players))
