"""Command-based odometry with explicit uncertainty growth."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _point(value: tuple[float, float]) -> tuple[float, float]:
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in point):
        raise ValueError("point must contain finite values")
    return point


def integrate_command(
    position: tuple[float, float],
    direction: tuple[float, float],
    speed_units_per_second: float,
    duration_ms: float,
) -> tuple[float, float]:
    """Integrate one controller pulse without mutating any runtime state."""
    start = _point(position)
    vector = _point(direction)
    speed = float(speed_units_per_second)
    duration_value = float(duration_ms)
    if not math.isfinite(duration_value) or duration_value < 0.0:
        raise ValueError("duration_ms must be finite and non-negative")
    duration = duration_value / 1000.0
    if not math.isfinite(speed) or speed < 0.0:
        raise ValueError("speed_units_per_second must be finite and non-negative")
    return (
        start[0] + vector[0] * speed * duration,
        start[1] + vector[1] * speed * duration,
    )


@dataclass(frozen=True, slots=True)
class OdometryEstimate:
    position: tuple[float, float]
    velocity: tuple[float, float]
    uncertainty: float
    captured_at_ms: int | None


class CommandOdometry:
    """Track expected movement while allowing later visual correction."""

    def __init__(
        self,
        position: tuple[float, float],
        *,
        uncertainty: float = 0.0,
        captured_at_ms: int | None = None,
    ) -> None:
        self._position = _point(position)
        self._velocity = (0.0, 0.0)
        self._uncertainty = max(0.0, float(uncertainty))
        if not math.isfinite(self._uncertainty):
            raise ValueError("uncertainty must be finite")
        self._captured_at_ms = None if captured_at_ms is None else int(captured_at_ms)

    def snapshot(self) -> OdometryEstimate:
        return OdometryEstimate(self._position, self._velocity, self._uncertainty, self._captured_at_ms)

    def reset(
        self,
        position: tuple[float, float],
        *,
        uncertainty: float = 0.0,
        captured_at_ms: int | None = None,
    ) -> OdometryEstimate:
        self._position = _point(position)
        self._velocity = (0.0, 0.0)
        self._uncertainty = max(0.0, float(uncertainty))
        self._captured_at_ms = None if captured_at_ms is None else int(captured_at_ms)
        return self.snapshot()

    def step(
        self,
        direction: tuple[float, float],
        speed_units_per_second: float,
        duration_ms: float,
        *,
        now_ms: int | None = None,
        speed_error_units_per_second: float = 0.0,
        timing_error_ms: float = 0.0,
    ) -> OdometryEstimate:
        vector = _point(direction)
        speed = float(speed_units_per_second)
        speed_error = max(0.0, float(speed_error_units_per_second))
        timing_error = max(0.0, float(timing_error_ms))
        if not math.isfinite(speed) or speed < 0.0 or not math.isfinite(speed_error) or not math.isfinite(timing_error):
            raise ValueError("odometry speed and error values must be finite")
        duration = max(0.0, float(duration_ms))
        self._position = integrate_command(self._position, vector, speed, duration)
        self._velocity = (vector[0] * speed, vector[1] * speed)
        elapsed_seconds = duration / 1000.0
        self._uncertainty += speed_error * elapsed_seconds + speed * timing_error / 1000.0
        if now_ms is not None:
            now = int(now_ms)
            if now < 0:
                raise ValueError("now_ms must be non-negative")
            self._captured_at_ms = now
        return self.snapshot()
