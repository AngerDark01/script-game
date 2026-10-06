"""Deterministic follow runtime used by the PoE2 lab before real output."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from auto_modules.core.routing.geometry import (
    distance_to_path,
    line_clearance_stats,
    line_is_walkable,
    line_min_clearance,
    point_distance,
)
from auto_modules.core.routing.pathfinder.runtime import PathFinder
from auto_modules.core.routing.local_controller import LocalMotionController
from auto_modules.core.routing.contact_evidence import ContactEvidence, ContactMonitor
from auto_modules.core.routing.vector_tracker import VectorPathTracker

from .models import (
    ControlMode,
    FollowObservation,
    FollowState,
    MapIdentity,
    PositionSample,
    RoleId,
)
from .closed_loop_controller import ClosedLoopMotionController
from .motion_models import MotionObservation, MotionResponse
from .motion_snapshot import build_motion_snapshot
from .reacquisition import select_reacquisition_vector
from .target_projection import WalkableTargetProjector


@dataclass
class SimulatedRemoteRole:
    """Map-click-backed target; it never opens a network connection."""

    role: RoleId = field(default_factory=lambda: RoleId("simulated-device", "remote-leader"))
    position: PositionSample | None = None

    def update(self, map_identity: MapIdentity, position: tuple[float, float], now_ms: int) -> PositionSample:
        self.position = PositionSample(
            role=self.role,
            map_identity=map_identity,
            position=position,
            captured_at_ms=int(now_ms),
            confidence=1.0,
            source="simulated",
        )
        return self.position


@dataclass
class _Follower:
    role: RoleId
    mode: ControlMode
    position: PositionSample | None = None
    last_tick_ms: int | None = None
    route: tuple[tuple[float, float], ...] = ()
    planned_target: tuple[float, float] | None = None
    state: FollowState = FollowState.IDLE
    arrival_hold: bool = False
    failed_start: tuple[float, float] | None = None
    failed_target: tuple[float, float] | None = None
    retry_after_ms: int = 0
    plan_attempts: tuple[int, ...] = ()
    plan_factor: int | None = None
    last_distance: float | None = None
    last_position: tuple[float, float] | None = None
    no_progress_ticks: int = 0
    recovery_attempts: int = 0
    recovery_target: tuple[float, float] | None = None
    recovery_deadline_ms: int = 0
    recovery_candidates_checked: int = 0
    recovery_selected_index: int | None = None
    observed_velocity: tuple[float, float] = (0.0, 0.0)
    observed_speed: float = 0.0
    last_command_vector: tuple[float, float] = (0.0, 0.0)
    last_observation_at_ms: int | None = None
    last_trusted_position: tuple[float, float] | None = None
    last_local_diagnostics: dict[str, Any] = field(default_factory=dict)
    last_local_angle_offset: float | None = None
    local_oscillation_count: int = 0
    observed_displacement: float = 0.0
    command_observed_alignment: float | None = None
    command_observed_angle_degrees: float | None = None
    direction_mismatch_ticks: int = 0
    command_duration_ms: int = 0
    progress_sample_at_ms: int | None = None
    wall_recovery_position: tuple[float, float] | None = None
    wall_recovery_target: tuple[float, float] | None = None
    wall_recovery_origin: tuple[float, float] | None = None
    wall_recovery_route: tuple[tuple[float, float], ...] = ()
    wall_recovery_candidates_checked: int = 0
    wall_recovery_pulses: int = 0
    contact_monitor: ContactMonitor = field(default_factory=ContactMonitor)
    last_contact_evidence: ContactEvidence | None = None
    local_obstacle_ahead: bool | None = None
    local_raw_obstacle_ahead: bool | None = None
    local_escape_available: bool = False
    local_obstacle_distance: float | None = None
    local_free_left: float | None = None
    local_free_right: float | None = None
    local_contact_captured_at_ms: int | None = None


class SimulatedFollowRuntime:
    """Plan and optionally advance one or more local actors toward a target.

    The runtime returns normalized movement vectors for the future program
    adapter. ``SIMULATED`` advances its own position deterministically;
    ``PREVIEW`` and ``PROGRAM`` never mutate position.
    """

    def __init__(
        self,
        *,
        wall_map: Any,
        map_identity: MapIdentity,
        arrival_radius: float = 8.0,
        resume_radius: float | None = None,
        speed_units_per_second: float = 80.0,
        position_ttl_ms: int = 700,
        downsample_factor: int = 8,
        safety_margin: int = 0,
        clearance_radius: float = 0.0,
        clearance_weight: float = 0.0,
        dead_end_weight: float = 0.0,
        minimum_clearance: float = 0.0,
        footprint_radius: float = 0.0,
        inflate_collision: bool = True,
        progress_epsilon: float = 1.0,
        stalled_ticks: int = 3,
        contact_required_samples: int = 2,
        local_lookahead: float = 18.0,
        prediction_horizon: float = 0.22,
        closed_loop_controller: ClosedLoopMotionController | None = None,
    ) -> None:
        import cv2
        import numpy as np

        walls = np.asarray(wall_map)
        if walls.ndim != 2 or min(walls.shape) < 2:
            raise ValueError("wall_map must be a two-dimensional grid")
        if arrival_radius <= 0 or speed_units_per_second <= 0:
            raise ValueError("arrival_radius and speed must be positive")
        if resume_radius is not None and resume_radius < arrival_radius:
            raise ValueError("resume_radius must be at least arrival_radius")
        if position_ttl_ms <= 0 or downsample_factor <= 0:
            raise ValueError("position_ttl_ms and downsample_factor must be positive")
        if (
            safety_margin < 0
            or clearance_radius < 0
            or clearance_weight < 0
            or dead_end_weight < 0
            or minimum_clearance < 0
            or footprint_radius < 0
        ):
            raise ValueError("route safety values must be non-negative")
        if progress_epsilon < 0 or stalled_ticks < 1 or contact_required_samples < 1:
            raise ValueError("progress monitor values are invalid")
        # PathFinder thresholds wall pixels above 50, while geometry checks
        # treat any nonzero cell as blocked. Preserve the shared 0/255 map
        # contract so both stages evaluate the same obstacles.
        self.wall_map = np.where(walls > 0, 255, 0).astype("uint8")
        self.wall_map.setflags(write=False)
        self.target_projector = WalkableTargetProjector(self.wall_map, radius=8)
        self._clearance_distance = cv2.distanceTransform(
            np.where(self.wall_map > 0, 0, 255).astype("uint8"),
            cv2.DIST_L2,
            3,
        )
        self.map_identity = map_identity
        self.arrival_radius = float(arrival_radius)
        self.resume_radius = float(arrival_radius if resume_radius is None else resume_radius)
        self.speed_units_per_second = float(speed_units_per_second)
        self.position_ttl_ms = int(position_ttl_ms)
        self.blocked_retry_ms = 1000
        self.progress_epsilon = float(progress_epsilon)
        self.stalled_ticks = int(stalled_ticks)
        self.contact_required_samples = int(contact_required_samples)
        self.minimum_clearance = float(minimum_clearance)
        self.footprint_radius = float(footprint_radius)
        self.inflate_collision = bool(inflate_collision)
        # Keep centre-line evidence separate from the collision map used by
        # planning and control. PoE2 can disable body inflation because its
        # native wall layer already closes many genuine narrow passages; the
        # local controller then handles short collision-free steering around
        # the raw wall boundary.
        if self.inflate_collision and self.footprint_radius > 0.0:
            radius = int(round(self.footprint_radius))
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1)
            )
            self.collision_map = cv2.dilate(self.wall_map, kernel)
        else:
            self.collision_map = self.wall_map
        self.collision_map.setflags(write=False)
        # A moving target does not justify a full A* run on every control
        # tick. Replan only when it leaves this goal band, when the visual
        # position leaves the current corridor, or when collision validation
        # invalidates the route. This mirrors the bounded local-replanning
        # policy used by the stable follow runtime elsewhere in the project.
        self.route_target_refresh_distance = max(self.arrival_radius * 2.0, 16.0)
        self.route_deviation_threshold = max(self.arrival_radius * 2.0, 12.0)
        self.pathfinder = PathFinder(
            downsample_factor=int(downsample_factor),
            safety_margin=int(safety_margin),
            clearance_radius=float(clearance_radius),
            clearance_weight=float(clearance_weight),
            dead_end_weight=float(dead_end_weight),
            start_clear_radius=0,
            walkable_snap_radius=0,
        )
        # A coarse grid is fast but can cut across a one-cell corner.  Keep a
        # small fallback ladder and accept a route only after checking every
        # segment on the original wall map.
        self._pathfinders = tuple(
            PathFinder(
                downsample_factor=factor,
                safety_margin=int(safety_margin),
                clearance_radius=float(clearance_radius),
                clearance_weight=float(clearance_weight),
                dead_end_weight=float(dead_end_weight),
                start_clear_radius=0,
                walkable_snap_radius=0,
            )
            for factor in dict.fromkeys((int(downsample_factor), 4, 2, 1))
            if factor > 0
        )
        self._last_plan_diagnostics: dict[str, Any] = {
            "attempted_factors": (),
            "accepted_factor": None,
        }
        self.tracker = VectorPathTracker(arrival_radius=self.arrival_radius)
        self._collision_clearance_distance = cv2.distanceTransform(
            np.where(self.collision_map > 0, 0, 255).astype("uint8"),
            cv2.DIST_L2,
            3,
        )
        self.local_controller = LocalMotionController(
            lookahead=float(local_lookahead),
            prediction_horizon=float(prediction_horizon),
            expected_speed=self.speed_units_per_second,
            arrival_radius=self.arrival_radius,
        )
        self.closed_loop_controller = closed_loop_controller
        self.remote = SimulatedRemoteRole()
        self._followers: dict[str, _Follower] = {}
        self._closed_loop_commands: dict[str, Any] = {}

    def add_follower(self, role: RoleId, position: PositionSample, *, mode: ControlMode = ControlMode.PREVIEW) -> None:
        self._validate_position(position, role)
        self._followers[role.key] = _Follower(
            role=role,
            mode=ControlMode(mode),
            position=position,
            last_trusted_position=(position.position if position.source == "visual" else None),
            contact_monitor=ContactMonitor(required_samples=self.contact_required_samples),
        )

    def set_mode(self, role: RoleId, mode: ControlMode) -> None:
        follower = self._followers.get(role.key)
        if follower is None:
            raise KeyError(role.key)
        follower.mode = ControlMode(mode)
        if follower.mode is ControlMode.MANUAL:
            follower.route = ()
            follower.planned_target = None
            follower.arrival_hold = False
            follower.state = FollowState.MANUAL
            self._clear_failed_plan(follower)

    def mode_for(self, role: RoleId) -> ControlMode:
        follower = self._followers.get(role.key)
        if follower is None:
            raise KeyError(role.key)
        return follower.mode

    def update_follower_position(self, position: PositionSample) -> None:
        follower = self._followers.get(position.role.key)
        if follower is None:
            raise KeyError(position.role.key)
        self._validate_position(position, follower.role)
        previous = follower.position
        if position.source == "visual":
            follower.last_trusted_position = position.position
        if (
            previous is not None
            and previous.source not in {"wall_estimate", "command_prediction", "target_hold"}
            and position.source not in {"wall_estimate", "command_prediction", "target_hold"}
            and position.captured_at_ms > previous.captured_at_ms
            and previous.map_identity == position.map_identity
        ):
            dt = (position.captured_at_ms - previous.captured_at_ms) / 1000.0
            if 0.005 <= dt <= 1.0:
                raw_velocity = (
                    (position.position[0] - previous.position[0]) / dt,
                    (position.position[1] - previous.position[1]) / dt,
                )
                # A short exponential filter is enough to reject one noisy
                # visual frame without hiding a real stop or wall collision.
                alpha = 0.45
                follower.observed_velocity = (
                    follower.observed_velocity[0] * (1.0 - alpha) + raw_velocity[0] * alpha,
                    follower.observed_velocity[1] * (1.0 - alpha) + raw_velocity[1] * alpha,
                )
                follower.observed_speed = point_distance((0.0, 0.0), follower.observed_velocity)
                follower.observed_displacement = point_distance(previous.position, position.position)
                follower.last_contact_evidence = follower.contact_monitor.observe(
                    follower.last_command_vector,
                    (
                        position.position[0] - previous.position[0],
                        position.position[1] - previous.position[1],
                    ),
                    elapsed_ms=max(1, int(position.captured_at_ms - previous.captured_at_ms)),
                    local_obstacle_ahead=follower.local_obstacle_ahead,
                    local_obstacle_distance=follower.local_obstacle_distance,
                    blocking_obstacle_ahead=follower.local_obstacle_ahead,
                    escape_available=follower.local_escape_available,
                )
                # Compare the command sent in the previous control period with
                # the displacement observed by the next trusted visual frame.
                # This is deliberately diagnostic/fail-safe data: the shared
                # runtime cannot assume a particular gamepad basis, but it can
                # detect a persistent axis/sign mismatch instead of repeatedly
                # driving the same wall.
                command = follower.last_command_vector
                command_norm = point_distance((0.0, 0.0), command)
                velocity_norm = point_distance((0.0, 0.0), raw_velocity)
                if command_norm > 0.15 and velocity_norm > 0.5:
                    alignment = (
                        float(command[0]) * raw_velocity[0]
                        + float(command[1]) * raw_velocity[1]
                    ) / (command_norm * velocity_norm)
                    alignment = max(-1.0, min(1.0, alignment))
                    follower.command_observed_alignment = alignment
                    follower.command_observed_angle_degrees = math.degrees(math.acos(alignment))
                    if alignment < 0.20 and follower.observed_displacement >= self.progress_epsilon:
                        follower.direction_mismatch_ticks += 1
                    else:
                        follower.direction_mismatch_ticks = max(
                            0, follower.direction_mismatch_ticks - 1
                        )
                    closed_command = self._closed_loop_commands.get(position.role.key)
                    if self.closed_loop_controller is not None and closed_command is not None:
                        try:
                            response = MotionResponse(
                                command_id=closed_command.command_id,
                                displacement=(
                                    position.position[0] - previous.position[0],
                                    position.position[1] - previous.position[1],
                                ),
                                elapsed_ms=max(1, int(position.captured_at_ms - previous.captured_at_ms)),
                                alignment=alignment,
                                speed=point_distance((0.0, 0.0), raw_velocity),
                                progress=0.0,
                                accepted=alignment >= 0.20 and follower.observed_displacement >= 0.5,
                                reason="accepted" if alignment >= 0.20 else "direction_mismatch",
                            )
                            self.closed_loop_controller.record_response(
                                closed_command, response, now_ms=position.captured_at_ms,
                            )
                            # ``record_response`` returns the sequential estimator
                            # update.  Calibration state is owned by the calibrator
                            # and must be read back by role after the update.  Keep
                            # the two observations separate so a future estimator
                            # change cannot silently break diagnostics.
                            calibration = self.closed_loop_controller.calibrator.state_for(
                                position.role.key
                            )
                            follower.last_local_diagnostics = {
                                **follower.last_local_diagnostics,
                                "calibration_confidence": calibration.confidence,
                                "calibration_samples": calibration.sample_count,
                                "calibration_speed_gain": calibration.speed_gain,
                            }
                        except (RuntimeError, ValueError) as exc:
                            follower.last_local_diagnostics = {
                                **follower.last_local_diagnostics,
                                "calibration_update_error": str(exc),
                            }
                elif follower.observed_displacement < self.progress_epsilon:
                    # A no-motion frame is handled by the existing progress
                    # watchdog; do not call it an axis mismatch without a
                    # measurable displacement direction.
                    follower.command_observed_alignment = None
                    follower.command_observed_angle_degrees = None
        follower.last_observation_at_ms = position.captured_at_ms
        follower.position = position

    def update_local_contact(
        self,
        role: RoleId,
        *,
        wall_ahead: bool | None,
        blocking_wall_ahead: bool | None = None,
        escape_available: bool | None = None,
        wall_distance: float | None = None,
        free_left: float | None = None,
        free_right: float | None = None,
        captured_at_ms: int | None = None,
    ) -> None:
        """Attach a sensor-local obstacle observation to one follower.

        The runtime stores the observation only; the adapter remains
        responsible for interpreting pixels or device sensors.  A stale
        observation is ignored by callers when they provide its timestamp.
        """
        follower = self._followers.get(role.key)
        if follower is None:
            raise KeyError(role.key)
        follower.local_raw_obstacle_ahead = None if wall_ahead is None else bool(wall_ahead)
        blocking = wall_ahead if blocking_wall_ahead is None else blocking_wall_ahead
        follower.local_obstacle_ahead = None if blocking is None else bool(blocking)
        follower.local_escape_available = bool(escape_available) if escape_available is not None else False
        follower.local_obstacle_distance = None if wall_distance is None else float(wall_distance)
        follower.local_free_left = None if free_left is None else float(free_left)
        follower.local_free_right = None if free_right is None else float(free_right)
        follower.local_contact_captured_at_ms = None if captured_at_ms is None else int(captured_at_ms)

    def set_simulated_target(self, position: tuple[float, float], *, now_ms: int) -> PositionSample:
        return self.remote.update(self.map_identity, position, int(now_ms))

    def set_target_sample(self, sample: PositionSample) -> PositionSample | None:
        """Accept a real target observation without replacing its capture time."""
        if sample.map_identity != self.map_identity:
            raise ValueError("target map identity does not match runtime")
        previous = self.remote.position
        if previous is not None and sample.captured_at_ms <= previous.captured_at_ms:
            return None
        self.remote.position = sample
        return sample

    def refresh_simulated_target(self, *, now_ms: int) -> PositionSample | None:
        """Publish a heartbeat for the click-backed target.

        A click is a static test source, but it still goes through the same
        freshness gate as a remote device.  The UI calls this once per tick;
        tests that want to exercise expiry deliberately omit the heartbeat.
        """
        target = self.remote.position
        if target is None:
            return None
        return self.remote.update(self.map_identity, target.position, int(now_ms))

    def tick(self, *, now_ms: int) -> dict[str, FollowObservation]:
        now = int(now_ms)
        target = self.remote.position
        observations: dict[str, FollowObservation] = {}
        for follower in self._followers.values():
            observations[follower.role.key] = self._tick_follower(follower, target, now)
        return observations

    def _tick_follower(self, follower: _Follower, target: PositionSample | None, now_ms: int) -> FollowObservation:
        current = follower.position
        if follower.mode is ControlMode.MANUAL:
            follower.state = FollowState.MANUAL
            return self._observation(follower, target, reason="manual_control")
        if target is None:
            follower.state = FollowState.WAITING_POSITION
            return self._observation(follower, target, reason="target_not_seeded")
        if current is not None and follower.mode is ControlMode.SIMULATED and current.source == "simulated":
            # The deterministic actor is an active local source.  Refresh its
            # timestamp even when it is waiting at the arrival band, while
            # leaving visual/manual samples subject to the normal TTL gate.
            current = PositionSample(
                follower.role,
                self.map_identity,
                current.position,
                now_ms,
                current.confidence,
                current.source,
            )
            follower.position = current
        if current is None:
            follower.state = FollowState.WAITING_POSITION
            return self._observation(follower, target, reason="follower_position_unseeded")
        if now_ms - current.captured_at_ms > self.position_ttl_ms:
            current = PositionSample(
                follower.role, self.map_identity, current.position, now_ms,
                max(0.25, current.confidence * 0.5), "command_prediction",
            )
            follower.position = current
        if now_ms - target.captured_at_ms > self.position_ttl_ms:
            target = PositionSample(
                target.role, self.map_identity, target.position, now_ms,
                max(0.25, target.confidence * 0.5), "target_hold",
            )
        if current.map_identity != self.map_identity or target.map_identity != self.map_identity:
            follower.state = FollowState.MAP_MISMATCH
            return self._observation(follower, target, reason="map_identity_mismatch")
        distance = point_distance(current.position, target.position)
        if target.source == "target_hold" and distance <= self.arrival_radius:
            follower.state = FollowState.WAITING_POSITION
            return self._observation(follower, target, distance=distance, reason="target_arrival_unconfirmed")
        if current.source == "command_prediction" and distance <= self.arrival_radius:
            # Command odometry is an estimate, not proof that the actor has
            # arrived.  Releasing the output here made a stale visual marker
            # look like a successful arrival: the predictor reached the goal,
            # the real actor had not moved, and the next frame triggered a
            # re-anchor.  Keep a short approach pulse active until a trusted
            # visual sample confirms the arrival.
            vector = self._local_command(
                follower,
                current,
                target,
                active_target=target.position,
                now_ms=now_ms,
                peer_position=self._peer_position_for(follower),
            )
            if vector == (0.0, 0.0) and distance > 1e-6:
                dx = target.position[0] - current.position[0]
                dy = target.position[1] - current.position[1]
                scale = math.hypot(dx, dy)
                if scale > 1e-6:
                    vector = (dx / scale, dy / scale)
            # ``ClosedLoopMotionController`` exposes policy durations, not a
            # per-tick ``command_duration_ms`` field.  Use its constrained
            # pulse duration for this bounded approach step and keep a safe
            # fallback for callers that inject a lightweight controller in
            # tests or adapters.
            approach_duration = (
                getattr(self.closed_loop_controller, "constrained_duration_ms", 80)
                if self.closed_loop_controller is not None else 80
            )
            follower.command_duration_ms = min(80, max(1, int(approach_duration)))
            follower.state = (
                FollowState.PROGRAM_READY
                if follower.mode is ControlMode.PROGRAM else FollowState.PREVIEWING
            )
            return self._observation(
                follower, target, distance=distance,
                reason="arrival_unconfirmed", vector=vector,
            )
        if follower.arrival_hold and distance < self.resume_radius:
            follower.state = FollowState.ARRIVED
            return self._observation(follower, target, distance=distance, reason="within_resume_radius")
        follower.arrival_hold = False
        if distance <= self.arrival_radius:
            follower.arrival_hold = True
            follower.route = ()
            follower.planned_target = None
            follower.state = FollowState.ARRIVED
            self._clear_failed_plan(follower)
            return self._observation(follower, target, distance=distance, reason="within_arrival_radius")

        if (
            follower.local_contact_captured_at_ms is not None
            and current.captured_at_ms - follower.local_contact_captured_at_ms > 700
        ):
            follower.local_obstacle_ahead = None
            follower.local_raw_obstacle_ahead = None
            follower.local_escape_available = False
            follower.local_obstacle_distance = None
            follower.local_free_left = None
            follower.local_free_right = None
            follower.local_contact_captured_at_ms = None

        contact_evidence = follower.last_contact_evidence
        # A recovery flag is only actionable while the newest local sample
        # still confirms a blocking obstacle.  Contact evidence is produced
        # when a visual position arrives, so reusing it after a later open
        # local sample would resurrect a collision that has already cleared.
        contact_pending = bool(
            current.source not in {"wall_estimate", "command_prediction", "target_hold"}
            and contact_evidence
            and contact_evidence.recovery_required
            and follower.local_obstacle_ahead is True
        )

        # Keep a boundary actor under a short escape pulse until a newer
        # observation places it on walkable terrain.  Native samples can stay
        # in the same raster cell for several frames while the game is moving
        # continuously; releasing the command after the first pulse would
        # otherwise look like an unexplained stop at the wall edge.
        if follower.mode is not ControlMode.SIMULATED and not contact_pending:
            open_minimap_sample = not self._wall_start_recovery_allowed(follower)
            boundary_vector = self._wall_start_recovery_command(
                follower,
                current,
                target,
                allow_open_sample=(
                    open_minimap_sample and follower.wall_recovery_origin is not None
                ),
            )
            if boundary_vector is not None:
                follower.state = (
                    FollowState.PROGRAM_READY
                    if follower.mode is ControlMode.PROGRAM
                    else FollowState.PREVIEWING
                )
                return self._observation(
                    follower,
                    target,
                    distance=distance,
                    reason=(
                        "stale_wall_raster_recovery"
                        if open_minimap_sample
                        else "wall_start_recovery"
                    ),
                    vector=boundary_vector,
                )

        if (
            follower.recovery_target is not None
            and (
                now_ms >= follower.recovery_deadline_ms
                or point_distance(current.position, follower.recovery_target) <= self.arrival_radius
            )
        ):
            follower.recovery_target = None
            follower.route = ()
            follower.planned_target = None

        if (
            current.source not in {"wall_estimate", "command_prediction", "target_hold"}
            and follower.progress_sample_at_ms != current.captured_at_ms
            and follower.last_distance is not None
        ):
            distance_delta = follower.last_distance - distance
            movement = (
                point_distance(current.position, follower.last_position)
                if follower.last_position is not None
                else float("inf")
            )
            if distance_delta < self.progress_epsilon and movement < self.progress_epsilon:
                follower.no_progress_ticks += 1
            else:
                follower.no_progress_ticks = 0
                follower.last_distance = distance
                follower.last_position = current.position
        if follower.last_distance is None:
            follower.last_distance = distance
            follower.last_position = current.position
        follower.progress_sample_at_ms = current.captured_at_ms

        if (
            follower.recovery_target is None
            and (
                follower.no_progress_ticks >= self.stalled_ticks
                or (
                    follower.direction_mismatch_ticks >= 3
                    and (
                        follower.local_obstacle_ahead is not True
                        or follower.observed_displacement < self.progress_epsilon
                    )
                )
                or contact_pending
            )
        ):
            mismatch_recovery = follower.direction_mismatch_ticks >= 3
            # A local minimap obstacle is the extra evidence that should
            # bypass the cached global route.  Without it, preserve the
            # runtime's existing stalled/direction-mismatch reasons so a
            # healthy low-rate visual stream is not treated as a wall.
            contact_recovery = contact_pending and follower.local_obstacle_ahead is True
            follower.recovery_attempts += 1
            follower.no_progress_ticks = 0
            follower.direction_mismatch_ticks = 0
            follower.last_distance = distance
            follower.last_position = current.position
            follower.recovery_target = None
            follower.recovery_candidates_checked = 0
            follower.recovery_selected_index = None

            # Two failed local escapes mean the native transform is no longer
            # trustworthy.  Stop issuing the old route and let the owning
            # composition perform its one-shot memory/visual re-anchor.
            if (
                contact_recovery
                and follower.recovery_attempts >= 2
                and not follower.local_escape_available
            ):
                probe = self._cooldown_probe_command(
                    follower, current.position, target.position,
                )
                follower.state = (
                    FollowState.PROGRAM_READY
                    if follower.mode is ControlMode.PROGRAM
                    else FollowState.PREVIEWING
                )
                return self._observation(
                    follower,
                    target,
                    distance=distance,
                    reason="contact_relocalization_probe",
                    vector=probe,
                )

            # A visual/native registration can land on a wall cell by a few
            # pixels even though the actor is physically beside the wall.
            # Normal route validation must reject such a start, but stopping
            # immediately leaves no way to escape the quantisation error.
            # First search a small ring of free cells and plan from the best
            # one; the emitted vector is only a bounded nudge out of the bad
            # cell.  The actual follower position is never rewritten.
            if contact_recovery:
                contact_vector = self._contact_recovery_command(
                    follower,
                    current,
                    target,
                )
                if contact_vector is not None:
                    follower.state = (
                        FollowState.PROGRAM_READY
                        if follower.mode is ControlMode.PROGRAM
                        else FollowState.PREVIEWING
                    )
                    return self._observation(
                        follower,
                        target,
                        distance=distance,
                        reason="contact_recovery",
                        vector=contact_vector,
                    )

            open_minimap_sample = not self._wall_start_recovery_allowed(follower)
            wall_vector = None if contact_recovery else self._wall_start_recovery_command(
                follower,
                current,
                target,
                allow_open_sample=open_minimap_sample,
            )
            if wall_vector is not None:
                follower.state = (
                    FollowState.PROGRAM_READY
                    if follower.mode is ControlMode.PROGRAM
                    else FollowState.PREVIEWING
                )
                return self._observation(
                    follower,
                    target,
                    distance=distance,
                    reason=(
                        "stale_wall_raster_recovery"
                        if open_minimap_sample
                        else "wall_start_recovery"
                    ),
                    vector=wall_vector,
                )

            # A visual stall does not prove that the destination is
            # unreachable.  Rebuild the route to the real target first: the
            # character may have just cleared a doorway while the cached
            # corridor still points at the wall-facing approach vector.
            direct_route = None if contact_recovery else self._plan_safe_route(current.position, target.position)
            if direct_route:
                follower.plan_attempts = tuple(
                    self._last_plan_diagnostics.get("attempted_factors", ())
                )
                follower.plan_factor = self._last_plan_diagnostics.get("accepted_factor")
                follower.route = tuple((float(x), float(y)) for x, y in direct_route)
                follower.planned_target = target.position
                direct_vector = self._local_command(
                    follower,
                    current,
                    target,
                    active_target=target.position,
                    now_ms=now_ms,
                    peer_position=self._peer_position_for(follower),
                )
                if direct_vector != (0.0, 0.0):
                    follower.state = (
                        FollowState.PROGRAM_READY
                        if follower.mode is ControlMode.PROGRAM
                        else FollowState.PREVIEWING
                    )
                    return self._observation(
                        follower,
                        target,
                        distance=distance,
                        reason="stalled_replanned",
                        vector=direct_vector,
                    )

            # If the direct command is still blocked, probe several short
            # lateral/forward waypoints.  One failed probe must not terminate
            # an otherwise valid route through a narrow doorway.
            recovery_candidates = self._recovery_waypoints(
                current.position,
                target.position,
                follower.recovery_attempts,
                preferred_side=(
                    1.0
                    if follower.local_free_left is not None
                    and follower.local_free_right is not None
                    and follower.local_free_left >= follower.local_free_right
                    else -1.0
                    if follower.local_free_left is not None
                    and follower.local_free_right is not None
                    else None
                ),
            )
            follower.recovery_candidates_checked = len(recovery_candidates)
            for candidate_index, recovery in enumerate(recovery_candidates):
                escape_route = self._plan_safe_route(current.position, recovery)
                if not escape_route:
                    continue
                follower.plan_attempts = tuple(
                    self._last_plan_diagnostics.get("attempted_factors", ())
                )
                follower.plan_factor = self._last_plan_diagnostics.get("accepted_factor")
                follower.recovery_target = recovery
                follower.recovery_selected_index = candidate_index
                follower.recovery_deadline_ms = now_ms + 450
                follower.route = tuple((float(x), float(y)) for x, y in escape_route)
                follower.planned_target = recovery
                vector = self._local_command(
                    follower,
                    current,
                    target,
                    active_target=recovery,
                    now_ms=now_ms,
                    peer_position=self._peer_position_for(follower),
                )
                if vector == (0.0, 0.0):
                    follower.recovery_target = None
                    follower.recovery_selected_index = None
                    continue
                follower.state = (
                    FollowState.PROGRAM_READY
                    if follower.mode is ControlMode.PROGRAM
                    else FollowState.PREVIEWING
                )
                return self._observation(
                    follower,
                    target,
                    distance=distance,
                    reason=(
                        "contact_recovery"
                        if contact_recovery
                        else (
                        "direction_mismatch_recovery"
                        if mismatch_recovery
                        else "stalled_recovery"
                        )
                    ),
                    vector=vector,
                )
            follower.direction_mismatch_ticks = 0
            probe = self._cooldown_probe_command(
                follower, current.position, target.position,
            )
            follower.state = (
                FollowState.PROGRAM_READY
                if follower.mode is ControlMode.PROGRAM
                else FollowState.PREVIEWING
            )
            return self._observation(
                follower, target, distance=distance,
                reason="stalled_probe", vector=probe,
            )
        # The cached route may end inside the old arrival band but outside the
        # new one.  Replan before VectorPathTracker reports arrival at that old
        # endpoint and leaves an actor motionless short of the actual target.
        active_target = follower.recovery_target or target.position
        target_shift = (
            float("inf")
            if follower.planned_target is None
            else point_distance(follower.planned_target, active_target)
        )
        route_deviation = (
            float("inf")
            if not follower.route
            else distance_to_path(current.position, follower.route)
        )
        route_stale = (
            not follower.route
            or target_shift > self.route_target_refresh_distance
            or route_deviation > self.route_deviation_threshold
        )
        if route_stale:
            if self._failed_plan_on_cooldown(follower, current.position, target.position, now_ms):
                # A failed route is cached briefly to avoid repeating a full
                # search every tick. It is not evidence that the actor must
                # stop: the native/map point can be one raster cell inside a
                # wall while the real actor is merely touching its edge.
                # Keep the controller alive and probe locally; the next
                # observation can clear the stale start cell and rebuild the
                # route normally.
                probe = self._cooldown_probe_command(
                    follower, current.position, target.position,
                )
                follower.state = (
                    FollowState.PROGRAM_READY
                    if follower.mode is ControlMode.PROGRAM
                    else FollowState.PREVIEWING
                )
                return self._observation(
                    follower, target, distance=distance,
                    reason="no_safe_route_probe", vector=probe,
                )
            planned = self._plan_safe_route(current.position, active_target)
            follower.plan_attempts = tuple(self._last_plan_diagnostics.get("attempted_factors", ()))
            follower.plan_factor = self._last_plan_diagnostics.get("accepted_factor")
            if not planned:
                # The first route attempt can fail before the progress
                # watchdog has a chance to fire.  If the native point is only
                # on a wall raster boundary, issue the same bounded escape
                # pulse immediately instead of entering the failed-plan
                # cooldown and stopping the program output.
                wall_vector = self._wall_start_recovery_command(
                    follower,
                    current,
                    target,
                )
                if wall_vector is not None:
                    follower.state = (
                        FollowState.PROGRAM_READY
                        if follower.mode is ControlMode.PROGRAM
                        else FollowState.PREVIEWING
                    )
                    return self._observation(
                        follower,
                        target,
                        distance=distance,
                        reason="wall_start_recovery",
                        vector=wall_vector,
                    )
                follower.failed_start = current.position
                follower.failed_target = target.position
                follower.retry_after_ms = now_ms + self.blocked_retry_ms
                probe = self._cooldown_probe_command(
                    follower, current.position, target.position,
                )
                follower.state = (
                    FollowState.PROGRAM_READY
                    if follower.mode is ControlMode.PROGRAM
                    else FollowState.PREVIEWING
                )
                return self._observation(
                    follower, target, distance=distance,
                    reason="no_safe_route_probe", vector=probe,
                )
            follower.route = tuple((float(point[0]), float(point[1])) for point in planned)
            follower.planned_target = active_target
            self._clear_failed_plan(follower)
        vector = self._local_command(
            follower, current, target, active_target=active_target, now_ms=now_ms,
            peer_position=self._peer_position_for(follower),
        )
        if (
            vector == (0.0, 0.0)
            and distance > self.arrival_radius
            and not route_stale
            and bool(follower.route)
            and point_distance(follower.route[-1], target.position) > 1e-6
        ):
            # The target can move *inside* the old endpoint's arrival band.
            # The tracker then stops at that endpoint although the follower is
            # outside the new target's band.  Try the exact new goal once.
            updated = self._plan_safe_route(current.position, target.position)
            if updated:
                candidate = tuple((float(point[0]), float(point[1])) for point in updated)
                revised_vector = self.tracker.command(
                    current.position, candidate, walls=self.collision_map,
                    confidence=min(current.confidence, target.confidence),
                )
                if revised_vector != (0.0, 0.0):
                    follower.route = candidate
                    follower.planned_target = target.position
                    vector = self._local_command(
                        follower, current, target, active_target=target.position, now_ms=now_ms,
                        peer_position=self._peer_position_for(follower),
                    )
        if vector == (0.0, 0.0) and distance > self.arrival_radius:
            # A zero vector is often the first observable symptom of a
            # character scraping a wall or the visual position leaving the
            # old route.  Keep the route alive long enough for the progress
            # watchdog above to emit a lateral recovery waypoint; declaring
            # BLOCKED here used to release the stick before recovery could
            # ever run.
            vector = self._cooldown_probe_command(
                follower, current.position, target.position,
            )
            follower.last_tick_ms = now_ms
            follower.state = (
                FollowState.PROGRAM_READY
                if follower.mode is ControlMode.PROGRAM
                else FollowState.PREVIEWING
            )
            return self._observation(
                follower,
                target,
                distance=distance,
                reason="route_not_progressing_probe",
                vector=vector,
            )
        follower.last_command_vector = vector
        # The closed-loop controller owns the pulse duration. Do not replace
        # it with the UI timer interval: a delayed Qt tick must not turn a
        # 160 ms pulse into a 667 ms stick hold. Legacy local control still
        # uses elapsed tick time as its duration.
        if self.closed_loop_controller is None:
            follower.command_duration_ms = (
                0 if follower.last_tick_ms is None else max(0, int(now_ms - follower.last_tick_ms))
            )
        if follower.mode is ControlMode.SIMULATED and vector != (0.0, 0.0):
            dt = 0.0 if follower.last_tick_ms is None else max(0.0, min(0.2, (now_ms - follower.last_tick_ms) / 1000.0))
            if dt:
                step = self.speed_units_per_second * dt
                next_position = (
                    current.position[0] + vector[0] * step,
                    current.position[1] + vector[1] * step,
                )
                if line_is_walkable(self.collision_map, current.position, next_position, corner_safe=True):
                    follower.position = PositionSample(
                        role=follower.role,
                        map_identity=self.map_identity,
                        position=next_position,
                        captured_at_ms=now_ms,
                        confidence=current.confidence,
                        source="simulated",
                    )
                else:
                    follower.route = ()
                    follower.state = FollowState.BLOCKED
                    follower.last_tick_ms = now_ms
                    return self._observation(follower, target, distance=distance, reason="simulated_step_blocked")
        follower.last_tick_ms = now_ms
        follower.state = FollowState.SIMULATING if follower.mode is ControlMode.SIMULATED else (
            FollowState.PROGRAM_READY if follower.mode is ControlMode.PROGRAM else FollowState.PREVIEWING
        )
        return self._observation(follower, target, distance=distance, reason="route_ready", vector=vector)

    def _local_command(
        self,
        follower: _Follower,
        current: PositionSample,
        target: PositionSample,
        *,
        active_target: tuple[float, float],
        now_ms: int,
        peer_position: tuple[float, float] | None = None,
    ) -> tuple[float, float]:
        """Apply short-horizon collision and speed control to a route vector."""
        if self.closed_loop_controller is not None and current.source != "command_prediction":
            observation = MotionObservation(
                role_key=follower.role.key,
                position=current.position,
                target=active_target,
                captured_at_ms=current.captured_at_ms,
                frame_age_ms=max(0, int(now_ms) - int(current.captured_at_ms)),
                confidence=min(current.confidence, target.confidence),
                map_version=self.map_identity.map_version,
                registration_version=0,
                observed_velocity=follower.observed_velocity,
                command_alignment=follower.command_observed_alignment,
                peer_position=peer_position,
            )
            snapshot = build_motion_snapshot(
                observation=observation,
                wall_map=self.collision_map,
                distance_field=self._collision_clearance_distance,
                route=tuple(follower.route),
                target=active_target,
                peer_position=peer_position,
            )
            decision = self.closed_loop_controller.step(snapshot, now_ms=current.captured_at_ms)
            follower.last_local_diagnostics = {
                **decision.complexity.diagnostics,
                **dict(decision.diagnostics),
                "policy": decision.diagnostics.get("policy", "neutral"),
                "motion_loop_state": decision.complexity.state.value,
                "motion_loop_command_id": None if decision.command is None else decision.command.command_id,
            }
            if decision.command is None:
                follower.last_command_vector = (0.0, 0.0)
                return (0.0, 0.0)
            self._closed_loop_commands[follower.role.key] = decision.command
            follower.last_command_vector = decision.command.desired_native_vector
            follower.command_duration_ms = decision.command.duration_ms
            return decision.command.desired_native_vector
        desired = self.tracker.command(
            current.position,
            follower.route,
            walls=self.collision_map,
            confidence=min(current.confidence, target.confidence),
        )
        previous_command = follower.last_command_vector
        decision = self.local_controller.command(
            current.position,
            active_target,
            follower.route,
            desired_vector=desired,
            walls=self.collision_map,
            distance_map=self._collision_clearance_distance,
            observed_velocity=follower.observed_velocity,
            previous_command=follower.last_command_vector,
            previous_angle_offset=follower.last_local_angle_offset,
            oscillation_count=follower.local_oscillation_count,
            arrival_radius=self.arrival_radius,
            confidence=min(current.confidence, target.confidence),
        )
        previous_angle = follower.last_local_angle_offset
        if (
            previous_angle is not None
            and abs(float(previous_angle)) > 1e-6
            and abs(float(decision.angle_offset_degrees)) > 1e-6
            and float(previous_angle) * float(decision.angle_offset_degrees) < 0.0
        ):
            follower.local_oscillation_count += 1
        elif abs(float(decision.angle_offset_degrees)) < 1e-6:
            follower.local_oscillation_count = 0
        else:
            follower.local_oscillation_count = max(0, follower.local_oscillation_count - 1)
        follower.last_local_angle_offset = float(decision.angle_offset_degrees)
        follower.last_command_vector = decision.vector
        follower.last_local_diagnostics = {
            **decision.diagnostics,
            "oscillation_count": follower.local_oscillation_count,
        }
        if current.source == "command_prediction":
            follower.command_duration_ms = 80
            recovery = select_reacquisition_vector(
                current.position, active_target,
                follower.last_trusted_position or current.position,
                decision.vector,
                walls=self.collision_map,
                distance_map=self._collision_clearance_distance,
                previous_command=previous_command,
            )
            follower.last_local_diagnostics = {
                **follower.last_local_diagnostics,
                "policy": "bounded_reacquisition_pulse",
                "motion_loop_state": "predicted",
                "reacquisition_score": None if recovery is None else recovery.score,
                "reacquisition_candidates": 0 if recovery is None else recovery.valid_candidates,
                "reacquisition_angle": None if recovery is None else recovery.angle_degrees,
            }
            return (0.0, 0.0) if recovery is None else recovery.vector
        return decision.vector

    def _peer_position_for(self, follower: _Follower) -> tuple[float, float] | None:
        """Return the newest valid position of another local role.

        This is only an observation for local complexity scoring.  It does not
        create a second target or mutate the other role's state.
        """
        candidates = [
            item.position.position
            for key, item in self._followers.items()
            if key != follower.role.key and item.position is not None
            and item.position.map_identity == self.map_identity
        ]
        return candidates[0] if candidates else None

    def _recovery_waypoint(
        self,
        current: tuple[float, float],
        target: tuple[float, float],
        attempt: int,
    ) -> tuple[float, float] | None:
        """Create a short lateral probe so a blocked stick direction changes."""
        dx = float(target[0]) - float(current[0])
        dy = float(target[1]) - float(current[1])
        length = point_distance(current, target)
        if length <= 1e-6:
            return None
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        side = -1.0 if int(attempt) % 2 == 0 else 1.0
        distance = min(64.0, max(28.0, self.arrival_radius * 4.0))
        return (current[0] + px * side * distance, current[1] + py * side * distance)

    def _cooldown_probe_command(
        self,
        follower: _Follower,
        current: tuple[float, float],
        target: tuple[float, float],
    ) -> tuple[float, float]:
        """Emit a short exploratory vector during a failed-plan cooldown.

        The collision raster is intentionally not a hard constraint here: it
        may be stale by one cell at a wall edge. The small alternating pulse
        changes the approach axis and is corrected by the next observation.
        """
        dx = float(target[0]) - float(current[0])
        dy = float(target[1]) - float(current[1])
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return (0.0, 0.0)
        ux, uy = dx / length, dy / length
        # Score several short directions against the current map.  This is a
        # local escape policy, not a second path planner: it deliberately
        # tolerates stale collision cells and lets the next observation decide.
        base_angle = math.atan2(uy, ux)
        angles = (0.0, -0.55, 0.55, -1.05, 1.05, math.pi)
        probe_distance = min(32.0, max(12.0, self.arrival_radius * 2.5))
        candidates: list[dict[str, float | bool]] = []
        previous = follower.last_command_vector or (ux, uy)
        for offset in angles:
            angle = base_angle + offset
            vector = (math.cos(angle), math.sin(angle))
            endpoint = (
                current[0] + vector[0] * probe_distance,
                current[1] + vector[1] * probe_distance,
            )
            walkable = bool(line_is_walkable(self.collision_map, current, endpoint, corner_safe=True))
            metrics = self._point_metrics(endpoint)
            clearance = float(metrics.get("clearance", 0.0) or 0.0)
            approach = point_distance(current, target) - point_distance(endpoint, target)
            continuity = vector[0] * float(previous[0]) + vector[1] * float(previous[1])
            free_hint = 0.0
            if offset < 0 and follower.local_free_left is not None:
                free_hint = float(follower.local_free_left)
            elif offset > 0 and follower.local_free_right is not None:
                free_hint = float(follower.local_free_right)
            score = (
                approach * 1.5
                + min(clearance, 24.0) * 0.35
                + min(free_hint, 24.0) * 0.15
                + continuity * 2.0
                + (8.0 if walkable else -12.0)
            )
            candidates.append({
                "angle": float(math.degrees(offset)), "score": float(score),
                "walkable": walkable, "clearance": clearance,
                "approach": float(approach), "vector_x": vector[0], "vector_y": vector[1],
            })
        selected = max(candidates, key=lambda item: float(item["score"]))
        vector = (float(selected["vector_x"]), float(selected["vector_y"]))
        follower.last_command_vector = vector
        follower.command_duration_ms = 100
        follower.last_local_diagnostics = {
            **follower.last_local_diagnostics,
            "reason": "no_safe_route_probe",
            "policy": "bounded_cooldown_probe",
            "probe_candidates": tuple(candidates),
            "selected_probe_score": float(selected["score"]),
            "selected_probe_angle": float(selected["angle"]),
        }
        return vector

    def _recovery_waypoints(
        self,
        current: tuple[float, float],
        target: tuple[float, float],
        attempt: int,
        *,
        preferred_side: float | None = None,
    ) -> tuple[tuple[float, float], ...]:
        """Return bounded escape probes ordered by low-risk lateral motion.

        The old recovery policy tried one fixed side.  That is insufficient
        at a doorway: the first side can be outside the walkable island even
        while the opposite side or a shorter forward probe is valid.  Keep
        the probes local and deterministic so a stall cannot trigger a large
        global search or an uncontrolled input burst.
        """
        dx = float(target[0]) - float(current[0])
        dy = float(target[1]) - float(current[1])
        length = point_distance(current, target)
        if length <= 1e-6:
            return ()
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        base = max(8.0, min(28.0, self.arrival_radius * 2.0))
        lateral_distances = (
            base,
            min(40.0, max(base + 8.0, self.arrival_radius * 3.0)),
            min(64.0, max(base + 16.0, self.arrival_radius * 4.0)),
        )
        forward_distances = (0.0, min(18.0, base), min(28.0, base * 1.5))
        if preferred_side not in (-1.0, 1.0):
            preferred_side = -1.0 if int(attempt) % 2 == 0 else 1.0
        candidates: list[tuple[float, float]] = []
        for forward in forward_distances:
            for side in (preferred_side, -preferred_side):
                lateral = lateral_distances[min(len(lateral_distances) - 1, len(candidates) // 2)]
                candidates.append(
                    (
                        current[0] + ux * forward + px * side * lateral,
                        current[1] + uy * forward + py * side * lateral,
                    )
                )
        # Include a short forward-only probe last.  This is useful after a
        # doorway has opened but the previous command was sampled too early.
        candidates.append(
            (
                current[0] + ux * min(24.0, max(10.0, self.arrival_radius * 3.0)),
                current[1] + uy * min(24.0, max(10.0, self.arrival_radius * 3.0)),
            )
        )
        return tuple(candidates)

    def _wall_start_recovery_command(
        self,
        follower: _Follower,
        current: PositionSample,
        target: PositionSample,
        *,
        allow_open_sample: bool = False,
    ) -> tuple[float, float] | None:
        # A minimap sample with an open centreline is stronger evidence than a
        # stale native raster cell.  Do not keep issuing a wall-start pulse
        # after the actor has already cleared the obstacle in the live view.
        if not allow_open_sample and not self._wall_start_recovery_allowed(follower):
            self._clear_wall_recovery(follower)
            return None
        if follower.wall_recovery_pulses >= 3:
            # A bounded wall-start assist is only a quantisation correction;
            # repeated zero-displacement pulses must return control to the
            # progress watchdog and its lateral/relocalisation recovery.
            if (
                follower.wall_recovery_position is None
                or point_distance(current.position, follower.wall_recovery_position) <= 3.0
            ) and (
                follower.wall_recovery_target is None
                or point_distance(target.position, follower.wall_recovery_target)
                <= self.route_target_refresh_distance
            ):
                follower.wall_recovery_origin = None
                follower.wall_recovery_route = ()
                return None
            self._clear_wall_recovery(follower)
            return None
        cached = (
            follower.wall_recovery_origin is not None
            and bool(follower.wall_recovery_route)
            and follower.wall_recovery_position is not None
            and follower.wall_recovery_target is not None
            and point_distance(current.position, follower.wall_recovery_position) <= 3.0
            and point_distance(target.position, follower.wall_recovery_target)
            <= self.route_target_refresh_distance
        )
        wall_escape = (
            (
                follower.wall_recovery_origin,
                follower.wall_recovery_route,
                follower.wall_recovery_candidates_checked,
            )
            if cached
            else self._wall_start_recovery(current.position, target.position)
        )
        if wall_escape is None:
            return None
        escape_origin, escape_route, checked = wall_escape
        if escape_origin is None or escape_route is None:
            return None
        dx = float(escape_origin[0]) - float(current.position[0])
        dy = float(escape_origin[1]) - float(current.position[1])
        norm = math.hypot(dx, dy)
        if norm <= 1e-6:
            return None
        magnitude = min(0.45, max(0.25, norm / 12.0))
        vector = (dx / norm * magnitude, dy / norm * magnitude)
        follower.recovery_candidates_checked = checked
        follower.recovery_selected_index = 0
        follower.route = tuple((float(x), float(y)) for x, y in escape_route)
        follower.planned_target = target.position
        follower.failed_start = None
        follower.failed_target = None
        follower.retry_after_ms = 0
        follower.plan_attempts = tuple(self._last_plan_diagnostics.get("attempted_factors", ()))
        follower.plan_factor = self._last_plan_diagnostics.get("accepted_factor")
        follower.last_command_vector = vector
        if not cached:
            follower.wall_recovery_pulses = 0
        follower.wall_recovery_pulses += 1
        follower.wall_recovery_position = (
            follower.wall_recovery_position or current.position
        )
        follower.wall_recovery_target = target.position
        follower.wall_recovery_origin = escape_origin
        follower.wall_recovery_route = tuple(
            (float(x), float(y)) for x, y in escape_route
        )
        follower.wall_recovery_candidates_checked = checked
        # This is a short escape pulse, not a closed-loop route duration. Keep
        # it bounded while the next visual frame confirms walkable terrain.
        follower.command_duration_ms = 120
        follower.last_local_diagnostics = {
            **follower.last_local_diagnostics,
            "reason": "wall_start_recovery",
            "escape_origin": escape_origin,
            "escape_distance": norm,
            "escape_candidates_checked": checked,
            "escape_pulses": follower.wall_recovery_pulses,
        }
        return vector

    @staticmethod
    def _clear_wall_recovery(follower: _Follower) -> None:
        follower.wall_recovery_position = None
        follower.wall_recovery_target = None
        follower.wall_recovery_origin = None
        follower.wall_recovery_route = ()
        follower.wall_recovery_candidates_checked = 0
        follower.wall_recovery_pulses = 0

    @staticmethod
    def _wall_start_recovery_allowed(follower: _Follower) -> bool:
        """Return whether the latest minimap sample still permits wall assist."""
        return not (
            follower.local_contact_captured_at_ms is not None
            and follower.local_obstacle_ahead is False
        )

    def _contact_recovery_command(
        self,
        follower: _Follower,
        current: PositionSample,
        target: PositionSample,
    ) -> tuple[float, float] | None:
        """Build one local escape command from minimap contact evidence.

        A visual/native registration can place the actor on a wall raster
        cell even when the game reports that it is beside the wall.  The
        regular planner intentionally rejects that start.  For a confirmed
        minimap contact, search a small ring of walkable native cells, ordered
        toward the side with more free minimap space, and plan from that cell.
        The command only nudges from the observed position to the selected
        origin; it never rewrites the observed position or disables collision
        checks for the rest of the route.
        """
        metrics = self._point_metrics(current.position)
        if not metrics.get("in_bounds") or not metrics.get("collision"):
            return None

        dx = float(target.position[0]) - float(current.position[0])
        dy = float(target.position[1]) - float(current.position[1])
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return None
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        left = follower.local_free_left
        right = follower.local_free_right
        preferred_side = 1.0 if left is None or right is None or left >= right else -1.0
        cx = int(round(float(current.position[0])))
        cy = int(round(float(current.position[1])))
        height, width = self.collision_map.shape
        candidates: list[tuple[float, float, float, float]] = []
        max_radius = 12
        for radius in range(1, max_radius + 1):
            for oy in range(-radius, radius + 1):
                for ox in range(-radius, radius + 1):
                    if max(abs(ox), abs(oy)) != radius:
                        continue
                    x, y = cx + ox, cy + oy
                    if x < 0 or y < 0 or x >= width or y >= height:
                        continue
                    if int(self.collision_map[y, x]) != 0:
                        continue
                    offset_x = float(x) - float(current.position[0])
                    offset_y = float(y) - float(current.position[1])
                    lateral = offset_x * px + offset_y * py
                    forward = offset_x * ux + offset_y * uy
                    # Prefer the side reported as open, then shorter escapes;
                    # a small forward component is useful at a corner.
                    side_penalty = 0.0 if lateral * preferred_side >= 0.0 else 6.0
                    score = side_penalty + math.hypot(offset_x, offset_y) + max(0.0, -forward) * 0.25
                    candidates.append((score, float(x), float(y), lateral))
            if candidates and radius >= 3:
                # The first few rings contain all useful wall-edge origins;
                # avoid turning this recovery path into a global search.
                break

        candidates.sort(key=lambda item: item[0])
        for _, origin_x, origin_y, _ in candidates:
            origin = (origin_x, origin_y)
            route = self._plan_safe_route(origin, target.position)
            if not route:
                continue
            escape_x = origin_x - float(current.position[0])
            escape_y = origin_y - float(current.position[1])
            norm = math.hypot(escape_x, escape_y)
            if norm <= 1e-6:
                continue
            magnitude = min(0.45, max(0.25, norm / 12.0))
            vector = (escape_x / norm * magnitude, escape_y / norm * magnitude)
            follower.recovery_candidates_checked = len(candidates)
            follower.recovery_selected_index = 0
            follower.route = tuple((float(x), float(y)) for x, y in route)
            follower.planned_target = target.position
            follower.failed_start = None
            follower.failed_target = None
            follower.retry_after_ms = 0
            follower.last_command_vector = vector
            follower.command_duration_ms = 120
            follower.last_local_diagnostics = {
                **follower.last_local_diagnostics,
                "reason": "contact_recovery",
                "escape_origin": origin,
                "escape_distance": norm,
                "escape_candidates_checked": len(candidates),
                "preferred_side": preferred_side,
                "local_free_left": left,
                "local_free_right": right,
            }
            return vector
        return None

    def _wall_start_recovery(
        self,
        current: tuple[float, float],
        target: tuple[float, float],
    ) -> tuple[tuple[float, float], tuple[tuple[float, float], ...], int] | None:
        """Find a nearby free planning origin when the observed cell is wall.

        The search is intentionally local and bounded.  It compensates for
        native/grid quantisation at a wall edge without weakening collision
        checks for ordinary starts or changing the stored visual position.
        """
        metrics = self._point_metrics(current)
        if not metrics.get("in_bounds") or not metrics.get("collision"):
            return None
        height, width = self.collision_map.shape
        cx = int(round(float(current[0])))
        cy = int(round(float(current[1])))
        candidates: list[tuple[float, float, float, int, int]] = []
        max_radius = 12
        for radius in range(1, max_radius + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    x, y = cx + dx, cy + dy
                    if x < 0 or y < 0 or x >= width or y >= height:
                        continue
                    if int(self.collision_map[y, x]) != 0:
                        continue
                    distance = math.hypot(float(x) - current[0], float(y) - current[1])
                    clearance = float(self._clearance_distance[y, x])
                    # Prefer a close cell, then one with more room.  The
                    # target distance is only a tie-breaker; this remains a
                    # local escape, not a second global search.
                    target_distance = point_distance((float(x), float(y)), target)
                    candidates.append((distance, -clearance, target_distance, x, y))
            if candidates and radius >= 3:
                # Once a close ring has enough candidates, avoid scanning the
                # entire map around a noisy wall edge.
                if len(candidates) >= 8:
                    break
        candidates.sort()
        checked = 0
        for _distance, _negative_clearance, _target_distance, x, y in candidates[:12]:
            checked += 1
            origin = (float(x), float(y))
            route = self._plan_safe_route(origin, target)
            if route:
                return origin, tuple(route), checked
        return None

    def _validate_position(self, position: PositionSample, role: RoleId) -> None:
        if position.role != role:
            raise ValueError("position role does not match follower role")
        if position.map_identity != self.map_identity:
            raise ValueError("position map identity does not match runtime")

    @staticmethod
    def _clear_failed_plan(follower: _Follower) -> None:
        follower.failed_start = None
        follower.failed_target = None
        follower.retry_after_ms = 0

    def _failed_plan_on_cooldown(
        self, follower: _Follower, start: tuple[float, float],
        target: tuple[float, float], now_ms: int,
    ) -> bool:
        return (
            follower.failed_start is not None
            and follower.failed_target is not None
            and now_ms < follower.retry_after_ms
            and point_distance(start, follower.failed_start) <= self.arrival_radius
            and point_distance(target, follower.failed_target) <= self.arrival_radius
        )

    def _plan_safe_route(self, start: tuple[float, float], end: tuple[float, float]):
        projected_target = self.target_projector.project(end)
        planning_end = projected_target.position
        attempted_factors: list[int] = []
        rejections: list[dict[str, object]] = []
        start_metrics = self._point_metrics(start)
        target_metrics = self._point_metrics(end)
        valid_routes: list[
            tuple[float, float, float, float, float, int, str, list[tuple[int, int]]]
        ] = []
        relaxed_routes: list[
            tuple[float, float, float, float, float, int, str, list[tuple[int, int]]]
        ] = []
        from auto_modules.core.routing.geometry import smooth_path

        for finder in self._pathfinders:
            factor = int(getattr(finder, "downsample_factor", 0))
            attempted_factors.append(factor)
            planned = finder.find_path(self.collision_map, start, planning_end)
            if not planned:
                rejections.append({"factor": factor, "reason": "no_path"})
                continue
            if planned:
                # Downsampled A* may leave a staircase with unnecessary
                # waypoints. Simplify only through the inflated map, so a
                # shortcut can never cut through the actor footprint.
                planned = smooth_path(self.collision_map, planned, corner_safe=True)
            safety_reason = self._route_safety_reason(start, planned, planning_end)
            if safety_reason is None:
                chain = (start, *planned, planning_end)
                route_length = sum(
                    point_distance(first, second)
                    for first, second in pairwise(chain)
                )
                clearance_stats = [
                    line_clearance_stats(
                        self.wall_map,
                        first,
                        second,
                        distance_map=self._clearance_distance,
                        clearance_band=max(
                            self.minimum_clearance,
                            float(getattr(self._pathfinders[0], "clearance_radius", 0.0)) * 0.5,
                        ),
                    )
                    for first, second in pairwise(chain[:-1])
                ]
                minimum_clearance = min(
                    (item["minimum"] for item in clearance_stats),
                    default=float("inf"),
                )
                total_samples = sum(item["samples"] for item in clearance_stats)
                mean_clearance = (
                    sum(item["mean"] * item["samples"] for item in clearance_stats) / total_samples
                    if total_samples else float("inf")
                )
                low_clearance_fraction = (
                    sum(item["low_fraction"] * item["samples"] for item in clearance_stats) / total_samples
                    if total_samples else 0.0
                )
                # Compare a route's geometric length with its wall exposure.
                # A length-only comparison can select a barely walkable
                # corridor even when a slightly longer open route exists.
                # Keep the penalty bounded by the configured clearance band so
                # a genuinely necessary doorway remains usable.
                clearance_band = max(
                    self.minimum_clearance,
                    float(getattr(self._pathfinders[0], "clearance_radius", 0.0)) * 0.5,
                )
                clearance_weight = float(getattr(self._pathfinders[0], "clearance_weight", 0.0))
                exposure = max(0.0, clearance_band - mean_clearance)
                # Penalise the whole narrow section, not only its worst pixel.
                # A short doorway remains usable when it is unavoidable, but
                # a longer open route wins when both are topologically valid.
                safety_cost = exposure + clearance_band * 0.5 * low_clearance_fraction
                route_score = route_length + clearance_weight * safety_cost
                candidate = (
                    route_score,
                    route_length,
                    -minimum_clearance,
                    mean_clearance,
                    low_clearance_fraction,
                    factor,
                    "strict",
                    planned,
                )
                valid_routes.append(candidate)
            else:
                # A route can be rejected by the configured wall-clearance
                # preference even though the actor footprint collision map
                # proves that it is physically traversable.  Keep this as a
                # second-choice candidate only for an explicitly modelled
                # actor.  A runtime with footprint_radius=0 remains strict,
                # which preserves the generic planner contract and prevents
                # this fallback from hiding bad geometry in tests or callers.
                relaxed_reason = None
                if self.footprint_radius > 0.0 and safety_reason.startswith("clearance_segment"):
                    # The collision map already contains the full actor
                    # footprint. Keep only a small rasterisation margin here;
                    # adding a full extra native pixel rejects narrow but
                    # physically walkable passages in the PoE2 map.
                    # The inflated collision map already accounts for the full
                    # actor body. Keep only the body-radius floor here so the
                    # PoE2 experiment does not reject narrow but traversable
                    # passages because of an additional visual margin.
                    relaxed_floor = max(self.footprint_radius, 2.0)
                    relaxed_reason = self._route_safety_reason(
                        start,
                        planned,
                        end,
                        clearance_floor=relaxed_floor,
                    )
                    if relaxed_reason is None:
                        chain = (start, *planned, end)
                        route_length = sum(
                            point_distance(first, second)
                            for first, second in pairwise(chain)
                        )
                        clearance_stats = [
                            line_clearance_stats(
                                self.wall_map,
                                first,
                                second,
                                distance_map=self._clearance_distance,
                                clearance_band=max(
                                    self.minimum_clearance,
                                    float(getattr(self._pathfinders[0], "clearance_radius", 0.0)) * 0.5,
                                ),
                            )
                            for first, second in pairwise(chain[:-1])
                        ]
                        minimum_clearance = min(
                            (item["minimum"] for item in clearance_stats),
                            default=float("inf"),
                        )
                        total_samples = sum(item["samples"] for item in clearance_stats)
                        mean_clearance = (
                            sum(item["mean"] * item["samples"] for item in clearance_stats) / total_samples
                            if total_samples else float("inf")
                        )
                        low_clearance_fraction = (
                            sum(item["low_fraction"] * item["samples"] for item in clearance_stats) / total_samples
                            if total_samples else 0.0
                        )
                        clearance_band = max(
                            self.minimum_clearance,
                            float(getattr(self._pathfinders[0], "clearance_radius", 0.0)) * 0.5,
                        )
                        clearance_weight = float(getattr(self._pathfinders[0], "clearance_weight", 0.0))
                        exposure = max(0.0, clearance_band - mean_clearance)
                        safety_cost = exposure + clearance_band * 0.5 * low_clearance_fraction
                        relaxed_routes.append(
                            (
                                route_length + clearance_weight * safety_cost,
                                route_length,
                                -minimum_clearance,
                                mean_clearance,
                                low_clearance_fraction,
                                factor,
                                "relaxed_clearance",
                                planned,
                            )
                        )
                rejections.append(
                    {
                        "factor": factor,
                        "reason": safety_reason,
                        "relaxed_reason": relaxed_reason,
                    }
                )
        selected_routes = valid_routes or relaxed_routes
        if selected_routes:
            (
                route_score,
                route_length,
                negative_clearance,
                mean_clearance,
                low_clearance_fraction,
                factor,
                clearance_mode,
                planned,
            ) = min(selected_routes)
            self._last_plan_diagnostics = {
                "attempted_factors": tuple(attempted_factors),
                "accepted_factor": factor,
                "candidate_route_count": len(valid_routes),
                "relaxed_candidate_route_count": len(relaxed_routes),
                "selected_clearance_mode": clearance_mode,
                "plan_rejections": tuple(rejections),
                "start_metrics": start_metrics,
                "target_metrics": target_metrics,
                "planning_target": planning_end,
                "target_projection": projected_target.diagnostics,
                "selected_route_score": route_score,
                "selected_route_length": route_length,
                "selected_route_minimum_clearance": -negative_clearance,
                "selected_route_mean_clearance": mean_clearance,
                "selected_route_low_clearance_fraction": low_clearance_fraction,
            }
            return planned
        self._last_plan_diagnostics = {
            "attempted_factors": tuple(attempted_factors),
            "accepted_factor": None,
            "candidate_route_count": 0,
            "relaxed_candidate_route_count": len(relaxed_routes),
            "selected_clearance_mode": None,
            "plan_rejections": tuple(rejections),
            "start_metrics": start_metrics,
            "target_metrics": target_metrics,
            "planning_target": planning_end,
            "target_projection": projected_target.diagnostics,
        }
        return None

    def _route_is_safe(
        self,
        start: tuple[float, float],
        planned: Sequence[tuple[float | int, float | int]],
        end: tuple[float, float],
    ) -> bool:
        """Validate collision and minimum wall clearance in map space.

        A* operates on a downsampled grid.  This final gate runs on the
        original native wall map so a coarse cell cannot hide a wall scrape.
        The exact requested endpoint is allowed to be closer than the floor;
        the approach segment and all intermediate waypoints still must keep
        the configured clearance.
        """
        return self._route_safety_reason(start, planned, end) is None

    def _route_safety_reason(
        self,
        start: tuple[float, float],
        planned: Sequence[tuple[float | int, float | int]],
        end: tuple[float, float],
        *,
        clearance_floor: float | None = None,
    ) -> str | None:
        chain = (start, *planned, end)
        if not all(
            line_is_walkable(self.collision_map, first, second, corner_safe=True)
            for first, second in pairwise(chain)
        ):
            return "collision_segment"
        floor = self.minimum_clearance if clearance_floor is None else max(0.0, float(clearance_floor))
        if floor <= 0.0:
            return None
        start_clearance = float(self._point_metrics(start)["clearance"])
        for index, (first, second) in enumerate(pairwise(chain)):
            clearance = line_min_clearance(
                self.wall_map,
                first,
                second,
                distance_map=self._clearance_distance,
            )
            # The final target can be deliberately near a wall.  Do not make
            # a user click impossible; keep the safe approach segments strict.
            if index == len(chain) - 2:
                continue
            if clearance < floor:
                # A real character can be observed already close to a wall.
                # Permit only the first escape segment, with a hard body
                # clearance floor. This lets a valid character recover from a
                # scrape without allowing later route segments to hug walls.
                escape_floor = max(self.footprint_radius + 1.0, 2.5)
                if index == 0 and start_clearance < floor and clearance >= escape_floor:
                    continue
                return f"clearance_segment_{index}"
        return None

    def _point_metrics(self, point: tuple[float, float]) -> dict[str, object]:
        x = int(round(float(point[0])))
        y = int(round(float(point[1])))
        height, width = self.wall_map.shape
        if x < 0 or y < 0 or x >= width or y >= height:
            return {
                "point": (float(point[0]), float(point[1])),
                "grid": (x, y),
                "in_bounds": False,
                "wall": None,
                "collision": None,
                "clearance": 0.0,
            }
        return {
            "point": (float(point[0]), float(point[1])),
            "grid": (x, y),
            "in_bounds": True,
            "wall": int(self.wall_map[y, x]),
            "collision": int(self.collision_map[y, x]),
            "clearance": float(self._clearance_distance[y, x]),
        }

    def _observation(self, follower, target, *, distance=None, reason="", vector=(0.0, 0.0)) -> FollowObservation:
        position = follower.position.position if follower.position is not None else None
        target_position = target.position if target is not None else None
        route_points = ((position,) if position is not None else ()) + tuple(follower.route)
        route_length = sum(
            point_distance(first, second)
            for first, second in pairwise(route_points)
        )
        collision_segments = sum(
            not line_is_walkable(self.collision_map, first, second, corner_safe=True)
            for first, second in pairwise(route_points)
        )
        escape_origin = follower.last_local_diagnostics.get("escape_origin")
        planning_route_points = (
            (tuple(escape_origin),) if escape_origin is not None else ()
        ) + tuple(follower.route)
        planning_collision_segments = sum(
            not line_is_walkable(self.collision_map, first, second, corner_safe=True)
            for first, second in pairwise(planning_route_points)
        )
        return FollowObservation(
            state=follower.state,
            follower=follower.role,
            target=target.role if target is not None else SimulatedRemoteRole().role,
            position=position,
            target_position=target_position,
            route=follower.route,
            vector=vector,
            distance=distance,
            reason=reason,
            diagnostics={
                "coordinate_space": "reference_native",
                "position": position,
                "target_position": target_position,
                # Keep the raw observed cell separate from the planning
                # diagnostics.  A boundary recovery plan may overwrite
                # ``plan_start_metrics`` with the nearby walkable origin;
                # this field is the evidence for what the actor sample itself
                # mapped to.
                "observed_position_metrics": (
                    self._point_metrics(position) if position is not None else None
                ),
                "route_end": follower.route[-1] if follower.route else None,
                "planned_target": follower.planned_target,
                "route_target_shift": (
                    None
                    if follower.planned_target is None or target_position is None
                    else point_distance(follower.planned_target, target_position)
                ),
                "route_deviation": (
                    None
                    if position is None or not follower.route
                    else distance_to_path(position, follower.route)
                ),
                "route_points": len(follower.route),
                "route_length": route_length,
                "route_chain_points": len(route_points),
                "route_collision_segments": int(collision_segments),
                "route_walkable": len(route_points) >= 2 and collision_segments == 0,
                "planning_route_collision_segments": int(planning_collision_segments),
                "planning_route_walkable": (
                    len(planning_route_points) >= 2
                    and planning_collision_segments == 0
                ),
                "plan_attempted_factors": follower.plan_attempts,
                "plan_accepted_factor": follower.plan_factor,
                "plan_candidate_route_count": self._last_plan_diagnostics.get("candidate_route_count", 0),
                "plan_relaxed_candidate_route_count": self._last_plan_diagnostics.get(
                    "relaxed_candidate_route_count", 0
                ),
                "plan_selected_clearance_mode": self._last_plan_diagnostics.get(
                    "selected_clearance_mode"
                ),
                "plan_rejections": self._last_plan_diagnostics.get("plan_rejections", ()),
                "plan_start_metrics": self._last_plan_diagnostics.get("start_metrics"),
                "plan_target_metrics": self._last_plan_diagnostics.get("target_metrics"),
                "plan_selected_route_score": self._last_plan_diagnostics.get("selected_route_score"),
                "plan_selected_route_length": self._last_plan_diagnostics.get("selected_route_length"),
                "plan_selected_route_minimum_clearance": self._last_plan_diagnostics.get(
                    "selected_route_minimum_clearance"
                ),
                "plan_selected_route_mean_clearance": self._last_plan_diagnostics.get(
                    "selected_route_mean_clearance"
                ),
                "plan_selected_route_low_clearance_fraction": self._last_plan_diagnostics.get(
                    "selected_route_low_clearance_fraction"
                ),
                "route_safety_margin": getattr(self._pathfinders[0], "safety_margin", 0),
                "route_clearance_radius": getattr(self._pathfinders[0], "clearance_radius", 0.0),
                "route_clearance_weight": getattr(self._pathfinders[0], "clearance_weight", 0.0),
                "route_dead_end_weight": getattr(self._pathfinders[0], "dead_end_weight", 0.0),
                "route_minimum_clearance": self.minimum_clearance,
                "route_footprint_radius": self.footprint_radius,
                "route_collision_inflation": self.inflate_collision,
                "no_progress_ticks": follower.no_progress_ticks,
                "recovery_attempts": follower.recovery_attempts,
                "recovery_candidates_checked": follower.recovery_candidates_checked,
                "recovery_selected_index": follower.recovery_selected_index,
                "recovery_target": follower.recovery_target,
                "observed_velocity": follower.observed_velocity,
                "observed_speed": follower.observed_speed,
                "observed_displacement": follower.observed_displacement,
                "command_observed_alignment": follower.command_observed_alignment,
                "command_observed_angle_degrees": follower.command_observed_angle_degrees,
                "direction_mismatch_ticks": follower.direction_mismatch_ticks,
                "command_duration_ms": follower.command_duration_ms,
                "last_observation_at_ms": follower.last_observation_at_ms,
                "command_vector": follower.last_command_vector,
                "contact_evidence": None if follower.last_contact_evidence is None else {
                    "no_progress": follower.last_contact_evidence.no_progress,
                    "consecutive_no_progress": follower.last_contact_evidence.consecutive_no_progress,
                    "recovery_required": follower.last_contact_evidence.recovery_required,
                    "alignment": follower.last_contact_evidence.alignment,
                    "reason": follower.last_contact_evidence.reason,
                    "state": follower.last_contact_evidence.state.value,
                    "escape_available": follower.last_contact_evidence.escape_available,
                },
                "local_obstacle_ahead": follower.local_obstacle_ahead,
                "local_raw_obstacle_ahead": follower.local_raw_obstacle_ahead,
                "local_escape_available": follower.local_escape_available,
                "local_obstacle_distance": follower.local_obstacle_distance,
                "local_free_left": follower.local_free_left,
                "local_free_right": follower.local_free_right,
                "local_contact_captured_at_ms": follower.local_contact_captured_at_ms,
                "relocalization_requested": reason == "contact_relocalization_required",
                "local_controller": dict(follower.last_local_diagnostics),
                "motion_loop_policy": follower.last_local_diagnostics.get("policy"),
                "motion_loop_state": follower.last_local_diagnostics.get("motion_loop_state"),
                "motion_loop_complexity": follower.last_local_diagnostics.get("complexity"),
                "motion_loop_command_id": follower.last_local_diagnostics.get("motion_loop_command_id"),
                "calibration_confidence": follower.last_local_diagnostics.get("calibration_confidence"),
                "calibration_samples": follower.last_local_diagnostics.get("calibration_samples"),
                "calibration_speed_gain": follower.last_local_diagnostics.get("calibration_speed_gain"),
            },
        )


__all__ = ["SimulatedFollowRuntime", "SimulatedRemoteRole"]
