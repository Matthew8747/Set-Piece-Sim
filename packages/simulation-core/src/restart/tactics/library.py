"""Canonical content library: corner routines, FK routines, and defensive schemes.

All routines use the attacking-toward-+x coordinate frame. Corners are designed
for the right-side default (kick from (52.5, -34)); the Scenario constructor
takes corner_side to flip if needed.

Coordinate reference points:
  Goal center (attacking target): (52.5, 0)
  Near post (right corner attack): (52.5, -3.66)
  Far post:                        (52.5, +3.66)
  6-yard box corners:              (46.5, Â±9.16)  â€” approx
  Penalty spot:                    (41.5, 0)
  Penalty box edge (center):       (36.5, 0)
  Penalty box corners:             (36.5, Â±20.16)

Zonal scheme coordinate choices:
  Defenders cluster around the six-yard box and near/far post region.
  Typical zonal lines:
    x~50: near-goal line (just off goal line, inside 6-yd box)
    x~47: six-yard box edge
    x~44: edge of main contest zone
    x~41: penalty spot area
    x~38: edge-of-box / recycling zone
"""

from __future__ import annotations

from restart.tactics.routine import (
    Assignment,
    Delivery,
    DeliveryType,
    Intent,
    PitchPoint,
    RoutineSpec,
    RunLeg,
    SetPiece,
    Trigger,
)
from restart.tactics.scheme import DefensiveScheme

# ---------------------------------------------------------------------------
# Defensive schemes
# ---------------------------------------------------------------------------


def zonal_six_two() -> DefensiveScheme:
    """Zonal-dominant scheme: 8 zonal positions + 2 man-markers.

    Zonal points occupy the main goal-threat corridor from goal line to the
    penalty arc. Two markers shadow the primary aerial threats.

    Points (8 zonal):
      Near-post inner guard:  (50.5, -2.0)
      Near-post outer guard:  (50.5, -5.0)
      Far-post inner guard:   (50.5,  2.0)
      Far-post outer guard:   (50.5,  5.0)
      Goal-line sweep left:   (48.0, -4.0)
      Goal-line sweep right:  (48.0,  4.0)
      Penalty-spot anchor:    (44.0,  0.0)
      Short-edge recycler:    (38.0,  0.0)
    """
    return DefensiveScheme(
        name="zonal_six_two",
        zonal_points=(
            PitchPoint(x=50.5, y=-2.0),
            PitchPoint(x=50.5, y=-5.0),
            PitchPoint(x=50.5, y=2.0),
            PitchPoint(x=50.5, y=5.0),
            PitchPoint(x=48.0, y=-4.0),
            PitchPoint(x=48.0, y=4.0),
            PitchPoint(x=44.0, y=0.0),
            PitchPoint(x=38.0, y=0.0),
        ),
        n_man_markers=2,
        gk_position=PitchPoint(x=51.5, y=0.0),
        wall_size=0,
    )


def man_marking_heavy() -> DefensiveScheme:
    """Man-marking-heavy scheme: 2 zonal positions + 8 man-markers.

    Two zonal anchors hold the goal-line and penalty-spot; 8 markers
    shadow attackers aggressively. Common against teams with a clear
    aerial hierarchy.

    Zonal points (2):
      Goal-line sweeper:  (50.0, 0.0)  â€” central cover
      Penalty-arc anchor: (36.5, 0.0)  â€” second-ball collector
    """
    return DefensiveScheme(
        name="man_marking_heavy",
        zonal_points=(
            PitchPoint(x=50.0, y=0.0),
            PitchPoint(x=36.5, y=0.0),
        ),
        n_man_markers=8,
        gk_position=PitchPoint(x=51.5, y=0.0),
        wall_size=0,
    )


def hybrid() -> DefensiveScheme:
    """Hybrid 5-5 scheme: 5 zonal positions + 5 man-markers.

    Balances space coverage and individual tracking. The five zonal points
    occupy the key delivery zones; the five markers shadow the primary
    attacking threats.

    Zonal points (5):
      Near-post guard:    (50.5, -3.0)
      Far-post guard:     (50.5,  3.0)
      Six-yard box left:  (47.5, -3.5)
      Six-yard box right: (47.5,  3.5)
      Penalty-spot:       (41.5,  0.0)
    """
    return DefensiveScheme(
        name="hybrid",
        zonal_points=(
            PitchPoint(x=50.5, y=-3.0),
            PitchPoint(x=50.5, y=3.0),
            PitchPoint(x=47.5, y=-3.5),
            PitchPoint(x=47.5, y=3.5),
            PitchPoint(x=41.5, y=0.0),
        ),
        n_man_markers=5,
        gk_position=PitchPoint(x=51.5, y=0.0),
        wall_size=0,
    )


# ---------------------------------------------------------------------------
# Corner routines (right-side default; kick from (52.5, -34))
# ---------------------------------------------------------------------------


