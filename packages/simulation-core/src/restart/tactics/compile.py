"""compile_scenario: Scenario → SimProgram (ADR-004 d4).

Resolves all symbolic references (roles, player ids, positions) into flat
read-only float64/int64 arrays suitable for direct consumption by the NumPy
engine and future Numba kernels (ADR-003 d8). The hot loop contains no dict
lookups, no string comparisons, and no pydantic objects after this point.

Spin-sign convention (z-axis = vertical up; positive spin = counter-clockwise
from above):

A RIGHT-side corner is taken from (52.2, -33.7) — bottom-right corner arc.
The delivery velocity is dominantly +y. Magnus acceleration ~ unit(w x v):
w = +z gives z_hat x y_hat = -x_hat — the ball curls AWAY from the goal line
(out-swing). w = -z curls toward +x, into the goal mouth (in-swing). Verified
empirically against the flight model (engine integration tests).

For the LEFT corner (52.2, +33.7) the delivery velocity is dominantly -y and
the signs mirror.

Summary:
  INSWINGER:  spin_sign = -1 if right corner, +1 if left corner
  OUTSWINGER: spin_sign = +1 if right corner, -1 if left corner
  DRIVEN:     spin_sign = 0, effective spin_rps = 2 (topspin/backspin small)
  FLOATED:    spin_sign = 0, effective spin_rps = 1 (minimal spin)
  SHORT:      spin_sign = 0, effective spin_rps = 0 (no spin modelled)
"""

from __future__ import annotations

import dataclasses
from typing import Literal, Self, TypeVar

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, model_validator

from restart.domain.vectors import FloatArray
from restart.players.player import PositionGroup
from restart.players.team import Team
from restart.tactics.routine import (
    INTENT_CODES,
    TRIGGER_CODES,
    DeliveryType,
    Intent,
    PitchPoint,
    RoutineSpec,
    SetPiece,
)
from restart.tactics.scheme import DefensiveScheme

_AnyArray = TypeVar("_AnyArray", bound=npt.NDArray[np.generic])

# ---------------------------------------------------------------------------
# Scenario — validated "compile input"
# ---------------------------------------------------------------------------


