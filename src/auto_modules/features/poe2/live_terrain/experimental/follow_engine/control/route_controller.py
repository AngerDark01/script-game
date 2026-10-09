"""Bounded route-controller adapters for the process-safe follow runtime.

The straight-line controller remains the default.  ``MapAwareRouteController``
is an explicit opt-in adapter around the shared A* pathfinder and target
projection primitives; it never turns a planning miss into a stop command.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import cv2

from auto_modules.core.routing.pathfinder import PathFinder
from ...multiplayer_follow.target_projection import WalkableTargetProjector
from auto_modules.core.routing.vector_tracker import VectorPathTracker
from auto_modules.core.routing.local_controller import LocalMotionController
from ...multiplayer_follow.models import ControlMode, MapIdentity, PositionSample, RoleId
from ...multiplayer_follow.runtime import SimulatedFollowRuntime


@dataclass(frozen=True, slots=True)
class RouteDecision:
    vector: tuple[float, float]
    duration_ms: int
    distance: float
    arrived: bool
    route: tuple[tuple[float, float], ...] = ()
    reason: str = ""


class LegacyDynamicFollowRouteController:
    """Thin adapter around the validated legacy routing/steering components.

    This adapter owns no movement policy. It feeds the fused native
    position/target into the complete legacy ``SimulatedFollowRuntime``. The
    runtime remains the owner of route, pulse, arrival, progress and recovery
    state; this class only translates process-safe coordinates to the legacy
    model and back to ``RouteDecision``.
    """

    def __init__(self, wall_map: Any, *, arrival_radius: float = 12.0,
                 resume_radius: float = 20.0, speed_units_per_second: float = 80.0,
                 downsample_factor: int = 8, local_lookahead: float = 24.0,
                 prediction_horizon: float = 0.25) -> None:
        grid = np.asarray(wall_map)
        if grid.ndim != 2 or min(grid.shape) < 2:
            raise ValueError("wall_map must be a two-dimensional grid")
        self.wall_map = np.where(grid > 0, 255, 0).astype("uint8")
        self.arrival_radius = float(arrival_radius)
        self.resume_radius = float(resume_radius)
        self.map_identity = MapIdentity("follow-engine", "legacy-motion-v1")
        self.role = RoleId("follow-engine", "follower")
        self.target_role = RoleId("follow-engine", "leader")
        self._runtime = SimulatedFollowRuntime(
            wall_map=self.wall_map,
            map_identity=self.map_identity,
            arrival_radius=self.arrival_radius,
            resume_radius=self.resume_radius,
            speed_units_per_second=float(speed_units_per_second),
            downsample_factor=int(downsample_factor),
            local_lookahead=float(local_lookahead),
            prediction_horizon=float(prediction_horizon),
            continuous_follow=True,
        )
        self._position: tuple[float, float] | None = None
        self._target: tuple[float, float] | None = None
        self._position_at_ms = 0
        self._target_at_ms = 0
        # Kept as compatibility metadata for control diagnostics. The legacy
        # runtime decides the real vector magnitude and duration per tick.
        self.magnitude = 1.0
        self.duration_ms = 0

    def sync_position(self, position: tuple[float, float], *, now_ms: int = 0,
                      source: str = "visual_fused", confidence: float = 1.0) -> None:
        point = (float(position[0]), float(position[1]))
        sample = PositionSample(self.role, self.map_identity, point, max(0, int(now_ms)),
                                max(0.0, min(1.0, float(confidence))), str(source))
        if self._position is None:
            self._runtime.add_follower(self.role, sample, mode=ControlMode.PROGRAM)
        else:
            self._runtime.update_follower_position(sample)
        self._position = point
        self._position_at_ms = int(now_ms)

    def sync_target(self, target: tuple[float, float], *, now_ms: int = 0,
                    confidence: float = 1.0) -> None:
        point = (float(target[0]), float(target[1]))
        target_at = max(self._target_at_ms + 1, int(now_ms))
        sample = PositionSample(self.target_role, self.map_identity, point, max(0, target_at),
                                max(0.0, min(1.0, float(confidence))), "simulated")
        self._runtime.set_target_sample(sample)
        self._target = point
        self._target_at_ms = target_at

    def plan(self, position: tuple[float, float], target: tuple[float, float],
             *, now_ms: int | None = None, position_source: str = "visual_fused") -> RouteDecision:
        now = max(self._position_at_ms, self._target_at_ms, 0) if now_ms is None else int(now_ms)
        self.sync_position(position, now_ms=now, source=position_source)
        self.sync_target(target, now_ms=now)
        observation = self._runtime.tick(now_ms=now)[self.role.key]
        distance = float(observation.distance if observation.distance is not None else math.dist(position, target))
        return RouteDecision(tuple(observation.vector), int(observation.diagnostics.get("command_duration_ms", 0)),
                             distance, observation.state.value in {"arrived", "waiting_position"},
                             tuple(observation.route), observation.reason or "legacy_runtime")

    def corrective_vector(self, position, target, *, fallback=(0.0, 0.0)):
        return self.plan(position, target).vector


class RouteController(Protocol):
    magnitude: float
    duration_ms: int

    def plan(self, position: tuple[float, float], target: tuple[float, float]) -> RouteDecision: ...

    def corrective_vector(
        self,
        position: tuple[float, float],
        target: tuple[float, float],
        *,
        fallback: tuple[float, float] = (0.0, 0.0),
    ) -> tuple[float, float]: ...


class StraightLineRouteController:
    """Return a bounded direction; map-aware steering is injected later."""

    def __init__(self, *, arrival_radius: float = 12.0, magnitude: float = 0.65, duration_ms: int = 80) -> None:
        if arrival_radius <= 0.0 or not 0.0 < magnitude <= 1.0 or duration_ms <= 0:
            raise ValueError("route controller parameters are invalid")
        self.arrival_radius = float(arrival_radius)
        self.magnitude = float(magnitude)
        self.duration_ms = int(duration_ms)

    def plan(self, position: tuple[float, float], target: tuple[float, float]) -> RouteDecision:
        dx = float(target[0]) - float(position[0])
        dy = float(target[1]) - float(position[1])
        distance = math.hypot(dx, dy)
        if not math.isfinite(distance):
            raise ValueError("route positions must be finite")
        if distance <= self.arrival_radius:
            return RouteDecision((0.0, 0.0), 0, distance, True, (target,), "within_arrival_radius")
        vector = (dx / distance * self.magnitude, dy / distance * self.magnitude)
        return RouteDecision(vector, self.duration_ms, distance, False, (target,), "direct_route")

    def corrective_vector(
        self,
        position: tuple[float, float],
        target: tuple[float, float],
        *,
        fallback: tuple[float, float] = (0.0, 0.0),
    ) -> tuple[float, float]:
        """Return a bounded, tapered pulse while predicted arrival is unconfirmed."""

        dx = float(target[0]) - float(position[0])
        dy = float(target[1]) - float(position[1])
        distance = math.hypot(dx, dy)
        if distance <= 1e-6:
            fallback_distance = math.hypot(float(fallback[0]), float(fallback[1]))
            if fallback_distance <= 1e-6:
                return (0.0, 0.0)
            return (
                float(fallback[0]) / fallback_distance * self.magnitude * 0.25,
                float(fallback[1]) / fallback_distance * self.magnitude * 0.25,
            )
        scale = min(self.magnitude, max(self.magnitude * 0.25, self.magnitude * distance / self.arrival_radius))
        return (dx / distance * scale, dy / distance * scale)


class MapAwareRouteController:
    """Use the shared map planner while preserving continuous movement.

    ``wall_map`` is an immutable, process-safe map snapshot in map/native
    coordinates.  A route is planned from the current fused position to a
    locally projected walkable target.  When a map snapshot is stale or A*
    cannot produce a route, the controller falls back to a bounded direct
    pulse so a transient planning error cannot stop a dynamic follow session.
    """

    supports_bounded_replan = True

    def __init__(
        self,
        wall_map: Any,
        *,
        pathfinder: PathFinder | None = None,
        target_projector: WalkableTargetProjector | None = None,
        arrival_radius: float = 12.0,
        magnitude: float = 0.65,
        duration_ms: int = 80,
        lookahead_points: int = 1,
        projection_radius: int = 8,
        target_refresh_distance: float = 16.0,
        route_replan_distance: float = 12.0,
        route_deviation_threshold: float = 12.0,
        map_instance: str | None = None,
    ) -> None:
        grid = np.asarray(wall_map)
        if grid.ndim != 2 or min(grid.shape) < 2:
            raise ValueError("wall_map must be a two-dimensional grid")
        if arrival_radius <= 0.0 or not 0.0 < magnitude <= 1.0 or duration_ms <= 0:
            raise ValueError("route controller parameters are invalid")
        if int(lookahead_points) < 1 or int(projection_radius) < 1:
            raise ValueError("route lookahead/projection parameters are invalid")
        if (
            not math.isfinite(float(target_refresh_distance))
            or not math.isfinite(float(route_replan_distance))
            or not math.isfinite(float(route_deviation_threshold))
            or min(float(target_refresh_distance), float(route_replan_distance), float(route_deviation_threshold)) <= 0.0
        ):
            raise ValueError("route cache thresholds must be finite and positive")
        self.wall_map = np.array(grid, copy=True, order="C")
        self.wall_map.setflags(write=False)
        self.pathfinder = pathfinder or PathFinder(
            downsample_factor=4,
            safety_margin=0,
            wall_shrink_iterations=0,
            start_clear_radius=0,
            walkable_snap_radius=max(1, int(projection_radius)),
            clearance_radius=0.0,
            clearance_weight=0.0,
            dead_end_weight=0.0,
        )
        self.target_projector = target_projector or WalkableTargetProjector(
            self.wall_map, radius=int(projection_radius)
        )
        self.arrival_radius = float(arrival_radius)
        self.magnitude = float(magnitude)
        self.duration_ms = int(duration_ms)
        self.lookahead_points = int(lookahead_points)
        self.map_instance = None if map_instance is None else str(map_instance).strip()
        if self.map_instance == "":
            raise ValueError("map_instance must be non-empty when provided")
        self.target_refresh_distance = float(target_refresh_distance)
        self.route_replan_distance = float(route_replan_distance)
        self.route_deviation_threshold = float(route_deviation_threshold)
        self._cached_target: tuple[float, float] | None = None
        self._cached_position: tuple[float, float] | None = None
        self._cached_route: tuple[tuple[float, float], ...] = ()
        self.plan_calls = 0
        self.replan_count = 0

    def plan(
        self,
        position: tuple[float, float],
        target: tuple[float, float],
        *,
        allow_replan: bool = True,
    ) -> RouteDecision:
        self.plan_calls += 1
        dx = float(target[0]) - float(position[0])
        dy = float(target[1]) - float(position[1])
        distance = math.hypot(dx, dy)
        if not math.isfinite(distance):
            raise ValueError("route positions must be finite")
        if distance <= self.arrival_radius:
            self._cached_route = ()
            return RouteDecision((0.0, 0.0), 0, distance, True, (target,), "within_arrival_radius")

        projected = self.target_projector.project((float(target[0]), float(target[1])))
        route = self._cached_route
        if self._needs_replan(position, projected.position) and allow_replan:
            self.replan_count += 1
            planned = self.pathfinder.find_path(self.wall_map, position, projected.position)
            route = tuple((float(point[0]), float(point[1])) for point in (planned or ()))
            # A one-point cache records a bounded fallback decision without
            # pretending that a safe A* corridor exists.  It also prevents a
            # no-route map from consuming the full control budget every tick.
            self._cached_route = route or (projected.position,)
            self._cached_target = projected.position
            self._cached_position = (float(position[0]), float(position[1]))
        if route and len(route) >= 2:
            points = tuple((float(point[0]), float(point[1])) for point in route)
            index = self._lookahead_index(points, position)
            waypoint = points[index]
            vector, _ = _bounded_direction(position, waypoint, self.magnitude)
            if vector != (0.0, 0.0):
                reason = "map_route_projected" if projected.projected else "map_route"
                return RouteDecision(vector, self.duration_ms, distance, False, points, reason)

        # Planning is advisory.  Keep the session moving and let the next
        # frame, local recovery, or low-frequency memory anchor correct it.
        vector, _ = _bounded_direction(position, target, self.magnitude)
        return RouteDecision(vector, self.duration_ms, distance, False, (target,), "map_route_fallback")

    def _needs_replan(
        self,
        position: tuple[float, float],
        projected_target: tuple[float, float],
    ) -> bool:
        if not self._cached_route or self._cached_target is None or self._cached_position is None:
            return True
        target_delta = math.hypot(
            float(projected_target[0]) - self._cached_target[0],
            float(projected_target[1]) - self._cached_target[1],
        )
        if target_delta >= self.target_refresh_distance:
            return True
        position_delta = math.hypot(
            float(position[0]) - self._cached_position[0],
            float(position[1]) - self._cached_position[1],
        )
        if position_delta >= self.route_replan_distance:
            return True
        nearest_distance = min(
            math.hypot(float(point[0]) - float(position[0]), float(point[1]) - float(position[1]))
            for point in self._cached_route
        )
        return nearest_distance >= self.route_deviation_threshold

    def _lookahead_index(self, route: tuple[tuple[float, float], ...], position: tuple[float, float]) -> int:
        nearest = min(
            range(len(route)),
            key=lambda index: math.hypot(
                float(route[index][0]) - float(position[0]),
                float(route[index][1]) - float(position[1]),
            ),
        )
        return min(nearest + self.lookahead_points, len(route) - 1)

    def corrective_vector(
        self,
        position: tuple[float, float],
        target: tuple[float, float],
        *,
        fallback: tuple[float, float] = (0.0, 0.0),
    ) -> tuple[float, float]:
        dx = float(target[0]) - float(position[0])
        dy = float(target[1]) - float(position[1])
        distance = math.hypot(dx, dy)
        if distance <= 1e-6:
            return _bounded_fallback(fallback, self.magnitude * 0.25)
        scale = min(self.magnitude, max(self.magnitude * 0.25, self.magnitude * distance / self.arrival_radius))
        return (dx / distance * scale, dy / distance * scale)


def _bounded_direction(
    position: tuple[float, float],
    target: tuple[float, float],
    magnitude: float,
) -> tuple[tuple[float, float], float]:
    dx = float(target[0]) - float(position[0])
    dy = float(target[1]) - float(position[1])
    distance = math.hypot(dx, dy)
    if distance <= 1e-6:
        return (0.0, 0.0), distance
    return (dx / distance * magnitude, dy / distance * magnitude), distance


def _bounded_fallback(vector: tuple[float, float], magnitude: float) -> tuple[float, float]:
    distance = math.hypot(float(vector[0]), float(vector[1]))
    if distance <= 1e-6:
        return (0.0, 0.0)
    return (float(vector[0]) / distance * magnitude, float(vector[1]) / distance * magnitude)


__all__ = [
    "MapAwareRouteController",
    "RouteController",
    "RouteDecision",
    "StraightLineRouteController",
]
