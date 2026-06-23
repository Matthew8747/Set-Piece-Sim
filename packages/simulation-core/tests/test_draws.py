"""Externalized per-sim RNG draw plan (ADR-011, Phase 10).

``SimDraws`` is the seam that lets the Numba kernel and the NumPy reference
engine consume *identical* Philox draws (Numba's in-kernel RNG cannot reproduce
NumPy Philox bit-for-bit). Draws are raw unit variates; the engine/kernel apply
the program+config scaling. The central property tested here is **category
isolation**: each draw category is an independent SeedSequence sub-stream, so
over-provisioning one (e.g. the variable-count contest Gumbels) never shifts
another category's draws — the property that makes a fixed-budget plan safe.
"""

import numpy as np
import pytest

from restart.engine.draws import SimDraws, draw_sim


class TestStructure:
    def test_budgets_and_shapes(self) -> None:
        na, nd = 7, 11
        d = draw_sim(seed=123, n_attackers=na, n_defenders=nd)
        assert isinstance(d, SimDraws)
        assert d.delivery.shape == (2,)
        assert d.jitter.shape == (na + nd,)
        assert d.contest.shape == (na + nd,)
        assert d.shot_perturb.shape == (2,)
        for scalar in (d.shot_aim_y, d.shot_aim_z, d.shot_final, d.second_ball):
            assert isinstance(scalar, float)

    def test_arrays_are_float64_readonly(self) -> None:
        d = draw_sim(seed=1, n_attackers=4, n_defenders=6)
        for arr in (d.delivery, d.jitter, d.contest, d.shot_perturb):
            assert arr.dtype == np.float64
            assert not arr.flags.writeable

    def test_unit_ranges(self) -> None:
        d = draw_sim(seed=7, n_attackers=7, n_defenders=11)
        assert np.all(d.jitter >= -1.0) and np.all(d.jitter <= 1.0)
        assert -1.0 <= d.shot_aim_y <= 1.0
        assert 0.0 <= d.shot_aim_z <= 1.0
        assert 0.0 <= d.shot_final <= 1.0
        assert 0.0 <= d.second_ball <= 1.0


class TestDeterminism:
    def test_same_inputs_byte_identical(self) -> None:
        a = draw_sim(seed=99, n_attackers=7, n_defenders=11)
        b = draw_sim(seed=99, n_attackers=7, n_defenders=11)
        np.testing.assert_array_equal(a.delivery, b.delivery)
        np.testing.assert_array_equal(a.jitter, b.jitter)
        np.testing.assert_array_equal(a.contest, b.contest)
        np.testing.assert_array_equal(a.shot_perturb, b.shot_perturb)
        assert (a.shot_aim_y, a.shot_aim_z, a.shot_final, a.second_ball) == (
            b.shot_aim_y,
            b.shot_aim_z,
            b.shot_final,
            b.second_ball,
        )

    def test_different_seeds_differ(self) -> None:
        a = draw_sim(seed=1, n_attackers=7, n_defenders=11)
        b = draw_sim(seed=2, n_attackers=7, n_defenders=11)
        assert not np.array_equal(a.delivery, b.delivery)
        assert not np.array_equal(a.contest, b.contest)


class TestCategoryIsolation:
    """The sub-stream property: changing one category's budget must not move
    another category's draws (ADR-011 decision 2)."""

    def test_contest_budget_change_does_not_shift_other_categories(self) -> None:
        small = draw_sim(seed=55, n_attackers=2, n_defenders=5)
        big = draw_sim(seed=55, n_attackers=9, n_defenders=11)
        # delivery + shot + second_ball categories are independent of arity.
        np.testing.assert_array_equal(small.delivery, big.delivery)
        np.testing.assert_array_equal(small.shot_perturb, big.shot_perturb)
        assert small.shot_aim_y == big.shot_aim_y
        assert small.shot_aim_z == big.shot_aim_z
        assert small.shot_final == big.shot_final
        assert small.second_ball == big.second_ball

    def test_arity_dependent_categories_share_a_prefix(self) -> None:
        small = draw_sim(seed=55, n_attackers=2, n_defenders=5)  # n=7
        big = draw_sim(seed=55, n_attackers=9, n_defenders=11)  # n=20
        # Same sub-stream drawn longer: the shorter draw is a prefix of the longer.
        np.testing.assert_array_equal(small.contest, big.contest[:7])
        np.testing.assert_array_equal(small.jitter, big.jitter[:7])


class TestDistribution:
    def test_delivery_is_standard_normal(self) -> None:
        samples = np.array([draw_sim(s, 7, 11).delivery[0] for s in range(2000)])
        assert abs(float(samples.mean())) < 0.1
        assert abs(float(samples.std()) - 1.0) < 0.1

    def test_invalid_arity_rejected(self) -> None:
        with pytest.raises(ValueError):
            draw_sim(seed=1, n_attackers=0, n_defenders=5)
