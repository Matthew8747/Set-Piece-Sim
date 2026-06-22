"""Study persistence: studies are resumable/auditable JSON under
``optimization_studies/<name>/`` (roadmap Phase 5).

Plain JSON (sorted keys, trailing newline) mirrors the xG bundle artifact style
(restart_ml.artifacts) so committed study artifacts stay diff-stable under
end-of-file hooks. The directory is git-ignored except the one committed
canonical study the case-study writeup cites.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from restart.optimize.confirm import ConfirmResult
from restart_opt.study import StudyOutcome


def studies_root(root: Path | None = None) -> Path:
    return root if root is not None else Path("optimization_studies")


def study_dir(name: str, root: Path | None = None) -> Path:
    return studies_root(root) / name


def outcome_to_dict(o: StudyOutcome) -> dict[str, Any]:
    return {
        "sampler": o.sampler,
        "n_trials": o.n_trials,
        "seed": o.seed,
        "best_params": o.best_params,
        "best_value": o.best_value,
        "trials": [
            {
                "params": t.params,
                "value": t.value,
                "state": t.state,
                "generation": t.generation,  # NSGA-II lineage; None for non-generational samplers
            }
            for t in o.trials
        ],
    }


def confirm_to_dict(c: ConfirmResult) -> dict[str, Any]:
    return {
        "params": c.params,
        "mean_xg": c.mean_xg,
        "ci_lo": c.ci_lo,
        "ci_hi": c.ci_hi,
        "n_sims": c.n_sims,
        "root_seed": c.root_seed,
    }


def save_study(name: str, document: dict[str, Any], root: Path | None = None) -> Path:
    """Write ``study.json`` for ``name``; returns its path."""
    d = study_dir(name, root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "study.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_study(name: str, root: Path | None = None) -> dict[str, Any]:
    path = study_dir(name, root) / "study.json"
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded
