"""Bounded history of confirmed global localization positions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class TrajectorySample:
    position: tuple[float, float]
    captured_at_ms: int
    confidence: float
    source: str = ""


class TrajectoryBuffer:
    """Keep only fresh, confirmed positions for map visualization."""

    def __init__(self, max_length: int = 200) -> None:
        if isinstance(max_length, bool) or int(max_length) < 1:
            raise ValueError("max_length must be a positive integer")
        self.max_length = int(max_length)
        self._samples: deque[TrajectorySample] = deque(maxlen=self.max_length)

    @property
    def samples(self) -> tuple[TrajectorySample, ...]:
        return tuple(self._samples)

    @property
    def points(self) -> tuple[tuple[float, float], ...]:
        return tuple(sample.position for sample in self._samples)

    def append(
        self,
        position,
        *,
        captured_at_ms: int,
        confidence: float,
        fresh: bool,
        source: str = "",
    ) -> bool:
        if not fresh:
            return False
        if len(position) != 2 or not all(isfinite(float(value)) for value in position):
            raise ValueError("position must contain two finite values")
        if int(captured_at_ms) < 0:
            raise ValueError("captured_at_ms must be non-negative")
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        self._samples.append(
            TrajectorySample(
                position=(float(position[0]), float(position[1])),
                captured_at_ms=int(captured_at_ms),
                confidence=float(confidence),
                source=str(source or ""),
            )
        )
        return True

    def reset(self) -> None:
        self._samples.clear()
