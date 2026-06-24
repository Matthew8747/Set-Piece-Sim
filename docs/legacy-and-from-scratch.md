# Build-vs-buy ledger — what is hand-rolled, what is imported, and why

**Purpose.** A single place that records every component we built *from scratch* versus pulled from an
existing library/service, with the rationale and the off-the-shelf alternative. Two reasons it exists:

1. **Talking points.** For interviews / portfolio / write-ups: each "from scratch" entry is a
   deliberate engineering decision with a defensible trade-off, not an accident.
2. **Product hygiene.** The standing policy (2026-06-22) is *use existing solutions for anything that
   already exists well* — ML models, databases, APIs, statistics, optimization — and only build
   bespoke where no good off-the-shelf option fits the domain. This ledger is where we justify each
   exception so we don't reinvent wheels by drift.

Legend: 🟢 imported/bought · 🔵 bespoke by necessity (no good off-the-shelf fit) · 🟡 bespoke by
choice (alternative exists; reasons given) · ⚪ hybrid.

---

## Imported / bought (🟢) — the default

| Area | What we use | Why not from scratch |
|---|---|---|
| Optimization search | **Optuna** (TPE, random, NSGA-II) + **cmaes** | Mature samplers, study storage, pruners. ADR-006/010. |
| ML / xG model | **LightGBM** + **SHAP** | Gradient-boosted trees + explanations are solved; we train on real data, not invent a learner. ADR-005. |
| Statistics | **SciPy** (`binomtest` Wilson CIs, KS tests) | "Statistics are bought, not built" (ADR-001) — see `montecarlo/aggregate.py`. |
| Numerical core | **NumPy** + **Numba** (JIT) | Array ops + LLVM-compiled kernels; we write the *physics*, not a compiler. ADR-001 addendum. |
| API runtime | **FastAPI** + **Pydantic** | Standard async API + validation. ADR-007. |
| Frontend | **Next.js / React / Tailwind** + **React-Three-Fiber** (3D) | Standard app stack; R3F for WebGL replay. ADR-008. |
| Persistence / jobs | **Postgres** (marts), **Arq** (async jobs) | Standard data + queue infra. ADR-007. |
| Data | **StatsBomb open** (license-clean) | Real event data; ratings provenance-tagged, never scraped. |

## Bespoke by necessity (🔵) — no good off-the-shelf fit

| Component | Where | Why no library fits |
|---|---|---|
| Set-piece **physics + agent engine** | `restart/engine`, `restart/physics`, `restart/agents` | No off-the-shelf simulator models a football set-piece (RK4 flight + Magnus/drag-crisis + bounce, scripted runs, interception, Gumbel contest, GK/shot resolution). The domain *is* the product. |
| **Fused Numba scenario kernel** (Phase 10) | `restart/engine/kernel.py` | A faithful njit port of the bespoke engine above for batch throughput. There is no generic "football-physics batch simulator" to import. Considered: GPU (JAX/CuPy) and distributed Optuna — different throughput tiers, deferred (ADR-011). |
| **Externalized-RNG draw plan** (Phase 10) | `restart/engine/draws.py` | Required so the Numba kernel and the NumPy reference consume identical Philox draws (Numba's in-kernel RNG can't reproduce NumPy Philox bit-for-bit). A domain-specific determinism device. ADR-011. |
| **Routine Spec → SimProgram** compiler | `restart/tactics` | A small DSL for set-piece routines compiled to flat SoA arrays; nothing generic captures this. ADR-004. |

## Bespoke by choice (🟡) — alternative exists; reasons given

| Component | Where | Alternative we declined, and why |
|---|---|---|
| Hand-rolled **SVG charts** | frontend `@restart/pitch-kit`, convergence / parallel-coords / SHAP views | **visx/d3/recharts** exist. Declined because visx is React-18-capped (we run React 19) and the pitch primitives are domain-specific. Standing carried constraint: charts hand-rolled SVG *except* R3F. Revisit if a React-19 chart lib matures. |
| Hand-rolled **screen→confirm** two-rung budget ladder | `restart_opt`, `optimize/confirm.py` | A weak multi-fidelity scheme; **ASHA/Hyperband/BOHB** (in Optuna) are the principled replacement (roadmap §3). Kept for now because it is simple and CRN-friendly; flagged for upgrade. |
| Custom **xG-driven outcome** Bernoulli + GK-save logit | `engine._resolve_shot_xg` | The xG *model* is imported (LightGBM); only the thin mapping from xG → replay-consistent goal/save event is ours, because it must stay consistent with our event log. |

## Review trigger

When adding any new capability, check this ledger first. If an off-the-shelf option exists and fits,
use it (🟢) and note it here. If building bespoke, add a 🔵/🟡 row with the alternative and the reason.
