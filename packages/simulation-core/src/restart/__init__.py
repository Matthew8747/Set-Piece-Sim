"""Restart Lab simulation core.

The pure domain heart of the platform: ball physics, player agents, tactical
compilation, and Monte Carlo execution will live here. This package must never
import from the API, storage, or worker layers (enforced by import-linter in CI
once those layers exist).

``ENGINE_VERSION`` identifies the simulation engine build. Every persisted
simulation result carries it; physics-affecting changes must bump it (see
docs/02-system-architecture.md, "Determinism & versioning").
"""

__version__ = "0.4.0"

#: Bumped for Phase 4: the engine can score shots with a real-data xG model
#: (injected XGScorer) and emits ShotEvent.xg; ShotEvent gained an xg field and
#: shot outcomes follow a Bernoulli on scored xG when a model is wired (G-14).
ENGINE_VERSION = "sim/0.4.0"
