"""Screen-then-confirm statistics: mean-xG CIs, the non-overlap decision rule,
and CRN-deterministic confirmation."""

import numpy as np

from restart.optimize.confirm import (
    beats_baseline,
    confirm_candidates,
    mean_ci,
)


class TestMeanCI:
    def test_brackets_mean_and_clamps_to_unit(self) -> None:
        samples = np.array([0.1] * 10 + [0.2] * 10, dtype=np.float64)
        mean, lo, hi = mean_ci(samples)
        assert abs(mean - 0.15) < 1e-9
        assert 0.0 <= lo < mean < hi <= 1.0

    def test_degenerate_sizes(self) -> None:
        assert mean_ci(np.array([], dtype=np.float64)) == (0.0, 0.0, 0.0)
        m, lo, hi = mean_ci(np.array([0.3], dtype=np.float64))
        assert (m, lo, hi) == (0.3, 0.3, 0.3)


class TestBeatsBaseline:
    def test_non_overlapping_higher_beats(self) -> None:
        assert beats_baseline((0.20, 0.18, 0.22), (0.10, 0.08, 0.12)) is True

    def test_overlapping_does_not_beat(self) -> None:
        assert beats_baseline((0.20, 0.15, 0.25), (0.10, 0.08, 0.18)) is False

    def test_lower_candidate_does_not_beat(self) -> None:
        assert beats_baseline((0.05, 0.03, 0.07), (0.10, 0.08, 0.12)) is False


class TestConfirmCandidates:
    @staticmethod
    def _make_samples(params: dict[str, object], n: int, seed: int) -> np.ndarray:
        # Deterministic per (params, seed) -> stands in for the xG objective.
        rng = np.random.default_rng(seed + int(params["k"]))  # type: ignore[call-overload]
        return rng.uniform(0.0, 0.3, n)

    def test_common_random_numbers_deterministic(self) -> None:
        cands = [{"k": 1}, {"k": 2}]
        a = confirm_candidates(self._make_samples, cands, n_confirm=200, root_seed=5)
        b = confirm_candidates(self._make_samples, cands, n_confirm=200, root_seed=5)
        assert [r.mean_xg for r in a] == [r.mean_xg for r in b]
        assert a[0].n_sims == 200 and a[0].root_seed == 5
        assert a[0].params == {"k": 1}

    def test_ci_tuple_exposed(self) -> None:
        out = confirm_candidates(self._make_samples, [{"k": 1}], n_confirm=300, root_seed=1)
        mean, lo, hi = out[0].ci
        assert lo <= mean <= hi
