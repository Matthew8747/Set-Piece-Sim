"""Set-piece engine: SimProgram + seed -> terminal outcome with events.

Single-scenario reference implementation (ADR-003). The Phase-3 Monte Carlo
layer wraps `SetPieceEngine.run` for batches; the Phase-3 fused kernel ports
its semantics.
"""

from restart.engine.config import EngineConfig
from restart.engine.engine import SetPieceEngine, SetPieceResult

__all__ = ["EngineConfig", "SetPieceEngine", "SetPieceResult"]