class Scenario(BaseModel):
    """Everything needed to compile a SimProgram for one set-piece execution.

    Validation rules (all raise ValueError on violation):
    * role_assignments must cover exactly the routine's roles — no missing,
      no extra.
    * All player_ids in role_assignments must be in attacking_team.
    * kicker_id must be in attacking_team and NOT among role_assignment values
      (the kicker is the delivery agent, not a running assignment).
    * For FREE_KICK: fk_position is required and must be in the attacking half
      (x > 0).
    * For CORNER: fk_position must be None.
    * For CORNER: scheme.wall_size must be 0 (no FK wall on corners).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    routine: RoutineSpec
    attacking_team: Team
    defending_team: Team
    kicker_id: str
    role_assignments: dict[str, str]  # role -> player_id
    scheme: DefensiveScheme
    corner_side: Literal["left", "right"] = "right"
    fk_position: PitchPoint | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_scenario(self) -> Self:
        att_ids = {p.player_id for p in self.attacking_team.players}
        routine_roles = {a.role for a in self.routine.assignments}

        # Role coverage: role_assignments must cover exactly the routine's roles
        assigned_roles = set(self.role_assignments.keys())
        missing = routine_roles - assigned_roles
        extra = assigned_roles - routine_roles
        if missing:
            msg = f"role_assignments missing roles: {sorted(missing)}"
            raise ValueError(msg)
        if extra:
            msg = f"role_assignments has extra roles not in routine: {sorted(extra)}"
            raise ValueError(msg)

        # All assigned player ids must be in attacking team
        foreign = {pid for pid in self.role_assignments.values() if pid not in att_ids}
        if foreign:
            msg = f"role_assignments references player_ids not in attacking_team: {sorted(foreign)}"
            raise ValueError(msg)

        # kicker_id must be in attacking team
        if self.kicker_id not in att_ids:
            msg = f"kicker_id {self.kicker_id!r} is not in attacking_team"
            raise ValueError(msg)

        # kicker must not be among the role assignment values (no double-use)
        if self.kicker_id in self.role_assignments.values():
            msg = (
                f"kicker_id {self.kicker_id!r} appears in role_assignments; "
                f"the kicker cannot simultaneously run an assignment"
            )
            raise ValueError(msg)

        # FREE_KICK: fk_position required and in attacking half
        if self.routine.set_piece == SetPiece.FREE_KICK:
            if self.fk_position is None:
                msg = "fk_position is required for FREE_KICK set pieces"
                raise ValueError(msg)
            if self.fk_position.x <= 0.0:
                msg = f"fk_position x={self.fk_position.x} must be in the attacking half (x > 0)"
                raise ValueError(msg)

        # CORNER: fk_position must be None; wall_size must be 0
        if self.routine.set_piece == SetPiece.CORNER:
            if self.fk_position is not None:
                msg = "fk_position must be None for CORNER set pieces"
                raise ValueError(msg)
            if self.scheme.wall_size != 0:
                msg = f"scheme.wall_size={self.scheme.wall_size} must be 0 for CORNER set pieces"
                raise ValueError(msg)

        return self


# ---------------------------------------------------------------------------
# SimProgram — flat read-only SoA arrays for the hot loop
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class SimProgram:
    """Compiled, flat, read-only representation of a set-piece scenario.

    All arrays are float64 or int64/int8, C-contiguous, read-only. No dicts,
    strings, or pydantic objects are reachable from the hot loop — only this
    dataclass and its arrays (ADR-003 d8, ADR-004 d4).

    Array shapes and dtypes
    -----------------------
    set_piece: int — 0=corner, 1=free_kick
    kick_pos: (2,) float64 — [x, y] kick position
    delivery_type: int — DeliveryType code (INSWINGER=0..SHORT=4)
    delivery_target: (2,) float64
    delivery_speed_ms: float
    delivery_spin_rps: float — magnitude (after type-scaling)
    spin_sign: float — +1/-1/0 (see module docstring for derivation)

    n_attackers: int — number of assignment runners (kicker excluded)
    att_attr: (na, N_ATTR) float64 — attribute matrix
    att_start: (na, 2) float64 — starting positions
    att_intent: (na,) int8 — INTENT_CODES values
    att_player_ids: tuple[str, ...] — for event/replay labelling only
    att_legs_to: (na, 3, 2) float64 — padded NaN for unused legs
    att_legs_trigger: (na, 3) int8 — TRIGGER_CODES; -1 for unused legs
    att_legs_delay: (na, 3) float64 — 0.0 for unused legs
    att_n_legs: (na,) int64 — actual number of legs per attacker

    n_defenders: int
    def_attr: (nd, N_ATTR) float64
    def_start: (nd, 2) float64
    def_player_ids: tuple[str, ...] — for event/replay labelling only
    gk_index: int — index into defender arrays for the GK
    def_mark_target: (nd,) int64 — attacker index (-1 = zonal/no target)

    kicker_attr: (N_ATTR,) float64
    kicker_id: str — for event/replay labelling only
    """

    # Delivery
    set_piece: int
    kick_pos: FloatArray
    delivery_type: int
    delivery_target: FloatArray
    delivery_speed_ms: float
    delivery_spin_rps: float
    spin_sign: float

    # Attackers
    n_attackers: int
    att_attr: FloatArray
    att_start: FloatArray
    att_intent: npt.NDArray[np.int8]
    att_player_ids: tuple[str, ...]
    att_legs_to: FloatArray
    att_legs_trigger: npt.NDArray[np.int8]
    att_legs_delay: FloatArray
    att_n_legs: npt.NDArray[np.int64]

    # Defenders
    n_defenders: int
    def_attr: FloatArray
    def_start: FloatArray
    def_player_ids: tuple[str, ...]
    gk_index: int
    def_mark_target: npt.NDArray[np.int64]

    # Kicker
    kicker_attr: FloatArray
    kicker_id: str


# ---------------------------------------------------------------------------
# DeliveryType codes (parallel to the enum for the hot loop)
# ---------------------------------------------------------------------------

_DELIVERY_TYPE_CODES: dict[DeliveryType, int] = {
    DeliveryType.INSWINGER: 0,
    DeliveryType.OUTSWINGER: 1,
    DeliveryType.DRIVEN: 2,
    DeliveryType.FLOATED: 3,
    DeliveryType.SHORT: 4,
}


def _spin_sign_and_rps(
    delivery_type: DeliveryType, spin_rps: float, corner_side: Literal["left", "right"]
) -> tuple[float, float]:
    """Compute (spin_sign, effective_spin_rps) from delivery type and corner side.

    See module docstring for full sign derivation.
    For FK deliveries, corner_side is ignored; DRIVEN/FLOATED/SHORT get
    reduced spin magnitudes regardless of side.
    """
    # Sign derivation (verified against the Magnus force in flight tests):
    # right corner (52.5, -34), delivery velocity is dominantly +y;
    # Magnus accel ~ unit(w x v): w=+z gives z_hat x y_hat = -x_hat (curls
    # AWAY from the goal line, i.e. OUT-swing); w=-z curls +x toward the goal
    # mouth (IN-swing). Mirrored for the left corner (velocity ~ -y).
    if delivery_type == DeliveryType.INSWINGER:
        sign = -1.0 if corner_side == "right" else 1.0
        return sign, spin_rps
    if delivery_type == DeliveryType.OUTSWINGER:
        sign = 1.0 if corner_side == "right" else -1.0
        return sign, spin_rps
    if delivery_type == DeliveryType.DRIVEN:
        return 0.0, 2.0
    if delivery_type == DeliveryType.FLOATED:
        return 0.0, 1.0
    # SHORT
    return 0.0, 0.0


def _ro(arr: _AnyArray) -> _AnyArray:
    """Make an array read-only and return it (in-place flag set)."""
    arr.setflags(write=False)
    return arr


def _goal_dist(xy: FloatArray) -> float:
    """Euclidean distance from a (2,) point to the attacking goal (52.5, 0)."""
    return float(np.sqrt((xy[0] - 52.5) ** 2 + xy[1] ** 2))


def compile_scenario(scenario: Scenario) -> SimProgram:
    """Compile a Scenario into a flat, read-only SimProgram.

    This is the only place where symbolic role/player mappings are resolved.
    After this function returns, the engine touches only arrays and scalars.

    Determinism: same Scenario (same field values) always produces identical
    byte-level array content — no randomness, no process-state dependence.
    """
    routine = scenario.routine
    scheme = scenario.scheme
    att_team = scenario.attacking_team
    def_team = scenario.defending_team

    # ------------------------------------------------------------------
    # 1. Kick position
    # ------------------------------------------------------------------
    if routine.set_piece == SetPiece.CORNER:
        # corner_side: "left" from attacker view = y=+34, "right" = y=-34
        # Ball placed on the corner arc, ~0.3 m inside both lines: taking it
        # exactly on the goal-line plane makes every inswinger cross the plane
        # (out of play) the moment spin bites.
        ky = 33.7 if scenario.corner_side == "left" else -33.7
        kick_pos = _ro(np.array([52.2, ky], dtype=np.float64))
    else:
        assert scenario.fk_position is not None  # validated by Scenario
        kick_pos = _ro(scenario.fk_position.as_array().copy())

    # ------------------------------------------------------------------
    # 2. Delivery
    # ------------------------------------------------------------------
    delivery = routine.delivery
    spin_sign, eff_spin_rps = _spin_sign_and_rps(
        delivery.type, delivery.spin_rps, scenario.corner_side
    )
    delivery_target = _ro(delivery.target.as_array().copy())
    delivery_type_code = _DELIVERY_TYPE_CODES[delivery.type]

    # ------------------------------------------------------------------
    # 3. Build attacker arrays (routine.assignments order; kicker excluded)
    # ------------------------------------------------------------------
    # role -> player_id mapping from scenario; assignments define order
    # Build a lookup for player objects from attacking team
    att_by_id = {p.player_id: p for p in att_team.players}

    # attacker list in assignment order
    att_entries = [
        (assignment, scenario.role_assignments[assignment.role])
        for assignment in routine.assignments
    ]
    na = len(att_entries)

    att_player_ids: tuple[str, ...] = tuple(pid for _, pid in att_entries)
    att_attr_arr = _ro(
        np.ascontiguousarray(att_team.attribute_matrix(list(att_player_ids)), dtype=np.float64)
    )

    att_start_arr = np.empty((na, 2), dtype=np.float64)
    att_intent_arr = np.empty((na,), dtype=np.int8)
    att_legs_to_arr = np.full((na, 3, 2), np.nan, dtype=np.float64)
    att_legs_trigger_arr = np.full((na, 3), -1, dtype=np.int8)
    att_legs_delay_arr = np.zeros((na, 3), dtype=np.float64)
    att_n_legs_arr = np.zeros((na,), dtype=np.int64)

    for i, (assignment, _pid) in enumerate(att_entries):
        att_start_arr[i, 0] = assignment.start.x
        att_start_arr[i, 1] = assignment.start.y
        att_intent_arr[i] = INTENT_CODES[assignment.intent]
        n_legs = len(assignment.runs)
        att_n_legs_arr[i] = n_legs
        for j, leg in enumerate(assignment.runs):
            att_legs_to_arr[i, j, 0] = leg.to.x
            att_legs_to_arr[i, j, 1] = leg.to.y
            att_legs_trigger_arr[i, j] = TRIGGER_CODES[leg.trigger]
            att_legs_delay_arr[i, j] = leg.delay_s

    att_start_arr = _ro(np.ascontiguousarray(att_start_arr))
    att_intent_arr = _ro(np.ascontiguousarray(att_intent_arr))
    att_legs_to_arr = _ro(np.ascontiguousarray(att_legs_to_arr))
    att_legs_trigger_arr = _ro(np.ascontiguousarray(att_legs_trigger_arr))
    att_legs_delay_arr = _ro(np.ascontiguousarray(att_legs_delay_arr))
    att_n_legs_arr = _ro(np.ascontiguousarray(att_n_legs_arr))

    # ------------------------------------------------------------------
    # 4. Kicker
    # ------------------------------------------------------------------
    kicker_player = att_by_id[scenario.kicker_id]
    kicker_attr = _ro(np.ascontiguousarray(kicker_player.attributes.to_row(), dtype=np.float64))

    # ------------------------------------------------------------------
    # 5. Build defender arrays
    # ------------------------------------------------------------------
    # Select defenders: GK + 10 outfielders in squad order
    def_players_all = def_team.players  # full squad

    # Identify GK (first GK in squad)
    gk_player = next(p for p in def_players_all if p.position_group == PositionGroup.GK)

    # Outfielders in squad order (not GK)
    outfielders = [p for p in def_players_all if p.position_group != PositionGroup.GK]
    # Take first 10 outfielders
    outfielders_11 = outfielders[:10]

    # Validate we have enough
    if len(outfielders_11) < 10:
        msg = f"defending_team must have at least 10 outfielders, " f"got {len(outfielders_11)}"
        raise ValueError(msg)

    # Wall positions (FK only; corners have wall_size=0 per Scenario validation)
    wall_player_ids: list[str] = []
    wall_positions: list[FloatArray] = []

    if scheme.wall_size > 0:
        # Direction from kick_pos to goal center (52.5, 0)
        goal_center = np.array([52.5, 0.0], dtype=np.float64)
        kick_xy = kick_pos.copy()
        to_goal = goal_center - kick_xy
        dist_to_goal = float(np.linalg.norm(to_goal))
        if dist_to_goal < 1e-9:
            to_goal = np.array([1.0, 0.0], dtype=np.float64)
        else:
            to_goal = to_goal / dist_to_goal

        # Wall midpoint at 9.15 m from kick_pos
        wall_mid = kick_xy + 9.15 * to_goal

        # Perpendicular to wall direction (rotate 90 deg)
        perp = np.array([-to_goal[1], to_goal[0]], dtype=np.float64)

        # Place wall players spaced 0.4 m apart, centered on wall_mid
        n_wall = scheme.wall_size
        offsets = np.arange(n_wall, dtype=np.float64) - (n_wall - 1) / 2.0
        for k in range(n_wall):
            pos = wall_mid + offsets[k] * 0.4 * perp
            wall_positions.append(pos)

        # Use the highest-marking outfielders for the wall
        wall_outfielders = sorted(outfielders_11, key=lambda p: p.attributes.marking, reverse=True)[
            :n_wall
        ]
        wall_player_ids = [p.player_id for p in wall_outfielders]
        remaining_outfielders = [p for p in outfielders_11 if p not in wall_outfielders]
    else:
        remaining_outfielders = outfielders_11

    # Man-marker assignment
    # Attacker threat ordering: ATTACK_BALL first, then SECOND_BALL, then others.
    # Within class: sorted by distance of final run target (or start if no runs) to goal.
    def _attacker_final_pos(idx: int) -> FloatArray:
        """Return the final position array for attacker at index idx."""
        n = int(att_n_legs_arr[idx])
        if n > 0:
            return np.asarray(att_legs_to_arr[idx, n - 1], dtype=np.float64)
        return np.asarray(att_start_arr[idx], dtype=np.float64)

    def _intent_priority(idx: int) -> int:
        intent_code = int(att_intent_arr[idx])
        if intent_code == INTENT_CODES[Intent.ATTACK_BALL]:
            return 0
        if intent_code == INTENT_CODES[Intent.SECOND_BALL]:
            return 1
        return 2

    attacker_indices_by_threat = sorted(
        range(na),
        key=lambda i: (_intent_priority(i), _goal_dist(_attacker_final_pos(i))),
    )

    n_markers = scheme.n_man_markers
    # Pick highest-marking outfielders from remaining for man-marking
    marker_outfielders = sorted(
        remaining_outfielders, key=lambda p: p.attributes.marking, reverse=True
    )[:n_markers]
    remaining_outfielders_2 = [p for p in remaining_outfielders if p not in marker_outfielders]

    # Marker positions: goal-side of their target attacker
    # Offset = 0.7 m toward goal center (52.5, 0)
    goal_center_arr = np.array([52.5, 0.0], dtype=np.float64)
    marker_positions: list[FloatArray] = []
    marker_target_attacker: list[int] = []

    for k, _marker in enumerate(marker_outfielders):
        att_idx = attacker_indices_by_threat[k] if k < len(attacker_indices_by_threat) else 0
        att_pos = att_start_arr[att_idx].copy()
        to_goal_vec = goal_center_arr - att_pos
        dist = float(np.linalg.norm(to_goal_vec))
        offset_dir = to_goal_vec / dist if dist > 1e-9 else np.array([1.0, 0.0], dtype=np.float64)
        marker_pos = att_pos + 0.7 * offset_dir
        marker_positions.append(marker_pos)
        marker_target_attacker.append(att_idx)

    # Zonal fillers
    zonal_outfielders = remaining_outfielders_2
    zonal_positions = list(scheme.zonal_points)

    # ------------------------------------------------------------------
    # 6. Build defender arrays: GK first (index 0), then wall, markers, zonal
    # ------------------------------------------------------------------
    # Order: [GK, wall..., markers..., zonal...]
    # gk_index = 0
    gk_index = 0

    def_player_ids_list: list[str] = [gk_player.player_id]
    def_positions_list: list[FloatArray] = [
        np.array([scheme.gk_position.x, scheme.gk_position.y], dtype=np.float64)
    ]
    def_mark_target_list: list[int] = [-1]  # GK is zonal

    for k in range(len(wall_player_ids)):
        def_player_ids_list.append(wall_player_ids[k])
        def_positions_list.append(wall_positions[k])
        def_mark_target_list.append(-1)

    for k in range(len(marker_outfielders)):
        def_player_ids_list.append(marker_outfielders[k].player_id)
        def_positions_list.append(marker_positions[k])
        def_mark_target_list.append(marker_target_attacker[k])

    for k, zonal_player in enumerate(zonal_outfielders):
        def_player_ids_list.append(zonal_player.player_id)
        if k < len(zonal_positions):
            zp = zonal_positions[k]
            def_positions_list.append(np.array([zp.x, zp.y], dtype=np.float64))
        else:
            # fallback: place near goal line (should not happen with valid scheme)
            def_positions_list.append(np.array([48.0, 0.0], dtype=np.float64))
        def_mark_target_list.append(-1)

    nd = len(def_player_ids_list)
    def_player_ids: tuple[str, ...] = tuple(def_player_ids_list)

    # Attribute matrix for defenders
    def_attr_arr = _ro(
        np.ascontiguousarray(def_team.attribute_matrix(list(def_player_ids)), dtype=np.float64)
    )

    def_start_arr = np.empty((nd, 2), dtype=np.float64)
    for k, pos in enumerate(def_positions_list):
        def_start_arr[k, 0] = pos[0]
        def_start_arr[k, 1] = pos[1]
    def_start_arr = _ro(np.ascontiguousarray(def_start_arr))

    def_mark_target_arr = _ro(np.ascontiguousarray(np.array(def_mark_target_list, dtype=np.int64)))

    # ------------------------------------------------------------------
    # 7. set_piece code
    # ------------------------------------------------------------------
    set_piece_code = 0 if routine.set_piece == SetPiece.CORNER else 1

    return SimProgram(
        set_piece=set_piece_code,
        kick_pos=kick_pos,
        delivery_type=delivery_type_code,
        delivery_target=delivery_target,
        delivery_speed_ms=float(delivery.speed_ms),
        delivery_spin_rps=float(eff_spin_rps),
        spin_sign=float(spin_sign),
        n_attackers=na,
        att_attr=att_attr_arr,
        att_start=att_start_arr,
        att_intent=att_intent_arr,
        att_player_ids=att_player_ids,
        att_legs_to=att_legs_to_arr,
        att_legs_trigger=att_legs_trigger_arr,
        att_legs_delay=att_legs_delay_arr,
        att_n_legs=att_n_legs_arr,
        n_defenders=nd,
        def_attr=def_attr_arr,
        def_start=def_start_arr,
        def_player_ids=def_player_ids,
        gk_index=gk_index,
        def_mark_target=def_mark_target_arr,
        kicker_attr=kicker_attr,
        kicker_id=scenario.kicker_id,
    )