def near_post_inswinger() -> RoutineSpec:
    """Classic near-post inswinger corner (4 attackers).

    Primary threat: near-post flick-on runner arriving at (49.5, -2.5).
    Secondary threat: far-post arrival at (50.0, 4.5) for a redirect.
    Screen: a tall player occupies the GK at (50.5, 0.5).
    Edge: second-ball collector at (38.0, 2.0) for any clearance.

    All runners start 8-12 m from their targets and time their runs to arrive
    as the ball reaches the near post.
    """
    return RoutineSpec(
        set_piece=SetPiece.CORNER,
        name="near_post_inswinger",
        delivery=Delivery(
            type=DeliveryType.INSWINGER,
            target=PitchPoint(x=49.5, y=-2.5),
            speed_ms=24.0,
            spin_rps=8.0,
        ),
        assignments=(
            Assignment(
                role="near_post_runner",
                start=PitchPoint(x=38.0, y=-5.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=49.5, y=-2.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.ATTACK_BALL,
            ),
            Assignment(
                role="far_post_runner",
                start=PitchPoint(x=40.0, y=8.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=50.0, y=4.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.2,
                    ),
                ),
                intent=Intent.ATTACK_BALL,
            ),
            Assignment(
                role="gk_screen",
                start=PitchPoint(x=46.0, y=1.5),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=50.5, y=0.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SCREEN,
            ),
            Assignment(
                role="edge_collector",
                start=PitchPoint(x=36.5, y=5.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=38.0, y=2.0),
                        trigger=Trigger.BALL_APEX,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SECOND_BALL,
            ),
        ),
    )


def far_post_outswinger() -> RoutineSpec:
    """Far-post outswinger corner (4 attackers).

    The outswinger curves away from the near post toward the far post zone,
    inviting a far-post header. A near-post decoy drags attention away.

    Primary: far-post header at (50.5, 5.0).
    Secondary: penalty-spot header at (42.0, 0.5) for second ball.
    Decoy: near-post drag run to (49.0, -3.5).
    Edge: recycler at (37.0, -2.0).
    """
    return RoutineSpec(
        set_piece=SetPiece.CORNER,
        name="far_post_outswinger",
        delivery=Delivery(
            type=DeliveryType.OUTSWINGER,
            target=PitchPoint(x=50.5, y=5.0),
            speed_ms=23.0,
            spin_rps=7.0,
        ),
        assignments=(
            Assignment(
                role="far_post_header",
                start=PitchPoint(x=39.0, y=9.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=50.5, y=5.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.1,
                    ),
                ),
                intent=Intent.ATTACK_BALL,
            ),
            Assignment(
                role="penalty_spot",
                start=PitchPoint(x=37.0, y=3.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=42.0, y=0.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.3,
                    ),
                ),
                intent=Intent.SECOND_BALL,
            ),
            Assignment(
                role="near_post_decoy",
                start=PitchPoint(x=41.0, y=-5.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=49.0, y=-3.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.DECOY,
            ),
            Assignment(
                role="edge_recycler",
                start=PitchPoint(x=35.0, y=-4.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=37.0, y=-2.0),
                        trigger=Trigger.BALL_APEX,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SECOND_BALL,
            ),
        ),
    )


def crowd_keeper() -> RoutineSpec:
    """Crowd-the-keeper corner (4 attackers): two screens + two runners.

    Two tall players screen the GK's movement while two runners attack the
    delivery zones. The GK is hemmed in by bodies near (50.5, 0.5) and
    (50.0, -1.5), creating space for the late runners.

    Primary runners: near-post late arrival and far-post early run.
    """
    return RoutineSpec(
        set_piece=SetPiece.CORNER,
        name="crowd_keeper",
        delivery=Delivery(
            type=DeliveryType.INSWINGER,
            target=PitchPoint(x=50.0, y=0.0),
            speed_ms=22.0,
            spin_rps=7.5,
        ),
        assignments=(
            Assignment(
                role="screen_near_gk",
                start=PitchPoint(x=47.0, y=-1.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=50.5, y=0.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SCREEN,
            ),
            Assignment(
                role="screen_far_gk",
                start=PitchPoint(x=47.0, y=1.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=50.0, y=-1.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SCREEN,
            ),
            Assignment(
                role="late_near_runner",
                start=PitchPoint(x=40.0, y=-6.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=49.5, y=-2.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.3,
                    ),
                ),
                intent=Intent.ATTACK_BALL,
            ),
            Assignment(
                role="far_post_runner",
                start=PitchPoint(x=38.0, y=7.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=50.0, y=4.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.1,
                    ),
                ),
                intent=Intent.ATTACK_BALL,
            ),
        ),
    )


