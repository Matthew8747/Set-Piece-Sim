"""Read-only optimization studies surface (Phase 7, ADR-008).

Serves the persisted ``study.json`` artifacts as typed DTOs. The optimizer
(``restart_opt``: Optuna / LightGBM / SHAP) is never imported here — these
routes load data, they never run a search.
"""

from fastapi import APIRouter, HTTPException

from restart_api.deps import study_loader
from restart_api.schemas import OptimizationDetailDTO, OptimizationSummaryDTO

router = APIRouter(tags=["optimizations"])


@router.get("/optimizations", response_model=list[OptimizationSummaryDTO])
def list_optimizations() -> list[OptimizationSummaryDTO]:
    return study_loader().list_summaries()


@router.get("/optimizations/{study_id}", response_model=OptimizationDetailDTO)
def get_optimization(study_id: str) -> OptimizationDetailDTO:
    try:
        return study_loader().get_detail(study_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"study not found: {study_id}") from exc
