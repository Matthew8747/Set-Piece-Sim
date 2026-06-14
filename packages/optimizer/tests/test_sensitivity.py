"""Attribute sensitivity (doc 04 sec3 guardrail): if a +/-10% attribute
perturbation flips the routine ranking, report routine CLASSES not precise picks
(roadmap R9). Tests the ranking-stability decision and the attribute scaling."""

from restart.players.attributes import PlayerAttributes
from restart_opt.sensitivity import rank_stability, scale_attributes


class TestRankStability:
    def test_stable_ranking_is_routine_precise(self) -> None:
        baseline = {"A": 0.30, "B": 0.20, "C": 0.10}
        perturbed = {
            "+10%": {"A": 0.31, "B": 0.19, "C": 0.11},
            "-10%": {"A": 0.28, "B": 0.21, "C": 0.09},
        }
        res = rank_stability(baseline, perturbed)
        assert res.top1_stable is True
        assert res.verdict == "routine-precise"

    def test_top1_flip_triggers_class_reporting(self) -> None:
        baseline = {"A": 0.30, "B": 0.20, "C": 0.10}
        perturbed = {"+10%": {"A": 0.20, "B": 0.30, "C": 0.10}}
        res = rank_stability(baseline, perturbed)
        assert res.top1_stable is False
        assert res.rankings_flip is True
        assert res.verdict == "report-routine-classes"
        assert "+10%" in res.flipped


class TestScaleAttributes:
    def test_scales_curated_fields(self) -> None:
        attrs = PlayerAttributes(heading=0.5, delivery=0.5)
        up = scale_attributes(attrs, 0.10, ("heading", "delivery"))
        assert abs(up.heading - 0.55) < 1e-9
        assert abs(up.delivery - 0.55) < 1e-9

    def test_clamps_to_bounds(self) -> None:
        attrs = PlayerAttributes(heading=0.95)
        up = scale_attributes(attrs, 0.10, ("heading",))
        assert up.heading == 1.0  # 0.95 * 1.10 = 1.045 -> clamped to bound
