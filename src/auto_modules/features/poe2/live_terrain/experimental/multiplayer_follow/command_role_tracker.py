"""Per-role command odometry corrected by delayed visual observations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..multiframe_localization.state_estimator import PositionStateEstimator


@dataclass(frozen=True, slots=True)
class RoleEstimate:
    position: tuple[float, float]
    covariance: np.ndarray
    uncertainty_native: float
    source: str
    last_visual_at_ms: int
    accepted_observation: bool = False
    reason: str = "prediction"


@dataclass(slots=True)
class _OutputInterval:
    start_ms: int
    end_ms: int
    velocity: tuple[float, float]
    quality: float


@dataclass(slots=True)
class _RoleHistory:
    map_version: str
    anchor_at_ms: int
    anchor_position: tuple[float, float]
    anchor_covariance: np.ndarray
    intervals: list[_OutputInterval] = field(default_factory=list)
    estimated_speed: float = 0.0
    visual_position: tuple[float, float] | None = None
    visual_at_ms: int | None = None
    speed_samples: int = 0


class CommandRoleTracker:
    """Replay acknowledged inputs from the last measured position of each role."""

    def __init__(
        self,
        *,
        expected_speed: float = 80.0,
        visual_phase_grace_ms: int = 750,
        visual_phase_variance: float = 64.0,
    ) -> None:
        if not math.isfinite(expected_speed) or expected_speed <= 0:
            raise ValueError("expected_speed must be positive")
        if visual_phase_grace_ms < 0:
            raise ValueError("visual_phase_grace_ms must be non-negative")
        if not math.isfinite(visual_phase_variance) or visual_phase_variance <= 0:
            raise ValueError("visual_phase_variance must be positive")
        self.expected_speed = float(expected_speed)
        self.visual_phase_grace_ms = int(visual_phase_grace_ms)
        self.visual_phase_variance = float(visual_phase_variance)
        self._roles: dict[str, _RoleHistory] = {}
        self._visual_phase_until_ms: dict[str, int] = {}

    def seed(
        self, role_key: str, map_version: str, position: tuple[float, float],
        *, captured_at_ms: int,
    ) -> None:
        point = np.asarray(position, dtype=np.float64)
        if point.shape != (2,) or not np.isfinite(point).all() or captured_at_ms < 0:
            raise ValueError("invalid visual anchor")
        self._roles[role_key] = _RoleHistory(
            str(map_version), int(captured_at_ms),
            (float(point[0]), float(point[1])), np.eye(2) * 1.0,
            estimated_speed=self.expected_speed,
            visual_position=(float(point[0]), float(point[1])),
            visual_at_ms=int(captured_at_ms),
        )
        self._visual_phase_until_ms.pop(role_key, None)

    def arm_visual_phase(
        self,
        role_key: str,
        *,
        started_at_ms: int,
        grace_ms: int | None = None,
    ) -> None:
        """Allow a bounded output-to-visual synchronization interval.

        A controller acknowledgement and the next captured frame are not
        synchronous.  During this short episode a frame can legitimately
        still show the pre-command position; the normal innovation gate must
        not turn that phase difference into a re-anchor loop.  The allowance
        is time-bounded and scoped to one role, so it cannot weaken steady
        state jump rejection.
        """
        if role_key not in self._roles:
            raise KeyError(role_key)
        if started_at_ms < 0:
            raise ValueError("started_at_ms must be non-negative")
        duration = self.visual_phase_grace_ms if grace_ms is None else int(grace_ms)
        if duration < 0:
            raise ValueError("grace_ms must be non-negative")
        self._visual_phase_until_ms[role_key] = int(started_at_ms) + duration

    def visual_phase_active(self, role_key: str, *, now_ms: int) -> bool:
        """Return whether the bounded startup/recovery phase is still active."""
        if role_key not in self._roles:
            raise KeyError(role_key)
        until = self._visual_phase_until_ms.get(role_key)
        if until is None:
            return False
        if now_ms >= until:
            self._visual_phase_until_ms.pop(role_key, None)
            return False
        return True

    def record_output(
        self, role_key: str, effective_native_vector: tuple[float, float],
        *, accepted_at_ms: int, ttl_ms: int, speed_gain: float = 1.0,
        calibration_confidence: float = 0.0,
    ) -> None:
        history = self._roles[role_key]
        vector = np.asarray(effective_native_vector, dtype=np.float64)
        if vector.shape != (2,) or not np.isfinite(vector).all():
            raise ValueError("effective input must have two finite axes")
        if accepted_at_ms < 0 or ttl_ms <= 0 or not math.isfinite(speed_gain) or speed_gain <= 0:
            raise ValueError("invalid accepted output interval")
        start = max(int(accepted_at_ms), history.anchor_at_ms)
        end = int(accepted_at_ms) + int(ttl_ms)
        if end <= start:
            return
        if history.intervals and start < history.intervals[-1].start_ms:
            raise ValueError("output intervals must be chronological")
        if history.intervals:
            history.intervals[-1].end_ms = min(history.intervals[-1].end_ms, start)
        quality = max(0.0, min(1.0, float(calibration_confidence)))
        # Before the first trusted visual displacement there is no measured
        # speed, so the calibrator's bounded gain may refine the cold-start
        # prior.  Once visual samples exist, ``estimated_speed`` already
        # represents the measured native displacement/time EWMA.  Applying the
        # input calibrator gain again would double-count the same response and
        # gradually drive command odometry away from the observed speed.
        if history.speed_samples <= 0:
            speed = history.estimated_speed * max(0.25, min(4.0, float(speed_gain)))
        else:
            speed = history.estimated_speed
        history.intervals.append(_OutputInterval(
            start, end, (float(vector[0] * speed), float(vector[1] * speed)), quality,
        ))

    def has_output_since_visual(self, role_key: str) -> bool:
        history = self._roles[role_key]
        return any(item.end_ms > history.anchor_at_ms for item in history.intervals)

    def observe(
        self, role_key: str, map_version: str, position: tuple[float, float],
        *, captured_at_ms: int, covariance: np.ndarray | None = None,
    ) -> RoleEstimate:
        history = self._roles[role_key]
        if history.map_version != map_version:
            raise ValueError("map version changed")
        if captured_at_ms < history.anchor_at_ms:
            raise ValueError("older visual frame")
        if captured_at_ms == history.anchor_at_ms:
            return self._snapshot(history, history.anchor_position, history.anchor_covariance,
                                  captured_at_ms, True, "duplicate_visual")
        estimator = self._project(history, int(captured_at_ms))
        # A marker arriving just after a successful stick pulse can still show
        # the pre-command position because capture, Host acknowledgement and
        # game simulation are not synchronous.  Use the estimator's normal
        # visual measurement variance unless the caller supplies a stricter
        # calibrated covariance; 1 native px squared was too strict and
        # caused ordinary startup latency to trigger repeated re-anchors.
        if covariance is None:
            phase_active = self.visual_phase_active(role_key, now_ms=int(captured_at_ms))
            matrix = np.eye(2) * (
                self.visual_phase_variance if phase_active else 9.0
            )
        else:
            matrix = np.asarray(covariance, dtype=np.float64)
        if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
            raise ValueError("visual covariance must be a finite 2x2 matrix")
        corrected = estimator.observe(position, covariance=matrix, now_ms=captured_at_ms)
        if corrected.accepted_observation:
            self._update_visual_speed(
                history,
                (float(position[0]), float(position[1])),
                int(captured_at_ms),
            )
            history.anchor_at_ms = int(captured_at_ms)
            history.anchor_position = corrected.position
            history.anchor_covariance = corrected.covariance.copy()
            history.intervals = [item for item in history.intervals if item.end_ms > captured_at_ms]
        return self._snapshot(
            history, corrected.position, corrected.covariance, captured_at_ms,
            corrected.accepted_observation, corrected.reason,
        )

    def rebase_visual(
        self,
        role_key: str,
        map_version: str,
        position: tuple[float, float],
        *,
        captured_at_ms: int,
        covariance: np.ndarray | None = None,
        reason: str = "visual_continuity_rebase",
    ) -> RoleEstimate:
        """Promote a bounded continuous visual point to the command anchor.

        The caller must establish marker identity and local continuity before
        calling this method.  It is the explicit escape hatch for a speed
        model that is still learning: the visual point becomes authoritative,
        its measured displacement updates the per-role speed estimate, and all
        pending odometry is discarded so the next pulse starts from the new
        anchor.
        """
        history = self._roles[role_key]
        if history.map_version != map_version:
            raise ValueError("map version changed")
        point = np.asarray(position, dtype=np.float64)
        if point.shape != (2,) or not np.isfinite(point).all():
            raise ValueError("position must contain two finite values")
        if captured_at_ms < history.anchor_at_ms:
            raise ValueError("older visual frame")
        matrix = (
            np.eye(2, dtype=np.float64) * 9.0
            if covariance is None else np.asarray(covariance, dtype=np.float64)
        )
        if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
            raise ValueError("visual covariance must be a finite 2x2 matrix")
        point_tuple = (float(point[0]), float(point[1]))
        self._update_visual_speed(history, point_tuple, int(captured_at_ms))
        history.anchor_at_ms = int(captured_at_ms)
        history.anchor_position = point_tuple
        history.anchor_covariance = matrix.copy()
        history.intervals.clear()
        return self._snapshot(
            history, point_tuple, history.anchor_covariance,
            int(captured_at_ms), True, str(reason),
        )

    def estimate(self, role_key: str, *, now_ms: int) -> RoleEstimate:
        history = self._roles[role_key]
        estimator = self._project(history, int(now_ms))
        snapshot = estimator.snapshot
        assert snapshot is not None
        return self._snapshot(
            history, snapshot.position, snapshot.covariance, int(now_ms),
            False, "command_prediction",
        )

    def diagnostics(self, role_key: str, *, now_ms: int) -> dict:
        """Return a serializable snapshot of one role's command odometry.

        This is deliberately read-only and does not change the estimator.  The
        follow page uses it to pair every visual frame with the exact command
        intervals that produced the prediction, which is needed to distinguish
        a speed mismatch from an input-axis or capture-timing mismatch.
        """
        history = self._roles[role_key]
        estimate = self.estimate(role_key, now_ms=int(now_ms))
        return {
            "role_key": role_key,
            "map_version": history.map_version,
            "anchor_at_ms": history.anchor_at_ms,
            "anchor_position": history.anchor_position,
            "anchor_covariance": tuple(
                tuple(float(value) for value in row)
                for row in history.anchor_covariance.tolist()
            ),
            "visual_phase_until_ms": self._visual_phase_until_ms.get(role_key),
            "estimated_speed": history.estimated_speed,
            "speed_samples": history.speed_samples,
            "visual_position": history.visual_position,
            "visual_at_ms": history.visual_at_ms,
            "intervals": tuple(
                {
                    "start_ms": item.start_ms,
                    "end_ms": item.end_ms,
                    "velocity": item.velocity,
                    "quality": item.quality,
                }
                for item in history.intervals
            ),
            "estimate": {
                "position": estimate.position,
                "uncertainty_native": estimate.uncertainty_native,
                "source": estimate.source,
                "last_visual_at_ms": estimate.last_visual_at_ms,
                "accepted_observation": estimate.accepted_observation,
                "reason": estimate.reason,
            },
        }

    def _update_visual_speed(
        self,
        history: _RoleHistory,
        position: tuple[float, float],
        captured_at_ms: int,
    ) -> None:
        previous = history.visual_position
        previous_at_ms = history.visual_at_ms
        history.visual_position = position
        history.visual_at_ms = int(captured_at_ms)
        if previous is None or previous_at_ms is None:
            return
        elapsed_ms = int(captured_at_ms) - int(previous_at_ms)
        if elapsed_ms < 40:
            return
        displacement = math.hypot(
            float(position[0]) - float(previous[0]),
            float(position[1]) - float(previous[1]),
        )
        if displacement < 0.25:
            return
        observed_speed = displacement / (elapsed_ms / 1000.0)
        if not math.isfinite(observed_speed):
            return
        observed_speed = max(0.5, min(self.expected_speed * 4.0, observed_speed))
        if history.speed_samples <= 0:
            history.estimated_speed = observed_speed
        else:
            history.estimated_speed = (
                0.65 * history.estimated_speed + 0.35 * observed_speed
            )
        history.speed_samples += 1

    def _project(self, history: _RoleHistory, at_ms: int) -> PositionStateEstimator:
        if at_ms < history.anchor_at_ms:
            raise ValueError("prediction precedes visual anchor")
        estimator = PositionStateEstimator(
            initial_covariance=1.0, base_process_variance=0.25,
            low_quality_variance=0.05,
        )
        estimator.reset(
            history.anchor_position, covariance=history.anchor_covariance,
            now_ms=history.anchor_at_ms,
        )
        cursor = history.anchor_at_ms
        for item in history.intervals:
            start = max(item.start_ms, history.anchor_at_ms)
            end = min(item.end_ms, at_ms)
            if end <= start:
                continue
            if start > cursor:
                estimator.predict((0.0, 0.0), now_ms=start)
            dt = (end - start) / 1000.0
            delta = (item.velocity[0] * dt, item.velocity[1] * dt)
            distance = math.hypot(*delta)
            estimator.predict(
                delta, quality=item.quality, now_ms=end,
                registration_variance=(0.08 * distance) ** 2,
            )
            cursor = end
        if at_ms > cursor:
            estimator.predict((0.0, 0.0), now_ms=at_ms)
        return estimator

    @staticmethod
    def _snapshot(
        history: _RoleHistory, position: tuple[float, float], covariance: np.ndarray,
        at_ms: int, accepted: bool, reason: str,
    ) -> RoleEstimate:
        matrix = np.array(covariance, copy=True)
        matrix.setflags(write=False)
        radius = math.sqrt(5.99 * max(0.0, float(np.linalg.eigvalsh(matrix)[-1])))
        return RoleEstimate(
            position, matrix, radius,
            "visual" if accepted or at_ms == history.anchor_at_ms else "command_prediction",
            history.anchor_at_ms, accepted, reason,
        )


__all__ = ["CommandRoleTracker", "RoleEstimate"]
