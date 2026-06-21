"""The optimizer genome: typed search-space params and the params -> Scenario map.

Pure domain (the dependency rule): no Optuna/ML/IO here. This module defines the
mixed-type search space (design doc 06 sec3.1) and the *genotype -> phenotype*
builder that turns a flat parameter dict into a validated :class:`Scenario`. The
search algorithms (Optuna TPE, random) live in the ``restart_opt`` package and
only ever see this pure interface.

Why a fixed runner template + a zone grid (not raw coordinates): keeps the
dimensionality sane (~10-15 dims) and keeps every sampled genome close to a
football-plausible shape, instead of letting the optimizer scatter runners to
arbitrary points it can exploit. Infeasible combinations are rejected by Routine
Spec validation (ADR-004 d2): the builder raises, the driver prunes the trial.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from restart.players.player import PositionGroup
from restart.tactics.compile import Scenario
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

#: A single genome value: continuous, integral, or a categorical label.
ParamValue = float | int | str


@runtime_checkable
class Param(Protocol):
    """A named search dimension that validates one value (raises on violation)."""

    @property
    def name(self) -> str: ...

    def validate(self, value: object) -> ParamValue: ...


@dataclass(frozen=True, slots=True)
class ContinuousParam:
    name: str
    lo: float
    hi: float

    def validate(self, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"param {self.name} expects a number, got {value!r}")
        v = float(value)
        if not self.lo <= v <= self.hi:
            raise ValueError(f"param {self.name}={v} outside [{self.lo}, {self.hi}]")
        return v


@dataclass(frozen=True, slots=True)
class IntParam:
    name: str
    lo: int
    hi: int

    def validate(self, value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"param {self.name} expects an integer, got {value!r}")
        f = float(value)
        if f != int(f):
            raise ValueError(f"param {self.name}={value!r} is not integral")
        iv = int(f)
        if not self.lo <= iv <= self.hi:
            raise ValueError(f"param {self.name}={iv} outside [{self.lo}, {self.hi}]")
        return iv


@dataclass(frozen=True, slots=True)
class CategoricalParam:
    name: str
    choices: tuple[str, ...]

    def validate(self, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError(f"param {self.name} expects a string, got {value!r}")
        if value not in self.choices:
            raise ValueError(f"param {self.name}={value!r} not a valid choice {self.choices}")
        return value


@dataclass(frozen=True, slots=True)
class SearchSpace:
    """The optimizer's genome definition: an ordered tuple of typed params."""

    params: tuple[Param, ...]

    def names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.params)

    def validate(self, values: Mapping[str, object]) -> dict[str, ParamValue]:
        by_name = {p.name: p for p in self.params}
        unknown = set(values) - set(by_name)
        if unknown:
            raise ValueError(f"unknown params: {sorted(unknown)}")
        return {name: by_name[name].validate(values[name]) for name in values}


@runtime_checkable
class Genome(Protocol):
    """A genotype -> phenotype map: a search space plus a builder to a Scenario."""

    @property
    def space(self) -> SearchSpace: ...

    def defaults(self) -> dict[str, ParamValue]: ...

    def to_scenario(self, base: Scenario, values: Mapping[str, object]) -> Scenario: ...


# ---------------------------------------------------------------------------
# Corner genome: a fixed runner template over a discrete zone grid
# ---------------------------------------------------------------------------

#: Named delivery target zones for runner final legs. A grid (not raw x/y) keeps
#: dimensionality sane and keeps sampled genomes football-plausible (doc 06).
ZONE_GRID: dict[str, PitchPoint] = {
    "near_post": PitchPoint(x=50.5, y=-3.0),
    "far_post": PitchPoint(x=50.5, y=3.0),
    "six_left": PitchPoint(x=47.5, y=-4.0),
    "six_right": PitchPoint(x=47.5, y=4.0),
    "penalty_spot": PitchPoint(x=41.5, y=0.0),
    "goalmouth": PitchPoint(x=50.0, y=0.0),
    "edge": PitchPoint(x=38.0, y=0.0),
    # Off-ball zones (Phase 8): not every runner contests the 6-yard box — these
    # let the optimizer place lurkers / recyclers / half-space arrivals for
    # cut-backs and second balls.
    "top_of_box": PitchPoint(x=35.0, y=0.0),
    "left_half_space": PitchPoint(x=41.0, y=-10.0),
    "right_half_space": PitchPoint(x=41.0, y=10.0),
    "deep_recycle": PitchPoint(x=32.0, y=0.0),
}
ZONE_CHOICES: tuple[str, ...] = tuple(ZONE_GRID)

