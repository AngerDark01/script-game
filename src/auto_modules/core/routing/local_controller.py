"""Short-horizon local steering for a planned map-space route."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .geometry import distance_to_path, line_is_walkable, line_min_clearance, point_distance, project_point_onto_path


@dataclass(frozen=True)
class LocalMotionDecision:
    """One bounded local steering decision."""

    vector: tuple[float, float]
    score: float
    angle_offset_degrees: float
    predicted_position: tuple[float, float]
    predicted_clearance: float
    candidate_count: int
    rejected_collision_count: int
    diagnostics: dict


def _rotate(vector: tuple[float, float], degrees: float) -> tuple[float, float]:
    radians = math.radians(float(degrees))
    cosine, sine = math.cos(radians), math.sin(radians)
    return (
        vector[0] * cosine - vector[1] * sine,
        vector[0] * sine + vector[1] * cosine,
    )


class LocalMotionController:
    """Choose a short collision-safe steering vector around a global route.

    The global planner supplies a safe corridor, but a gamepad does not move
    an actor to a point instantaneously. This controller evaluates a small set
    of short steering trajectories around the route direction. It consumes
    observed velocity so an already-moving actor is not driven into a wall.
    """

    def __init__(
        self,
        *,
        lookahead: float = 18.0,
        prediction_horizon: float = 0.22,
        expected_speed: float = 80.0,
        arrival_radius: float = 3.0,
        candidate_angles: Sequence[float] = (0.0, -15.0, 15.0, -30.0, 30.0, -45.0, 45.0, -75.0, 75.0, 90.0, -90.0),
        clearance_weight: float = 1.2,
        progress_weight: float = 4.0,
        deviation_weight: float = 0.35,
        turn_weight: float = 0.25,
        oscillation_weight: float = 0.65,
        alignment_weight: float = 0.8,
    ) -> None:
        if not all(math.isfinite(float(value)) and value > 0 for value in (lookahead, prediction_horizon, expected_speed, arrival_radius)):
            raise ValueError("local controller distances and speed must be positive")
        if not candidate_angles:
            raise ValueError("candidate_angles must not be empty")
        if not all(math.isfinite(float(value)) for value in candidate_angles):
            raise ValueError("candidate angles must be finite")
        for value in (clearance_weight, progress_weight, deviation_weight, turn_weight, oscillation_weight, alignment_weight):
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError("local controller weights must be finite and non-negative")
        self.lookahead = float(lookahead)
        self.prediction_horizon = float(prediction_horizon)
        self.expected_speed = float(expected_speed)
        self.arrival_radius = float(arrival_radius)
        self.candidate_angles = tuple(float(value) for value in candidate_angles)
        self.clearance_weight = float(clearance_weight)
        self.progress_weight = float(progress_weight)
        self.deviation_weight = float(deviation_weight)
        self.turn_weight = float(turn_weight)
        self.oscillation_weight = float(oscillation_weight)
        self.alignment_weight = float(alignment_weight)

    def command(
        self,
        position: tuple[float, float],
        target: tuple[float, float],
        path: Sequence[tuple[float, float]],
        *,
        desired_vector: tuple[float, float],
        walls,
        distance_map=None,
        observed_velocity: tuple[float, float] = (0.0, 0.0),
        previous_command: tuple[float, float] = (0.0, 0.0),
        previous_angle_offset: float | None = None,
        oscillation_count: int = 0,
        arrival_radius: float | None = None,
        confidence: float = 1.0,
    ) -> LocalMotionDecision:
        if (
            not path or not math.isfinite(float(confidence)) or confidence < 0.5
            or not all(math.isfinite(float(value)) for point in (position, target, desired_vector, observed_velocity, previous_command, *path) for value in point)
        ):
            return self._empty("invalid_route_or_confidence")
        desired_norm = math.hypot(*desired_vector)
        target_delta = (float(target[0]) - float(position[0]), float(target[1]) - float(position[1]))
        target_distance = math.hypot(*target_delta)
        if target_distance <= 1e-6 or desired_norm <= 1e-6:
            return self._empty("no_desired_motion")
        base = (float(desired_vector[0]) / desired_norm, float(desired_vector[1]) / desired_norm)
        observed_speed = math.hypot(*observed_velocity)
        speed_ratio = observed_speed / self.expected_speed
        goal_radius = self.arrival_radius if arrival_radius is None else max(float(arrival_radius), 0.1)
        # Once the actor is close to the goal, a long lookahead makes the
        # stick overshoot the goal and the clearance term can repeatedly pick
        # alternating side candidates.  Switch to a short, goal-directed
        # approach band.  This is the same bounded-horizon idea used by
        # regulated pure pursuit, expressed in map-space units.
        approach_band = max(goal_radius * 3.0, self.lookahead)
        near_goal = target_distance <= approach_band
        direct_safe = line_is_walkable(walls, position, target, corner_safe=True)
        if near_goal and direct_safe:
            target_unit = (target_delta[0] / target_distance, target_delta[1] / target_distance)
            base = target_unit
        magnitude = min(1.0, max(0.25, desired_norm))
        if near_goal:
            # Reduce the stick magnitude with distance.  The lower bound keeps
            # a real controller responsive while the endpoint cap below
            # prevents a single tick from planning past the goal.
            magnitude = min(magnitude, max(0.20, target_distance / max(approach_band, 1.0)))
        if speed_ratio > 1.0:
            magnitude *= max(0.35, 1.0 - min(0.55, (speed_ratio - 1.0) * 0.35))
        if near_goal:
            # Limit even a faster-than-configured actor to a short approach
            # step. Do not impose an artificial simulation-only target snap.
            magnitude = min(magnitude, target_distance / (max(self.expected_speed, observed_speed) * self.prediction_horizon))
        horizon_distance = (
            min(self.lookahead, target_distance)
            if near_goal
            else max(self.lookahead, min(target_distance, self.expected_speed * self.prediction_horizon))
        )
        velocity_prediction = (
            float(position[0]) + float(observed_velocity[0]) * self.prediction_horizon,
            float(position[1]) + float(observed_velocity[1]) * self.prediction_horizon,
        )
        previous_norm = math.hypot(*previous_command)
        previous_unit = (
            (previous_command[0] / previous_norm, previous_command[1] / previous_norm)
            if previous_norm > 1e-6 else None
        )
        candidates: list[tuple[float, float, float, float, tuple[float, float], float]] = []
        rejected_collision = 0
        projection = project_point_onto_path(position, path)
        for offset in self.candidate_angles:
            unit = _rotate(base, offset)
            endpoint = (
                float(position[0]) + unit[0] * horizon_distance * magnitude,
                float(position[1]) + unit[1] * horizon_distance * magnitude,
            )
            if not line_is_walkable(walls, position, endpoint, corner_safe=True):
                rejected_collision += 1
                continue
            if observed_speed > 1e-6 and not line_is_walkable(walls, position, velocity_prediction, corner_safe=True):
                dot = unit[0] * observed_velocity[0] + unit[1] * observed_velocity[1]
                if dot > 0.0:
                    rejected_collision += 1
                    continue
            clearance = line_min_clearance(walls, position, endpoint, distance_map=distance_map)
            if near_goal and direct_safe:
                progress = target_distance - point_distance(endpoint, target)
            else:
                projected_end = project_point_onto_path(endpoint, path)
                progress = projected_end["distance"] - projection["distance"]
            deviation = distance_to_path(endpoint, path)
            turn_penalty = 0.0 if previous_unit is None else (1.0 - (unit[0] * previous_unit[0] + unit[1] * previous_unit[1]))
            overshoot = max(0.0, point_distance(endpoint, target) - target_distance)
            effective_progress_weight = self.progress_weight * (1.75 if near_goal else 1.0)
            effective_clearance_weight = self.clearance_weight * (0.35 if near_goal else 1.0)
            sign_flip = (
                near_goal
                and previous_angle_offset is not None
                and abs(float(offset)) > 1e-6
                and abs(float(previous_angle_offset)) > 1e-6
                and float(offset) * float(previous_angle_offset) < 0.0
            )
            score = (
                effective_progress_weight * progress / max(horizon_distance, 1.0)
                + effective_clearance_weight * min(clearance / max(self.lookahead, 1.0), 1.0)
                - self.deviation_weight * deviation / max(horizon_distance, 1.0)
                - self.turn_weight * turn_penalty
                - self.alignment_weight * min(1.0, abs(float(offset)) / 90.0)
                - (self.oscillation_weight * min(1.0, float(oscillation_count + 1) / 3.0) if sign_flip else 0.0)
                - (2.0 * overshoot / max(horizon_distance, 1.0))
                + (0.6 if near_goal and direct_safe and abs(float(offset)) < 1e-6 else 0.0)
            )
            candidates.append((score, offset, clearance, magnitude, endpoint, progress))
        if not candidates:
            return self._empty(
                "all_local_candidates_blocked",
                candidate_count=len(self.candidate_angles),
                rejected_collision_count=rejected_collision,
            )
        best = max(candidates, key=lambda item: (item[0], item[2], item[5], -abs(item[1])))
        score, offset, clearance, selected_magnitude, endpoint, progress = best
        selected_unit = _rotate(base, offset)
        vector = (selected_unit[0] * selected_magnitude, selected_unit[1] * selected_magnitude)
        return LocalMotionDecision(
            vector=vector,
            score=float(score),
            angle_offset_degrees=float(offset),
            predicted_position=(float(endpoint[0]), float(endpoint[1])),
            predicted_clearance=float(clearance),
            candidate_count=len(self.candidate_angles),
            rejected_collision_count=rejected_collision,
            diagnostics={
                "reason": "selected_local_candidate",
                "observed_speed": float(observed_speed),
                "speed_ratio": float(speed_ratio),
                "candidate_count": len(self.candidate_angles),
                "valid_candidate_count": len(candidates),
                "rejected_collision_count": rejected_collision,
                "angle_offset_degrees": float(offset),
                "predicted_clearance": float(clearance),
                "predicted_progress": float(progress),
                "target_distance": float(target_distance),
                "near_goal": bool(near_goal),
                "approach_band": float(approach_band),
                "direct_safe": bool(direct_safe),
                "oscillation_count": int(oscillation_count),
                "score": float(score),
            },
        )

    def _empty(self, reason: str, *, candidate_count: int = 0, rejected_collision_count: int = 0) -> LocalMotionDecision:
        return LocalMotionDecision(
            vector=(0.0, 0.0),
            score=float("-inf"),
            angle_offset_degrees=0.0,
            predicted_position=(0.0, 0.0),
            predicted_clearance=0.0,
            candidate_count=int(candidate_count),
            rejected_collision_count=int(rejected_collision_count),
            diagnostics={
                "reason": reason,
                "candidate_count": int(candidate_count),
                "valid_candidate_count": 0,
                "rejected_collision_count": int(rejected_collision_count),
            },
        )


__all__ = ["LocalMotionController", "LocalMotionDecision"]
