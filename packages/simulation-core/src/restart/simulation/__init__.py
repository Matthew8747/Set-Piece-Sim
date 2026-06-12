"""Simulation contracts: event schemas, termination reasons, and protocols.

This package owns the *shapes* that flow between simulation layers. The
physics package provides concrete implementations; the Monte Carlo layer
(Phase 3) and tactical layer (Phase 2+) consume these contracts without
importing physics internals.
"""

from restart.simulation.events import (
    ApexEvent,
    BounceEvent,
    GoalEvent,
    LaunchEvent,
    OutOfPlayEvent,
    RestEvent,
    SimEvent,
    TerminationReason,
)
from restart.simulation.interfaces import BallSimulator, ForceModel

__all__ = [
    "ApexEvent",
    "BallSimulator",
    "BounceEvent",
    "ForceModel",
    "GoalEvent",
    "LaunchEvent",
    "OutOfPlayEvent",
    "RestEvent",
    "SimEvent",
    "TerminationReason",
]
