"""Anti-exploit guards: bound-pinning detection and face-validity screening."""

from restart.optimize.boundary import boundary_flags, face_validity_flags
from restart.optimize.genome import CategoricalParam, ContinuousParam, SearchSpace

SPACE = SearchSpace((ContinuousParam("x", 0.0, 10.0), CategoricalParam("k", ("a", "b"))))


class TestBoundaryFlags:
    def test_flags_lower_edge_skips_categorical(self) -> None:
        assert boundary_flags(SPACE, {"x": 0.1, "k": "a"}, eps_frac=0.02) == ["x"]

    def test_flags_upper_edge(self) -> None:
        assert boundary_flags(SPACE, {"x": 9.95, "k": "b"}, eps_frac=0.02) == ["x"]

    def test_interior_is_clean(self) -> None:
        assert boundary_flags(SPACE, {"x": 5.0, "k": "a"}, eps_frac=0.02) == []


class TestFaceValidity:
    def test_implausible_mean_xg_flagged(self) -> None:
        flags = face_validity_flags(0.6)
        assert any("implausible" in f for f in flags)

    def test_plausible_is_clean(self) -> None:
        assert face_validity_flags(0.08) == []

    def test_boundary_pinning_surfaced(self) -> None:
        flags = face_validity_flags(0.08, boundary=["x"])
        assert any("pinned" in f for f in flags)
