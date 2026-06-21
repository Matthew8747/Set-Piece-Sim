"""Read-only access to persisted optimizer studies.

The optimization surface is DATA, not compute: this package parses the committed
``study.json`` artifacts into typed DTOs. It never imports ``restart_opt``
(Optuna / LightGBM / SHAP / MLflow) — those stay out of the API runtime
(ADR-006/008). Re-running a search is a CLI/offline concern, never a request.
"""
