"""Restart Lab simulation core.

The pure domain heart of the platform: ball physics, player agents, tactical
compilation, and Monte Carlo execution will live here. This package must never
import from the API, storage, or worker layers (enforced by import-linter in CI
once those layers exist).

``ENGINE_VERSION`` identifies the simulation engine build. Every persisted
simulation result carries it; physics-affecting changes must bump it (see
docs/02-system-architecture.md, "Determinism & versioning").
"""

__version__ = "0.3.0"

#: Bumped for Phase 3: engine ball-horizon cap (4s) shifts some outcomes.
ENGINE_VERSION = "sim/0.3.0"
