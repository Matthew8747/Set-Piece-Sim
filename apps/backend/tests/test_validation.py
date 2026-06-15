"""Input-bounds validation: sim inputs are hostile (doc 02 9, ADR-007 d5).

Covers the request-body bounds that protect compute endpoints (cost-bomb
protection) and the shared ``PitchPoint`` coordinate guard reused by scenario
DTOs.
"""

import pytest
from pydantic import ValidationError

from restart_api.schemas import PITCH_LENGTH_M, PITCH_WIDTH_M, PitchPoint


def test_pitch_point_accepts_in_bounds() -> None:
    p = PitchPoint(x=5.5, y=34.0)
    assert p.x == 5.5 and p.y == 34.0
    # Corners of the valid surface are allowed.
    PitchPoint(x=0.0, y=0.0)
    PitchPoint(x=PITCH_LENGTH_M, y=PITCH_WIDTH_M)


@pytest.mark.parametrize(
    ("x", "y"),
    [(-0.1, 0.0), (PITCH_LENGTH_M + 0.1, 0.0), (0.0, -1.0), (0.0, PITCH_WIDTH_M + 1.0)],
)
def test_pitch_point_rejects_out_of_bounds(x: float, y: float) -> None:
    with pytest.raises(ValidationError):
        PitchPoint(x=x, y=y)
