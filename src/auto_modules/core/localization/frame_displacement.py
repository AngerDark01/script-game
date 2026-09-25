"""Gated frame-to-frame displacement estimation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from auto_modules.core.vision.phase_displacement import estimate_phase_displacement


@dataclass(frozen=True)
class FrameDisplacement:
    shift: tuple[float, float] | None
    quality: float
    distance: float
    accepted: bool
    reason: str


def estimate_bounded_displacement(
    previous: np.ndarray,
    current: np.ndarray,
    *,
    min_quality: float = 0.20,
    max_shift: float = 40.0,
    dead_zone: float = 0.2,
) -> FrameDisplacement:
    """Estimate and gate a frame displacement without owning localization state."""
    shift, raw_quality = estimate_phase_displacement(
        previous,
        current,
        dead_zone=dead_zone,
    )
    quality = float(raw_quality)
    if shift is None:
        return FrameDisplacement(None, quality, 0.0, False, "phase_failed")
    dx, dy = float(shift[0]), float(shift[1])
    distance = float(math.hypot(dx, dy))
    if quality < float(min_quality):
        return FrameDisplacement((dx, dy), quality, distance, False, "low_quality")
    if distance > float(max_shift) and quality < 0.75:
        return FrameDisplacement((dx, dy), quality, distance, False, "large_shift")
    return FrameDisplacement((dx, dy), quality, distance, True, "accepted")


__all__ = ["FrameDisplacement", "estimate_bounded_displacement"]
