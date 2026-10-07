"""Closed-loop speed calibration from trusted position observations."""

from __future__ import annotations

import math


class VelocityCalibrator:
    def __init__(
        self,
        *,
        initial_speed: float = 80.0,
        smoothing: float = 0.35,
        minimum_speed: float = 1.0,
        maximum_speed: float = 500.0,
    ) -> None:
        self._speed = float(initial_speed)
        self._smoothing = float(smoothing)
        self._minimum = float(minimum_speed)
        self._maximum = float(maximum_speed)
        if not all(math.isfinite(value) for value in (self._speed, self._smoothing, self._minimum, self._maximum)):
            raise ValueError("calibration parameters must be finite")
        if not 0.0 < self._smoothing <= 1.0 or not 0.0 < self._minimum <= self._maximum:
            raise ValueError("calibration parameter range is invalid")
        self._speed = min(self._maximum, max(self._minimum, self._speed))

    @property
    def speed(self) -> float:
        return self._speed

    def update(
        self,
        previous_position: tuple[float, float],
        current_position: tuple[float, float],
        elapsed_ms: float,
        *,
        confidence: float = 1.0,
    ) -> float:
        elapsed = float(elapsed_ms)
        confidence = float(confidence)
        if elapsed <= 0.0 or not math.isfinite(elapsed) or not 0.0 <= confidence <= 1.0:
            raise ValueError("elapsed_ms/confidence is invalid")
        dx = float(current_position[0]) - float(previous_position[0])
        dy = float(current_position[1]) - float(previous_position[1])
        observed = math.hypot(dx, dy) / (elapsed / 1000.0)
        observed = min(self._maximum, max(self._minimum, observed))
        effective_alpha = self._smoothing * confidence
        self._speed = min(self._maximum, max(self._minimum, self._speed + effective_alpha * (observed - self._speed)))
        return self._speed
