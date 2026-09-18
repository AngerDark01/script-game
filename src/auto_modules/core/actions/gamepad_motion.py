"""Reusable motion primitives for smooth virtual-gamepad axis changes."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot


_AXIS_MIN = -32_768
_AXIS_MAX = 32_767


@dataclass
class StickSlewLimiter:
    """Move a two-axis stick command toward a target at a bounded slew rate.

    The limiter is device-neutral: callers decide when to publish the returned
    values.  Keeping the current value here lets a new target transition from
    the previous command instead of snapping directly to a new direction.
    """

    max_delta_per_second: float = 180_000.0
    _x: float = 0.0
    _y: float = 0.0

    def __post_init__(self) -> None:
        if self.max_delta_per_second <= 0:
            raise ValueError("max_delta_per_second must be positive")

    @property
    def current(self) -> tuple[int, int]:
        """Return the currently applied stick value as bounded integers."""
        return _round_axis(self._x), _round_axis(self._y)

    def update(self, target_x: int, target_y: int, *, elapsed_ms: int) -> tuple[int, int]:
        """Advance toward ``(target_x, target_y)`` for one elapsed interval."""
        if not isinstance(elapsed_ms, int) or isinstance(elapsed_ms, bool) or elapsed_ms < 0:
            raise ValueError("elapsed_ms must be a non-negative integer")
        target = (_validate_axis(target_x, "target_x"), _validate_axis(target_y, "target_y"))
        if elapsed_ms == 0:
            return self.current

        max_step = self.max_delta_per_second * elapsed_ms / 1000.0
        delta_x = target[0] - self._x
        delta_y = target[1] - self._y
        distance = hypot(delta_x, delta_y)
        if distance <= max_step:
            self._x, self._y = target
        elif distance > 0.0:
            scale = max_step / distance
            self._x += delta_x * scale
            self._y += delta_y * scale
        return self.current

    def reset(self) -> tuple[int, int]:
        """Return to neutral immediately and report the neutral command."""
        self._x = 0.0
        self._y = 0.0
        return self.current


def _validate_axis(value: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not _AXIS_MIN <= value <= _AXIS_MAX:
        raise ValueError(f"{name} must be an integer between -32768 and 32767")
    return value


def _round_axis(value: float) -> int:
    return max(_AXIS_MIN, min(_AXIS_MAX, int(round(value))))
