"""Restart Lab System B - the routine optimizer (design doc 06 sec3).

This package owns the search algorithms (Optuna TPE primary; random-search
baseline at equal budget), the screen-then-confirm pipeline with common random
numbers, study persistence, MLflow logging, the LightGBM+SHAP surrogate, and the
attribute sensitivity analysis. It consumes the *pure* optimization surface in
``restart.optimize`` (genome, objective, confirm, anti-exploit) and never the
other way around, keeping the simulation core free of Optuna/ML/IO.
"""

OPT_VERSION = "0.1.0"
