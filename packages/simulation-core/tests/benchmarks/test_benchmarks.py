"""Performance benchmarks and the throughput regression gate.

pytest-benchmark publishes timing tables in CI logs; the hard assertion at
the bottom is deliberately generous (CI runners vary wildly) while the local
target from the roadmap (10k ball-only flights < 1 s single-core) is printed
for the record on every run.
"""

import time

import numpy as np
from pytest_benchmark.fixture import BenchmarkFixture

from restart.physics import BallState, PhysicsConfig, TrajectorySimulator, simulate_flights
from restart.physics.forces import default_force_system
from restart.physics.integrator import make_derivative, rk4_step
from restart.physics.state import pack_states


def corner_batch(n: int) -> np.ndarray:
    rng = np.random.default_rng(1837)
    pos = np.tile([52.5, -34.0, 0.11], (n, 1))
    vel = np.array([-8.0, 22.0, 7.5]) + rng.normal(0.0, 0.8, (n, 3))
    spin = np.array([0.0, 0.0, 55.0]) + rng.normal(0.0, 4.0, (n, 3))
    return pack_states(pos, vel, spin)


class TestBenchmarks:
    def test_bench_rk4_step_batch_10k(self, benchmark: BenchmarkFixture) -> None:
        cfg = PhysicsConfig.default()
        force = default_force_system(cfg.ball, cfg.environment)
        deriv = make_derivative(force, cfg.ball.spin_decay_tau_s)
        y = corner_batch(10_000)
        benchmark(rk4_step, y, cfg.integrator.dt_s, deriv)

    def test_bench_single_trajectory(self, benchmark: BenchmarkFixture) -> None:
        sim = TrajectorySimulator()
        state = BallState(
            position=np.array([52.5, -34.0, 0.11]),
            velocity=np.array([-8.0, 22.0, 7.5]),
            spin=np.array([0.0, 0.0, 55.0]),
        )
        benchmark(sim.simulate, state)

    def test_bench_batch_1k_flights(self, benchmark: BenchmarkFixture) -> None:
        batch = corner_batch(1_000)
        benchmark(simulate_flights, batch)


class TestThroughputGate:
    def test_10k_flights_throughput(self) -> None:
        """Roadmap Phase-1 target: 10k ball-only flights < 1 s single-core.

        Hard CI gate is 5 s (runner variance); the measured number is printed
        so the local target is auditable in every CI log.
        """
        batch = corner_batch(10_000)
        simulate_flights(batch)  # warm-up (allocator, caches)

        start = time.perf_counter()
        result = simulate_flights(batch)
        elapsed = time.perf_counter() - start

        assert bool(result.landed.all())
        print(f"\n10k flights: {elapsed:.3f}s ({10_000 / elapsed:,.0f} flights/s)")
        assert elapsed < 5.0
