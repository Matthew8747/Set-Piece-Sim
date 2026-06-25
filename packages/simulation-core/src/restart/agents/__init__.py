"""Agent kinematics and interception kernels for the set-piece simulation.

Provides broadcast NumPy kernels over agent arrays (SoA contract - ADR-003 d8)
and the frozen ``AgentConfig`` pydantic model. All kernels are Numba-portable:
pure functions over float64 arrays, no Python objects in hot signatures.

See ADR-003 for the full agent-architecture rationale (two-layer scripted +
reactive model, fixed 20 ms tick, 2.5-D kinematics, soft-disc separation).
"""

from restart.agents.config import AgentConfig
from restart.agents.interception import earliest_interception
from restart.agents.kinematics import separate, step_agents, time_to_point

__all__ = [
    "AgentConfig",
    "earliest_interception",
    "separate",
    "step_agents",
    "time_to_point",
]
