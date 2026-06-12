"""Ball physics: forces, integration, bounce, trajectories.

Public API re-exported here; internals are importable but not contract.
Assumptions implemented by this package are registered with P-numbers in
``docs/simulation-assumptions.md``.
"""

from restart.physics.batch import FlightBatchResult, simulate_flights
from restart.physics.config import (
    BallConfig,
    BounceConfig,
    DragConfig,
    EnvironmentConfig,
    IntegratorConfig,
    MagnusConfig,
    PhysicsConfig,
)
from restart.physics.forces import ForceSystem, Gravity, MagnusLift, QuadraticDrag
from restart.physics.state import BallState
from restart.physics.trajectory import Trajectory, TrajectorySimulator

__all__ = [
    "BallConfig",
    "BallState",
    "BounceConfig",
    "DragConfig",
    "EnvironmentConfig",
    "FlightBatchResult",
    "ForceSystem",
    "Gravity",
    "IntegratorConfig",
    "MagnusConfig",
    "MagnusLift",
    "PhysicsConfig",
    "QuadraticDrag",
    "Trajectory",
    "TrajectorySimulator",
    "simulate_flights",
]
