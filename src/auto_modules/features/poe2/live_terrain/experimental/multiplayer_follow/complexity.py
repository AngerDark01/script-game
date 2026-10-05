"""Local geometry classification for the PoE2 experimental motion loop."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

import numpy as np

from .motion_snapshot import MotionSnapshot


class ComplexityState(StrEnum):
    OPEN = "open"
    TRANSITION = "transition"
    CONSTRAINED = "constrained"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ComplexityFeatures:
    c_min: float
    c_p10: float
    c_mean: float
    clearance_quality: float
    visibility_quality: float
    free_ratio: float
    unknown_ratio: float
    curvature: float
    turn_density: float
    localization_quality: float
    motion_residual: float
    peer_risk: float


@dataclass(frozen=True, slots=True)
class ComplexityDecision:
    state: ComplexityState
    score: float
    features: ComplexityFeatures
    diagnostics: dict[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", ComplexityState(self.state))
        object.__setattr__(self, "score", float(np.clip(float(self.score), 0.0, 1.0)))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return float(np.clip(float(value), low, high))


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(float(second[0]) - first[0], float(second[1]) - first[1])


class LocalComplexityClassifier:
    """Classify only the local route region and retain hysteresis state."""

    def __init__(
        self,
        *,
        clearance_reference: float = 18.0,
        hard_clearance: float = 2.0,
        visibility_reference: float = 48.0,
        max_ray_length: float = 96.0,
        local_radius: int = 32,
        sample_step: float = 4.0,
        unknown_ratio_threshold: float = 0.35,
        min_confidence: float = 0.5,
        max_frame_age_ms: int = 500,
        open_threshold: float = 0.35,
        constrained_threshold: float = 0.60,
        enter_constrained_frames: int = 2,
        leave_constrained_frames: int = 4,
        peer_min_distance: float = 16.0,
        ray_angles: tuple[float, ...] = (-60.0, -45.0, -30.0, -15.0, 0.0, 15.0, 30.0, 45.0, 60.0),
    ) -> None:
        if clearance_reference <= 0 or hard_clearance < 0 or visibility_reference <= 0 or max_ray_length <= 0:
            raise ValueError("clearance and visibility references must be positive")
        if local_radius < 1 or sample_step <= 0 or not 0.0 <= unknown_ratio_threshold <= 1.0:
            raise ValueError("invalid local geometry thresholds")
        if not 0.0 <= min_confidence <= 1.0 or max_frame_age_ms <= 0:
            raise ValueError("invalid localization thresholds")
        if not 0.0 <= open_threshold < constrained_threshold <= 1.0:
            raise ValueError("complexity thresholds must be ordered")
        if enter_constrained_frames < 1 or leave_constrained_frames < 1 or peer_min_distance < 0:
            raise ValueError("invalid hysteresis or peer thresholds")
        self.clearance_reference = float(clearance_reference)
        self.hard_clearance = float(hard_clearance)
        self.visibility_reference = float(visibility_reference)
        self.max_ray_length = float(max_ray_length)
        self.local_radius = int(local_radius)
        self.sample_step = float(sample_step)
        self.unknown_ratio_threshold = float(unknown_ratio_threshold)
        self.min_confidence = float(min_confidence)
        self.max_frame_age_ms = int(max_frame_age_ms)
        self.open_threshold = float(open_threshold)
        self.constrained_threshold = float(constrained_threshold)
        self.enter_constrained_frames = int(enter_constrained_frames)
        self.leave_constrained_frames = int(leave_constrained_frames)
        self.peer_min_distance = float(peer_min_distance)
        self.ray_angles = tuple(float(angle) for angle in ray_angles)
        self._state = ComplexityState.OPEN
        self._constrained_count = 0
        self._safe_count = 0

    @property
    def state(self) -> ComplexityState:
        return self._state

    def clone(self) -> "LocalComplexityClassifier":
        """Create a fresh classifier with the same thresholds and no history.

        Hysteresis is temporal state.  A controller that tracks two roles must
        not let one role's corridor frames make the other role enter or leave
        ``CONSTRAINED``.  Keeping the construction parameters here gives the
        runtime an explicit, game-neutral way to create one state machine per
        role without sharing mutable configuration.
        """
        return LocalComplexityClassifier(
            clearance_reference=self.clearance_reference,
            hard_clearance=self.hard_clearance,
            visibility_reference=self.visibility_reference,
            max_ray_length=self.max_ray_length,
            local_radius=self.local_radius,
            sample_step=self.sample_step,
            unknown_ratio_threshold=self.unknown_ratio_threshold,
            min_confidence=self.min_confidence,
            max_frame_age_ms=self.max_frame_age_ms,
            open_threshold=self.open_threshold,
            constrained_threshold=self.constrained_threshold,
            enter_constrained_frames=self.enter_constrained_frames,
            leave_constrained_frames=self.leave_constrained_frames,
            peer_min_distance=self.peer_min_distance,
            ray_angles=self.ray_angles,
        )

    def classify(self, snapshot: MotionSnapshot) -> ComplexityDecision:
        if not isinstance(snapshot, MotionSnapshot):
            raise TypeError("snapshot must be MotionSnapshot")
        features = self._features(snapshot)
        hard_unknown = (
            snapshot.observation.frame_age_ms > self.max_frame_age_ms
            or snapshot.observation.confidence < self.min_confidence
            or features.unknown_ratio > self.unknown_ratio_threshold
            or not snapshot.route
        )
        hard_clearance = features.c_min < self.hard_clearance
        if hard_unknown:
            self._state = ComplexityState.UNKNOWN
            self._constrained_count = 0
            self._safe_count = 0
        elif hard_clearance:
            self._state = ComplexityState.CONSTRAINED
            self._constrained_count = self.enter_constrained_frames
            self._safe_count = 0
        else:
            self._state = self._transition(features)
        score = self._score(features)
        diagnostics = {
            "c_min": features.c_min,
            "c_p10": features.c_p10,
            "c_mean": features.c_mean,
            "clearance_quality": features.clearance_quality,
            "visibility_quality": features.visibility_quality,
            "free_ratio": features.free_ratio,
            "unknown_ratio": features.unknown_ratio,
            "curvature": features.curvature,
            "turn_density": features.turn_density,
            "localization_quality": features.localization_quality,
            "motion_residual": features.motion_residual,
            "peer_risk": features.peer_risk,
            "hard_clearance": hard_clearance,
            "hard_unknown": hard_unknown,
            "score": score,
            "state": self._state.value,
        }
        return ComplexityDecision(self._state, score, features, diagnostics)

    def _features(self, snapshot: MotionSnapshot) -> ComplexityFeatures:
        route = snapshot.route
        distances = self._route_distances(snapshot)
        c_min = float(np.min(distances)) if distances else 0.0
        c_p10 = float(np.percentile(distances, 10)) if distances else 0.0
        c_mean = float(np.mean(distances)) if distances else 0.0
        clearance_quality = _clip(c_p10 / self.clearance_reference)
        position = snapshot.observation.position
        visibility = self._visibility(snapshot, position, route)
        visibility_quality = _clip(visibility / self.visibility_reference)
        free_ratio, unknown_ratio = self._local_occupancy(snapshot, position)
        curvature, turn_density = self._route_shape(route)
        localization_quality = self._localization_quality(snapshot)
        alignment = snapshot.observation.command_alignment
        motion_residual = 0.0 if alignment is None else _clip((1.0 - alignment) / 2.0)
        peer_risk = 0.0
        if snapshot.peer_position is not None:
            peer_distance = _distance(position, snapshot.peer_position)
            peer_risk = _clip((self.peer_min_distance - peer_distance) / max(self.peer_min_distance, 1.0))
        return ComplexityFeatures(
            c_min, c_p10, c_mean, clearance_quality, visibility_quality,
            free_ratio, unknown_ratio, curvature, turn_density,
            localization_quality, motion_residual, peer_risk,
        )

    def _route_distances(self, snapshot: MotionSnapshot) -> list[float]:
        route = snapshot.route
        distances: list[float] = []
        for point in self._sample_polyline(route):
            distances.append(self._sample_field(snapshot.distance_field, point))
        return distances

    def _sample_polyline(self, route: tuple[tuple[float, float], ...]) -> list[tuple[float, float]]:
        if len(route) < 2:
            return list(route)
        points: list[tuple[float, float]] = [route[0]]
        for first, second in zip(route, route[1:]):
            length = _distance(first, second)
            count = max(1, int(math.ceil(length / self.sample_step)))
            for index in range(1, count + 1):
                ratio = index / count
                points.append((first[0] + (second[0] - first[0]) * ratio, first[1] + (second[1] - first[1]) * ratio))
        return points

    @staticmethod
    def _sample_field(field: np.ndarray, point: tuple[float, float]) -> float:
        x = int(round(point[0]))
        y = int(round(point[1]))
        x = min(max(x, 0), field.shape[1] - 1)
        y = min(max(y, 0), field.shape[0] - 1)
        value = float(field[y, x])
        return value if math.isfinite(value) else 0.0

    def _visibility(self, snapshot: MotionSnapshot, position: tuple[float, float], route: tuple[tuple[float, float], ...]) -> float:
        if len(route) >= 2:
            dx = route[1][0] - route[0][0]
            dy = route[1][1] - route[0][1]
        else:
            dx = snapshot.target[0] - position[0]
            dy = snapshot.target[1] - position[1]
        base_angle = math.degrees(math.atan2(dy, dx)) if dx or dy else 0.0
        lengths = [self._ray_length(snapshot, position, base_angle + offset) for offset in self.ray_angles]
        return max(lengths) if not lengths else self._ray_length(snapshot, position, base_angle)

    def _ray_length(self, snapshot: MotionSnapshot, position: tuple[float, float], angle: float) -> float:
        radians = math.radians(angle)
        for distance in np.arange(1.0, self.max_ray_length + 1.0, 1.0):
            point = (position[0] + math.cos(radians) * distance, position[1] + math.sin(radians) * distance)
            x, y = int(round(point[0])), int(round(point[1]))
            if x < 0 or y < 0 or x >= snapshot.wall_map.shape[1] or y >= snapshot.wall_map.shape[0]:
                return distance
            if snapshot.wall_map[y, x] > 0:
                return distance
            if snapshot.unknown_mask is not None and snapshot.unknown_mask[y, x]:
                return distance
        return self.max_ray_length

    def _local_occupancy(self, snapshot: MotionSnapshot, position: tuple[float, float]) -> tuple[float, float]:
        x, y = int(round(position[0])), int(round(position[1]))
        radius = self.local_radius
        x1, x2 = max(0, x - radius), min(snapshot.wall_map.shape[1], x + radius + 1)
        y1, y2 = max(0, y - radius), min(snapshot.wall_map.shape[0], y + radius + 1)
        wall = snapshot.wall_map[y1:y2, x1:x2] > 0
        unknown = np.zeros_like(wall, dtype=bool) if snapshot.unknown_mask is None else snapshot.unknown_mask[y1:y2, x1:x2]
        known = ~unknown
        free_ratio = float(np.count_nonzero((~wall) & known) / max(np.count_nonzero(known), 1))
        unknown_ratio = float(np.count_nonzero(unknown) / max(unknown.size, 1))
        return free_ratio, unknown_ratio

    @staticmethod
    def _route_shape(route: tuple[tuple[float, float], ...]) -> tuple[float, float]:
        if len(route) < 3:
            return 0.0, 0.0
        angles: list[float] = []
        lengths = 0.0
        for first, second in zip(route, route[1:]):
            dx, dy = second[0] - first[0], second[1] - first[1]
            length = math.hypot(dx, dy)
            if length > 1e-6:
                angles.append(math.atan2(dy, dx))
                lengths += length
        if len(angles) < 2 or lengths <= 1e-6:
            return 0.0, 0.0
        changes = [abs(math.atan2(math.sin(b - a), math.cos(b - a))) for a, b in zip(angles, angles[1:])]
        curvature = float(sum(changes) / lengths)
        turn_density = float(sum(change >= math.radians(30.0) for change in changes) / max(lengths, 1.0) * 20.0)
        return _clip(curvature / 0.15), _clip(turn_density)

    def _localization_quality(self, snapshot: MotionSnapshot) -> float:
        observation = snapshot.observation
        age_quality = _clip(1.0 - observation.frame_age_ms / self.max_frame_age_ms)
        covariance_quality = 1.0
        if observation.covariance is not None:
            eigenvalues = np.linalg.eigvalsh(observation.covariance)
            uncertainty = math.sqrt(max(float(np.max(eigenvalues)), 0.0))
            covariance_quality = _clip(1.0 - uncertainty / max(self.clearance_reference, 1.0))
        return _clip(observation.confidence * age_quality * covariance_quality)

    @staticmethod
    def _score(features: ComplexityFeatures) -> float:
        return _clip(
            0.30 * (1.0 - features.clearance_quality)
            + 0.20 * (1.0 - features.visibility_quality)
            + 0.10 * (1.0 - features.free_ratio)
            + 0.10 * features.unknown_ratio
            + 0.12 * features.curvature
            + 0.08 * features.turn_density
            + 0.06 * (1.0 - features.localization_quality)
            + 0.04 * features.motion_residual
            + 0.05 * features.peer_risk
        )

    def _transition(self, features: ComplexityFeatures) -> ComplexityState:
        score = self._score(features)
        if score >= self.constrained_threshold:
            self._constrained_count += 1
            self._safe_count = 0
            if self._constrained_count >= self.enter_constrained_frames:
                self._state = ComplexityState.CONSTRAINED
            else:
                self._state = ComplexityState.TRANSITION
            return self._state
        self._constrained_count = 0
        if score <= self.open_threshold:
            if self._state in {ComplexityState.CONSTRAINED, ComplexityState.TRANSITION} and self._safe_count < self.leave_constrained_frames:
                self._safe_count += 1
                self._state = ComplexityState.OPEN if self._safe_count >= self.leave_constrained_frames else ComplexityState.TRANSITION
            else:
                self._safe_count = self.leave_constrained_frames
                self._state = ComplexityState.OPEN
            return self._state
        self._safe_count = 0
        self._state = ComplexityState.TRANSITION
        return self._state


__all__ = ["ComplexityDecision", "ComplexityFeatures", "ComplexityState", "LocalComplexityClassifier"]
