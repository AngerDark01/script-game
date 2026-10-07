"""Low-frequency wall displacement processing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from auto_modules.core.localization import estimate_bounded_displacement


@dataclass(frozen=True, slots=True)
class WallObservation:
    shift: tuple[float, float] | None
    quality: float
    accepted: bool
    reason: str
    processing_ms: float = 0.0


def process_wall(
    previous: np.ndarray,
    current: np.ndarray,
    *,
    min_quality: float = 0.20,
    max_shift: float = 40.0,
    processing_ms: float = 0.0,
) -> WallObservation:
    previous_array = np.asarray(previous)
    current_array = np.asarray(current)
    if previous_array.ndim != 2 or current_array.ndim != 2 or previous_array.shape != current_array.shape:
        return WallObservation(None, 0.0, False, "shape_mismatch", float(processing_ms))
    if previous_array.size == 0 or current_array.size == 0:
        return WallObservation(None, 0.0, False, "empty_wall", float(processing_ms))
    result = estimate_bounded_displacement(
        previous_array.astype(np.uint8, copy=False),
        current_array.astype(np.uint8, copy=False),
        min_quality=float(min_quality),
        max_shift=float(max_shift),
    )
    return WallObservation(result.shift, result.quality, result.accepted, result.reason, float(processing_ms))
