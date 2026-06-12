"""Unit tests for vector utilities (broadcast-polymorphic contract)."""

import numpy as np
import pytest

from restart.domain.vectors import cross, dot, horizontal, norm, unit, vec3


class TestVec3:
    def test_constructs_float64(self) -> None:
        v = vec3(1, 2, 3)
        assert v.dtype == np.float64
        assert v.shape == (3,)


class TestNorm:
    def test_single(self) -> None:
        assert norm(vec3(3.0, 4.0, 0.0)) == pytest.approx(5.0)

    def test_batch_shape(self) -> None:
        batch = np.array([[3.0, 4.0, 0.0], [1.0, 0.0, 0.0]])
        result = norm(batch)
        assert result.shape == (2,)
        assert result == pytest.approx([5.0, 1.0])


class TestUnit:
    def test_normalizes(self) -> None:
        u = unit(vec3(0.0, 0.0, 7.0))
        np.testing.assert_allclose(u, [0.0, 0.0, 1.0])

    def test_zero_maps_to_zero(self) -> None:
        """Load-bearing for Magnus: spin parallel to velocity must not NaN."""
        u = unit(vec3(0.0, 0.0, 0.0))
        np.testing.assert_array_equal(u, np.zeros(3))

    def test_batch_mixed_zero_and_nonzero(self) -> None:
        batch = np.array([[2.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        u = unit(batch)
        np.testing.assert_allclose(u[0], [1.0, 0.0, 0.0])
        np.testing.assert_array_equal(u[1], np.zeros(3))

    def test_result_has_unit_length(self) -> None:
        rng = np.random.default_rng(7)
        v = rng.normal(size=(50, 3))
        lengths = norm(unit(v))
        np.testing.assert_allclose(lengths, np.ones(50), atol=1e-12)


class TestCrossDot:
    def test_cross_right_handed(self) -> None:
        np.testing.assert_allclose(cross(vec3(1, 0, 0), vec3(0, 1, 0)), [0.0, 0.0, 1.0])

    def test_cross_perpendicular_to_inputs(self) -> None:
        rng = np.random.default_rng(11)
        a, b = rng.normal(size=3), rng.normal(size=3)
        c = cross(a, b)
        assert dot(a, c) == pytest.approx(0.0, abs=1e-12)
        assert dot(b, c) == pytest.approx(0.0, abs=1e-12)

    def test_dot_batch(self) -> None:
        a = np.array([[1.0, 2.0, 3.0], [0.0, 1.0, 0.0]])
        b = np.array([[4.0, 5.0, 6.0], [0.0, 2.0, 0.0]])
        np.testing.assert_allclose(dot(a, b), [32.0, 2.0])


class TestHorizontal:
    def test_zeroes_z_only(self) -> None:
        h = horizontal(vec3(1.0, 2.0, 3.0))
        np.testing.assert_allclose(h, [1.0, 2.0, 0.0])

    def test_does_not_mutate_input(self) -> None:
        v = vec3(1.0, 2.0, 3.0)
        horizontal(v)
        assert v[2] == 3.0
