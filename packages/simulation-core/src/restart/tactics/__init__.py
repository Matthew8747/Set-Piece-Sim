"""Restart Lab tactics layer - set-piece routine specs, schemes, and compilation.

Implements the rs/1.0 contract (ADR-004): a validated pydantic ``RoutineSpec``
document + ``DefensiveScheme`` → ``Scenario`` → ``SimProgram`` pipeline.

The public API is stable for the engine (Work Package C) and future optimizer
(Phase 5). Column orders and code mappings (INTENT_CODES, TRIGGER_CODES) are
ABI: append-only.

Typical usage::

    from restart.tactics import (
        RoutineSpec, Delivery, Assignment, RunLeg, PitchPoint,
        SetPiece, DeliveryType, Intent, Trigger,
        DefensiveScheme,
        Scenario, SimProgram, compile_scenario,
        INTENT_CODES, TRIGGER_CODES,
    )
    from restart.tactics import library
"""

from restart.tactics import library
from restart.tactics.compile import (
    Scenario,
    SimProgram,
    compile_scenario,
)
from restart.tactics.routine import (
    INTENT_CODES,
    TRIGGER_CODES,
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

__all__ = [
    "INTENT_CODES",
    "TRIGGER_CODES",
    "Assignment",
    "DefensiveScheme",
    "Delivery",
    "DeliveryType",
    "Intent",
    "PitchPoint",
    "RoutineSpec",
    "RunLeg",
    "Scenario",
    "SetPiece",
    "SimProgram",
    "Trigger",
    "compile_scenario",
    "library",
]