DELIVERY_CHOICES: tuple[str, ...] = ("inswinger", "outswinger", "driven", "floated")
#: Crossing-delivery genome excludes SHORT (different routine semantics + the
#: ATTACK_BALL-requirement exemption); SHORT routines are a separate study.
_DELIVERY_MAP: dict[str, DeliveryType] = {
    "inswinger": DeliveryType.INSWINGER,
    "outswinger": DeliveryType.OUTSWINGER,
    "driven": DeliveryType.DRIVEN,
    "floated": DeliveryType.FLOATED,
}

INTENT_CHOICES: tuple[str, ...] = ("attack_ball", "decoy", "screen", "second_ball")
_INTENT_MAP: dict[str, Intent] = {
    "attack_ball": Intent.ATTACK_BALL,
    "decoy": Intent.DECOY,
    "screen": Intent.SCREEN,
    "second_ball": Intent.SECOND_BALL,
}

#: Fixed runner start positions by slot (the optimizer moves targets + timing,
#: not start points — those are an attacking-shape choice, not a search dim).
_DEFAULT_STARTS: tuple[PitchPoint, ...] = (
    PitchPoint(x=38.0, y=-5.0),
    PitchPoint(x=40.0, y=8.0),
    PitchPoint(x=46.0, y=1.5),
    PitchPoint(x=36.5, y=5.0),
    PitchPoint(x=42.0, y=-7.0),
    PitchPoint(x=39.0, y=2.0),
    PitchPoint(x=34.0, y=-2.0),
)

# Slots 0-3 contest the box; slots 4-6 default to off-ball roles (lurk / recycle
# / half-space) so a widened template reads like a real overload, not seven
# bodies in the six-yard box.
_DEFAULT_ZONES = (
    "near_post",
    "far_post",
    "goalmouth",
    "six_right",
    "top_of_box",
    "left_half_space",
    "deep_recycle",
)
_DEFAULT_INTENTS = (
    "attack_ball",
    "attack_ball",
    "screen",
    "attack_ball",
    "second_ball",
    "decoy",
    "second_ball",
)
_DEFAULT_DELAYS = (0.0, 0.2, 0.0, 0.1, 0.3, 0.4, 0.5)


# --- Shared template builders (corner + free-kick genomes use the same shape) -
# A fixed-arity runner template: delivery (target/speed/spin/type) + per-runner
# (target zone, run-timing delay, intent). Extracted so the corner and free-kick
# genomes cannot drift apart silently (both are policed by the genome tests).


def _template_params(n_runners: int, fixed_lead_attacker: bool) -> tuple[Param, ...]:
    params: list[Param] = [
        ContinuousParam("target_x", 40.0, 52.0),
        ContinuousParam("target_y", -8.0, 8.0),
        ContinuousParam("speed_ms", 16.0, 32.0),
        ContinuousParam("spin_rps", 2.0, 12.0),
        CategoricalParam("delivery_type", DELIVERY_CHOICES),
    ]
    for i in range(n_runners):
        params.append(CategoricalParam(f"r{i}_zone", ZONE_CHOICES))
        params.append(ContinuousParam(f"r{i}_delay", 0.0, 1.0))
        if not (fixed_lead_attacker and i == 0):
            params.append(CategoricalParam(f"r{i}_intent", INTENT_CHOICES))
    return tuple(params)


