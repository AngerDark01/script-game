from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolylineProjection:
    point: tuple[float, float]
    progress: float
    segment_index: int
    deviation: float
