"""Gated position/velocity estimation inside one confirmed transform hypothesis."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class EstimateUpdate:
    position: tuple[float, float]
    velocity: tuple[float, float]
    covariance: np.ndarray
    accepted_observation: bool
    reason: str

    def __post_init__(self) -> None:
        matrix = np.array(self.covariance, dtype=np.float64, copy=True, order="C")
        matrix.setflags(write=False)
        object.__setattr__(self, "covariance", matrix)


class PositionStateEstimator:
    def __init__(
        self,
        *,
        initial_covariance: float = 25.0,
        max_mahalanobis: float = 9.21,
        base_process_variance: float = 0.5,
        low_quality_variance: float = 4.0,
    ) -> None:
        if (
            initial_covariance <= 0
            or max_mahalanobis <= 0
            or base_process_variance <= 0
            or low_quality_variance < 0
        ):
            raise ValueError("estimator thresholds must be positive")
        self.initial_covariance = float(initial_covariance)
        self.max_mahalanobis = float(max_mahalanobis)
        self.base_process_variance = float(base_process_variance)
        self.low_quality_variance = float(low_quality_variance)
        self._position: np.ndarray | None = None
        self._velocity = np.zeros(2, dtype=np.float64)
        self._covariance = np.eye(2, dtype=np.float64) * self.initial_covariance
        self._last_ms: int | None = None

    @property
    def position(self) -> tuple[float, float] | None:
        position = self._position
        if position is None:
            return None
        return float(position[0]), float(position[1])

    @property
    def snapshot(self) -> EstimateUpdate | None:
        if self._position is None:
            return None
        return self._snapshot(False, "snapshot")

    def reset(self, position: tuple[float, float], *, covariance: np.ndarray | None = None, now_ms: int | None = None) -> EstimateUpdate:
        position_array = np.asarray(position, dtype=np.float64)
        if position_array.shape != (2,) or not np.isfinite(position_array).all():
            raise ValueError("position must contain two finite values")
        self._position = position_array
        if covariance is not None:
            matrix = np.asarray(covariance, dtype=np.float64)
            if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
                raise ValueError("covariance must be a finite 2x2 matrix")
            self._covariance = matrix.copy()
        else:
            self._covariance = np.eye(2, dtype=np.float64) * self.initial_covariance
        self._velocity[:] = 0.0
        self._last_ms = None if now_ms is None else int(now_ms)
        return self._snapshot(True, "reset")

    def predict(
        self,
        delta: tuple[float, float],
        *,
        quality: float = 1.0,
        now_ms: int | None = None,
        registration_variance: float = 0.0,
    ) -> EstimateUpdate:
        if self._position is None:
            raise RuntimeError("estimator is not initialized")
        vector = np.asarray(delta, dtype=np.float64)
        if vector.shape != (2,) or not np.isfinite(vector).all():
            raise ValueError("delta must contain two finite values")
        previous_ms = self._last_ms
        self._position += vector
        if now_ms is not None and self._last_ms is not None and int(now_ms) > self._last_ms:
            self._velocity = 0.7 * self._velocity + 0.3 * vector / ((int(now_ms) - self._last_ms) / 1000.0)
        self._last_ms = None if now_ms is None else int(now_ms)
        dt_seconds = 0.1
        if now_ms is not None and previous_ms is not None:
            dt_seconds = max(1e-3, (int(now_ms) - previous_ms) / 1000.0)
        clipped_quality = max(0.0, min(1.0, float(quality)))
        process_variance = (
            self.base_process_variance * dt_seconds
            + self.low_quality_variance * (1.0 - clipped_quality)
            + max(0.0, float(registration_variance))
        )
        self._covariance += np.eye(2) * process_variance
        return self._snapshot(False, "prediction")

    def observe(self, position: tuple[float, float], *, covariance: np.ndarray | None = None, now_ms: int | None = None) -> EstimateUpdate:
        if self._position is None:
            return self.reset(position, covariance=covariance, now_ms=now_ms)
        measurement = np.asarray(position, dtype=np.float64)
        if covariance is None:
            measurement_covariance = np.eye(2, dtype=np.float64) * 9.0
        else:
            measurement_covariance = np.asarray(covariance, dtype=np.float64)
        innovation = measurement - self._position
        innovation_covariance = self._covariance + measurement_covariance
        mahalanobis = float(innovation.T @ np.linalg.pinv(innovation_covariance) @ innovation)
        if not math.isfinite(mahalanobis) or mahalanobis > self.max_mahalanobis:
            self._covariance += np.eye(2) * 2.0
            return self._snapshot(False, "observation_rejected")
        gain = self._covariance @ np.linalg.pinv(innovation_covariance)
        self._position = self._position + gain @ innovation
        identity = np.eye(2)
        self._covariance = (identity - gain) @ self._covariance @ (identity - gain).T + gain @ measurement_covariance @ gain.T
        if now_ms is not None and self._last_ms is not None and int(now_ms) > self._last_ms:
            self._velocity = 0.7 * self._velocity + 0.3 * innovation / ((int(now_ms) - self._last_ms) / 1000.0)
        self._last_ms = None if now_ms is None else int(now_ms)
        return self._snapshot(True, "observation_accepted")

    def _snapshot(self, accepted: bool, reason: str) -> EstimateUpdate:
        assert self._position is not None
        position = float(self._position[0]), float(self._position[1])
        velocity = float(self._velocity[0]), float(self._velocity[1])
        return EstimateUpdate(position, velocity, self._covariance, accepted, reason)


__all__ = ["EstimateUpdate", "PositionStateEstimator"]
