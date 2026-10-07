"""Bounded local visual reacquisition around a predicted native position."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoiMatch:
    valid: bool
    position_native: tuple[float, float] | None
    score: float
    radius: float
    reason: str
    processing_ms: float = 0.0


class LocalRoiMatcher:
    def __init__(
        self,
        *,
        radii: Sequence[float] = (80.0, 140.0, 220.0),
        minimum_score: float = 0.60,
    ) -> None:
        values = tuple(float(radius) for radius in radii)
        if not values or any(not math.isfinite(radius) or radius <= 0.0 for radius in values):
            raise ValueError("ROI radii must be finite and positive")
        if not 0.0 <= float(minimum_score) <= 1.0:
            raise ValueError("minimum_score must be between 0 and 1")
        self.radii = values
        self.minimum_score = float(minimum_score)

    def match(
        self,
        frame: object,
        predicted_position: tuple[float, float],
        search: Callable[[object, tuple[float, float], float], RoiMatch | None],
    ) -> RoiMatch:
        point = (float(predicted_position[0]), float(predicted_position[1]))
        if not all(math.isfinite(value) for value in point):
            raise ValueError("predicted_position must contain finite values")
        last_reason = "no_candidate"
        for radius in self.radii:
            candidate = search(frame, point, radius)
            if candidate is None:
                last_reason = "no_candidate"
                continue
            score = float(candidate.score)
            if candidate.valid and math.isfinite(score) and score >= self.minimum_score and candidate.position_native is not None:
                return RoiMatch(True, candidate.position_native, score, radius, "accepted", candidate.processing_ms)
            last_reason = candidate.reason or "score_below_threshold"
        return RoiMatch(False, None, 0.0, self.radii[-1], last_reason)
