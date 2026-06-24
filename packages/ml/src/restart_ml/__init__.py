"""Restart Lab System A: expected-goals (xG) models.

Trained on **real StatsBomb marts only** - never on simulator output - so the xG
layer is the simulator's ground-truth anchor (design doc 06 §1). The package
produces calibrated P(goal) models, serializes the shipped logistic model to a
plain coefficient artifact the pure simulation core can score with, and logs
every run to MLflow.
"""

ML_VERSION = "ml/0.1.0"

__all__ = ["ML_VERSION"]
