"""Tests for restart.simulation.rng - determinism and independence guarantees."""

import numpy as np
import pytest

from restart.simulation.rng import spawn_rng, spawn_rngs


class TestSpawnRng:
    def test_same_seed_stream_identical_sequence(self) -> None:
        """Same (seed, stream) must produce bit-identical draws."""
        r1 = spawn_rng(42, 0)
        r2 = spawn_rng(42, 0)
        draws1 = r1.random(100)
        draws2 = r2.random(100)
        np.testing.assert_array_equal(draws1, draws2)

    def test_different_stream_different_sequence(self) -> None:
        """Different stream index must produce a different sequence."""
        r1 = spawn_rng(42, 0)
        r2 = spawn_rng(42, 1)
        draws1 = r1.random(100)
        draws2 = r2.random(100)
        assert not np.array_equal(draws1, draws2)

    def test_different_seed_different_sequence(self) -> None:
        """Different root seed must produce a different sequence."""
        r1 = spawn_rng(42, 0)
        r2 = spawn_rng(99, 0)
        draws1 = r1.random(100)
        draws2 = r2.random(100)
        assert not np.array_equal(draws1, draws2)

    def test_streams_statistically_independent(self) -> None:
        """No two streams should have identical first 100 draws."""
        rngs = spawn_rngs(1234, 8)
        draws = [rng.random(100) for rng in rngs]
        for i in range(len(draws)):
            for j in range(i + 1, len(draws)):
                assert not np.array_equal(
                    draws[i], draws[j]
                ), f"streams {i} and {j} produced identical draws"

    def test_negative_root_seed_raises(self) -> None:
        with pytest.raises(ValueError, match="root_seed"):
            spawn_rng(-1, 0)

    def test_negative_stream_raises(self) -> None:
        with pytest.raises(ValueError, match="stream"):
            spawn_rng(0, -1)

    def test_zero_seed_zero_stream_valid(self) -> None:
        """Edge case: seed=0, stream=0 is valid."""
        rng = spawn_rng(0, 0)
        assert rng.random() >= 0.0

    def test_returns_numpy_generator(self) -> None:
        rng = spawn_rng(7, 3)
        assert isinstance(rng, np.random.Generator)


class TestSpawnRngs:
    def test_length_matches_n(self) -> None:
        rngs = spawn_rngs(10, 5)
        assert len(rngs) == 5

    def test_zero_n_returns_empty_list(self) -> None:
        assert spawn_rngs(10, 0) == []

    def test_all_generators(self) -> None:
        rngs = spawn_rngs(10, 3)
        for rng in rngs:
            assert isinstance(rng, np.random.Generator)

    def test_reproducible_across_calls(self) -> None:
        rngs1 = spawn_rngs(77, 4)
        rngs2 = spawn_rngs(77, 4)
        for r1, r2 in zip(rngs1, rngs2, strict=True):
            np.testing.assert_array_equal(r1.random(50), r2.random(50))

    def test_negative_root_seed_raises(self) -> None:
        with pytest.raises(ValueError, match="root_seed"):
            spawn_rngs(-5, 3)

    def test_negative_n_raises(self) -> None:
        with pytest.raises(ValueError, match="n must be"):
            spawn_rngs(0, -1)

    def test_stream_indices_match_spawn_rng(self) -> None:
        """spawn_rngs(seed, n)[i] must match spawn_rng(seed, i) exactly."""
        rngs = spawn_rngs(55, 5)
        for i, rng in enumerate(rngs):
            ref = spawn_rng(55, i)
            np.testing.assert_array_equal(rng.random(30), ref.random(30))
