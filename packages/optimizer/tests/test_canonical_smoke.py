"""End-to-end smoke of the canonical pipeline at a tiny budget: the study runs,
produces a well-formed document, and persists it. Validates wiring, not numbers
(real budgets take hours on the ~3 sims/s reference engine)."""

from pathlib import Path

import pytest

from restart_opt.canonical import CanonicalConfig, run_canonical


@pytest.mark.integration
def test_canonical_pipeline_smoke(tmp_path: Path) -> None:
    cfg = CanonicalConfig(
        n_trials=3, n_screen=4, k=2, n_confirm=6, sensitivity_sims=4, seed=0, prune=True
    )
    doc = run_canonical(cfg, out_root=tmp_path)

    # Structure: all three searches ran (TPE, random, evolution), confirm +
    # baseline + winner + guards present.
    assert doc["name"] == "england-vs-argentina"
    assert doc["tpe"]["sampler"] == "tpe"
    assert doc["random"]["sampler"] == "random"
    assert doc["evolution"]["sampler"] == "nsga2"
    # Evolution recorded its generations (the lineage).
    evo_gens = {t["generation"] for t in doc["evolution"]["trials"] if t["generation"] is not None}
    assert len(evo_gens) >= 1
    assert "mean_xg" in doc["winner"]
    assert doc["winner"]["sampler"] in ("tpe", "nsga2", "baseline")
    assert isinstance(doc["winner"]["beats_baseline"], bool)
    assert "verdict" in doc["sensitivity"]
    assert (tmp_path / "england-vs-argentina" / "study.json").exists()
