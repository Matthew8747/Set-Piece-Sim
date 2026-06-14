"""Pure xG scoring contract: feature vector, logistic scorer, bundle routing."""

from __future__ import annotations

import math

from restart.engine.xg import (
    FEATURE_NAMES,
    LogisticXGScorer,
    ShotContext,
    XGModelBundle,
    XGScorer,
    shot_feature_vector,
)


def _ctx(is_header: bool = False, distance: float = 8.0) -> ShotContext:
    return ShotContext(
        distance_m=distance,
        angle_rad=0.5,
        is_header=is_header,
        set_piece_phase="first_contact",
        defenders_in_cone=1,
        nearest_def_dist_m=2.0,
        defenders_within_3m=1,
        gk_dist_to_goal_m=1.0,
        gk_lateral_m=0.3,
        under_pressure=True,
    )


def test_feature_vector_covers_all_names() -> None:
    feats = shot_feature_vector(_ctx())
    assert set(feats) == set(FEATURE_NAMES)
    # Closed-form sanity: inverse-distance and header interaction.
    assert math.isclose(feats["inv_distance"], 1.0 / 8.5)
    assert feats["header_x_distance"] == 0.0


def test_logistic_scorer_matches_manual_sigmoid() -> None:
    scorer = LogisticXGScorer(
        model_id="t",
        feature_names=("distance", "is_header"),
        coef=(-0.2, 0.5),
        intercept=0.1,
    )
    ctx = _ctx(is_header=True, distance=6.0)
    z = 0.1 + (-0.2) * 6.0 + 0.5 * 1.0
    assert math.isclose(scorer.score(ctx), 1.0 / (1.0 + math.exp(-z)))


def test_scorer_is_xgscorer_protocol() -> None:
    scorer = LogisticXGScorer("t", ("distance",), (0.0,), 0.0)
    assert isinstance(scorer, XGScorer)


def test_roundtrip_dict() -> None:
    scorer = LogisticXGScorer(
        "foot",
        ("distance", "angle"),
        (0.1, -0.3),
        0.2,
        calibration={"type": "platt", "a": 1.1, "b": -0.05},
    )
    again = LogisticXGScorer.from_dict(scorer.to_dict())
    assert again == scorer


def test_bundle_routes_by_body_part() -> None:
    header = LogisticXGScorer("h", ("is_header",), (0.0,), 5.0)  # ~1.0
    foot = LogisticXGScorer("f", ("is_header",), (0.0,), -5.0)  # ~0.0
    bundle = XGModelBundle(header=header, foot=foot)
    assert bundle.score(_ctx(is_header=True)) > 0.9
    assert bundle.score(_ctx(is_header=False)) < 0.1
    restored = XGModelBundle.from_dict(bundle.to_dict())
    assert restored.score(_ctx(is_header=True)) > 0.9


def test_mismatched_coef_length_rejected() -> None:
    try:
        LogisticXGScorer("bad", ("distance", "angle"), (0.1,), 0.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError on name/coef mismatch")
