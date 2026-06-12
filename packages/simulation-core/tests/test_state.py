"""BallState and state-packing tests: validation, immutability, round-trips."""

import numpy as np
import pytest

from restart.physics import BallState
from restart.physics.state import pack_states


class TestValidation:
    def test_wrong_shape_rejected(self) -> None:
        with pytest.raises(ValueError, match="position"):
            BallState(position=np.zeros(2), velocity=np.zeros(3))

    def test_non_finite_rejected(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            BallState(position=np.array([0.0, np.nan, 0.0]), velocity=np.zeros(3))

    def test_negative_time_rejected(self) -> None:
        with pytest.raises(ValueError, match="time_s"):
            BallState(position=np.zeros(3), velocity=np.zeros(3), time_s=-1.0)

    def test_from_vector_shape_check(self) -> None:
        with pytest.raises(ValueError, match=r"\(9,\)"):
            BallState.from_vector(np.zeros(6))


class TestImmutability:
    def test_arrays_read_only(self) -> None:
        s = BallState(position=np.zeros(3), velocity=np.zeros(3))
        with pytest.raises(ValueError, match="read-only"):
            s.position[0] = 1.0

    def test_defensive_copy_breaks_aliasing(self) -> None:
        raw = np.array([1.0, 2.0, 3.0])
        s = BallState(position=raw, velocity=np.zeros(3))
        raw[0] = 99.0
        assert s.position[0] == 1.0


class TestConversions:
    def test_vector_round_trip(self) -> None:
        s = BallState(
            position=np.array([1.0, 2.0, 3.0]),
            velocity=np.array([4.0, 5.0, 6.0]),
            spin=np.array([7.0, 8.0, 9.0]),
            time_s=2.5,
        )
        s2 = BallState.from_vector(s.to_vector(), time_s=s.time_s)
        np.testing.assert_array_equal(s2.position, s.position)
        np.testing.assert_array_equal(s2.velocity, s.velocity)
        np.testing.assert_array_equal(s2.spin, s.spin)
        assert s2.time_s == s.time_s

    def test_to_vector_is_writable_copy(self) -> None:
        s = BallState(position=np.zeros(3), velocity=np.zeros(3))
        y = s.to_vector()
        y[0] = 42.0  # must not raise: integrator needs writable state
        assert s.position[0] == 0.0

    def test_speed_and_spin_properties(self) -> None:
        s = BallState(
            position=np.zeros(3),
            velocity=np.array([3.0, 4.0, 0.0]),
            spin=np.array([0.0, 0.0, 2.0 * np.pi]),
        )
        assert s.speed_ms == pytest.approx(5.0)
        assert s.spin_rps == pytest.approx(1.0)


class TestPackStates:
    def test_packs_columns_in_state_order(self) -> None:
        pos = np.array([[1.0, 2.0, 3.0]])
        vel = np.array([[4.0, 5.0, 6.0]])
        spin = np.array([[7.0, 8.0, 9.0]])
        y = pack_states(pos, vel, spin)
        np.testing.assert_array_equal(y, [[1, 2, 3, 4, 5, 6, 7, 8, 9]])

    def test_mismatched_shapes_rejected(self) -> None:
        with pytest.raises(ValueError, match="share shape"):
            pack_states(np.zeros((2, 3)), np.zeros((3, 3)), np.zeros((2, 3)))
