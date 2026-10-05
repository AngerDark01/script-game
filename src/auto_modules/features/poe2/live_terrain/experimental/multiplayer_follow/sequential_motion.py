"""Sequential position/velocity update for command/observation feedback."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from ..multiframe_localization.state_estimator import PositionStateEstimator
from .motion_models import MotionCommand, MotionResponse


class SequentialMotionState(StrEnum):
    UNKNOWN = "unknown"
    STATIONARY = "stationary"
    MOVING = "moving"
    STALLED = "stalled"


@dataclass(frozen=True, slots=True)
class SequentialMotionUpdate:
    position: tuple[float, float]
    velocity: tuple[float, float]
    covariance: np.ndarray
    accepted: bool
    state: SequentialMotionState
    reason: str


class SequentialMotionEstimator:
    """Treat controller output as a prediction and visual displacement as evidence."""

    def __init__(self, *, min_displacement: float = 0.5, estimator: PositionStateEstimator | None = None) -> None:
        if min_displacement < 0:
            raise ValueError("min_displacement must be non-negative")
        self.min_displacement = float(min_displacement)
        self._estimator = estimator or PositionStateEstimator()
        self._initialized = False

    @property
    def position(self) -> tuple[float, float] | None:
        return self._estimator.position

    def reset(self, position: tuple[float, float], *, now_ms: int | None = None) -> None:
        self._estimator.reset(position, now_ms=now_ms)
        self._initialized = True

    def apply(self, command: MotionCommand, response: MotionResponse, *, now_ms: int) -> SequentialMotionUpdate:
        if not self._initialized:
            raise RuntimeError("sequential estimator is not initialized")
        displacement = math.hypot(*response.displacement)
        accepted = bool(response.accepted and displacement >= self.min_displacement)
        if accepted:
            estimate = self._estimator.predict(response.displacement, quality=max(0.0, min(1.0, response.alignment)), now_ms=now_ms)
            state = SequentialMotionState.MOVING
            reason = "observation_accepted"
        else:
            estimate = self._estimator.predict((0.0, 0.0), quality=0.0, now_ms=now_ms)
            state = SequentialMotionState.STALLED if response.reason in {"stalled", "blocked", "direction_mismatch"} else SequentialMotionState.STATIONARY
            reason = response.reason or "observation_rejected"
        return SequentialMotionUpdate(
            position=estimate.position,
            velocity=estimate.velocity,
            covariance=estimate.covariance,
            accepted=accepted,
            state=state,
            reason=reason,
        )


__all__ = ["SequentialMotionEstimator", "SequentialMotionState", "SequentialMotionUpdate"]