def _template_defaults(n_runners: int, fixed_lead_attacker: bool) -> dict[str, ParamValue]:
    d: dict[str, ParamValue] = {
        "target_x": 49.5,
        "target_y": -2.5,
        "speed_ms": 24.0,
        "spin_rps": 8.0,
        "delivery_type": "inswinger",
    }
    for i in range(n_runners):
        d[f"r{i}_zone"] = _DEFAULT_ZONES[i]
        d[f"r{i}_delay"] = _DEFAULT_DELAYS[i]
        if not (fixed_lead_attacker and i == 0):
            d[f"r{i}_intent"] = _DEFAULT_INTENTS[i]
    return d


def _build_delivery(v: Mapping[str, ParamValue]) -> Delivery:
    return Delivery(
        type=_DELIVERY_MAP[str(v["delivery_type"])],
        target=PitchPoint(x=float(v["target_x"]), y=float(v["target_y"])),
        speed_ms=float(v["speed_ms"]),
        spin_rps=float(v["spin_rps"]),
    )


def _build_assignments(
    v: Mapping[str, ParamValue], n_runners: int, fixed_lead_attacker: bool
) -> tuple[Assignment, ...]:
    assignments: list[Assignment] = []
    for i in range(n_runners):
        target = ZONE_GRID[str(v[f"r{i}_zone"])]
        intent = (
            Intent.ATTACK_BALL
            if (fixed_lead_attacker and i == 0)
            else _INTENT_MAP[str(v[f"r{i}_intent"])]
        )
        assignments.append(
            Assignment(
                role=f"runner_{i}",
                start=_DEFAULT_STARTS[i],
                runs=(
                    RunLeg(
                        to=target,
                        trigger=Trigger.KICK_APPROACH,
                        delay_s=float(v[f"r{i}_delay"]),
                    ),
                ),
                intent=intent,
            )
        )
    return tuple(assignments)


def _role_map(base: Scenario, n_runners: int) -> dict[str, str]:
    outfield = [
        p.player_id
        for p in base.attacking_team.players
        if p.position_group is not PositionGroup.GK and p.player_id != base.kicker_id
    ]
    if len(outfield) < n_runners:
        raise ValueError(f"attacking_team has {len(outfield)} outfielders < {n_runners}")
    return {f"runner_{i}": outfield[i] for i in range(n_runners)}


@dataclass(frozen=True, slots=True)
class CornerGenome:
    """A fixed-arity corner template parameterized for optimization.

    Free dimensions: delivery (target x/y, speed, spin, type) + per-runner
    (target zone, run-timing delay, intent). With ``fixed_lead_attacker`` the
    slot-0 runner's intent is pinned to ATTACK_BALL, which guarantees the CORNER
    non-short feasibility rule and avoids wasting trials on infeasible genomes.

    ``n_runners`` is fixed per study (kicker + n_runners attackers); the template
    spans box contesters and off-ball roles (lurk / recycle / half-space) so a
    wider overload reads like a real corner, not bodies stacked in the six-yard
    box (Phase 8, O-2 widened — arity stays fixed, not searched).
    """

    n_runners: int = 4
    fixed_lead_attacker: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.n_runners <= len(_DEFAULT_STARTS):
            raise ValueError(f"n_runners must be in [1, {len(_DEFAULT_STARTS)}]")

    @property
    def space(self) -> SearchSpace:
        return SearchSpace(_template_params(self.n_runners, self.fixed_lead_attacker))

    def defaults(self) -> dict[str, ParamValue]:
        return _template_defaults(self.n_runners, self.fixed_lead_attacker)

    def to_scenario(self, base: Scenario, values: Mapping[str, object]) -> Scenario:
        v = self.space.validate(values)
        missing = set(self.space.names()) - set(v)
        if missing:
            raise ValueError(f"missing genome params: {sorted(missing)}")
        # RoutineSpec validation raises ValueError on an infeasible genome.
        routine = RoutineSpec(
            set_piece=SetPiece.CORNER,
            name="optimized_corner",
            delivery=_build_delivery(v),
            assignments=_build_assignments(v, self.n_runners, self.fixed_lead_attacker),
        )
        return Scenario(
            routine=routine,
            attacking_team=base.attacking_team,
            defending_team=base.defending_team,
            kicker_id=base.kicker_id,
            role_assignments=_role_map(base, self.n_runners),
            scheme=base.scheme,
            corner_side=base.corner_side,
        )


