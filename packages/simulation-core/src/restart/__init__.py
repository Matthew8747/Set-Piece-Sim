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

#: Bumped for Phase 8 (scenario realism): the corner template now places up to
#: 7 attackers with off-ball roles and the optimizer can build basic free kicks,
#: so a given routine's simulated context - and therefore its results - changes.
#: (Phase 4 set sim/0.4.0: real-data xG scoring via an injected XGScorer, G-14.)
ENGINE_VERSION = "sim/0.5.0"
