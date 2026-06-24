"""Set-piece engine: plays one compiled SimProgram to a terminal outcome.

Single-scenario reference implementation per ADR-003: NumPy over the SoA
SimProgram arrays, 20 ms agent tick, precomputed ball-flight oracle, one
Gumbel-max contest, discrete GK model, first-contact-centric termination
(d1-d10). The Phase-3 batch kernel ports these exact semantics.

RNG is externalized (ADR-011): all per-sim randomness is drawn up front into a
``SimDraws`` struct (``engine/draws.py``) by category sub-stream — delivery,
reaction jitter (attackers then defenders, index order), contest Gumbel (one
slot per potential contestant by player index), shot aim/perturb/Bernoulli, and
the loose-ball jitter — and the engine reads those draws instead of calling an
``rng``. This is what lets the Numba kernel (Phase 10) consume identical draws
and match this reference to <=1e-9. Same (program, seed) => bit-identical result.

Planning simplification (G-13, registered): interception plans are computed
once at kick time from kick-instant agent states — agents commit to a plan
rather than re-planning during flight. Realism cost is small at corner
timescales; throughput gain is large (one (n,m) solve per sim).
"""

import math
from dataclasses import dataclass

import numpy as np

from restart.agents.config import AgentConfig
from restart.agents.interception import earliest_interception
from restart.agents.kinematics import separate, step_agents
from restart.domain.vectors import FloatArray
from restart.engine.config import EngineConfig
from restart.engine.draws import SimDraws, draw_sim
from restart.engine.xg import ShotContext, XGScorer
from restart.physics import BallState, IntegratorConfig, PhysicsConfig, TrajectorySimulator
from restart.physics.trajectory import Trajectory
from restart.players.attributes import Attr
from restart.simulation.events import (
    ApexEvent,
    BounceEvent,
    ClearanceEvent,
    FirstContactEvent,
    GoalEvent,
    KeeperClaimEvent,
    SaveEvent,
    SecondBallEvent,
    SetPieceOutcome,
    ShotEvent,
    SimEvent,
)
from restart.tactics.compile import SimProgram
from restart.tactics.routine import INTENT_CODES, TRIGGER_CODES, Intent, Trigger

_GOAL_CENTER = np.array([52.5, 0.0])
_POST_L = np.array([52.5, -3.66])
_POST_R = np.array([52.5, 3.66])
_ATTACK = "attack"
_DEFENSE = "defense"

_CODE_ATTACK_BALL = INTENT_CODES[Intent.ATTACK_BALL]
_CODE_SECOND_BALL = INTENT_CODES[Intent.SECOND_BALL]
_TRIG_KICK_APPROACH = TRIGGER_CODES[Trigger.KICK_APPROACH]
_TRIG_KICK = TRIGGER_CODES[Trigger.KICK]
_TRIG_APEX = TRIGGER_CODES[Trigger.BALL_APEX]


@dataclass(frozen=True, slots=True)
class SetPieceResult:
    """Everything one simulated set piece produced."""

    outcome: SetPieceOutcome
    events: tuple[SimEvent, ...]
    seed: int
    # Replay payloads (agent positions sampled at the agent tick).
    track_times_s: FloatArray  # (T,)
    att_tracks: FloatArray  # (T, na, 2)
    def_tracks: FloatArray  # (T, nd, 2)
    delivery: Trajectory
    after_contact: Trajectory | None

    @property
    def goal_scored(self) -> bool:
        return self.outcome is SetPieceOutcome.GOAL


def _point_in_triangle(p: FloatArray, a: FloatArray, b: FloatArray, c: FloatArray) -> bool:
    """True if 2-D point ``p`` lies within triangle ``a-b-c`` (shooting cone)."""

    def sign(u: FloatArray, v: FloatArray, w: FloatArray) -> float:
        return float((u[0] - w[0]) * (v[1] - w[1]) - (v[0] - w[0]) * (u[1] - w[1]))

    d1 = sign(p, a, b)
    d2 = sign(p, b, c)
    d3 = sign(p, c, a)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def _goal_opening_angle(pos: FloatArray) -> float:
    """Opening angle of the goal mouth (posts at (52.5, +/-3.66)) from pos."""
    a = np.array([52.5 - pos[0], -3.66 - pos[1]])
    b = np.array([52.5 - pos[0], 3.66 - pos[1]])
    cosang = float(np.dot(a, b) / max(float(np.linalg.norm(a) * np.linalg.norm(b)), 1e-9))
    return math.acos(max(-1.0, min(1.0, cosang)))