@dataclass(frozen=True, slots=True)
class FreeKickGenome:
    """A fixed-arity wide free-kick template (delivery into the box + runners).

    Reuses the corner runner template; builds a FREE_KICK routine and preserves
    the base scenario's ``fk_position`` (the kick origin is study config, not a
    search dimension) and its scheme (the wall is the defence's concern). Offside
    lines and runners-from-off-the-ball timing are NOT modeled here — that is the
    carried O-3 fidelity cut, a later phase.
    """

    n_runners: int = 4
    fixed_lead_attacker: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.n_runners <= len(_DEFAULT_STARTS):
            raise ValueError(f"n_runners must be in [1, {len(_DEFAULT_STARTS)}]")

    @property
    def space(self) -> SearchSpace:
        return SearchSpace(_template_params(self.n_runners, self.fixed_lead_attacker))

    def defaults(self) -> dict[str, ParamValue]:
        return _template_defaults(self.n_runners, self.fixed_lead_attacker)

    def to_scenario(self, base: Scenario, values: Mapping[str, object]) -> Scenario:
        if base.fk_position is None:
            raise ValueError("FreeKickGenome requires base.fk_position (the kick origin)")
        v = self.space.validate(values)
        missing = set(self.space.names()) - set(v)
        if missing:
            raise ValueError(f"missing genome params: {sorted(missing)}")
        routine = RoutineSpec(
            set_piece=SetPiece.FREE_KICK,
            name="optimized_free_kick",
            delivery=_build_delivery(v),
            assignments=_build_assignments(v, self.n_runners, self.fixed_lead_attacker),
        )
        return Scenario(
            routine=routine,
            attacking_team=base.attacking_team,
            defending_team=base.defending_team,
            kicker_id=base.kicker_id,
            role_assignments=_role_map(base, self.n_runners),
            scheme=base.scheme,
            corner_side=base.corner_side,
            fk_position=base.fk_position,
        )


# ---------------------------------------------------------------------------
# Delivery-only genome: the v1 continuous delivery sub-space
# ---------------------------------------------------------------------------


def corner_delivery_space() -> SearchSpace:
    """The continuous delivery sub-space (bounds match Routine Spec validation)."""
    return SearchSpace(
        (
            ContinuousParam("target_x", 40.0, 52.0),
            ContinuousParam("target_y", -8.0, 8.0),
            ContinuousParam("speed_ms", 16.0, 32.0),
            ContinuousParam("spin_rps", 2.0, 12.0),
        )
    )


@dataclass(frozen=True, slots=True)
class DeliveryGenome:
    """Mutates only the base routine's delivery (target/speed/spin); runner
    assignments are inherited unchanged. The minimal v1 sub-space."""

    @property
    def space(self) -> SearchSpace:
        return corner_delivery_space()

    def defaults(self) -> dict[str, ParamValue]:
        return {"target_x": 49.5, "target_y": -2.5, "speed_ms": 24.0, "spin_rps": 8.0}

    def to_scenario(self, base: Scenario, values: Mapping[str, object]) -> Scenario:
        v = self.space.validate(values)
        d = base.routine.delivery
        new_delivery = Delivery(
            type=d.type,
            target=PitchPoint(
                x=float(v.get("target_x", d.target.x)),
                y=float(v.get("target_y", d.target.y)),
            ),
            speed_ms=float(v.get("speed_ms", d.speed_ms)),
            spin_rps=float(v.get("spin_rps", d.spin_rps)),
        )
        routine = base.routine.model_copy(update={"delivery": new_delivery})
        return base.model_copy(update={"routine": routine})
