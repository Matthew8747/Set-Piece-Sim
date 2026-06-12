# Assumptions Register (status index)

**Canonical registry (values, citations, validation evidence):**
[docs/simulation-assumptions.md](../simulation-assumptions.md) — do not duplicate it; this file
tracks *status at a glance* and is refreshed each phase.

Legend: **[fixed]** physical constant · **[knob]** Phase-3 calibration parameter ·
**[simplification]** registered fidelity cut.

| ID | Topic | Class | Calibration | Validation |
|----|-------|-------|-------------|------------|
| P-1 | FIFA ball mass/radius | fixed | n/a | Law-2 bounds enforced in config |
| P-2 | Gravity, air density, altitude model | fixed | n/a | Altitude presets tested (Azteca) |
| P-3 | Drag crisis (4 params) | **knob** | pending P3 | Monotonicity + magnitude tests; oracle |
| P-4 | Magnus C_l fit (a, b, clamp) | **knob** | pending P3 — wide literature spread | Roberto Carlos plausibility band (2–9 m) |
| P-5 | Spin decay τ=8 s | **knob** | pending P3 (low sensitivity) | Exponential decay test |
| P-6 | RK4 dt=5 ms | fixed (ADR-002) | n/a | <1 cm vs DOP853; ~dt⁴ convergence |
| P-7 | Restitution e=0.65 | **knob** | pending P3 | Exact-restitution property test |
| P-8 | Bounce friction μ=0.40; roll μ_roll=0.06 | **knob** | pending P3 — **μ_roll flagged generous** | Stick/slide branch tests |
| P-9 | Shell inertia; no twist friction | fixed + simplification | n/a | Total-KE invariant (300 random cases) |
| P-10..P-12 | No wind / no knuckling / no Re-dependent C_l | exclusions | revisit on evidence | documented |
| P-13 | Batch = flight-to-first-contact only | simplification | resolves in P3 | kernel↔reference equivalence |
| P-14 | Events by in-step interpolation | simplification | n/a | sub-mm at 5 ms steps |
| P-15 | Ball-center goal/out decisions | simplification | revisit if calibration shows edge effects | bounded by ball radius |
| G-* | Agent assumptions (envelope, reaction latency, contest model, …) | mixed | **added in Phase 2** — see canonical registry after Phase-2 merge | Phase-2 invariant tests |