class SetPieceEngine:
    """Deterministic set-piece simulator over compiled SimPrograms."""

    def __init__(
        self,
        physics: PhysicsConfig | None = None,
        engine: EngineConfig | None = None,
        agents: AgentConfig | None = None,
        xg_scorer: XGScorer | None = None,
    ) -> None:
        self._phys = physics if physics is not None else PhysicsConfig.default()
        self._cfg = engine if engine is not None else EngineConfig()
        self._agents = agents if agents is not None else AgentConfig()
        # Optional real-data xG model (Phase 4). When present, shot outcomes are
        # driven by the model's P(goal) (Bernoulli) instead of the placeholder
        # geometry + GK-save logit; the shot's xG is recorded on the ShotEvent.
        self._xg = xg_scorer
        # Horizon-capped ball sim: set pieces resolve in ~2-4 s; integrating
        # roll-to-rest tails cost 10x per sim for nothing the engine reads.
        capped = PhysicsConfig(
            ball=self._phys.ball,
            environment=self._phys.environment,
            bounce=self._phys.bounce,
            integrator=IntegratorConfig(
                dt_s=self._phys.integrator.dt_s,
                max_flight_time_s=min(
                    self._phys.integrator.max_flight_time_s, self._cfg.ball_sim_horizon_s
                ),
            ),
        )
        self._ball_sim = TrajectorySimulator(capped)

    # ------------------------------------------------------------------ run
    def run(self, program: SimProgram, seed: int) -> SetPieceResult:
        cfg = self._cfg
        draws = draw_sim(seed, program.n_attackers, program.n_defenders)
        events: list[SimEvent] = []

        # --- 1. delivery execution (G-11): intent + skill-scaled noise -----
        delivery_state = self._execute_delivery(program, draws)
        delivery = self._ball_sim.simulate(delivery_state)
        events.append(delivery.events[0])  # LaunchEvent

        # Flight table at the agent tick, kick -> first ground contact.
        t_contact_ground = next(
            (e.time_s for e in delivery.events if isinstance(e, BounceEvent)),
            delivery.final_state.time_s,
        )
        t_apex = next(
            (e.time_s for e in delivery.events if isinstance(e, ApexEvent)),
            t_contact_ground / 2.0,
        )
        s_t = np.asarray(delivery.samples.times_s)
        s_p = np.asarray(delivery.samples.positions)
        ball_times = np.arange(0.0, max(t_contact_ground, cfg.agent_dt_s), cfg.agent_dt_s)
        ball_pos = np.stack([np.interp(ball_times, s_t, s_p[:, k]) for k in range(3)], axis=1)

        # --- 2. per-agent reaction readiness (G-3; externalized draws) -----
        # jitter draws are U(-1, 1); scale by the configured fraction. Attackers
        # occupy the first na slots, defenders the next nd (ADR-011 draw plan).
        na, nd = program.n_attackers, program.n_defenders
        frac = self._agents.reaction_jitter_frac
        att_react = program.att_attr[:, Attr.REACTION_TIME] * (1.0 + frac * draws.jitter[:na])
        def_react = program.def_attr[:, Attr.REACTION_TIME] * (
            1.0 + frac * draws.jitter[na : na + nd]
        )

        # --- 3. pre-kick window: runs develop before the ball moves ---------
        att_pos = program.att_start.copy()
        att_vel = np.zeros_like(att_pos)
        def_pos = program.def_start.copy()
        def_vel = np.zeros_like(def_pos)
        pre = self._sim_window(
            program,
            t_apex,
            -cfg.prekick_lead_s,
            -cfg.agent_dt_s,
            att_pos,
            att_vel,
            def_pos,
            def_vel,
        )
        pre_times, pre_att, pre_def, att_pos, att_vel, def_pos, def_vel = pre

        # --- 4. interception plans from kick-instant states (G-13) ----------
        # Scripted ball-attackers pre-committed to their runs: no reaction
        # latency gates their plan. Reaction gates agents *reading* the flight.
        att_contests_mask = np.asarray(program.att_intent) == _CODE_ATTACK_BALL
        att_ready = np.where(att_contests_mask, 0.0, att_react)
        att_icpt = earliest_interception(
            att_pos,
            att_vel,
            program.att_attr[:, Attr.TOP_SPEED],
            program.att_attr[:, Attr.ACCEL],
            program.att_attr[:, Attr.JUMP_REACH],
            att_ready,
            ball_times,
            ball_pos,
        )
        def_icpt = earliest_interception(
            def_pos,
            def_vel,
            program.def_attr[:, Attr.TOP_SPEED],
            program.def_attr[:, Attr.ACCEL],
            program.def_attr[:, Attr.JUMP_REACH],
            def_react,
            ball_times,
            ball_pos,
        )
        # Only ball-attacking attackers contest the first ball.
        att_contests = np.asarray(program.att_intent) == _CODE_ATTACK_BALL
        att_icpt = np.where(att_contests, att_icpt, -1)

        # --- 5. contest selection (G-6) + flight window ----------------------
        t_star, contestants = self._select_contest(att_icpt, def_icpt, ball_times)
        t_end = t_star if t_star is not None else float(ball_times[-1])
        flight = self._sim_window(program, t_apex, 0.0, t_end, att_pos, att_vel, def_pos, def_vel)
        track_times = np.concatenate([pre_times, flight[0]])
        att_tracks = np.concatenate([pre_att, flight[1]])
        def_tracks = np.concatenate([pre_def, flight[2]])

        if t_star is None:
            return self._resolve_untouched(
                program, delivery, events, draws, att_tracks, def_tracks, track_times, seed
            )

        # --- 6. contest winner (Gumbel-max; fixed contestant order) ---------
        winner_team, winner_idx = self._contest_winner(
            program, contestants, ball_times, ball_pos, t_star, draws
        )
        ball_at = self._ball_state_at(delivery, t_star)
        contact_h = float(ball_at.position[2])
        winner_id = (
            program.att_player_ids[winner_idx]
            if winner_team == _ATTACK
            else program.def_player_ids[winner_idx]
        )
        events.append(
            FirstContactEvent(
                time_s=t_star,
                position=ball_at.position,
                player_id=winner_id,
                team=winner_team,
                contact_height_m=contact_h,
            )
        )

        # --- 7. contact resolution ------------------------------------------
        if winner_team == _DEFENSE and winner_idx == program.gk_index:
            events.append(
                KeeperClaimEvent(time_s=t_star, position=ball_at.position, player_id=winner_id)
            )
            return self._finish(
                SetPieceOutcome.KEEPER_CLAIM,
                events,
                seed,
                track_times,
                att_tracks,
                def_tracks,
                delivery,
                None,
            )

        if winner_team == _DEFENSE:
            events.append(
                ClearanceEvent(time_s=t_star, position=ball_at.position, player_id=winner_id)
            )
            return self._finish(
                SetPieceOutcome.CLEARED,
                events,
                seed,
                track_times,
                att_tracks,
                def_tracks,
                delivery,
                None,
            )

        # Attacker first contact: header/volley at goal.
        return self._resolve_shot(
            program,
            winner_idx,
            ball_at,
            t_star,
            def_tracks,
            events,
            draws,
            seed,
            track_times,
            att_tracks,
            delivery,
        )

    # ------------------------------------------------------------ internals
    def _execute_delivery(self, program: SimProgram, draws: SimDraws) -> BallState:
        cfg = self._cfg
        kick = np.array([program.kick_pos[0], program.kick_pos[1], 0.11])
        aim = program.delivery_target - program.kick_pos
        dist = float(np.linalg.norm(aim))
        heading = math.atan2(float(aim[1]), float(aim[0]))

        skill = float(program.kicker_attr[Attr.DELIVERY])
        # Pre-aim against the curl (G-11): spin will bend the ball back.
        heading += (
            -program.spin_sign * cfg.curl_compensation_rad_per_rps * program.delivery_spin_rps
        )
        # Externalized draws (ADR-011): delivery[0]=dir error, [1]=speed mult,
        # both standard normal scaled by the skill-dependent sigma.
        heading += cfg.dir_noise_base_rad * (1.2 - skill) * float(draws.delivery[0])
        speed = program.delivery_speed_ms * (
            1.0 + cfg.speed_noise_frac * (1.2 - skill) * float(draws.delivery[1])
        )
        speed = max(6.0, speed)

        # Elevation solved from drag-free range with carry correction (G-11):
        # sin(2*theta) = d*g / v_eff^2 with v_eff = speed * carry_factor, then
        # clamped by per-type floors (a floated ball is lofted by definition).
        g = self._phys.environment.gravity_ms2
        v_eff = speed * cfg.carry_factor
        arg = min(1.0, dist * g / max(v_eff * v_eff, 1e-9))
        theta = 0.5 * math.asin(arg)
        floor_by_code = {
            0: cfg.elev_floor_cross_deg,  # inswinger
            1: cfg.elev_floor_cross_deg,  # outswinger
            2: cfg.elev_floor_driven_deg,  # driven
            3: cfg.elev_floor_floated_deg,  # floated
            4: cfg.elev_floor_short_deg,  # short
        }
        floor_deg = floor_by_code.get(program.delivery_type, cfg.elev_floor_cross_deg)
        elev = min(max(theta, math.radians(floor_deg)), math.radians(cfg.elev_max_deg))
        vel = np.array(
            [
                speed * math.cos(elev) * math.cos(heading),
                speed * math.cos(elev) * math.sin(heading),
                speed * math.sin(elev),
            ]
        )
        spin = np.array([0.0, 0.0, program.spin_sign * program.delivery_spin_rps * 2.0 * math.pi])
        return BallState(position=kick, velocity=vel, spin=spin)

    def _select_contest(
        self,
        att_icpt: np.ndarray,
        def_icpt: np.ndarray,
        ball_times: FloatArray,
    ) -> tuple[float | None, list[tuple[str, int, float]]]:
        """Earliest feasible interception defines the contest instant; everyone
        feasible within the window joins. Returns (t*, [(team, idx, t_arrive)])."""
        window = self._cfg.contest_window_s
        cands: list[tuple[str, int, float]] = []
        for i, k in enumerate(att_icpt):
            if k >= 0:
                cands.append((_ATTACK, i, float(ball_times[int(k)])))
        for i, k in enumerate(def_icpt):
            if k >= 0:
                cands.append((_DEFENSE, i, float(ball_times[int(k)])))
        if not cands:
            return None, []
        t_star = min(c[2] for c in cands)
        return t_star, [c for c in cands if c[2] <= t_star + window]

    def _contest_winner(
        self,
        program: SimProgram,
        contestants: list[tuple[str, int, float]],
        ball_times: FloatArray,
        ball_pos: FloatArray,
        t_star: float,
        draws: SimDraws,
    ) -> tuple[str, int]:
        cfg = self._cfg
        na = program.n_attackers
        k = int(np.searchsorted(ball_times, t_star))
        ball_z = float(ball_pos[min(k, len(ball_pos) - 1), 2])
        best_score, best = -np.inf, contestants[0]
        # Externalized draws (ADR-011): each potential contestant has a fixed
        # Gumbel slot in draws.contest by player index — attackers [0..na),
        # defenders [na..na+nd) — so over-provisioning never shifts other draws.
        for team, idx, t_arr in contestants:
            attr = program.att_attr[idx] if team == _ATTACK else program.def_attr[idx]
            gumbel = draws.contest[idx] if team == _ATTACK else draws.contest[na + idx]
            reach_margin = float(attr[Attr.JUMP_REACH]) - ball_z
            slack = (t_star + cfg.contest_window_s) - t_arr
            score = (
                cfg.w_reach * reach_margin
                + cfg.w_time * slack
                + cfg.w_strength * float(attr[Attr.STRENGTH])
                + cfg.w_heading * float(attr[Attr.HEADING])
                + (cfg.gk_claim_bonus if (team == _DEFENSE and idx == program.gk_index) else 0.0)
                + cfg.gumbel_scale * float(gumbel)
            )
            if score > best_score:
                best_score, best = score, (team, idx, t_arr)
        return best[0], best[1]

    def _sim_window(
        self,
        program: SimProgram,
        t_apex: float,
        t_from: float,
        t_to: float,
        att_pos: FloatArray,
        att_vel: FloatArray,
        def_pos: FloatArray,
        def_vel: FloatArray,
    ) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
        """Tick both teams over [t_from, t_to]; returns (times, att_tracks,
        def_tracks, att_pos, att_vel, def_pos, def_vel) — state passes through
        so windows chain (pre-kick, then flight)."""
        cfg, ag = self._cfg, self._agents
        dt = cfg.agent_dt_s
        na, nd = program.n_attackers, program.n_defenders

        att_pos = att_pos.copy()
        att_vel = att_vel.copy()
        def_pos = def_pos.copy()
        def_vel = def_vel.copy()

        trig_time = {_TRIG_KICK_APPROACH: cfg.trigger_kick_approach_s, _TRIG_KICK: 0.0}
        times = np.arange(t_from, t_to + 1e-9, dt)
        att_tracks = np.empty((len(times), na, 2))
        def_tracks = np.empty((len(times), nd, 2))

        for ti, t in enumerate(times):
            # Attacker targets: latest triggered run leg, else start/hold.
            att_targets = att_pos.copy()
            for i in range(na):
                target = program.att_start[i]
                for leg in range(int(program.att_n_legs[i])):
                    code = int(program.att_legs_trigger[i, leg])
                    t_trig = trig_time.get(code, t_apex) + float(program.att_legs_delay[i, leg])
                    if t >= t_trig:
                        target = program.att_legs_to[i, leg]
                att_targets[i] = target
            # Defender targets: marker -> goal-side of mark; zonal -> start.
            def_targets = program.def_start.copy()
            for j in range(nd):
                m = int(program.def_mark_target[j])
                if m >= 0:
                    to_goal = _GOAL_CENTER - att_pos[m]
                    n = float(np.linalg.norm(to_goal))
                    def_targets[j] = att_pos[m] + (to_goal / max(n, 1e-9)) * 0.7

            att_pos, att_vel = step_agents(
                att_pos,
                att_vel,
                att_targets,
                program.att_attr[:, Attr.TOP_SPEED],
                program.att_attr[:, Attr.ACCEL],
                program.att_attr[:, Attr.AGILITY],
                dt,
                turn_rate_base=ag.turn_rate_base_rads,
                speed_ref=ag.turn_speed_ref_ms,
                arrival_radius=ag.arrival_radius_m,
            )
            def_pos, def_vel = step_agents(
                def_pos,
                def_vel,
                def_targets,
                program.def_attr[:, Attr.TOP_SPEED],
                program.def_attr[:, Attr.ACCEL],
                program.def_attr[:, Attr.AGILITY],
                dt,
                turn_rate_base=ag.turn_rate_base_rads,
                speed_ref=ag.turn_speed_ref_ms,
                arrival_radius=ag.arrival_radius_m,
            )
            both = separate(np.vstack([att_pos, def_pos]), ag.separation_radius_m)
            att_pos, def_pos = both[:na].copy(), both[na:].copy()
            att_tracks[ti], def_tracks[ti] = att_pos, def_pos

        return times, att_tracks, def_tracks, att_pos, att_vel, def_pos, def_vel

    def _ball_state_at(self, traj: Trajectory, t: float) -> BallState:
        s_t = np.asarray(traj.samples.times_s)
        p = np.stack(
            [np.interp(t, s_t, np.asarray(traj.samples.positions)[:, k]) for k in range(3)]
        )
        v = np.stack(
            [np.interp(t, s_t, np.asarray(traj.samples.velocities)[:, k]) for k in range(3)]
        )
        w = np.stack([np.interp(t, s_t, np.asarray(traj.samples.spins)[:, k]) for k in range(3)])
        return BallState(position=p, velocity=v, spin=w, time_s=t)

    def _resolve_untouched(
        self,
        program: SimProgram,
        delivery: Trajectory,
        events: list[SimEvent],
        draws: SimDraws,
        att_tracks: FloatArray,
        def_tracks: FloatArray,
        track_times: FloatArray,
        seed: int,
    ) -> SetPieceResult:
        """Nobody reached the ball: classify by landing/termination (G-10)."""
        bounce = next((e for e in delivery.events if isinstance(e, BounceEvent)), None)
        if bounce is None:
            outcome = SetPieceOutcome.GOAL if delivery.goal_scored else SetPieceOutcome.OUT_OF_PLAY
            return self._finish(
                outcome, events, seed, track_times, att_tracks, def_tracks, delivery, None
            )
        land_xy = np.asarray(bounce.position[:2])
        att_d = np.linalg.norm(att_tracks[-1] - land_xy, axis=1)
        def_d = np.linalg.norm(def_tracks[-1] - land_xy, axis=1)
        r = self._cfg.second_ball_radius_m
        # Awareness-weighted proximity race; one uniform draw breaks near-ties.
        att_best = int(np.argmin(att_d))
        def_best = int(np.argmin(def_d))
        att_score = float(att_d[att_best]) / (
            0.5 + float(program.att_attr[att_best, Attr.AWARENESS_OFF])
        )
        def_score = float(def_d[def_best]) / (
            0.5 + float(program.def_attr[def_best, Attr.AWARENESS_DEF])
        )
        if min(att_d[att_best], def_d[def_best]) > r:
            outcome = SetPieceOutcome.OUT_OF_PLAY
            return self._finish(
                outcome, events, seed, track_times, att_tracks, def_tracks, delivery, None
            )
        # Externalized draw (ADR-011): U(0,1) mapped to the [0.9, 1.1] near-tie band.
        jitter = 0.9 + 0.2 * draws.second_ball
        if att_score * jitter < def_score:
            team, pid = _ATTACK, program.att_player_ids[att_best]
            outcome = SetPieceOutcome.SECOND_BALL_ATTACK
        else:
            team, pid = _DEFENSE, program.def_player_ids[def_best]
            outcome = SetPieceOutcome.SECOND_BALL_DEFENSE
        events.append(
            SecondBallEvent(
                time_s=bounce.time_s, position=bounce.position, player_id=pid, team=team
            )
        )
        return self._finish(
            outcome, events, seed, track_times, att_tracks, def_tracks, delivery, None
        )

    def _resolve_shot(
        self,
        program: SimProgram,
        shooter_idx: int,
        ball_at: BallState,
        t_star: float,
        def_tracks: FloatArray,
        events: list[SimEvent],
        draws: SimDraws,
        seed: int,
        track_times: FloatArray,
        att_tracks: FloatArray,
        delivery: Trajectory,
    ) -> SetPieceResult:
        cfg = self._cfg
        attr = program.att_attr[shooter_idx]
        heading_skill = float(attr[Attr.HEADING])
        pos = np.asarray(ball_at.position)
        is_header = pos[2] > 1.6

        # Externalized draws (ADR-011): aim_y U(-1,1)->[-max,max], aim_z
        # U(0,1)->[z_min,z_max], perturb 2x standard normal scaled by sigma.
        aim_y = cfg.shot_aim_y_max_m * draws.shot_aim_y
        aim_z = (
            cfg.shot_aim_z_min_m + (cfg.shot_aim_z_max_m - cfg.shot_aim_z_min_m) * draws.shot_aim_z
        )
        aim = np.array([52.5, aim_y, aim_z])
        direction = aim - pos
        direction = direction / max(float(np.linalg.norm(direction)), 1e-9)
        sigma = cfg.header_dir_sigma_rad * (1.6 - heading_skill)
        # Small-angle perturbation in two transverse axes.
        perturb = sigma * draws.shot_perturb
        tangent1 = np.cross(direction, [0.0, 0.0, 1.0])
        tangent1 = tangent1 / max(float(np.linalg.norm(tangent1)), 1e-9)
        tangent2 = np.cross(direction, tangent1)
        direction = direction + perturb[0] * tangent1 + perturb[1] * tangent2
        direction = direction / max(float(np.linalg.norm(direction)), 1e-9)

        v_in = float(np.linalg.norm(np.asarray(ball_at.velocity)))
        speed = min(0.7 * v_in + cfg.header_speed_base_ms * heading_skill, 32.0)  # P-12 cap

        shot_state = BallState(position=pos, velocity=direction * speed, spin=np.zeros(3))
        after = self._ball_sim.simulate(shot_state)

        dist = float(np.linalg.norm(_GOAL_CENTER - pos[:2]))
        def_xy = def_tracks[-1]
        defenders_close = int(np.sum(np.linalg.norm(def_xy - pos[:2], axis=1) < 3.0))

        # Score the shot context with the real-data xG model when one is wired.
        xg_val: float | None = None
        if self._xg is not None:
            ctx = self._shot_context(pos, def_xy, program.gk_index, is_header, defenders_close)
            xg_val = float(self._xg.score(ctx))

        events.append(
            ShotEvent(
                time_s=t_star,
                position=pos,
                player_id=program.att_player_ids[shooter_idx],
                distance_m=dist,
                angle_rad=_goal_opening_angle(pos),
                is_header=is_header,
                speed_ms=speed,
                defenders_within_3m=defenders_close,
                xg=xg_val,
            )
        )

        if xg_val is not None:
            # xG-driven outcome (G-14): one Bernoulli draw on the scored P(goal),
            # so replay goal events are consistent with the reported xG (doc 06).
            return self._resolve_shot_xg(
                xg_val,
                after,
                aim_y,
                aim_z,
                speed,
                t_star,
                program,
                events,
                seed,
                track_times,
                att_tracks,
                def_tracks,
                delivery,
                draws,
            )

        # --- placeholder path (no xG model): geometry + GK-save logit (G-9) ---
        if not after.goal_scored:
            return self._finish(
                SetPieceOutcome.OFF_TARGET,
                events,
                seed,
                track_times,
                att_tracks,
                def_tracks,
                delivery,
                after,
            )

        # On-target: GK save model (G-9). Entry point from the GoalEvent.
        goal_ev = after.events[-1]
        assert isinstance(goal_ev, GoalEvent)
        entry_y = goal_ev.entry_y_m
        entry_z = goal_ev.entry_z_m
        gk_xy = def_tracks[-1, program.gk_index]
        placement = math.hypot(float(entry_y) - float(gk_xy[1]), float(entry_z) - 1.0)
        logit = (
            cfg.save_c0
            + cfg.save_c_speed * (speed - 20.0) / 10.0
            + cfg.save_c_placement * placement
            + cfg.save_c_distance * dist
        )
        p_save = 1.0 / (1.0 + math.exp(-logit))
        # Externalized draw (ADR-011): shot_final serves the GK-save Bernoulli on
        # the placeholder path (the xG path uses the same slot for its Bernoulli).
        if draws.shot_final < p_save:
            events.append(
                SaveEvent(
                    time_s=after.final_state.time_s + t_star,
                    position=after.final_state.position,
                    player_id=program.def_player_ids[program.gk_index],
                    shot_speed_ms=speed,
                )
            )
            outcome = SetPieceOutcome.SAVED
        else:
            # Re-time the goal event into match time (shot traj starts at t*).
            events.append(
                GoalEvent(
                    time_s=goal_ev.time_s + t_star,
                    position=goal_ev.position,
                    entry_y_m=goal_ev.entry_y_m,
                    entry_z_m=goal_ev.entry_z_m,
                )
            )
            outcome = SetPieceOutcome.GOAL
        return self._finish(
            outcome, events, seed, track_times, att_tracks, def_tracks, delivery, after
        )

    def _shot_context(
        self,
        pos: FloatArray,
        def_xy: FloatArray,
        gk_index: int,
        is_header: bool,
        defenders_within_3m: int,
    ) -> ShotContext:
        """Build the xG :class:`ShotContext` from the strike geometry + traffic.

        Same quantities as ``mart_setpiece_shots`` (one frame, one transform), so
        simulated contexts and real training contexts are comparable.
        """
        shot_xy = np.asarray(pos[:2], dtype=np.float64)
        n = def_xy.shape[0]
        has_gk = 0 <= gk_index < n
        in_cone = 0
        nearest = math.inf
        for j in range(n):
            if has_gk and j == gk_index:
                continue
            p = def_xy[j]
            if _point_in_triangle(p, shot_xy, _POST_L, _POST_R):
                in_cone += 1
            d = float(np.hypot(p[0] - shot_xy[0], p[1] - shot_xy[1]))
            nearest = min(nearest, d)
        if has_gk:
            gk_xy = def_xy[gk_index]
            gk_goal = float(np.linalg.norm(_GOAL_CENTER - gk_xy))
            gk_lat = abs(float(gk_xy[1]))
        else:
            gk_goal = float(np.linalg.norm(_GOAL_CENTER - shot_xy))
            gk_lat = 0.0
        return ShotContext(
            distance_m=float(np.linalg.norm(_GOAL_CENTER - shot_xy)),
            angle_rad=_goal_opening_angle(pos),
            is_header=is_header,
            set_piece_phase="first_contact",
            defenders_in_cone=in_cone,
            nearest_def_dist_m=(0.0 if nearest == math.inf else nearest),
            defenders_within_3m=defenders_within_3m,
            gk_dist_to_goal_m=gk_goal,
            gk_lateral_m=gk_lat,
            under_pressure=defenders_within_3m > 0,
        )

    def _resolve_shot_xg(
        self,
        xg_val: float,
        after: Trajectory,
        aim_y: float,
        aim_z: float,
        speed: float,
        t_star: float,
        program: SimProgram,
        events: list[SimEvent],
        seed: int,
        track_times: FloatArray,
        att_tracks: FloatArray,
        def_tracks: FloatArray,
        delivery: Trajectory,
        draws: SimDraws,
    ) -> SetPieceResult:
        # Externalized draw (ADR-011): U(0,1) Bernoulli on the scored xG (G-14).
        scored = draws.shot_final < xg_val
        if scored:
            if after.goal_scored:
                goal_ev = after.events[-1]
                assert isinstance(goal_ev, GoalEvent)
                events.append(
                    GoalEvent(
                        time_s=goal_ev.time_s + t_star,
                        position=goal_ev.position,
                        entry_y_m=goal_ev.entry_y_m,
                        entry_z_m=goal_ev.entry_z_m,
                    )
                )
            else:
                # xG says goal but the geometric trajectory missed: synthesize a
                # replay-consistent goal at the aimed point.
                events.append(
                    GoalEvent(
                        time_s=after.final_state.time_s + t_star,
                        position=np.array([52.5, aim_y, aim_z]),
                        entry_y_m=aim_y,
                        entry_z_m=aim_z,
                    )
                )
            outcome = SetPieceOutcome.GOAL
        elif after.goal_scored:
            # Non-goal but on target -> the keeper saved it.
            events.append(
                SaveEvent(
                    time_s=after.final_state.time_s + t_star,
                    position=after.final_state.position,
                    player_id=program.def_player_ids[program.gk_index],
                    shot_speed_ms=speed,
                )
            )
            outcome = SetPieceOutcome.SAVED
        else:
            outcome = SetPieceOutcome.OFF_TARGET
        return self._finish(
            outcome, events, seed, track_times, att_tracks, def_tracks, delivery, after
        )

    def _finish(
        self,
        outcome: SetPieceOutcome,
        events: list[SimEvent],
        seed: int,
        track_times: FloatArray,
        att_tracks: FloatArray,
        def_tracks: FloatArray,
        delivery: Trajectory,
        after: Trajectory | None,
    ) -> SetPieceResult:
        for arr in (track_times, att_tracks, def_tracks):
            arr.setflags(write=False)
        return SetPieceResult(
            outcome=outcome,
            events=tuple(events),
            seed=seed,
            track_times_s=track_times,
            att_tracks=att_tracks,
            def_tracks=def_tracks,
            delivery=delivery,
            after_contact=after,
        )
