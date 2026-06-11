"""Domain primitives: entities, value objects, and physical constants.

Phase 0 pins only the coordinate frame and pitch geometry, because the
coordinate convention is the single most bug-prone contract in football data
(see docs/04-data-pipeline.md section 4). Everything downstream - ETL, physics,
the UI pitch component - standardizes on the frame defined in
:mod:`restart.domain.pitch`.
"""

from restart.domain.pitch import (
    GOAL_HEIGHT_M,
    GOAL_WIDTH_M,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    is_on_pitch,
)

__all__ = [
    "GOAL_HEIGHT_M",
    "GOAL_WIDTH_M",
    "PITCH_LENGTH_M",
    "PITCH_WIDTH_M",
    "is_on_pitch",
]