def edge_of_box_pullback() -> RoutineSpec:
    """Edge-of-box short-option pullback (4 attackers).

    A SHORT delivery is played to a player on the edge of the box who can
    shoot, lay off, or drive in. The other assignments make runs to create
    space or collect any secondary balls.

    Since delivery.type == SHORT, no ATTACK_BALL intent is required
    (ADR-004 validation: SHORT delivery exempts the ATTACK_BALL requirement).
    """
    return RoutineSpec(
        set_piece=SetPiece.CORNER,
        name="edge_of_box_pullback",
        delivery=Delivery(
            type=DeliveryType.SHORT,
            # SHORT delivery target: just outside the corner arc, near the
            # short-option player's starting position
            target=PitchPoint(x=47.0, y=-28.0),
            speed_ms=12.0,
            spin_rps=0.0,
        ),
        assignments=(
            Assignment(
                role="short_option",
                start=PitchPoint(x=44.0, y=-25.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=47.0, y=-28.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SHORT_OPTION,
            ),
            Assignment(
                role="box_runner_1",
                start=PitchPoint(x=40.0, y=-4.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=48.0, y=-2.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.4,
                    ),
                ),
                intent=Intent.DECOY,
            ),
            Assignment(
                role="box_runner_2",
                start=PitchPoint(x=38.0, y=4.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=46.0, y=2.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.4,
                    ),
                ),
                intent=Intent.DECOY,
            ),
            Assignment(
                role="edge_shooter",
                start=PitchPoint(x=35.0, y=-8.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=40.0, y=-5.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.2,
                    ),
                ),
                intent=Intent.SECOND_BALL,
            ),
        ),
    )


def decoy_overload() -> RoutineSpec:
    """Decoy overload: two decoys drag near-post, one late far-post run (5 attackers).

    Two decoys storm the near post early to drag all man-markers that side;
    one ATTACK_BALL runner makes a late diagonal run to the far post, arriving
    as defenders have committed. A fifth player holds the penalty spot for
    second ball.

    The late runner gets a delay of 0.4 s to time the run correctly.
    """
    return RoutineSpec(
        set_piece=SetPiece.CORNER,
        name="decoy_overload",
        delivery=Delivery(
            type=DeliveryType.OUTSWINGER,
            target=PitchPoint(x=50.0, y=5.5),
            speed_ms=23.0,
            spin_rps=6.0,
        ),
        assignments=(
            Assignment(
                role="decoy_1",
                start=PitchPoint(x=42.0, y=-7.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=49.0, y=-4.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.DECOY,
            ),
            Assignment(
                role="decoy_2",
                start=PitchPoint(x=39.0, y=-3.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=48.5, y=-2.0),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.1,
                    ),
                ),
                intent=Intent.DECOY,
            ),
            Assignment(
                role="late_far_post",
                start=PitchPoint(x=38.0, y=8.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=50.0, y=5.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.4,
                    ),
                ),
                intent=Intent.ATTACK_BALL,
            ),
            Assignment(
                role="penalty_spot_hold",
                start=PitchPoint(x=39.0, y=2.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=41.5, y=0.5),
                        trigger=Trigger.BALL_APEX,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SECOND_BALL,
            ),
            Assignment(
                role="edge_recycler",
                start=PitchPoint(x=34.0, y=-2.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=36.5, y=-1.0),
                        trigger=Trigger.BALL_APEX,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SECOND_BALL,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# FK routine
# ---------------------------------------------------------------------------


def direct_free_kick() -> RoutineSpec:
    """Direct free kick aimed at goal (1 assignment: second-ball rebounder).

    The delivery is a DRIVEN ball aimed just inside the near post: target
    (51.5, 1.5) â€” on the pitch, inside the goal-mouth area, realistic as a
    delivery aim point just below the crossbar inner post.

    A single rebounder waits at the penalty spot for any save/rebound.

    Note: fk_position is specified at the Scenario level, not in RoutineSpec.
    The delivery target here is the intended ball destination (near-post
    interior), not the kick origin.
    """
    return RoutineSpec(
        set_piece=SetPiece.FREE_KICK,
        name="direct_free_kick",
        delivery=Delivery(
            type=DeliveryType.DRIVEN,
            target=PitchPoint(x=51.5, y=1.5),
            speed_ms=28.0,
            spin_rps=3.0,
        ),
        assignments=(
            Assignment(
                role="rebounder",
                start=PitchPoint(x=39.0, y=0.0),
                runs=(
                    RunLeg(
                        to=PitchPoint(x=41.5, y=0.5),
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=0.0,
                    ),
                ),
                intent=Intent.SECOND_BALL,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Collection functions
# ---------------------------------------------------------------------------


def all_corner_routines() -> tuple[RoutineSpec, ...]:
    """Return all canonical corner routines."""
    return (
        near_post_inswinger(),
        far_post_outswinger(),
        crowd_keeper(),
        edge_of_box_pullback(),
        decoy_overload(),
    )


def all_schemes() -> tuple[DefensiveScheme, ...]:
    """Return all canonical defensive schemes."""
    return (
        zonal_six_two(),
        man_marking_heavy(),
        hybrid(),
    )
